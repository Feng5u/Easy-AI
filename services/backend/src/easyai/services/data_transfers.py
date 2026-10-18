"""Session-owned explicit upload jobs. No automatic restart/resume or training binding."""

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import threading
import time
from typing import Callable
from uuid import uuid4

from easyai.services.data_transfer_errors import TransferFailure, safe_transfer_error
from easyai.domain.data_transfer import (
    TransferPlanRequest,
    TransferPlan,
    TransferConfirmation,
    TransferJob,
    TransferHistory,
)
from easyai.domain.connections import AuthenticatedConnection, SessionControl
from easyai.services.data_transfer_source import TransferSource
from easyai.services.data_transfer_transport import DataUploadTransport
from easyai.services.remote_artifacts import _encoded
from easyai.services.data_transfer_record import (
    UploadLedger,
    UploadIntent,
    UploadRecord,
    source_files,
)


@dataclass
class _Plan:
    value: TransferPlan
    source: TransferSource
    transport: DataUploadTransport
    guard: Callable[[], None]
    uid: int
    home: str
    expires: float
    username: str = ""
    intent: UploadIntent | None = None
    missing: tuple[str, ...] | None = None


@dataclass
class _Job:
    value: TransferJob
    cancel: threading.Event
    deadline: float
    thread: threading.Thread | None = None


