"""One public install coordinator, with scoped local/remote target adapters."""

from itertools import islice
import os
import json
from pathlib import Path
import threading
from typing import Any, Callable
from uuid import UUID

from easyai.domain.connections import SessionControl
from easyai.domain.install import (
    InstallConfirmation,
    InstallJob,
    InstallJobHistory,
    InstallJobReport,
    InstallPlan,
    InstallPlanRequest,
)
from easyai.services.install_service import InstallService, digest
from easyai.services.remote_install import (
    RemoteConfiguration,
    RemoteInstallTarget,
    RemoteLease,
    configuration,
)
from easyai.services.install_runtime import private_snapshot


def remote_target_unsettled(root: Path, target_id: str) -> bool:
    """Read-only profile edit guard; no registry mutex/SSH or second ledger parser.

    Called under the workspace/profile lock. Taking the install registry lock
    there would invert the existing connection guard lock order.
    """
    directory = root / "remote-installs"
    if not directory.exists() and not directory.is_symlink():
        return False
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("INSTALL_LEDGER_FORBIDDEN")
    with os.scandir(directory) as entries:
        scopes = [Path(e.path) for e in islice(entries, 17)]
    if len(scopes) > 16:
        raise ValueError("INSTALL_REMOTE_TARGET_LIMIT")
    for scope in scopes:
        if (
            scope.is_symlink()
            or not scope.is_dir()
            or len(scope.name) != 64
            or any(c not in "0123456789abcdef" for c in scope.name)
        ):
            raise ValueError("INSTALL_LEDGER_FORBIDDEN")
        replay = InstallService(scope)  # Existing bounded read-only replay; never starts a worker.
        if any(
            j.target_id == target_id and j.state in {"INSTALLING", "VERIFYING", "CANCEL_REQUESTED"}
            for j in replay._jobs.values()
        ):
            return True
    return False


