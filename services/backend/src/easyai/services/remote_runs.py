"""SSH integration for the shared RunService ledger and application journal.

No second wire protocol: all execution ownership goes through SshRunCoordinator.
HTTP reads are cached; explicit start/resume alone establish a background I/O owner.
"""

from dataclasses import dataclass, field
import codecs
import hashlib
import json
from pathlib import PurePosixPath
import threading
import time
from typing import TYPE_CHECKING, Any, Literal, Callable, ContextManager
from uuid import uuid4

from easyai.domain.contracts import (
    ArtifactRecord,
    ArtifactSyncProgress,
    ArtifactSyncFailure,
    ArtifactSyncStage,
    RemoteExecution,
    Run,
    RunConfig,
)
from easyai.domain.desktop import RunLogs
from easyai.domain.connections import AuthenticatedConnection, SessionControl
from easyai.domain.remote_execution import RemoteBinding, RemoteRunStartRequest
from easyai.domain.remote_run import identity_from_config
from easyai.domain.program import ProgramIR
from easyai.security.files import read_regular
from easyai.services.project_service import ProjectService

if TYPE_CHECKING:
    from easyai.services.run_service import RunService
    from easyai.services.connection_manager import ConnectionManager

FINAL = {"COMPLETED", "FAILED", "CANCELLED"}


@dataclass
class _Worker:
    stop: threading.Event
    thread: threading.Thread | None = None
    paused: bool = False
    sync_cancel: threading.Event = field(default_factory=threading.Event)
    sync_transport: Any = None
    last_receipt: str | None = None


