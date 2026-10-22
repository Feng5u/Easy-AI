"""Shared local/SSH run ledger; runner authority comes from saved backend bindings."""

import csv
import hashlib
import io
import json
import os
import threading
from pathlib import Path, PurePosixPath
from typing import Callable
from uuid import uuid4

from easyai.compiler.bundle import export_bundle
from easyai.compiler.pipeline import Compilation, compile_project
from easyai.domain.contracts import ArtifactRecord, Contract, Event, Run, RunConfig
from easyai.domain.program import ProgramIR
from easyai.domain.remote_run import RemoteRunIdentity
from easyai.security.project_lock import ProjectLock
from easyai.security.remote_cache import (
    LocalDirectory,
    LocalOwnerLock,
    local_directory,
    windows_cache_enabled,
)
from easyai.security.files import read_regular, digest_regular
from easyai.services.event_journal import EventJournal, read_runtime_events
from easyai.services.project_service import ProjectService

TERMINAL = frozenset({"SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"})
METRICS = (
    "epoch",
    "train_loss",
    "test_accuracy",
    "train_samples",
    "test_samples",
    "elapsed_seconds",
)


class RunEntry(Contract):
    run: Run
    snapshot_hash: str
    idempotency_hash: str
    request_hash: str
    remote_identity: RemoteRunIdentity | None = None