class InstallRegistry(InstallService):
    def __init__(self, root: Path, manager: Callable[[], Any]):
        from easyai.services.install_runtime import InstallRuntime

        runtime = InstallRuntime(root)
        super().__init__(root, inspector=runtime.inspector, runtime=runtime)
        self._manager = manager
        self._remotes: dict[str, InstallService] = {}
        self._registry_mutex = threading.RLock()
        self._load_remote_ledgers()

    def _load_remote_ledgers(self) -> None:
        directory = self.app_root / "remote-installs"
        if not directory.exists() and not directory.is_symlink():
            return
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("INSTALL_LEDGER_FORBIDDEN")
        with os.scandir(directory) as entries:
            paths = [Path(e.path) for e in islice(entries, 17)]
        if len(paths) > 16:
            raise ValueError("INSTALL_REMOTE_TARGET_LIMIT")
        for path in paths:
            if (
                path.is_symlink()
                or not path.is_dir()
                or len(path.name) != 64
                or any(c not in "0123456789abcdef" for c in path.name)
            ):
                raise ValueError("INSTALL_LEDGER_FORBIDDEN")
            if path.name not in self._remotes:
                # Read-only recovery never attaches a transport or starts a worker.
                self._remotes[path.name] = InstallService(path)

    def _target_service(
        self,
        target_id: str,
        session: SessionControl,
        recovery_config: RemoteConfiguration | None = None,
    ) -> tuple[InstallService, RemoteInstallTarget]:
        config = recovery_config or configuration(self.app_root, target_id, session.project_id)
        identity_hash = digest(config.identity.model_dump(mode="json"))
        existing = self._remotes.get(identity_hash)
        if existing is not None and any(t.is_alive() for t in existing._workers.values()):
            raise ValueError("INSTALL_REMOTE_BUSY")
        transport = self._manager().install_transport(
            session, config.identity, config.launcher.path
        )
        root = self.app_root / "remote-installs"
        if root.is_symlink():
            raise ValueError("INSTALL_LEDGER_FORBIDDEN")
        root.mkdir(mode=0o700, exist_ok=True)
        path = root / identity_hash
        if path.is_symlink():
            raise ValueError("INSTALL_LEDGER_FORBIDDEN")
        if not path.exists():
            with os.scandir(root) as entries:
                full = len(list(islice(entries, 16))) >= 16
            if full:
                raise ValueError("INSTALL_REMOTE_TARGET_LIMIT")
            path.mkdir(mode=0o700)
        target = RemoteInstallTarget(path, config, session, transport.call)

        def policy_guard() -> None:
            if (
                recovery_config is not None
                or configuration(self.app_root, target_id, session.project_id) != config
            ):
                raise ValueError("INSTALL_PLAN_STALE")

        target.policy_guard = policy_guard
        if existing is None:
            existing = InstallService(
                path, inspector=target.inspector, runtime=target, target=target
            )
            self._remotes[identity_hash] = existing
        else:
            existing._target, existing._runtime, existing._inspector = (
                target,
                target,
                target.inspector,
            )
        return existing, target

    def plan(self, request: InstallPlanRequest) -> InstallPlan:
        with self._registry_mutex:
            self._verify_root()
            if request.target_id == "local":
                return super().plan(request)
            if request.remote_session is None:
                raise ValueError("INSTALL_TARGET_AMBIGUOUS")
            service, _ = self._target_service(request.target_id, request.remote_session)
            return service.plan(request)

    def _job_service(self, job_id: str) -> InstallService:
        if str(UUID(job_id)) != job_id:
            raise ValueError("INSTALL_REQUEST_INVALID")
        self._load_remote_ledgers()
        matches = [s for s in [self, *self._remotes.values()] if job_id in s._jobs]
        if len(matches) != 1:
            raise KeyError("INSTALL_JOB_NOT_FOUND")
        return matches[0]

    def confirm(self, request: InstallConfirmation) -> InstallJob:
        with self._registry_mutex:
            matches = [s for s in [self, *self._remotes.values()] if request.plan_id in s._plans]
            if len(matches) != 1:
                raise ValueError("INSTALL_PLAN_STALE")
            return super().confirm(request) if matches[0] is self else matches[0].confirm(request)

    def get(self, job_id: str) -> InstallJob:
        with self._registry_mutex:
            service = self._job_service(job_id)
            return super().get(job_id) if service is self else service.get(job_id)

    def cancel(self, job_id: str) -> InstallJob:
        with self._registry_mutex:
            service = self._job_service(job_id)
            return super().cancel(job_id) if service is self else service.cancel(job_id)

    def report(self, job_id: str) -> InstallJobReport:
        with self._registry_mutex:
            service = self._job_service(job_id)
            return super().report(job_id) if service is self else service.report(job_id)

    def history(self) -> InstallJobHistory:
        with self._registry_mutex:
            self._load_remote_ledgers()
            entries = super().history().entries
            for service in self._remotes.values():
                entries.extend(service.history().entries)
            entries.sort(key=lambda item: (item.recorded_at, item.job_id), reverse=True)
            return InstallJobHistory(entries=entries[:64])

    def reconcile(self, job_id: str, session: SessionControl, cancel: bool) -> InstallJob:
        """Authenticated observation/cancel only. Never replay or resume an install phase."""
        with self._registry_mutex:
            old = self._job_service(job_id)
            job = old.get(job_id)
            if job.target_id == "local" or job.target_identity is None:
                raise ValueError("INSTALL_REMOTE_JOB_REQUIRED")
            if job.state not in {"INSTALLING", "VERIFYING", "CANCEL_REQUESTED"}:
                return job  # Terminal/registration-only records are never rewritten by observation.
            raw, _ = private_snapshot(
                old.app_root / "install-jobs" / job_id / "remote-policy.json", 256 * 1024
            )
            frozen = json.loads(raw)
            if (
                set(frozen) != {"jobId", "planHash", "environmentId", "configuration"}
                or frozen["jobId"] != job_id
                or frozen["planHash"] != job.plan_hash
                or frozen["environmentId"] != job.environment_id
            ):
                raise ValueError("INSTALL_REMOTE_RECEIPT_INVALID")
            original = RemoteConfiguration.model_validate_json(json.dumps(frozen["configuration"]))
            if (
                original.identity != job.target_identity
                or original.identity.project_id != session.project_id
            ):
                raise ValueError("INSTALL_REMOTE_IDENTITY_CHANGED")
            original.execution_authorized = False  # Recovery mode has no writer capability.
            service, target = self._target_service(job.target_id, session, original)
            if service is not old or target.identity != job.target_identity:
                raise ValueError("INSTALL_REMOTE_IDENTITY_CHANGED")
            if any(t.is_alive() for t in service._workers.values()):
                raise ValueError("INSTALL_REMOTE_BUSY")
            # Reconciliation uses persisted job/plan identity, never reconstructed
            # package versions or fresh renderer input to resume a writer.
            target._local.environment_id, target._local.new = job.environment_id, False
            target._local.selected = set(job.selected_packages)
            target._local.job_id, target._local.plan_hash = job.job_id, job.plan_hash
            result = target.call("cancel" if cancel else "inspect")
            if not result.get("quiescent"):
                return job  # Uncertain owner stays isolated and keeps its lease.
            if result.get("outcome") not in {"completed", "cancelled", "failed", "not_dispatched"}:
                raise ValueError("INSTALL_REMOTE_RECEIPT_INVALID")
            # A quiet phase is not a healthy installed environment. Stop here;
            # require a new explicit plan/real inspection for any future writes.
            target.call("release")
            with service._mutex:
                live = service._jobs[job_id]
                live.state = "CANCELLED" if cancel or result["outcome"] == "cancelled" else "FAILED"
                live.status_code = (
                    "INSTALL_CANCELLED_REPROBE_REQUIRED"
                    if live.state == "CANCELLED"
                    else "INSTALL_REMOTE_INTERRUPTED_REPROBE_REQUIRED"
                )
                live.verified, live.needs_reprobe = False, True
                # A recovered ledger is immutable history. Append with a fresh
                # writer only under the same original journal ownership lock.
                if job_id in service._recovered:
                    from easyai.services.event_journal import EventJournal

                    service._journals[job_id] = EventJournal(
                        service.app_root / "install-jobs" / job_id / "events.jsonl",
                        job_id,
                        "application",
                    )
                    service._recovered.remove(job_id)
                service._record(live)
                lease = service._leases.pop(job_id, None)
                if isinstance(lease, RemoteLease):
                    # Remote release just proved quiet; close only local inode.
                    lease.reserved = False
                    lease.local.close()
                service._active.pop(job.environment_id, None)
                return live.model_copy(deep=True)

    def close(self) -> None:
        failures = False
        for service in self._remotes.values():
            try:
                service.close()
            except ValueError:
                failures = True
        try:
            super().close()
        except ValueError:
            failures = True
        if failures:
            raise ValueError("INSTALL_STOP_UNCONFIRMED")