class DataTransfers:
    def __init__(self, mutex: threading.RLock, application_root: Path | None = None):
        self.mutex = mutex
        self.plans: dict[str, _Plan] = {}
        self.jobs: dict[str, _Job] = {}
        self.planning = threading.Lock()
        self.planning_cancel = threading.Event()
        self.planning_transport: DataUploadTransport | None = None
        self.closed = False
        self.ledger = UploadLedger(application_root) if application_root is not None else None

    def _available(self) -> None:
        if self.closed:
            raise TransferFailure("DATA_TRANSFER_CLOSED")
        if self.ledger is not None and self.ledger.failed:
            raise TransferFailure("DATA_TRANSFER_PERSISTENCE_FAILED")
        if any(
            job.value.status == "CLEANUP_PENDING"
            or (job.thread is not None and job.thread.is_alive())
            for job in self.jobs.values()
        ):
            raise TransferFailure("DATA_TRANSFER_BUSY")
        if self.planning_transport is not None and not self.planning_transport.quiescent:
            raise TransferFailure("DATA_TRANSFER_CLEANUP_PENDING")

    def prepare(
        self,
        request: TransferPlanRequest,
        root: Path,
        auth: AuthenticatedConnection,
        transport: DataUploadTransport,
        guard: Callable[[], None],
    ) -> TransferPlan:
        if not self.planning.acquire(blocking=False):
            raise TransferFailure("DATA_TRANSFER_BUSY")
        try:
            with self.mutex:
                self._available()
                self.planning_transport = transport
                guard()
                self.plans = {
                    key: value
                    for key, value in self.plans.items()
                    if value.expires > time.monotonic()
                }
                if len(self.plans) >= 16 or len(self.jobs) >= 16:
                    raise TransferFailure("DATA_TRANSFER_JOB_LIMIT")
                if auth.target_id is None or auth.target_revision is None:
                    raise TransferFailure("DATA_TRANSFER_TARGET_REQUIRED")
            source = TransferSource.inventory(
                root, request.budget, lambda: self._planning_check(guard)
            )
            home, uid = transport.inspect(self.planning_cancel)
            identity = str(uuid4())
            manifest = _encoded(
                {
                    "protocolVersion": 1,
                    "projectId": request.project_id,
                    "transferId": identity,
                    "uid": uid,
                    "files": [
                        {"path": record.name, "bytes": record.size, "sha256": "0" * 64}
                        for record in source.files
                    ],
                }
            )
            if len(manifest) > 65536:
                raise TransferFailure("DATA_TRANSFER_MANIFEST_LIMIT")
            target = home + "/.easyai/projects/" + request.project_id + "/data/" + identity
            digest = hashlib.sha256(
                _encoded(
                    {
                        "request": request.model_dump(mode="json", by_alias=True),
                        "scope": auth.scope.model_dump(mode="json", by_alias=True),
                        "targetId": auth.target_id,
                        "targetRevision": auth.target_revision,
                        "home": home,
                        "uid": uid,
                        "root": str(source.root),
                        "identity": source.root_identity,
                        "directories": source.directories,
                        "files": [asdict(record) for record in source.files],
                        "target": target,
                    }
                )
            ).hexdigest()
            value = TransferPlan(
                plan_id=identity,
                plan_hash=digest,
                project_id=request.project_id,
                connection_id=request.connection_id,
                target_id=auth.target_id,
                target_revision=auth.target_revision,
                source_label=str(root),
                target_path=target,
                file_count=len(source.files),
                total_bytes=sum(record.size for record in source.files),
                budget=request.budget,
                expires_in_seconds=60,
                missing_files=len(source.files),
            )
            with self.mutex:
                self._available()
                guard()
                self.plans[identity] = _Plan(
                    value, source, transport, guard, uid, home, time.monotonic() + 60, auth.username
                )
            return value.model_copy(deep=True)
        finally:
            self.planning.release()

    def _planning_check(self, guard: Callable[[], None]) -> None:
        if self.planning_cancel.is_set():
            raise TransferFailure("DATA_TRANSFER_CANCELLED")
        guard()

    def history(self, project_id: str) -> list[TransferHistory]:
        with self.mutex:
            if self.ledger is None:
                return []
            return [
                TransferHistory(
                    transfer_id=record.intent.slot_id,
                    project_id=project_id,
                    target_id=record.intent.target_id,
                    target_revision=record.intent.target_revision,
                    target_path=record.intent.root,
                    file_count=len(record.intent.files),
                    total_bytes=sum(f.bytes for f in record.intent.files),
                    last_completed=record.last_completed,
                )
                for record in self.ledger.records.values()
                if record.intent.project_id == project_id
            ]

    def prepare_recovery(
        self,
        slot_id: str,
        request: TransferPlanRequest,
        root: Path,
        auth: AuthenticatedConnection,
        transport: DataUploadTransport,
        guard: Callable[[], None],
    ) -> TransferPlan:
        if not self.planning.acquire(blocking=False):
            raise TransferFailure("DATA_TRANSFER_BUSY")
        try:
            with self.mutex:
                self._available()
                self.planning_transport = transport
                guard()
                if (
                    self.ledger is None
                    or slot_id not in self.ledger.records
                    or len(self.jobs) >= 16
                    or len(self.plans) >= 16
                ):
                    raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
                record = self.ledger.records[slot_id].model_copy(deep=True)
                intent = record.intent
                if len(record.attempts) >= 16 or (
                    intent.project_id,
                    intent.target_id,
                    intent.target_revision,
                    intent.endpoint,
                    intent.username,
                    intent.host_fingerprint,
                ) != (
                    request.project_id,
                    auth.target_id,
                    auth.target_revision,
                    auth.scope.endpoint,
                    auth.username,
                    auth.scope.host_fingerprint,
                ):
                    raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
            deadline = time.monotonic() + request.budget.seconds

            def check() -> None:
                self._planning_check(guard)
                assert self.ledger is not None
                self.ledger.verify_intent(slot_id, intent)
                if time.monotonic() >= deadline:
                    raise TransferFailure("DATA_TRANSFER_TIMEOUT")

            source = TransferSource.inventory(root, request.budget, check)
            if (
                source_files(source, check) != intent.files
                or sorted(name for name, _ in source.directories) != intent.directories
            ):
                raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
            home, uid = transport.inspect(self.planning_cancel)
            if (home, uid) != (intent.home, intent.uid):
                raise TransferFailure("DATA_TRANSFER_HOME_CHANGED")
            from easyai.services.data_transfer_recovery import inspect

            absent = inspect(
                transport,
                intent,
                record.attempts,
                self.planning_cancel,
                request.budget.seconds,
                check,
            )
            reused = sum(f.bytes for f in intent.files if f.path not in absent)
            identity = str(uuid4())
            plan_hash = hashlib.sha256(
                _encoded(
                    {
                        "intent": hashlib.sha256(intent.raw()).hexdigest(),
                        "slot": slot_id,
                        "attempt": identity,
                        "request": request.model_dump(mode="json", by_alias=True),
                        "scope": auth.scope.model_dump(mode="json", by_alias=True),
                        "root": str(root),
                        "source": [asdict(f) for f in source.files],
                        "identity": source.root_identity,
                        "directories": source.directories,
                        "missing": absent,
                    }
                )
            ).hexdigest()
            value = TransferPlan(
                plan_id=identity,
                plan_hash=plan_hash,
                project_id=request.project_id,
                connection_id=request.connection_id,
                target_id=intent.target_id,
                target_revision=intent.target_revision,
                source_label=str(root),
                target_path=intent.root,
                file_count=len(intent.files),
                total_bytes=sum(f.bytes for f in intent.files),
                budget=request.budget,
                expires_in_seconds=60,
                slot_id=slot_id,
                reused_bytes=reused,
                missing_files=len(absent),
            )
            with self.mutex:
                self._available()
                check()
                if self.ledger.records.get(slot_id) != record:
                    raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
                self.plans[identity] = _Plan(
                    value,
                    source,
                    transport,
                    guard,
                    uid,
                    home,
                    time.monotonic() + 60,
                    auth.username,
                    intent,
                    absent,
                )
            return value.model_copy(deep=True)
        finally:
            self.planning.release()

    def confirm(self, request: TransferConfirmation) -> TransferJob:
        if request.confirmed is not True:
            raise TransferFailure("DATA_TRANSFER_CONFIRMATION_REQUIRED")
        with self.mutex:
            if request.plan_id in self.jobs:
                job = self.jobs[request.plan_id]
                if (job.value.plan_hash, job.value.project_id, job.value.connection_id) != (
                    request.plan_hash,
                    request.project_id,
                    request.connection_id,
                ):
                    raise TransferFailure("DATA_TRANSFER_CONFIRMATION_INVALID")
                return self.get(request.plan_id, request)  # Replay never starts a second worker.
            self._available()
            plan = self.plans.get(request.plan_id)
            if plan is None or time.monotonic() >= plan.expires:
                raise TransferFailure("DATA_TRANSFER_PLAN_EXPIRED")
            if (request.project_id, request.connection_id, request.plan_hash) != (
                plan.value.project_id,
                plan.value.connection_id,
                plan.value.plan_hash,
            ):
                raise TransferFailure("DATA_TRANSFER_CONFIRMATION_INVALID")
            plan.guard()
            for record in plan.source.files:
                with plan.source.open(record, plan.guard):
                    pass  # Metadata revalidation before ANY remote write.
            value = TransferJob(
                transfer_id=plan.value.plan_id,
                plan_id=plan.value.plan_id,
                plan_hash=plan.value.plan_hash,
                project_id=request.project_id,
                connection_id=request.connection_id,
                target_path=plan.value.target_path,
                status="UPLOADING",
                file_count=plan.value.file_count,
                total_bytes=plan.value.total_bytes,
                reused_bytes=plan.value.reused_bytes,
            )
            job = _Job(value, threading.Event(), time.monotonic() + plan.value.budget.seconds)
            self.jobs[value.transfer_id] = job

            def progress(kind: str, count: int, files: int) -> None:
                with self.mutex:
                    plan.guard()
                    if job.cancel.is_set():
                        raise TransferFailure("DATA_TRANSFER_CANCELLED")
                    if kind == "sent":
                        job.value.sent_bytes += count
                    elif kind == "verified":
                        job.value.verified_bytes += count
                        job.value.completed_files += files
                    elif kind == "verifying":
                        job.value.status = "VERIFYING"
                    if (
                        job.value.sent_bytes > job.value.total_bytes
                        or job.value.verified_bytes > job.value.total_bytes
                        or job.value.completed_files > job.value.file_count
                    ):
                        raise TransferFailure("DATA_TRANSFER_PROGRESS_INVALID")

            def worker() -> None:
                try:
                    intent = plan.intent

                    def check() -> None:
                        if job.cancel.is_set():
                            raise TransferFailure("DATA_TRANSFER_CANCELLED")
                        if time.monotonic() >= job.deadline:
                            raise TransferFailure("DATA_TRANSFER_TIMEOUT")
                        plan.guard()
                        if (
                            self.ledger is not None
                            and intent is not None
                            and intent.slot_id in self.ledger.records
                        ):
                            self.ledger.verify_intent(intent.slot_id, intent)

                    if self.ledger is not None:
                        hashed = source_files(plan.source, check)
                        if intent is None:
                            intent = UploadIntent(
                                project_id=request.project_id,
                                slot_id=value.transfer_id,
                                target_id=plan.value.target_id,
                                target_revision=plan.value.target_revision,
                                endpoint=plan.transport.scope.endpoint,
                                username=plan.username,
                                host_fingerprint=plan.transport.scope.host_fingerprint,
                                home=plan.home,
                                uid=plan.uid,
                                directories=sorted(name for name, _ in plan.source.directories),
                                files=hashed,
                            )
                        elif intent.files != hashed or intent.directories != sorted(
                            name for name, _ in plan.source.directories
                        ):
                            raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
                        with self.mutex:
                            check()
                            old = self.ledger.records.get(intent.slot_id)
                            attempts = list(old.attempts) if old else []
                            if value.transfer_id not in attempts:
                                attempts.append(value.transfer_id)
                            record = UploadRecord(intent=intent, attempts=attempts)
                            self.ledger.put(record)  # Durable intent before ANY remote write.
                        from easyai.services.data_transfer_recovery import send

                        remaining = int(job.deadline - time.monotonic())
                        if remaining < 1:
                            raise TransferFailure("DATA_TRANSFER_TIMEOUT")
                        send(
                            plan.transport,
                            plan.source,
                            intent,
                            value.transfer_id,
                            attempts,
                            plan.missing
                            if plan.missing is not None
                            else tuple(f.path for f in intent.files),
                            job.cancel,
                            remaining,
                            progress,
                            check,
                        )
                    else:
                        plan.transport.upload(
                            plan.source,
                            request.project_id,
                            value.transfer_id,
                            plan.home,
                            plan.uid,
                            job.cancel,
                            plan.value.budget.seconds,
                            progress,
                            check,
                        )
                    with self.mutex:
                        plan.guard()
                        if job.cancel.is_set():
                            raise TransferFailure("DATA_TRANSFER_CANCELLED")
                        if (
                            job.value.sent_bytes + job.value.reused_bytes,
                            job.value.verified_bytes,
                            job.value.completed_files,
                        ) != (value.total_bytes, value.total_bytes, value.file_count):
                            raise TransferFailure("DATA_TRANSFER_VERIFICATION_INCOMPLETE")
                        if self.ledger is not None and intent is not None:
                            self.ledger.put(
                                UploadRecord(intent=intent, attempts=attempts, last_completed=True)
                            )
                        job.value.status = "COMPLETED"
                except Exception as error:
                    with self.mutex:
                        code = safe_transfer_error(error)
                        job.value.error_code = code
                        if getattr(plan.transport, "cleanup_pending", True) or code in {
                            "DATA_TRANSFER_CLEANUP_PENDING",
                            "DATA_TRANSFER_CLEANUP_FAILED",
                        }:
                            job.value.status = "CLEANUP_PENDING"
                        else:
                            job.value.status = "CANCELLED" if job.cancel.is_set() else "FAILED"

            job.thread = threading.Thread(target=worker, daemon=True, name="easyai-data-upload")
            try:
                job.thread.start()
            except Exception:
                job.value.status = "FAILED"
                job.value.error_code = "DATA_TRANSFER_START_FAILED"
                raise TransferFailure("DATA_TRANSFER_START_FAILED") from None
            return value.model_copy(deep=True)

    def get(self, identity: str, request: SessionControl) -> TransferJob:
        with self.mutex:
            job = self.jobs.get(identity)
            if job is None or (job.value.project_id, job.value.connection_id) != (
                request.project_id,
                request.connection_id,
            ):
                raise KeyError("DATA_TRANSFER_NOT_FOUND")
            if (
                job.value.status not in {"COMPLETED", "CANCELLED", "FAILED"}
                and job.thread is not None
                and job.thread.is_alive()
                and time.monotonic() >= job.deadline + 2
            ):
                job.value.status = "CLEANUP_PENDING"
            return job.value.model_copy(deep=True)

    def cancel(self, identity: str, request: SessionControl) -> TransferJob:
        with self.mutex:
            if identity not in self.jobs:
                plan = self.plans.get(identity)
                if plan is None or (plan.value.project_id, plan.value.connection_id) != (
                    request.project_id,
                    request.connection_id,
                ):
                    raise KeyError("DATA_TRANSFER_NOT_FOUND")
                value = TransferJob(
                    transfer_id=identity,
                    plan_id=identity,
                    plan_hash=plan.value.plan_hash,
                    project_id=request.project_id,
                    connection_id=request.connection_id,
                    target_path=plan.value.target_path,
                    status="CANCELLED",
                    file_count=plan.value.file_count,
                    total_bytes=plan.value.total_bytes,
                    error_code="DATA_TRANSFER_CANCELLED",
                    reused_bytes=plan.value.reused_bytes,
                )
                cancellation = threading.Event()
                cancellation.set()
                self.jobs[identity] = _Job(value, cancellation, time.monotonic())
                return value.model_copy(deep=True)
            value = self.get(identity, request)
            if value.status in {"COMPLETED", "CANCELLED", "FAILED"}:
                return value
            job = self.jobs[identity]
            if job.thread is not None and job.thread.is_alive():
                job.cancel.set()
                job.deadline = min(job.deadline, time.monotonic())
                job.value.status = "CANCELLING"
            return self.get(identity, request)

    def invalidate(self) -> None:
        with self.mutex:
            self.plans.clear()
            for job in self.jobs.values():
                if (
                    job.value.status not in {"COMPLETED", "CANCELLED", "FAILED"}
                    and job.thread is not None
                    and job.thread.is_alive()
                ):
                    job.cancel.set()
                    job.deadline = min(job.deadline, time.monotonic())
                    job.value.status = "CANCELLING"

    def close(self) -> None:
        with self.mutex:
            self.closed = True
            self.planning_cancel.set()
            self.invalidate()

    def wait_idle(self) -> None:
        # Never hold the workspace mutex while waiting for planning or SDK cleanup.
        # A timed-out owner retains its writer lock, including after close().
        deadline = time.monotonic() + 3
        if not self.planning.acquire(timeout=max(0, deadline - time.monotonic())):
            raise TransferFailure("DATA_TRANSFER_CLEANUP_PENDING")
        try:
            with self.mutex:
                if not self.closed:
                    raise TransferFailure("DATA_TRANSFER_BUSY")
                threads = [job.thread for job in self.jobs.values() if job.thread is not None]
            for thread in threads:
                thread.join(max(0, deadline - time.monotonic()))
            with self.mutex:
                if (
                    any(thread.is_alive() for thread in threads)
                    or any(job.value.status == "CLEANUP_PENDING" for job in self.jobs.values())
                    or (
                        self.planning_transport is not None
                        and not self.planning_transport.quiescent
                    )
                ):
                    raise TransferFailure("DATA_TRANSFER_CLEANUP_PENDING")
                if self.ledger is not None:
                    self.ledger.close()
                    self.ledger = None
        finally:
            self.planning.release()
