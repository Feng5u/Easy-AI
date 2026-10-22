"""Remote target adapter for the existing InstallService, never a package resolver.

Operator-prepared offline sources only. No downloads or credential persistence.
Every remote operation is pinned to a current authenticated saved target.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import sys
import os
import json
import threading
import time
from typing import Any, Callable, Iterator, Literal
from uuid import uuid4

from pydantic import Field
from easyai.domain.contracts import Contract
from easyai.domain.connections import SessionControl
from easyai.domain.environment import remote_path
from easyai.domain.install import InstallInspection, InstallPlan, InstallTargetIdentity
from easyai.security.files import read_regular
from easyai.security.project_lock import ProjectLock
from easyai.services.install_process import (
    ManagedInstallInspector,
    inspection_source,
    pip_source,
)
from easyai.services.install_runtime import (
    Capability,
    CondaBootstrap,
    InstallRuntime,
    OfflineConfiguration,
    bootstrap_source,
    private_snapshot,
)
from easyai.services.install_service import PROFILE_ROOT, ProbeReceipt
from easyai.services.install_sources import constraints_hash, lock_bytes, wheels


def resource(name: str) -> str:
    if getattr(sys, "frozen", False):
        return read_regular(
            Path(getattr(sys, "_MEIPASS")) / "easyai/resources/runtime" / name, 1024 * 1024
        ).decode()
    from easyai.domain.catalog import SOURCE_ROOT

    path = (
        SOURCE_ROOT / "services/backend/src/easyai/runtime/managed.py"
        if name == "managed.py"
        else SOURCE_ROOT / "runtime" / name
    )
    return read_regular(path, 1024 * 1024).decode()


class RemoteConfiguration(OfflineConfiguration):
    identity: InstallTargetIdentity

    @property
    def wire(self) -> dict[str, Any]:
        return {**self.model_dump(mode="json", exclude={"identity"}), "root": self.identity.root}


class RemoteConfigurations(Contract):
    # A private operator policy, never populated through an HTTP renderer request.
    schema_version: Literal[1] = 1
    targets: list[RemoteConfiguration] = Field(max_length=16)


def configuration(root: Path, target_id: str, project_id: str) -> RemoteConfiguration:
    path = root / "remote-install-runtime.json"
    try:
        raw, _ = private_snapshot(path, 256 * 1024)
    except FileNotFoundError:
        raise ValueError("INSTALL_REMOTE_NOT_CONFIGURED") from None
    values = RemoteConfigurations.model_validate_json(raw).targets
    matches = [
        v
        for v in values
        if v.identity.target_id == target_id and v.identity.project_id == project_id
    ]
    if len(matches) != 1:
        raise ValueError("INSTALL_REMOTE_NOT_CONFIGURED")
    value = matches[0]
    for remote_name in [
        value.identity.root,
        value.launcher.path,
        value.module_root,
        value.wheelhouse,
        *(a.path for a in value.bootstrap),
    ]:
        remote_path(remote_name)
        if "//" in remote_name or remote_name.endswith("/") or "/./" in remote_name:
            raise ValueError("INSTALL_REMOTE_PATH_INVALID")
    if value.authorization_expires.tzinfo is None:
        raise ValueError("INSTALL_REMOTE_NOT_CONFIGURED")
    return value


class RemoteReservationUnknown(RuntimeError):
    def __init__(self, lease: "RemoteLease"):
        super().__init__("INSTALL_STOP_UNCONFIRMED")
        self.remote_lease = lease


class RemoteLease:
    def __init__(self, target: "RemoteInstallTarget", plan: InstallPlan, job_id: str):
        self.target, self.plan, self.job_id = target, plan, job_id
        root = target.local_root / "remote-leases"
        root.mkdir(mode=0o700, exist_ok=True)
        self.local = ProjectLock(root / (plan.environment_id + ".lock"))
        self.fd = self.local.fd
        self.reserved = False
        try:
            self.local.verify()
            target.bind(plan, job_id)
            self.reserved = True  # Intent may consume even if its ACK is lost.
            target.call("reserve")
        except BaseException:
            # Reserve may have reached the remote owner. Keep a durable local
            # quarantine even if the SSH reply did not reach this process.
            if self.reserved:
                raise RemoteReservationUnknown(self) from None
            self.local.close()
            raise

    def verify(self) -> None:
        self.local.verify()
        self.target.bind(self.plan, self.job_id)
        self.target.call("verify")

    def close(self) -> None:
        if self.reserved:
            self.target.bind(self.plan, self.job_id)
            self.target.call("release")
            self.reserved = False
        self.local.close()


class RemoteCreation:
    def __init__(self, target: "RemoteInstallTarget", plan: InstallPlan, job_id: str):
        self.target, self.plan, self.job_id = target, plan, job_id
        self.prefix_identity: tuple[int, int] | None = None
        self._lease: RemoteLease | None = None

    def reserve(self) -> RemoteLease:
        self._lease = self.target.lease(self.plan, self.job_id)
        return self._lease

    def verify(self) -> None:
        if self._lease is None:
            raise ValueError("INSTALL_REMOTE_CLAIM_MISSING")
        self._lease.verify()

    def allocate(self) -> Path:
        result = self.target.call("allocate")
        self.prefix_identity = tuple(result["prefixIdentity"])
        return self.target.prefix(self.plan.environment_id)

    def mark_owned(self) -> None:
        self.target.call("mark-owned")

    def mark_ready(self) -> None:
        self.target.call("mark-ready")


class RemoteInspector(ManagedInstallInspector):
    def __init__(self, target: "RemoteInstallTarget"):
        self.target = target

    def inspect_owned(self, prefix: Path, nonce: str, receipt: ProbeReceipt) -> InstallInspection:
        receipt.quiescent = False
        outcome, events, quiet = self.target.command(
            lambda work: (
                [
                    str(prefix / "bin/python"),
                    "-I",
                    "-B",
                    "-c",
                    inspection_source(nonce, receipt.import_names),
                ],
                {},
            ),
            receipt.cancel,
        )
        receipt.quiescent = quiet
        reports = [e["payload"] for e in events if e.get("type") == "progress"]
        if outcome != "completed" or not quiet or len(reports) != 1:
            raise ValueError("INSTALL_INSPECTION_FAILED")
        result = InstallInspection.model_validate(reports[0])
        if result.nonce != nonce or result.prefix != str(prefix):
            raise ValueError("INSTALL_INSPECTION_INVALID")
        return result


class RemoteBootstrap(CondaBootstrap):
    def __init__(self, target: "RemoteInstallTarget"):
        self.target = target

    def create(
        self, prefix: Path, plan: InstallPlan, cancel: threading.Event, progress: Callable[[], None]
    ) -> Literal["completed", "cancelled", "unknown", "failed"]:
        self.target.bind(plan)
        config = self.target.config

        def spec(work: str) -> tuple[list[str], dict[str, str]]:
            return (
                [
                    config.launcher.path,
                    "-I",
                    "-S",
                    "-B",
                    "-c",
                    bootstrap_source(
                        config, str(prefix), work + "/explicit.txt", work + "/condarc"
                    ),
                ],
                {
                    "explicit.txt": "@EXPLICIT\n"
                    + "".join(
                        PurePosixPath(a.path).as_uri() + "#" + a.sha256 + "\n"
                        for a in config.bootstrap
                    ),
                    "condarc": "channels: []\ncreate_default_packages: []\nauto_update_conda: false\nnotify_outdated_conda: false\nnumber_channel_notices: 0\nregister_envs: false\n",
                },
            )

        progress()
        outcome, _, _ = self.target.command(spec, cancel, bootstrap=True)
        progress()
        return outcome


class RemoteInstallTarget(InstallRuntime):
    """InstallRuntime-compatible target; all remote paths stay out of local filesystem calls."""

    def __init__(
        self,
        local_root: Path,
        config: RemoteConfiguration,
        session: SessionControl,
        rpc: Callable[[dict[str, Any]], dict[str, Any]],
    ):
        self.local_root = self.root = local_root
        self.config, self.identity, self.session, self.rpc = config, config.identity, session, rpc
        self.policy_guard: Callable[[], None] = lambda: None
        self._local = threading.local()
        self._shutdown = threading.Event()
        self.free_bytes: int | None = None
        self.inspector = RemoteInspector(self)
        self.provisioner = RemoteBootstrap(self)
        self.executor = self

    def bind(self, plan: InstallPlan, job_id: str | None = None) -> None:
        if plan.target_identity != self.identity or plan.target_id != self.identity.target_id:
            raise ValueError("INSTALL_REMOTE_IDENTITY_CHANGED")
        self._local.environment_id, self._local.new = plan.environment_id, plan.new_environment
        self._local.selected = {c.package_id for c in plan.package_changes if c.requested}
        self._local.plan_hash = plan.plan_hash
        if job_id is not None:
            self._local.job_id = job_id

    def prefix(self, environment_id: str) -> Path:
        from uuid import UUID

        if str(UUID(environment_id)) != environment_id:
            raise ValueError("INSTALL_ENVIRONMENT_FORBIDDEN")
        return Path(self.identity.root) / "training-environments" / environment_id

    def call(self, action: str, **values: Any) -> dict[str, Any]:
        if action not in {"inspect", "cancel", "release"}:
            self.policy_guard()
        nonce = str(uuid4())
        request = {
            "action": action,
            "nonce": nonce,
            "configuration": self.config.wire,
            "identity": self.identity.model_dump(mode="json", by_alias=True, exclude={"root"}),
            "environmentId": self._local.environment_id,
            "newEnvironment": self._local.new,
            "wheels": [
                {
                    "name": w["name"],
                    "version": w["version"],
                    "filename": w["filename"],
                    "sha256": w["sha256"],
                    "downloadBytes": w["downloadBytes"],
                }
                for w in wheels(PROFILE_ROOT, getattr(self._local, "selected", set()))
            ],
            **values,
        }
        if action != "snapshot":
            request.update(jobId=self._local.job_id, planHash=self._local.plan_hash)
        result = self.rpc(request)
        if result.get("nonce") != nonce:
            raise ValueError("INSTALL_REMOTE_RECEIPT_INVALID")
        if action != "snapshot" and (
            result.get("jobId") != self._local.job_id
            or result.get("planHash") != self._local.plan_hash
        ):
            raise ValueError("INSTALL_REMOTE_RECEIPT_INVALID")
        return result

    def baseline(self, environment_id: str, new: bool) -> tuple[str, dict[str, str]]:
        self._local.environment_id, self._local.new = environment_id, new
        result = self.call("snapshot")
        self._snapshot_identity(result)
        if not new and (not result["owned"] or not result["ready"]):
            raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE")
        return result["fingerprint"], result["versions"]

    def _snapshot_identity(self, result: dict[str, Any]) -> None:
        if (
            result["root"] != self.identity.root
            or result["prefix"] != str(self.prefix(self._local.environment_id))
            or result["platform"] != "linux-x86_64-cp311"
            or not result["pythonVersion"].startswith("3.11.")
        ):
            raise ValueError("INSTALL_REMOTE_RECEIPT_INVALID")
        self.free_bytes = result["freeBytes"]

    def snapshot(self, selected: set[str] | None = None) -> Capability:
        if not hasattr(self._local, "environment_id"):
            return Capability()  # Catalog never connects or grants execution.
        self._local.selected = selected or set()
        result = self.call("snapshot")
        self._snapshot_identity(result)
        enabled = (
            self.config.execution_authorized
            and self.config.authorization_expires > datetime.now(timezone.utc)
        )
        return Capability(
            result["sourceFingerprint"],
            enabled,
            result["bootstrapBytes"],
            self.config.disk_budget_bytes,
            self.config.seconds,
        )

    def owned(self, environment_id: str, *, allow_partial: bool = False) -> Path:
        if allow_partial:
            result = self.call("verify")
        else:
            self._local.environment_id, self._local.new = environment_id, False
            result = self.call("snapshot")
            if not result["owned"] or not result["ready"]:
                raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE")
        return self.prefix(environment_id)

    def creation(self, plan: InstallPlan, job_id: str) -> RemoteCreation:
        self.bind(plan, job_id)
        return RemoteCreation(self, plan, job_id)

    def lease(self, plan: InstallPlan, job_id: str) -> RemoteLease:
        return RemoteLease(self, plan, job_id)

    def persist_policy(self, plan: InstallPlan, job_id: str) -> None:
        """Private recovery input, persisted before reservation WAL and RPC.

        Recovery can observe/cancel/release only; this snapshot never grants a
        fresh execution right after the operator policy is revoked or removed.
        """
        path = self.local_root / "install-jobs" / job_id / "remote-policy.json"
        value = {
            "jobId": job_id,
            "planHash": plan.plan_hash,
            "environmentId": plan.environment_id,
            "configuration": self.config.model_dump(mode="json", by_alias=True),
        }
        raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        from easyai.services.owned_creation import sync_directory

        sync_directory(path.parent)

    def mark_ready(self, plan: InstallPlan, job_id: str) -> None:
        self.bind(plan, job_id)
        self.call("mark-ready")

    def request_cancel(self) -> None:
        self._shutdown.set()

    @contextmanager
    def job(self, cancel: threading.Event) -> Iterator[None]:
        yield

    def budget(self, prefix: Path, limit: int) -> None:
        self.call("verify")

    def command(
        self,
        prepare: Callable[[str], tuple[list[str], dict[str, str]]],
        cancel: threading.Event,
        *,
        bootstrap: bool = False,
    ) -> tuple[Literal["completed", "cancelled", "unknown", "failed"], list[dict[str, Any]], bool]:
        if cancel.is_set() or self._shutdown.is_set():
            return "cancelled", [], True  # This invocation never sent an intent.
        phase = str(uuid4())
        work = self.identity.root + "/install-processes/" + self._local.job_id + "/" + phase
        argv, files = prepare(work)
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": work + "/home",
            "TMPDIR": work + "/tmp",
            "XDG_CACHE_HOME": work + "/home",
            "XDG_CONFIG_HOME": work + "/home",
            "MPLCONFIGDIR": work + "/home",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if bootstrap:
            environment.update(
                PATH=str(Path(self.config.launcher.path).parent) + ":/usr/bin:/bin",
                CONDARC=work + "/condarc",
                CONDA_NO_PLUGINS="true",
                CONDA_OFFLINE="true",
                CONDA_PKGS_DIRS=work + "/pkgs",
                CONDA_ENVS_PATH=work + "/envs",
            )
        try:
            result = self.call(
                "run",
                phase=phase,
                argv=argv,
                environment=environment,
                files=files,
                helperSource=resource("install_owner.py"),
                helpers={
                    "managed.py": resource("managed.py"),
                    "portable_journal.py": resource("portable_journal.py"),
                },
            )
            deadline = time.monotonic() + self.config.seconds + 5
            cancel_sent = False
            while not result.get("quiescent", False):
                if (
                    cancel.is_set() or self._shutdown.is_set() or time.monotonic() > deadline
                ) and not cancel_sent:
                    self.call("cancel", phase=phase)
                    cancel_sent = True
                if time.monotonic() > deadline + 5:
                    return "unknown", [], False
                time.sleep(0.05)
                result = self.call("inspect", phase=phase)
            if result.get("phase") != phase or result["outcome"] not in {
                "completed",
                "cancelled",
                "failed",
            }:
                return "unknown", [], False
            return result["outcome"], result.get("events", []), True
        except Exception:
            # No retry and no quiet inference from a closed SSH channel.
            return "unknown", [], False

    def install(
        self, prefix: Path, plan: InstallPlan, cancel: threading.Event, progress: Callable[[], None]
    ) -> Literal["completed", "cancelled", "unknown", "failed"]:
        self.bind(plan)
        selected = {c.package_id for c in plan.package_changes if c.requested}
        reviewed = lock_bytes(PROFILE_ROOT, selected).decode()
        if constraints_hash(PROFILE_ROOT) != plan.constraints_hash:
            raise ValueError("INSTALL_PLAN_STALE")
        progress()
        outcome, _, _ = self.command(
            lambda work: (
                [
                    str(prefix / "bin/python"),
                    "-I",
                    "-B",
                    "-c",
                    pip_source(self.config.wheelhouse, work + "/requirements.lock"),
                ],
                {"requirements.lock": reviewed},
            ),
            cancel,
        )
        progress()
        return outcome
