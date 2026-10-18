"""Offline plans and confirmation ledger. Production installation is not connected.

The internal executor/inspector seams are tested contracts, not HTTP execution inputs.
No installer, network resolver, subprocess or environment writer is invoked here.
"""

from dataclasses import dataclass
import hashlib
import json
import platform
from pathlib import Path
import sys
import threading
import time
from typing import Callable, Literal, Protocol
from uuid import UUID, uuid4

from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.install import (
    InstallConfirmation,
    InstallInspection,
    InstallJob,
    InstallPlan,
    InstallPlanRequest,
    PackageCard,
    PackageCatalog,
    PackageChange,
)
from easyai.security.files import read_regular
from easyai.security.project_lock import ProjectLock

RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT))
PACKAGES_PATH = RESOURCE_ROOT / (
    "easyai/resources/package-groups/catalog.json"
    if getattr(sys, "frozen", False)
    else "packages/package-groups/catalog.json"
)
PROFILE_ROOT = RESOURCE_ROOT / (
    "easyai/resources/training-profiles"
    if getattr(sys, "frozen", False)
    else "packages/training-profiles"
)
Inspector = Callable[[Path, str], InstallInspection]


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class InstallExecutor(Protocol):
    def install(
        self, prefix: Path, plan: InstallPlan, cancel: threading.Event, progress: Callable[[], None]
    ) -> Literal["completed", "cancelled", "unknown"]: ...


@dataclass
class _Plan:
    value: InstallPlan
    deadline: float