class RunLedger(Contract):
    entries: dict[str, RunEntry]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class RunService:
    """One local owner; restart replays records and never starts an old process."""

    def __init__(self, root: Path, *, storage: Callable[[Path], LocalDirectory] | None = None):
        # Unsupported hosts retain local startup; gated Windows integration uses
        # the same selector as SSH/storage consumers, without POSIX substitution.
        self._storage = storage or (
            local_directory if os.name == "posix" or windows_cache_enabled() else None
        )
        self.root = root.absolute() if self._storage is not None else root.resolve(strict=True)
        self._mutex = threading.RLock()
        self._store: LocalDirectory | None = None
        self._lock: LocalOwnerLock | None = None
        self._run_directories: dict[str, LocalDirectory] = {}
        self._log_directories: dict[str, LocalDirectory] = {}
        self._supervisors: dict[str, object] = {}
        self._journals: dict[str, EventJournal] = {}
        self._closed = False
        self._write_uncertain = False
        from easyai.services.remote_runs import RemoteRuns

        self.remote = RemoteRuns(self)
        try:
            if self._storage is not None:
                self._store = self._storage(self.root)
            self._lock = (
                self._store.owner_lock(".runs.lock")
                if self._store is not None
                else ProjectLock(self.root / ".runs.lock")
            )
            if self._lock.fd is None:
                raise ValueError("RUN_STORE_HELD")
            self._verify()
            path = self.root / "catalog.json"
            if self._store is not None:
                try:
                    raw = self._read_store(self._store, "catalog.json", 16 * 1024 * 1024)
                except FileNotFoundError:
                    self._ledger = RunLedger(entries={})
                else:
                    self._ledger = RunLedger.model_validate_json(raw)
            else:
                if path.is_symlink():
                    raise ValueError("RUN_PATH_FORBIDDEN")
                self._ledger = (
                    RunLedger.model_validate_json(read_regular(path, 16 * 1024 * 1024))
                    if path.exists()
                    else RunLedger(entries={})
                )
            for run_id, entry in self._ledger.entries.items():
                self._directory(run_id)
                if entry.run.run_id != run_id or entry.run.config.run_id != run_id:
                    raise ValueError("RUN_IDENTITY_CONFLICT")
                if entry.run.status not in TERMINAL:
                    entry.run.connection_state = "disconnected"
            self.remote.recover()
            self._verify()
            # Recovered active processes are intentionally unknown: no PID-based kill,
            # automatic rerun or fabricated INTERRUPTED/exit code.
        except BaseException:
            self.remote.close()
            self._close_persistence()
            raise

    @staticmethod
    def _read_store(directory: LocalDirectory, name: str, limit: int) -> bytes:
        with os.fdopen(directory.open_file(name), "rb") as source:
            before = os.fstat(source.fileno())
            directory.verify_file(name, source.fileno())
            raw = source.read(limit + 1)
            after = os.fstat(source.fileno())
            directory.verify_file(name, source.fileno())
            if len(raw) > limit or len(raw) != before.st_size:
                raise ValueError("RUN_STORE_RECORD_LIMIT_OR_CHANGED")
            if (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError("RUN_STORE_RECORD_CHANGED")
            return raw

    @staticmethod
    def _write_store(
        directory: LocalDirectory, name: str, content: bytes, *, replace: bool = True
    ) -> None:
        temporary = ".record-" + str(uuid4())
        try:
            with os.fdopen(directory.open_file(temporary, "exclusive"), "wb") as output:
                if output.write(content) != len(content):
                    raise OSError("RUN_STORE_WRITE_INCOMPLETE")
                output.flush()
                directory.sync_file(output.fileno())
            directory.publish(temporary, name, replace=replace)
        finally:
            directory.remove(temporary, missing_ok=True)

    def _run_store(self, run_id: str) -> LocalDirectory:
        with self._mutex:
            return self._held_run_store(run_id)

    def _held_run_store(self, run_id: str) -> LocalDirectory:
        self._verify()
        self._directory(run_id)
        if self._store is None:
            raise ValueError("REMOTE_CACHE_PLATFORM_UNVERIFIED")
        if run_id not in self._run_directories:
            self._run_directories[run_id] = self._store.child(run_id)
        result = self._run_directories[run_id]
        result.verify()
        return result

    def _open_storage(self, path: Path) -> LocalDirectory:
        """Owned child for a coordinator; shared root/run handles remain borrowed."""
        with self._mutex:
            return self._open_storage_locked(path)

    def _open_storage_locked(self, path: Path) -> LocalDirectory:
        self._verify()
        parts = path.relative_to(self.root).parts
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise ValueError("RUN_PATH_FORBIDDEN")
        parent = self._run_store(parts[0])
        owned: LocalDirectory | None = None
        try:
            # Current callers request a descendant of a run (cache/coordinator).
            if len(parts) == 1:
                assert self._store is not None
                return self._store.child(parts[0])
            for part in parts[1:]:
                child = parent.child(part)
                try:
                    if owned is not None:
                        owned.close()
                except BaseException:
                    child.close()
                    raise
                parent = owned = child
            self._verify()
            self._run_store(parts[0]).verify()
            assert owned is not None
            result, owned = owned, None
            return result
        finally:
            if owned is not None:
                owned.close()

    def _close_persistence(self) -> None:
        # Do not release directories while journals/locks can still use them.
        for run_id in list(self._journals):
            self._journals[run_id].close()
            del self._journals[run_id]
        if self._lock is not None:
            self._lock.close()
            self._lock = None
        for directories in (self._log_directories, self._run_directories):
            for run_id in list(directories):
                directories[run_id].close()
                del directories[run_id]
        if self._store is not None:
            self._store.close()
            self._store = None

    def _directory(self, run_id: str) -> Path:
        from uuid import UUID

        if str(UUID(run_id)) != run_id:
            raise ValueError("RUN_ID_INVALID")
        if self._store is not None:
            self._store.verify()
        if run_id in self._run_directories:
            self._run_directories[run_id].verify()
        path = self.root / run_id
        if path.is_symlink():
            raise ValueError("RUN_PATH_FORBIDDEN")
        return path

    def _safe_path(self, run_id: str, relative: str) -> Path:
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or "\\" in relative:
            raise ValueError("RUN_PATH_FORBIDDEN")
        current = self._directory(run_id)
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("RUN_PATH_FORBIDDEN")
        return current

    def _verify(self) -> None:
        if self._closed:
            raise ValueError("RUN_SERVICE_CLOSED")
        if self._write_uncertain:
            raise ValueError("RUN_STORE_WRITE_UNCERTAIN")
        if self._store is not None:
            self._store.verify()
        if self._lock is None:
            raise ValueError("RUN_STORE_OWNER_CLOSED")
        self._lock.verify()

    def _persist(self) -> None:
        self._verify()
        try:
            content = self._ledger.model_dump_json(by_alias=True, indent=2).encode()
            if self._store is not None:
                self._write_store(self._store, "catalog.json", content)
            else:
                ProjectService.atomic_write(self.root / "catalog.json", content)
        except BaseException:
            self._write_uncertain = True
            raise

    def _journal(self, run_id: str) -> EventJournal:
        with self._mutex:
            return self._open_journal(run_id)

    def _open_journal(self, run_id: str) -> EventJournal:
        self._verify()
        path = self._safe_path(run_id, "logs/events.jsonl")
        if run_id not in self._journals:
            directory = None
            if self._store is not None:
                directory = self._run_store(run_id).child("logs")
                self._log_directories[run_id] = directory
            try:
                journal = EventJournal(path, run_id, "application", directory=directory)
            except BaseException:
                if directory is not None:
                    directory.close()
                    del self._log_directories[run_id]
                raise
            self._journals[run_id] = journal
            try:
                if self._ledger.entries[run_id].run.config.runner == "local":
                    self._fold_status(run_id, journal.after(0))
                    self._write_views(run_id, journal.after(0))
            except BaseException:
                self._journals[run_id].close()
                del self._journals[run_id]
                if directory is not None:
                    directory.close()
                    del self._log_directories[run_id]
                raise
        if run_id in self._log_directories:
            self._log_directories[run_id].verify()
        return self._journals[run_id]

    def _write_run_file(
        self, run_id: str, relative: str, content: bytes, *, replace: bool = True
    ) -> None:
        self._verify()
        path = self._safe_path(run_id, relative)
        if self._store is None:
            ProjectService.atomic_write(path, content)
            return
        directory = self._run_store(run_id)
        owned = None
        try:
            if path.parent != directory.path:
                owned = self._open_storage(path.parent)
                directory = owned
            self._write_store(directory, path.name, content, replace=replace)
        except BaseException:
            self._write_uncertain = True
            raise
        finally:
            if owned is not None:
                owned.close()

    def _create_run_directory(self, run_id: str, relative: str) -> None:
        path = self._safe_path(run_id, relative)
        if self._store is None:
            path.mkdir()
            return
        parent = self._run_store(run_id)
        owned = None
        try:
            if path.parent != parent.path:
                owned = self._open_storage(path.parent)
                parent = owned
            child = parent.new_child(path.name)
            child.close()
        finally:
            if owned is not None:
                owned.close()

    def _export_bundle(self, compiled: Compilation, run_id: str) -> dict[str, str]:
        self._verify()
        path = self._directory(run_id)
        if self._store is None:
            return export_bundle(compiled, path)
        if run_id in self._run_directories:
            raise ValueError("RUN_DIRECTORY_ALREADY_CLAIMED")
        # Retain the identity from the exclusive claim through bundle creation,
        # snapshots, journal and the lifetime of this owner. Never re-adopt a name.
        directory = self._store.new_child(run_id)
        self._run_directories[run_id] = directory
        return export_bundle(compiled, path, directory=directory)

    def prepare(
        self,
        project: ProjectService,
        expected_revision: int,
        expected_program_hash: str,
        idempotency_key: str,
        python_executable: Path,
        data_root: Path,
    ) -> Run:
        with self._mutex:
            self._verify()
            if not idempotency_key or len(idempotency_key) > 256:
                raise ValueError("RUN_IDEMPOTENCY_INVALID")
            # Resolving a venv's Python symlink discards its pyvenv.cfg context
            # and silently launches the bare interpreter. Preserve the selected
            # absolute entry path while verifying the target exists.
            if not python_executable.is_absolute():
                raise ValueError("RUN_BINDING_INVALID")
            python = Path(os.path.normpath(str(python_executable)))
            data = data_root.resolve(strict=True)
            if not python.is_file() or not data.is_dir():
                raise ValueError("RUN_BINDING_INVALID")
            key_hash = digest(idempotency_key.encode())
            request_hash = digest(
                json.dumps(
                    [
                        str(project.root),
                        expected_revision,
                        expected_program_hash,
                        str(python),
                        str(data),
                    ],
                    separators=(",", ":"),
                ).encode()
            )
            for entry in self._ledger.entries.values():
                if entry.idempotency_hash == key_hash:
                    if entry.request_hash != request_hash:
                        raise ValueError("RUN_IDEMPOTENCY_CONFLICT")
                    return self.get(entry.run.run_id)
            for previous in list(self._ledger.entries):
                self._refresh(previous)
            current_document = project.snapshot(expected_revision).document
            if current_document is None:
                raise ValueError("PROJECT_READ_ONLY")
            if any(
                entry.run.project_id == current_document.project_id
                and not self.remote.settled(entry.run)
                for entry in self._ledger.entries.values()
            ):
                raise ValueError("RUN_ACTIVE_CONFLICT")
            opened = project.snapshot(expected_revision)
            document = opened.document
            if document is None:
                raise ValueError("PROJECT_READ_ONLY")
            compiled = compile_project(document)
            if not compiled.result.runnable or compiled.program is None:
                raise ValueError("PROJECT_NOT_RUNNABLE")
            if compiled.result.program_hash != expected_program_hash:
                raise ValueError("PROGRAM_HASH_CONFLICT")
            run_id = str(uuid4())
            directory = self._directory(run_id)
            manifest = self._export_bundle(compiled, run_id)
            for child in ("snapshot", "logs", "metrics", "cache"):
                self._create_run_directory(run_id, child)
            self._write_run_file(run_id, "snapshot/project.easyai.json", opened.raw, replace=False)
            config = RunConfig(
                run_id=run_id,
                project_id=document.project_id,
                project_revision=document.revision,
                program_hash=compiled.result.program_hash,
                code_hash=manifest["codeHash"],
                bundle_hash=manifest["bundleHash"],
                target_id="local",
                runner="local",
                data_root=str(data),
                run_root=str(directory),
                python_executable=str(python),
                execution_mode=document.settings.execution_mode,
                seed=document.settings.seed,
                num_workers=0,
            )
            self._write_run_file(
                run_id,
                "run-config.json",
                config.model_dump_json(by_alias=True, indent=2).encode(),
                replace=False,
            )
            run = Run(
                run_id=run_id,
                project_id=document.project_id,
                status="CREATED",
                connection_state="connected",
                sync_state="pending",
                config=config,
            )
            self._ledger.entries[run_id] = RunEntry(
                run=run,
                snapshot_hash=digest(opened.raw),
                idempotency_hash=key_hash,
                request_hash=request_hash,
            )
            self._journal(run_id).append("status_changed", None, {"status": "CREATED"})
            self._persist()
            return run.model_copy(deep=True)

    def _verify_snapshot(self, run_id: str) -> None:
        entry = self._ledger.entries[run_id]
        directory = self._directory(run_id)
        snapshot = self._safe_path(run_id, "snapshot/project.easyai.json")
        if (
            snapshot.is_symlink()
            or digest(read_regular(snapshot, 5 * 1024 * 1024)) != entry.snapshot_hash
        ):
            raise ValueError("RUN_SNAPSHOT_CHANGED")
        manifest = json.loads(read_regular(self._safe_path(run_id, "bundle.json"), 1024 * 1024))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
            raise ValueError("BUNDLE_MANIFEST_INVALID")
        files = manifest["files"]
        if (
            digest(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())
            != entry.run.config.bundle_hash
        ):
            raise ValueError("BUNDLE_HASH_CONFLICT")
        for name, expected in files.items():
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError("RUN_PATH_FORBIDDEN")
            current = directory
            for part in path.parts:
                current = current / part
                if current.is_symlink():
                    raise ValueError("RUN_PATH_FORBIDDEN")
            if digest_regular(current, 8 * 1024 * 1024) != expected:
                raise ValueError("BUNDLE_FILE_HASH_CONFLICT")
        if (
            digest_regular(self._safe_path(run_id, "code/train.py"), 8 * 1024 * 1024)
            != entry.run.config.code_hash
        ):
            raise ValueError("CODE_HASH_CONFLICT")
        if (
            RunConfig.model_validate_json(
                read_regular(self._safe_path(run_id, "run-config.json"), 65536)
            )
            != entry.run.config
        ):
            raise ValueError("RUN_CONFIG_CHANGED")

    def start(self, run_id: str) -> Run:
        from easyai.runtime.supervisor import ManagedSupervisor

        with self._mutex:
            self._verify()
            self.get(run_id)
            run = self._ledger.entries[run_id].run
            if run.config.runner != "local":
                raise ValueError("REMOTE_START_REQUIRES_AUTHENTICATED_BINDING")
            if run_id in self._supervisors:
                return self.get(run_id)
            if run.status != "CREATED":
                raise ValueError("RUN_PROCESS_IDENTITY_UNKNOWN")
            self._verify_snapshot(run_id)
            from easyai.runtime.dataset_inputs import reject_legacy_cache, require_guarded_code
            from easyai.domain.program import ProgramIR

            require_guarded_code(
                read_regular(self._safe_path(run_id, "code/train.py"), 8 * 1024 * 1024).decode(
                    "utf-8"
                )
            )
            program = ProgramIR.model_validate_json(
                read_regular(self._safe_path(run_id, "program.ir.json"), 5 * 1024 * 1024)
            )
            from easyai.compiler.artifact_budget import validate_artifact_budget

            validate_artifact_budget(program)
            for dataset in program.datasets:
                if dataset.dataset_name in {"MNIST", "FashionMNIST"}:
                    reject_legacy_cache(Path(run.config.data_root), dataset.dataset_name)
            directory = self._directory(run_id)
            supervisor = ManagedSupervisor(
                directory,
                run_id,
                [
                    run.config.python_executable,
                    str(directory / "code/entry.py"),
                    "--config",
                    str(directory / "run-config.json"),
                ],
                directory / "code",
                environment={
                    "MPLBACKEND": "Agg",
                    "OMP_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1",
                    "MPLCONFIGDIR": str(directory / "cache/matplotlib"),
                    "XDG_CACHE_HOME": str(directory / "cache"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONPATH": "",
                },
            )
            self._supervisors[run_id] = supervisor
            run.status = "STARTING"
            self._journal(run_id).append("status_changed", None, {"status": "STARTING"})
            self._persist()
            try:
                supervisor.start()
            except BaseException:
                run.status = "FAILED"
                self._journal(run_id).append(
                    "status_changed", None, {"status": "FAILED", "reason": "PROCESS_START_FAILED"}
                )
                self._persist()
                raise
            run.status = "RUNNING"
            self._journal(run_id).append("status_changed", None, {"status": "RUNNING"})
            self._persist()
            return run.model_copy(deep=True)

    def _artifacts_complete(self, run_id: str, events: list[Event]) -> bool:
        from easyai.services.run_completion import artifacts_complete

        program = ProgramIR.model_validate_json(
            read_regular(self._safe_path(run_id, "program.ir.json"), 5 * 1024 * 1024)
        )

        def verified(item: ArtifactRecord) -> bool:
            if item.run_id != run_id:
                return False
            path = PurePosixPath(item.relative_path)
            if not path.parts or path.parts[0] != "outputs":
                return False
            target = self._safe_path(run_id, item.relative_path)
            return (
                target.is_file()
                and target.stat().st_size == item.size_bytes
                and digest_regular(target, min(item.size_bytes, 5_000_000_000)) == item.sha256
            )

        return artifacts_complete(program, events, verified)

    def _fold_status(self, run_id: str, events: list[Event]) -> None:
        # Application journal is the durable fact; catalog is its replaceable cache.
        previous: str | None = None
        for event in events:
            if event.source != "application" or event.type != "status_changed":
                continue
            status = event.payload.get("status")
            if not isinstance(status, str) or status not in {
                "CREATED",
                "PRECHECKING",
                "STAGING",
                "STARTING",
                "RUNNING",
                "CANCELLING",
                *TERMINAL,
            }:
                raise ValueError("RUN_STATE_EVENT_INVALID")
            if previous in TERMINAL and status != previous:
                raise ValueError("RUN_TERMINAL_CONFLICT")
            previous = status
        run = self._ledger.entries[run_id].run
        phases = {
            "CREATED": 0,
            "PRECHECKING": 1,
            "STAGING": 2,
            "STARTING": 3,
            "RUNNING": 4,
            "CANCELLING": 5,
        }
        if (
            previous not in TERMINAL
            and run.status not in TERMINAL
            and (previous is None or phases[previous] <= phases[run.status])
        ):
            # A cache ahead of a recovered journal is uncertain, never permission
            # to downgrade a potentially live process back to restartable CREATED.
            return
        if previous is not None and previous != run.status:
            if run.status in TERMINAL:
                raise ValueError("RUN_TERMINAL_CONFLICT")
            # Revalidate the literal through the contract rather than type casting.
            updated = run.model_dump()
            updated["status"] = previous
            if previous in TERMINAL:
                updated["sync_state"] = "complete"
            self._ledger.entries[run_id].run = Run.model_validate(updated)
            self._persist()

    def _write_views(self, run_id: str, events: list[Event]) -> None:
        epochs: dict[int, dict[str, object]] = {}
        artifacts: list[dict[str, object]] = []
        for event in events:
            if event.type == "epoch_completed":
                epoch = event.payload["epoch"]
                if epoch != len(epochs) + 1:
                    raise ValueError("RUN_EPOCH_DUPLICATED_OR_GAP")
                epochs[epoch] = event.payload
            if event.type == "artifact_created":
                item = ArtifactRecord.model_validate(event.payload)
                if item.run_id != run_id:
                    raise ValueError("RUN_ARTIFACT_IDENTITY_INVALID")
                artifacts.append(item.model_dump(by_alias=True))
        if self._ledger.entries[run_id].run.config.runner == "ssh":
            artifacts = [item.model_dump(by_alias=True) for item in self.remote.artifacts(run_id)]
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=METRICS)
        writer.writeheader()
        writer.writerows(epochs.values())
        self._write_run_file(run_id, "metrics/epochs.csv", output.getvalue().encode())
        self._write_run_file(
            run_id, "artifacts.json", json.dumps(artifacts, ensure_ascii=False, indent=2).encode()
        )

    def _refresh(self, run_id: str) -> None:
        if self._ledger.entries[run_id].run.config.runner == "ssh":
            return  # One explicit worker owns SSH I/O; GET/SSE remain cache-only.
        from easyai.runtime.supervisor import ManagedSupervisor

        raw = self._supervisors.get(run_id)
        journal = self._journal(run_id)
        self._fold_status(run_id, journal.after(0))
        events: list[Event] = []
        outcome: str | None = None
        run = self._ledger.entries[run_id].run
        if isinstance(raw, ManagedSupervisor):
            events = raw.events()
            if raw.status in ("COMPLETED", "FAILED", "CANCELLED"):
                outcome = raw.status
        else:
            path = self._safe_path(run_id, "logs/runtime-events.jsonl")
            if path.exists():
                events = read_runtime_events(path, run_id)
                exited = [event for event in events if event.type == "process_exited"]
                if events and not exited and run.status == "CREATED":
                    run.status = "RUNNING"
                    run.connection_state = "disconnected"
                    journal.append(
                        "status_changed",
                        None,
                        {"status": "RUNNING", "reason": "EXECUTION_RESULT_UNKNOWN"},
                    )
                    self._persist()
                spawn_failed = [event for event in events if event.type == "process_spawn_failed"]
                if spawn_failed:
                    if len(spawn_failed) != 1 or events[-1] != spawn_failed[0] or exited:
                        raise ValueError("RUN_SPAWN_EVIDENCE_INVALID")
                    outcome = "FAILED"
                if exited:
                    if (
                        len(exited) != 1
                        or events[-1] != exited[0]
                        or type(exited[0].payload.get("exitCode")) is not int
                    ):
                        raise ValueError("RUN_EXIT_EVIDENCE_INVALID")
                    kinds = [event.type for event in events]
                    if "runtime_error" in kinds:
                        outcome = "FAILED"
                    elif (
                        exited[0].payload["exitCode"] == 0
                        and kinds.count("pipeline_completed") == 1
                        and "pipeline_cancelled" not in kinds
                    ):
                        outcome = "COMPLETED"
                    elif "pipeline_cancelled" in kinds or run.status == "CANCELLING":
                        outcome = "CANCELLED"
                    else:
                        outcome = "FAILED"
        changed = False
        for event in events:
            changed = journal.ingest(event) is not None or changed
        all_events = journal.after(0)
        if outcome is not None and run.status not in TERMINAL:
            if outcome == "COMPLETED":
                try:
                    complete = self._artifacts_complete(run_id, all_events)
                except (ValueError, OSError):
                    complete = False
                run.status = "SUCCEEDED" if complete else "FAILED"
            else:
                run.status = "CANCELLED" if outcome == "CANCELLED" else "FAILED"
            run.sync_state = (
                "error" if outcome == "COMPLETED" and run.status == "FAILED" else "complete"
            )
            run.connection_state = "connected"
            journal.append("status_changed", None, {"status": run.status})
            self._persist()
            all_events = journal.after(0)
            changed = True
        if changed:
            self._write_views(run_id, all_events)

    def get(self, run_id: str) -> Run:
        with self._mutex:
            self._verify()
            self._ledger.entries[run_id]  # Reject unknown IDs before touching any path.
            self._refresh(run_id)
            return self._ledger.entries[run_id].run.model_copy(deep=True)

    def events(self, run_id: str, after: int = 0) -> list[Event]:
        with self._mutex:
            self.get(run_id)
            return self._journal(run_id).after(after)

    def cancel(self, run_id: str) -> Run:
        from easyai.runtime.supervisor import ManagedSupervisor

        if self.get(run_id).config.runner == "ssh":
            return self.remote.cancel(run_id)
        with self._mutex:
            run = self.get(run_id)
            if run.status in TERMINAL:
                return run
            if run.status == "CREATED":
                self._ledger.entries[run_id].run.status = "CANCELLED"
                self._journal(run_id).append("status_changed", None, {"status": "CANCELLED"})
                self._persist()
            else:
                supervisor = self._supervisors.get(run_id)
                if not isinstance(supervisor, ManagedSupervisor):
                    raise ValueError("RUN_PROCESS_IDENTITY_UNKNOWN")
                supervisor.request_cancel()
                if supervisor.status == "CANCELLING":
                    self._ledger.entries[run_id].run.status = "CANCELLING"
                    self._journal(run_id).append("status_changed", None, {"status": "CANCELLING"})
                    self._persist()
            return self.get(run_id)

    def close(self) -> None:
        from easyai.runtime.supervisor import ManagedSupervisor

        self.remote.close()  # Keep the store/journal locks until all I/O is quiescent.
        with self._mutex:
            if self._closed:
                return
            for run_id, supervisor in self._supervisors.items():
                if isinstance(supervisor, ManagedSupervisor):
                    supervisor.close()
                    if not self._write_uncertain:
                        self._refresh(run_id)
            self._close_persistence()
            self._closed = True