class RemoteRuns:
    def __init__(self, runs: "RunService"):
        self.runs = runs
        self._cores: dict[str, Any] = {}
        self._workers: dict[str, _Worker] = {}
        self._retiring_threads: dict[str, threading.Thread] = {}
        self._ready: dict[str, list[ArtifactRecord]] = {}
        self._gate = threading.RLock()
        self._closing = False

    @staticmethod
    def request_hash(project_id: str, request: RemoteRunStartRequest) -> str:
        raw = json.dumps(
            [project_id, request.model_dump(mode="json", by_alias=True)],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(raw).hexdigest()

    def replay(self, project_id: str, request: RemoteRunStartRequest, key: str) -> Run | None:
        with self.runs._mutex:
            self.runs._verify()
            if not 1 <= len(key) <= 256:
                raise ValueError("RUN_IDEMPOTENCY_INVALID")
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            for entry in self.runs._ledger.entries.values():
                if entry.idempotency_hash == key_hash:
                    if (
                        entry.run.project_id != project_id
                        or entry.request_hash != self.request_hash(project_id, request)
                    ):
                        raise ValueError("RUN_IDEMPOTENCY_CONFLICT")
                    return entry.run.model_copy(deep=True)
            return None

    def prepare(
        self,
        project: ProjectService,
        request: RemoteRunStartRequest,
        key: str,
        binding: RemoteBinding,
        auth: AuthenticatedConnection,
        environment: dict[str, Any],
    ) -> Run:
        from easyai.security.remote_cache import require_local_cache

        require_local_cache()
        from easyai.compiler.pipeline import compile_project
        from easyai.services.remote_bundle import RemoteBundle
        from easyai.services.run_service import RunEntry

        with self.runs._mutex:
            opened = project.snapshot(request.expected_revision)
            if opened.document is None:
                raise ValueError("PROJECT_READ_ONLY")
            document = opened.document
            existing = self.replay(document.project_id, request, key)
            if existing is not None:
                return existing
            if any(
                entry.run.project_id == document.project_id and not self.settled(entry.run)
                for entry in self.runs._ledger.entries.values()
            ):
                raise ValueError("RUN_ACTIVE_CONFLICT")
            compiled = compile_project(document)
            if not compiled.result.runnable or compiled.program is None:
                raise ValueError("PROJECT_NOT_RUNNABLE")
            if (
                compiled.result.program_hash != request.expected_program_hash
                or binding.program_hash != request.expected_program_hash
                or binding.project_revision != request.expected_revision
            ):
                raise ValueError("PROGRAM_HASH_CONFLICT")
            run_id = str(uuid4())
            directory = self.runs._directory(run_id)
            manifest = self.runs._export_bundle(compiled, run_id)
            for name in (
                "snapshot",
                "logs",
                "metrics",
                "cache",
                "cache/coordinator",
                "cache/artifacts",
            ):
                self.runs._create_run_directory(run_id, name)
            config = RunConfig(
                run_id=run_id,
                project_id=document.project_id,
                project_revision=document.revision,
                program_hash=compiled.result.program_hash,
                code_hash=manifest["codeHash"],
                bundle_hash=manifest["bundleHash"],
                target_id=binding.target_id,
                runner="ssh",
                data_root=binding.data_root,
                run_root=str(PurePosixPath(binding.run_base) / run_id),
                python_executable=binding.python_executable,
                environment_prefix=binding.environment_prefix,
                conda_executable=environment.get("condaExecutable"),
                device=binding.device,
                execution_mode=document.settings.execution_mode,
                seed=document.settings.seed,
                num_workers=2,
            )
            identity = identity_from_config(config, auth, str(uuid4()))
            for name, raw in (
                ("snapshot/project.easyai.json", opened.raw),
                (
                    "snapshot/environment.json",
                    json.dumps(environment, ensure_ascii=False, allow_nan=False).encode(),
                ),
                ("run-config.json", config.model_dump_json(by_alias=True).encode()),
                ("remote-identity.json", identity.model_dump_json(by_alias=True).encode()),
            ):
                self.runs._write_run_file(run_id, name, raw, replace=False)
            RemoteBundle.freeze(
                directory, config, identity
            )  # complete local proof before any network work
            run = Run(
                run_id=run_id,
                project_id=document.project_id,
                status="CREATED",
                connection_state="disconnected",
                sync_state="pending",
                config=config,
            )
            self.runs._ledger.entries[run_id] = RunEntry(
                run=run,
                snapshot_hash=hashlib.sha256(opened.raw).hexdigest(),
                idempotency_hash=hashlib.sha256(key.encode()).hexdigest(),
                request_hash=self.request_hash(document.project_id, request),
                remote_identity=identity,
            )
            self.runs._journal(run_id).append("status_changed", None, {"status": "CREATED"})
            self.runs._persist()
            return run.model_copy(deep=True)

    @staticmethod
    def settled(run: Run) -> bool:
        if run.config.runner == "ssh":
            return bool(
                run.remote
                and run.remote.execution_state in FINAL
                and run.sync_state in ("complete", "error")
            )
        return run.status in {"SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"}

    def core(self, run_id: str) -> Any:
        from easyai.runners.ssh import SshRunCoordinator

        with self._gate:
            self.runs._verify()
            if self.runs._store is None:
                raise ValueError("REMOTE_CACHE_PLATFORM_UNVERIFIED")
            if run_id not in self._cores:
                if self._closing:
                    raise ValueError("REMOTE_SERVICE_CLOSED")
                entry = self.runs._ledger.entries[run_id]
                if entry.remote_identity is None:
                    raise ValueError("REMOTE_RUN_IDENTITY_MISSING")
                self._cores[run_id] = SshRunCoordinator(
                    self.runs._safe_path(run_id, "cache/coordinator"),
                    entry.remote_identity,
                    journal=self.runs._journal(run_id),
                    storage=self.runs._open_storage,
                )
            return self._cores[run_id]

    def _publish(
        self,
        run_id: str,
        checkpoint: Any,
        *,
        verified: bool | None = None,
        sync: Literal["pending", "syncing", "complete", "error"] | None = None,
    ) -> None:
        with self.runs._mutex:
            if self.runs._closed:
                return
            self.runs._verify()
            run = self.runs._ledger.entries[run_id].run
            before = run.model_dump()
            state = checkpoint.execution_state
            if verified is None:
                verified = bool(
                    run.remote and run.remote.artifacts_verified and state == "COMPLETED"
                )
            run.status = state
            run.connection_state = checkpoint.connection_state
            if checkpoint.cancel_state in ("pending", "acknowledged") and state not in FINAL:
                run.status = "CANCELLING"
            identity = checkpoint.identity
            run.remote = RemoteExecution(
                host=identity.endpoint.host,
                port=identity.endpoint.port,
                username=identity.username,
                host_fingerprint=identity.host_fingerprint,
                execution_state=state,
                start_outcome=checkpoint.start_outcome,
                cancel_state=checkpoint.cancel_state,
                artifacts_verified=verified,
            )
            if checkpoint.cancelled_before_start:
                run.sync_state = "complete"  # No remote process or promised artifacts exist.
            elif sync is not None:
                run.sync_state = sync
            if state == "COMPLETED" and verified:
                run.status = "SUCCEEDED"
            if before != run.model_dump():
                self.runs._journal(run_id).append(
                    "status_changed",
                    None,
                    {
                        "status": run.status,
                        "connectionState": run.connection_state,
                        "syncState": run.sync_state,
                        "remote": run.remote.model_dump(mode="json", by_alias=True),
                    },
                )
            self.runs._write_views(run_id, self.runs._journal(run_id).after(0))
            self.runs._persist()

    def recover(self) -> None:
        for run_id, entry in self.runs._ledger.entries.items():
            if entry.run.config.runner != "ssh":
                continue
            checkpoint = self.core(run_id).checkpoint()
            entry.run.artifact_sync = (
                ArtifactSyncProgress()
            )  # No live transfer survives app restart.
            # Recovery imports committed facts only; no credentials, sockets or start.
            verified = False
            try:
                from easyai.services.remote_artifacts import SftpArtifactSync, _decode
                from easyai.services.run_completion import artifacts_complete
                from pydantic import TypeAdapter

                self.runs._verify_snapshot(run_id)
                from easyai.services.remote_bundle import RemoteBundle

                RemoteBundle.freeze(
                    self.runs._directory(run_id), entry.run.config, self.core(run_id).identity
                )
                snapshot = self.core(run_id).artifact_snapshot(
                    read_regular(self.runs._safe_path(run_id, "bundle.json"), 65536),
                    read_regular(
                        self.runs._safe_path(run_id, "code/source-map.json"), 8 * 1024 * 1024
                    ),
                )
                cache = self.runs._safe_path(run_id, "cache/artifacts")
                index = _decode(read_regular(cache / "artifact-index.json", 65536))
                records = TypeAdapter(list[ArtifactRecord]).validate_python(index["artifacts"])
                if [record.model_copy(update={"sync_state": "pending"}) for record in records] != [
                    record.model_copy(update={"sync_state": "pending"})
                    for record in snapshot.records
                ]:
                    raise ValueError("REMOTE_ARTIFACT_EVIDENCE_CHANGED")
                identity = self.core(run_id).identity
                for record in records:
                    SftpArtifactSync.read_ready(cache, identity, record.artifact_id, record)
                self._ready[run_id] = records
                program = ProgramIR.model_validate_json(
                    read_regular(self.runs._safe_path(run_id, "program.ir.json"), 5 * 1024 * 1024)
                )
                verified = checkpoint.execution_state == "COMPLETED" and artifacts_complete(
                    program,
                    self.core(run_id).events(),
                    lambda record: bool(
                        SftpArtifactSync.read_ready(cache, identity, record.artifact_id, record)
                    ),
                )
            except (ValueError, OSError, KeyError):
                pass
            self._publish(
                run_id,
                checkpoint,
                verified=verified,
                sync="complete"
                if verified
                else "error"
                if checkpoint.execution_state in FINAL
                else "pending",
            )

    def begin(
        self, run_id: str, manager: "ConnectionManager", control: SessionControl, *, initial: bool
    ) -> Run:
        from easyai.services.remote_bundle import RemoteBundle

        core = self.core(run_id)
        with self._gate:
            if self._closing:
                raise ValueError("REMOTE_SERVICE_CLOSED")
            prior = self._workers.get(run_id)
            if prior is not None and prior.thread is not None and prior.thread.is_alive():
                raise ValueError("REMOTE_RUN_BUSY")
            entry = self.runs._ledger.entries[run_id]
            auth = manager.current(control)
            if auth is None:
                raise ValueError("REMOTE_AUTHENTICATION_REQUIRED")
            bundle = RemoteBundle.freeze(
                self.runs._directory(run_id), entry.run.config, core.identity
            )
            checkpoint = core.checkpoint()
            transport = manager.owner_transport(control, bundle, checkpoint)
            core.attach(auth, transport, lambda: manager.current(control))
            self._publish(run_id, core.checkpoint(), sync="pending")
            with self.runs._mutex:
                self.runs._ledger.entries[run_id].run.connection_state = "reconnecting"
                self.runs._journal(run_id).append(
                    "status_changed",
                    None,
                    {
                        "status": self.runs._ledger.entries[run_id].run.status,
                        "connectionState": "reconnecting",
                    },
                )
                self.runs._persist()
            owner = _Worker(threading.Event())
            self._workers[run_id] = owner
            self._sync_progress(run_id, owner, state="idle", counts=(0, 0, 0))

            def work() -> None:
                operation_phase: ArtifactSyncStage = "scope"
                try:
                    if initial:
                        core.start()
                    while not owner.stop.is_set():
                        if owner.sync_transport is not None and not owner.sync_transport.quiescent:
                            self._sync_progress(run_id, owner, state="cleanup_pending")
                            owner.stop.wait(0.1)
                            continue
                        operation_phase = "owner_poll"
                        checkpoint = core.poll()
                        operation_phase = "unknown"
                        self._publish(run_id, checkpoint)
                        observed = checkpoint.last_observation
                        receipt = observed.artifact_receipt if observed else None
                        with self._gate:
                            quiet = owner.sync_transport is None or owner.sync_transport.quiescent
                            paused = owner.paused
                        if not quiet:
                            self._sync_progress(run_id, owner, state="cleanup_pending")
                        elif paused:
                            self._sync_progress(run_id, owner, state="paused")
                        elif observed is not None and (
                            observed.sealed
                            or (receipt is not None and receipt.sha256 != owner.last_receipt)
                        ):
                            if not self._sync(run_id, manager, control, owner, checkpoint):
                                if owner.paused or owner.sync_cancel.is_set():
                                    continue
                                return  # Explicit reconnect, never automatic new credentials/start.
                            if observed.sealed:
                                return
                            owner.last_receipt = receipt.sha256 if receipt else None
                        owner.stop.wait(0.5)
                except Exception as error:
                    # A failed I/O operation says nothing about whether the owner ran.
                    try:
                        from easyai.services.remote_artifacts import sync_failure

                        self._sync_progress(
                            run_id,
                            owner,
                            state="error",
                            failure=sync_failure(error, operation_phase),
                        )
                        core.disconnect()
                        self._publish(run_id, core.checkpoint())
                    except Exception:
                        pass
                finally:
                    try:
                        core.disconnect()
                        self._publish(run_id, core.checkpoint())
                    except Exception:
                        pass

            owner.thread = threading.Thread(target=work, name="easyai-run-" + run_id, daemon=True)
            owner.thread.start()
        return self.runs.get(run_id)

    def _sync(
        self,
        run_id: str,
        manager: "ConnectionManager",
        control: SessionControl,
        owner: _Worker,
        checkpoint: Any,
    ) -> bool:
        from easyai.services.remote_artifacts import SftpArtifactSync, ArtifactFailure, sync_failure
        from easyai.services.run_completion import artifacts_complete

        phase: ArtifactSyncStage = "snapshot"
        core = self.core(run_id)
        directory = self.runs._directory(run_id)
        self._publish(run_id, checkpoint, sync="syncing")
        try:
            snapshot = core.artifact_snapshot(
                read_regular(directory / "bundle.json", 65536),
                read_regular(directory / "code/source-map.json", 8 * 1024 * 1024),
            )
            with self._gate:
                if owner.paused or owner.stop.is_set():
                    return False
                owner.sync_cancel = threading.Event()
                owner.sync_transport = manager.artifact_sync(control, core.identity)
            self._sync_progress(
                run_id, owner, state="syncing", counts=(0, 0, 0), clear_failure=True
            )
            ready = owner.sync_transport.sync(
                snapshot,
                directory / "cache/artifacts",
                owner.sync_cancel,
                progress=lambda received, verified, total: self._sync_progress(
                    run_id, owner, state="syncing", counts=(received, verified, total)
                ),
            )
            with self.runs._mutex:
                self._ready[run_id] = ready
            if not snapshot.observation.sealed:
                self._sync_progress(run_id, owner, state="paused" if owner.paused else "idle")
                self._publish(run_id, checkpoint, verified=False, sync="pending")
                return True
            phase = "completion"
            self.runs._verify_snapshot(run_id)
            program = ProgramIR.model_validate_json(
                read_regular(directory / "program.ir.json", 5 * 1024 * 1024)
            )

            def verified(record: ArtifactRecord) -> bool:
                return bool(
                    SftpArtifactSync.read_ready(
                        directory / "cache/artifacts", core.identity, record.artifact_id, record
                    )
                )

            complete = checkpoint.execution_state == "COMPLETED" and artifacts_complete(
                program, core.events(), verified
            )
            self._publish(
                run_id,
                checkpoint,
                verified=complete,
                sync="complete"
                if complete or checkpoint.execution_state != "COMPLETED"
                else "error",
            )
            missing = checkpoint.execution_state == "COMPLETED" and not complete
            self._sync_progress(
                run_id,
                owner,
                state="error" if missing else "paused" if owner.paused else "idle",
                failure=ArtifactSyncFailure(
                    stage="completion", code="SYNC_REQUIRED_ARTIFACTS_MISSING"
                )
                if missing
                else None,
            )
            return True
        except Exception as error:
            detail = sync_failure(error, phase)
            cleanup = error.cleanup_failure if isinstance(error, ArtifactFailure) else None
            if owner.paused or owner.stop.is_set() or owner.sync_cancel.is_set():
                quiet = owner.sync_transport is None or owner.sync_transport.quiescent
                self._sync_progress(
                    run_id,
                    owner,
                    state=("paused" if owner.paused else "idle") if quiet else "cleanup_pending",
                    failure=detail,
                    cleanup_failure=cleanup,
                )
                self._publish(run_id, core.checkpoint(), sync="pending")
            else:
                core.disconnect()
                self._sync_progress(
                    run_id, owner, state="error", failure=detail, cleanup_failure=cleanup
                )
                self._publish(run_id, core.checkpoint(), sync="error")
            return False

    def _sync_progress(
        self,
        run_id: str,
        owner: _Worker,
        *,
        state: Literal["idle", "syncing", "paused", "cleanup_pending", "error"],
        counts: tuple[int, int, int] | None = None,
        failure: ArtifactSyncFailure | None = None,
        cleanup_failure: ArtifactSyncFailure | None = None,
        clear_failure: bool = False,
    ) -> None:
        with self._gate:
            if self._workers.get(run_id) is not owner or self._closing:
                return
            if state == "syncing" and (
                owner.paused or owner.sync_cancel.is_set() or owner.stop.is_set()
            ):
                raise ValueError("REMOTE_ARTIFACT_CANCELLED")
            with self.runs._mutex:
                if self.runs._closed:
                    return
                run = self.runs._ledger.entries[run_id].run
                current = run.artifact_sync or ArtifactSyncProgress()
                run.artifact_sync = ArtifactSyncProgress(
                    state=state,
                    received_bytes=counts[0] if counts else current.received_bytes,
                    verified_bytes=counts[1] if counts else current.verified_bytes,
                    total_bytes=counts[2] if counts else current.total_bytes,
                    failure=failure
                    if failure is not None
                    else None
                    if clear_failure
                    else current.failure,
                    cleanup_failure=cleanup_failure
                    if cleanup_failure is not None
                    else None
                    if clear_failure
                    else current.cleanup_failure,
                )  # Live byte counters are polled; never append per-chunk journal events.
                if failure is not None and (
                    failure != current.failure or cleanup_failure != current.cleanup_failure
                ):
                    self.runs._journal(run_id).append(
                        "artifact_sync_failed",
                        None,
                        {
                            "failure": failure.model_dump(mode="json", by_alias=True),
                            "cleanupFailure": cleanup_failure.model_dump(mode="json", by_alias=True)
                            if cleanup_failure
                            else None,
                        },
                    )
                    self.runs._persist()

    def sync_control(
        self, run_id: str, paused: bool, commit_scope: Callable[[], ContextManager[None]]
    ) -> Run:
        with self._gate:
            owner = self._workers.get(run_id)
            if owner is None or owner.thread is None or not owner.thread.is_alive():
                raise ValueError("REMOTE_SYNC_RECONNECT_REQUIRED")
            quiet = owner.sync_transport is None or owner.sync_transport.quiescent
            with commit_scope():
                if not paused and not quiet:
                    raise ValueError("REMOTE_ARTIFACT_CLEANUP_UNCONFIRMED")
                owner.paused = paused
                if paused:
                    owner.sync_cancel.set()
                self._sync_progress(
                    run_id,
                    owner,
                    state=("paused" if paused else "idle") if quiet else "cleanup_pending",
                )
            return self.runs.get(run_id)

    def cancel(
        self, run_id: str, commit_scope: Callable[[], ContextManager[None]] | None = None
    ) -> Run:
        core = self.core(run_id)
        checkpoint = core.request_cancel(commit_scope)  # scope and durable intent commit together
        self._publish(run_id, checkpoint)
        return self.runs.get(run_id)

    def logs(self, run_id: str, out: int, err: int) -> RunLogs:
        core = self.core(run_id)
        checkpoint = core.checkpoint()
        observed = checkpoint.last_observation
        sealed = bool(observed and observed.sealed)
        values = []
        done = sealed
        for stream, cursor in (("stdout", out), ("stderr", err)):
            size = getattr(observed.streams, stream).size_bytes if observed else 0
            if not 0 <= cursor <= size:
                raise ValueError("LOG_CURSOR_INVALID")
            raw = core.log_bytes(stream, cursor, 32768)
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            text = decoder.decode(raw, final=sealed and cursor + len(raw) == size)
            pending, _ = decoder.getstate()
            next_cursor = cursor + len(raw) - len(pending)
            values.append((text, next_cursor))
            done = done and next_cursor == size
        return RunLogs(
            stdout=values[0][0],
            stdout_after=values[0][1],
            stderr=values[1][0],
            stderr_after=values[1][1],
            done=done,
        )

    def artifacts(self, run_id: str) -> list[ArtifactRecord]:
        ready = {item.artifact_id: item for item in self._ready.get(run_id, [])}
        return [
            ArtifactRecord.model_validate(event.payload).model_copy(
                update={
                    "sync_state": "ready"
                    if (
                        event.payload.get("artifactId") in ready
                        and ArtifactRecord.model_validate(event.payload).model_copy(
                            update={"sync_state": "ready"}
                        )
                        == ready[event.payload["artifactId"]]
                    )
                    else "pending"
                }
            )
            for event in self.runs._journal(run_id).after(0)
            if event.type == "artifact_created"
        ]

    def image(self, run_id: str, artifact_id: str) -> bytes:
        from easyai.services.remote_artifacts import SftpArtifactSync

        record = next(
            (item for item in self.artifacts(run_id) if item.artifact_id == artifact_id), None
        )
        if record is None or record.kind != "figure" or record.mime_type != "image/png":
            raise ValueError("ARTIFACT_PATH_OR_TYPE_FORBIDDEN")
        return SftpArtifactSync.read_ready(
            self.runs._safe_path(run_id, "cache/artifacts"),
            self.core(run_id).identity,
            artifact_id,
            record,
        )

    def close(self) -> None:
        deadline = time.monotonic() + 3.0
        with self._gate:
            self._closing = True
            owners = list(self._workers.values())
            cores = list(self._cores.items())
            for owner in owners:
                owner.stop.set()
                owner.sync_cancel.set()
            # SDK close can itself block. Retain one owner and all store locks
            # until both the I/O worker and its dedicated retirement finish.
            for run_id, core in cores:
                if run_id not in self._retiring_threads:
                    thread = threading.Thread(
                        target=core.retire_transport, name="easyai-retire-" + run_id, daemon=True
                    )
                    self._retiring_threads[run_id] = thread
                    thread.start()
            retiring = list(self._retiring_threads.values())
        for thread in [*retiring, *(owner.thread for owner in owners if owner.thread is not None)]:
            thread.join(max(0.0, deadline - time.monotonic()))
            if thread.is_alive():
                raise ValueError("REMOTE_CLEANUP_UNCONFIRMED")
        for _, core in cores:
            core.close()