class InstallService:
    """Session-only ledger; new environment creation and real execution remain gated."""

    def __init__(
        self,
        application_root: Path,
        inspector: Inspector | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.app_root = application_root
        self.root = application_root / "training-environments"
        self._inspector = inspector
        self._clock = clock
        self._mutex = threading.RLock()
        self._plans: dict[str, _Plan] = {}
        self._jobs: dict[str, InstallJob] = {}
        self._by_plan: dict[str, str] = {}
        self._active: dict[str, str] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._leases: dict[str, ProjectLock] = {}
        self._closed = False

    def _verify_root(self) -> None:
        if self._closed:
            raise ValueError("INSTALL_SESSION_CLOSED")
        if (
            not self.app_root.is_absolute()
            or self.app_root.is_symlink()
            or not self.app_root.is_dir()
        ):
            raise ValueError("INSTALL_ROOT_FORBIDDEN")
        if self.root.is_symlink() or (self.root.exists() and not self.root.is_dir()):
            raise ValueError("INSTALL_ROOT_FORBIDDEN")

    def _profile_hash(self) -> str:
        return hashlib.sha256(
            read_regular(PROFILE_ROOT / "easyai-cpu-sources.json", 100_000)
            + read_regular(PROFILE_ROOT / "easyai-cpu-linux-cp311.lock", 100_000)
        ).hexdigest()

    def _wheels(self) -> list[dict[str, str | int]]:
        value: list[dict[str, str | int]] = json.loads(
            read_regular(PROFILE_ROOT / "easyai-cpu-sources.json", 100_000)
        )["packages"]
        return value

    def catalog(self) -> PackageCatalog:
        self._verify_root()
        versions = {str(item["name"]): str(item["version"]) for item in self._wheels()}
        raw = json.loads(read_regular(PACKAGES_PATH, 50_000))
        return PackageCatalog(
            packages=[
                PackageCard(**item, target_version=versions.get(item["packageId"]))
                for item in raw["packages"]
            ],
            profiles=["teacher-existing", "easyai-cpu"],
        )

    def _prefix(self, environment_id: str) -> Path:
        self._verify_root()
        # environment_id originates from a validated contract or server UUID only.
        try:
            if str(UUID(environment_id)) != environment_id:
                raise ValueError
        except ValueError:
            raise ValueError("INSTALL_ENVIRONMENT_FORBIDDEN") from None
        path = self.root / environment_id
        if path.is_symlink():
            raise ValueError("INSTALL_ENVIRONMENT_FORBIDDEN")
        return path

    def _owned(self, environment_id: str) -> Path:
        path = self._prefix(environment_id)
        if not path.is_dir():
            raise ValueError("INSTALL_ENVIRONMENT_FORBIDDEN")
        marker = json.loads(read_regular(path / ".easyai-owned.json", 2048))
        if marker != {"ownedByEasyAI": True, "environmentId": environment_id}:
            raise ValueError("INSTALL_ENVIRONMENT_FORBIDDEN")
        return path

    def _inspect(self, environment_id: str) -> InstallInspection:
        path = self._owned(environment_id)
        if self._inspector is None:
            raise ValueError("INSTALL_INSPECTION_NOT_ENABLED")
        nonce = str(uuid4())
        report = self._inspector(path, nonce)
        if report.nonce != nonce or report.prefix != str(path):
            raise ValueError("INSTALL_INSPECTION_INVALID")
        return report

    def _baseline(self, environment_id: str, new: bool) -> tuple[str, dict[str, str]]:
        path = self._prefix(environment_id)
        if new:
            if path.exists():
                raise ValueError("INSTALL_PLAN_STALE")
            info = self.app_root.stat()
            return digest(
                {
                    "environment": environment_id,
                    "absent": True,
                    "appDevice": info.st_dev,
                    "appInode": info.st_ino,
                }
            ), {}
        report = self._inspect(environment_id)
        if not report.python_version.startswith("3.11."):
            raise ValueError("INSTALL_PYTHON_UNSUPPORTED")
        info = path.stat()
        marker = read_regular(path / ".easyai-owned.json", 2048)
        return digest(
            {
                "report": report.model_dump(exclude={"nonce"}),
                "device": info.st_dev,
                "inode": info.st_ino,
                "owner": hashlib.sha256(marker).hexdigest(),
            }
        ), report.versions

    def plan(self, request: InstallPlanRequest) -> InstallPlan:
        with self._mutex:
            self._verify_root()
            if request.profile_id == "teacher-existing":
                raise ValueError("INSTALL_TEACHER_READ_ONLY")
            cards = {item.package_id: item for item in self.catalog().packages}
            if any(item not in cards for item in request.package_ids):
                raise ValueError("INSTALL_PACKAGE_FORBIDDEN")
            environment_id = request.owned_environment_id or str(uuid4())
            new = request.new_environment_spec is not None
            fingerprint, versions = self._baseline(environment_id, new)
            wheels = self._wheels()
            locked = {str(item["name"]): str(item["version"]) for item in wheels}
            selected = set(request.package_ids)
            blockers = []
            if platform.system() != "Linux" or platform.machine().lower() not in {
                "x86_64",
                "amd64",
            }:
                blockers.append("INSTALL_PROFILE_PLATFORM_UNSUPPORTED")
            if any(item not in locked for item in selected):
                blockers.append("INSTALL_DEPENDENCIES_UNRESOLVED")
            if any(versions.get(name, version) != version for name, version in locked.items()):
                blockers.append("INSTALL_VERSION_CONFLICT")
            changes = [
                PackageChange(
                    package_id=name,
                    previous_version=versions.get(name),
                    target_version=locked.get(name),
                    action="unresolved"
                    if name not in locked or (name in versions and versions[name] != locked[name])
                    else "keep"
                    if name in versions
                    else "add",
                    requested=name in selected,
                )
                for name in sorted(set(locked) | selected)
            ]
            resolved = not blockers
            value = InstallPlan(
                plan_id=str(uuid4()),
                plan_hash="0" * 64,
                environment_id=environment_id,
                environment_name=request.new_environment_spec.name
                if request.new_environment_spec
                else "应用受控环境",
                new_environment=new,
                baseline_fingerprint=fingerprint,
                constraints_hash=self._profile_hash(),
                package_changes=changes,
                download_bytes=sum(int(item["downloadBytes"]) for item in wheels)
                if resolved
                else None,
                installed_bytes=sum(int(item["unpackedBytes"]) for item in wheels)
                if resolved
                else None,
                size_status="locked-wheel-estimate" if resolved else "unresolved",
                platform="linux-x86_64-cp311",
                blockers=blockers,
            )
            value.plan_hash = digest(value.model_dump(exclude={"plan_hash"}))
            self._plans = {
                key: item
                for key, item in self._plans.items()
                if item.deadline > self._clock() or key in self._by_plan
            }
            if len(self._plans) >= 64:
                raise ValueError("INSTALL_PLAN_LIMIT")
            self._plans[value.plan_id] = _Plan(value.model_copy(deep=True), self._clock() + 600)
            return value

    def _fresh(self, plan: InstallPlan) -> None:
        fingerprint, _ = self._baseline(plan.environment_id, plan.new_environment)
        if (
            fingerprint != plan.baseline_fingerprint
            or self._profile_hash() != plan.constraints_hash
            or digest(plan.model_dump(exclude={"plan_hash"})) != plan.plan_hash
        ):
            raise ValueError("INSTALL_PLAN_STALE")

    def confirm(self, request: InstallConfirmation) -> InstallJob:
        with self._mutex:
            self._verify_root()
            saved = self._plans.get(request.plan_id)
            if (
                saved is None
                or saved.deadline <= self._clock()
                or saved.value.plan_hash != request.plan_hash
            ):
                raise ValueError("INSTALL_PLAN_STALE")
            if request.plan_id in self._by_plan:
                return self.get(self._by_plan[request.plan_id])
            plan = saved.value
            self._fresh(plan)
            if plan.blockers:
                raise ValueError("INSTALL_PLAN_BLOCKED")
            if plan.environment_id in self._active:
                raise ValueError("INSTALL_ENVIRONMENT_CONFLICT")
            job = InstallJob(
                job_id=str(uuid4()),
                plan_id=plan.plan_id,
                plan_hash=plan.plan_hash,
                environment_id=plan.environment_id,
                state="AWAITING_EXECUTION",
                status_code="INSTALL_EXECUTION_NOT_ENABLED",
                logs=["PLAN_CONFIRMED", "INSTALL_EXECUTION_NOT_ENABLED"],
            )
            self._jobs[job.job_id] = job
            self._by_plan[plan.plan_id] = job.job_id
            self._active[plan.environment_id] = job.job_id
            self._cancel[job.job_id] = threading.Event()
            return job.model_copy(deep=True)

    def get(self, job_id: str) -> InstallJob:
        with self._mutex:
            self._verify_root()
            return self._jobs[job_id].model_copy(deep=True)

    def cancel(self, job_id: str) -> InstallJob:
        with self._mutex:
            self._verify_root()
            job = self._jobs[job_id]
            previous = job.state
            if job.state == "AWAITING_EXECUTION":
                job.state, job.status_code = "CANCELLED", "INSTALL_CANCELLED_NO_EXECUTION"
                self._active.pop(job.environment_id, None)
            elif job.state in {"INSTALLING", "VERIFYING", "CANCEL_REQUESTED"}:
                job.state, job.status_code = "CANCEL_REQUESTED", "INSTALL_STOP_UNCONFIRMED"
                self._cancel[job_id].set()
            if previous != job.state and len(job.logs) < 128:
                job.logs.append(job.status_code)
            return job.model_copy(deep=True)

    def execute(self, job_id: str, executor: InstallExecutor) -> InstallJob:
        """Internal lifecycle seam only. No production caller/HTTP route exists."""
        with self._mutex:
            self._verify_root()
            job = self._jobs[job_id]
            if job.state != "AWAITING_EXECUTION":
                raise ValueError("INSTALL_JOB_CONFLICT")
            saved = self._plans[job.plan_id]
            if saved.deadline <= self._clock():
                raise ValueError("INSTALL_PLAN_STALE")
            plan = saved.value
            if plan.new_environment:
                raise ValueError("INSTALL_PROVISIONER_NOT_ENABLED")
            prefix = self._owned(plan.environment_id)
            lease = ProjectLock(prefix / ".easyai-install.lock")
            if lease.fd is None:
                lease.close()
                raise ValueError("INSTALL_ENVIRONMENT_CONFLICT")
            try:
                lease.verify()
                self._fresh(plan)  # Revalidate after acquiring the kernel environment lease.
            except BaseException:
                lease.close()
                raise
            self._leases[job_id] = lease
            job.state, job.status_code, job.changes_possible = "INSTALLING", "INSTALL_STARTED", True
            token = self._cancel[job_id]

        def progress() -> None:
            with self._mutex:
                if len(job.logs) < 128:
                    job.logs.append("INSTALL_PROGRESS")

        quiescent = False
        try:
            outcome = executor.install(prefix, plan.model_copy(deep=True), token, progress)
            quiescent = outcome in {"completed", "cancelled"}
            if not quiescent:
                raise ValueError("INSTALL_STOP_UNCONFIRMED")
            if token.is_set() or outcome == "cancelled":
                with self._mutex:
                    job.state, job.status_code = "CANCELLED", "INSTALL_CANCELLED_REPROBE_REQUIRED"
            else:
                with self._mutex:
                    job.state, job.status_code = "VERIFYING", "INSTALL_REPROBE_STARTED"
                    if len(job.logs) < 128:
                        job.logs.append("INSTALL_REPROBE_STARTED")
                report = self._inspect(plan.environment_id)
                expected = {item.package_id: item.target_version for item in plan.package_changes}
                if (
                    not report.python_version.startswith("3.11.")
                    or not report.tensor_ok
                    or any(
                        not report.imports.get(name)
                        for name in ("torch", "torchvision", "matplotlib")
                    )
                    or any(
                        report.versions.get(name) != version for name, version in expected.items()
                    )
                ):
                    raise ValueError("INSTALL_REPROBE_FAILED")
                with self._mutex:
                    if token.is_set():
                        job.state, job.status_code = (
                            "CANCELLED",
                            "INSTALL_CANCELLED_REPROBE_REQUIRED",
                        )
                    else:
                        job.state, job.status_code, job.verified, job.needs_reprobe = (
                            "SUCCEEDED",
                            "INSTALL_VERIFIED",
                            True,
                            False,
                        )
        except Exception:
            with self._mutex:
                job.state = "FAILED" if quiescent else "CANCEL_REQUESTED"
                job.status_code = (
                    "INSTALL_REPROBE_FAILED" if quiescent else "INSTALL_STOP_UNCONFIRMED"
                )
        finally:
            with self._mutex:
                if quiescent:
                    self._active.pop(job.environment_id, None)
                    self._leases.pop(job_id).close()
                if len(job.logs) < 128:
                    job.logs.append(job.status_code)
        return job.model_copy(deep=True)

    def close(self) -> None:
        with self._mutex:
            for job_id in self._active.values():
                self._cancel[job_id].set()
            self._closed = True
