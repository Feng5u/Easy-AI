"""SSH integration for the shared RunService ledger and application journal.

No second wire protocol: all execution ownership goes through SshRunCoordinator.
HTTP reads are cached; explicit start/resume alone establish a background I/O owner.
"""

from dataclasses import dataclass
import codecs
import hashlib
import json
from pathlib import PurePosixPath
import threading
import time
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from easyai.domain.contracts import ArtifactRecord, RemoteExecution, Run, RunConfig
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
        from easyai.compiler.pipeline import compile_project
        from easyai.compiler.bundle import export_bundle
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
            manifest = export_bundle(compiled, directory)
            for name in (
                "snapshot",
                "logs",
                "metrics",
                "cache",
                "cache/coordinator",
                "cache/artifacts",
            ):
                (directory / name).mkdir(mode=0o700)
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
                ProjectService.atomic_write(directory / name, raw)
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

            def work() -> None:
                try:
                    if initial:
                        core.start()
                    while not owner.stop.is_set():
                        checkpoint = core.poll()
                        self._publish(run_id, checkpoint)
                        if (
                            checkpoint.last_observation is not None
                            and checkpoint.last_observation.sealed
                        ):
                            self._sync(run_id, manager, control, owner.stop, checkpoint)
                            return
                        owner.stop.wait(0.5)
                except Exception:
                    # A failed I/O operation says nothing about whether the owner ran.
                    try:
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
        stop: threading.Event,
        checkpoint: Any,
    ) -> None:
        from easyai.services.remote_artifacts import SftpArtifactSync
        from easyai.services.run_completion import artifacts_complete

        core = self.core(run_id)
        directory = self.runs._directory(run_id)
        self._publish(run_id, checkpoint, sync="syncing")
        try:
            snapshot = core.artifact_snapshot(
                read_regular(directory / "bundle.json", 65536),
                read_regular(directory / "code/source-map.json", 8 * 1024 * 1024),
            )
            ready = manager.artifact_sync(control, core.identity).sync(
                snapshot, directory / "cache/artifacts", stop
            )
            with self.runs._mutex:
                self._ready[run_id] = ready
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
        except Exception:
            core.disconnect()
            self._publish(run_id, core.checkpoint(), sync="error")

    def cancel(self, run_id: str) -> Run:
        core = self.core(run_id)
        checkpoint = core.request_cancel()  # durable intent, never cancellation confirmation
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
        ready_ids = {item.artifact_id for item in self._ready.get(run_id, [])}
        return [
            ArtifactRecord.model_validate(event.payload).model_copy(
                update={
                    "sync_state": "ready"
                    if event.payload.get("artifactId") in ready_ids
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
            # SDK close can itself block. Retain one owner and all store locks
            # until both the I/O worker and its dedicated retirement finish.
            for run_id, core in cores:
                if run_id not in self._retiring_threads:
                    thread = threading.Thread(
                        target=core.disconnect, name="easyai-retire-" + run_id, daemon=True
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
