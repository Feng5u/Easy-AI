"""Offline plans and durable jobs with an optional trusted, plan-bound runtime.

Default configuration never executes. Confirmed policy-enabled jobs use one owned
worker; commands and paths are not accepted as HTTP execution inputs.
"""

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import os
from itertools import islice
import platform
from pathlib import Path
import sys
import threading
import time
from typing import Callable, Literal, Protocol, TYPE_CHECKING
from uuid import UUID, uuid4

from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.install import (
    InstallConfirmation,
    InstallInspection,
    InstallJob,
    InstallJobHistory,
    InstallJobSummary,
    InstallJobReport,
    InstallPlan,
    InstallPlanRequest,
    PackageCard,
    PackageCatalog,
    PackageChange,
    InstallSourceRequest,
    InstallSourcePreview,
    InstallSourceConfirmation,
    InstallSourceResult,
)
from easyai.security.files import read_regular
from easyai.security.project_lock import ProjectLock
from easyai.services.event_journal import EventJournal, read_events
from easyai.services.owned_creation import OwnedCreation, require_ready, read_install_job
from easyai.services.install_sources import (
    IMPORTS,
    OPTIONAL_ROOTS,
    UNSUPPORTED,
    constraints_hash,
    wheels,
    Wheel,
)

if TYPE_CHECKING:
    from easyai.services.install_runtime import InstallRuntime
    from easyai.services.install_source_selection import SourceSelection

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
    ) -> Literal["completed", "cancelled", "unknown", "failed"]: ...


class EnvironmentProvisioner(Protocol):
    def create(
        self, prefix: Path, plan: InstallPlan, cancel: threading.Event, progress: Callable[[], None]
    ) -> Literal["completed", "cancelled", "unknown", "failed"]: ...


@dataclass(eq=False)
class ProbeReceipt:
    # Per invocation, never global across concurrent jobs. Retain the actual
    # owner after unknown cleanup; a prior command's receipt is not this proof.
    cancel: threading.Event = field(default_factory=threading.Event)
    quiescent: bool = False
    owner: object | None = None
    prefix: Path | None = None
    import_names: tuple[str, ...] = ("torch", "torchvision", "matplotlib")


@dataclass
class _Plan:
    value: InstallPlan
    deadline: float


class _ProvisionCancelled(Exception):
    pass


class InstallService:
    """Session plans, durable jobs; new environments and execution remain gated."""

    def __init__(
        self,
        application_root: Path,
        inspector: Inspector | None = None,
        clock: Callable[[], float] = time.monotonic,
        runtime: "InstallRuntime | None" = None,
    ):
        self.app_root = application_root
        self.root = application_root / "training-environments"
        self._runtime = runtime
        self._sources: SourceSelection | None = None
        self._workers: dict[str, threading.Thread] = {}
        self._executing: set[threading.Thread] = set()
        self._probe_gate = threading.Lock()
        self._probes: set[ProbeReceipt] = set()
        self._closing = False
        self._close_requested = threading.Event()
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
        self._journals: dict[str, EventJournal] = {}
        self._recovered: set[str] = set()
        self._persistence_failed = False
        self._recover()

    def _recover(self) -> None:
        """Replay existing journals only; never launch or signal a recorded PID."""
        for job_id, (job, _) in self._saved_jobs().items():
            recovered = self._historical_view(job)
            if recovered.state == "CANCEL_REQUESTED":
                self._active[recovered.environment_id] = job_id
            self._jobs[job_id] = recovered
            self._recovered.add(job_id)

    def _ledger_slots(self) -> list[Path]:
        """Every durable directory occupies a slot, including interrupted empty ones."""
        root = self.app_root / "install-jobs"
        if not root.exists() and not root.is_symlink():
            return []
        if root.is_symlink() or not root.is_dir():
            raise ValueError("INSTALL_LEDGER_FORBIDDEN")
        with os.scandir(root) as entries:
            paths = [Path(entry.path) for entry in islice(entries, 65)]
        if len(paths) > 64:
            raise ValueError("INSTALL_JOB_LIMIT")
        for path in paths:
            if path.is_symlink() or not path.is_dir() or str(UUID(path.name)) != path.name:
                raise ValueError("INSTALL_LEDGER_FORBIDDEN")
        return paths

    def _saved_jobs(self) -> dict[str, tuple[InstallJob, str]]:
        """Bounded read-only ledger replay. Never acquire a writer or repair tails."""
        result = {}
        for path in self._ledger_slots():
            journal_path = path / "events.jsonl"
            if not journal_path.exists():
                # An interrupted exclusive mkdir before the first durable event is
                # not an executable job. Never delete or reuse its directory.
                continue
            events = read_events(
                journal_path, path.name, "application", max_bytes=4 * 1024 * 1024, max_records=512
            )
            if not events:
                raise ValueError("INSTALL_LEDGER_INVALID")
            identity = None
            for event in events:
                if event.type != "status_changed":
                    raise ValueError("INSTALL_LEDGER_INVALID")
                job, _ = read_install_job(event.payload)
                if job.job_id != path.name:
                    raise ValueError("INSTALL_LEDGER_INVALID")
                current = (job.plan_id, job.plan_hash, job.environment_id)
                if identity is not None and current != identity:
                    raise ValueError("INSTALL_LEDGER_INVALID")
                identity = current
            result[job.job_id] = job, events[-1].timestamp
        return result

    @staticmethod
    def _historical_view(recorded: InstallJob) -> InstallJob:
        job = recorded.model_copy(deep=True)
        if job.state == "AWAITING_EXECUTION":
            job.state, job.status_code = "CANCELLED", "INSTALL_RESTART_CONFIRMATION_EXPIRED"
        elif job.state in {"INSTALLING", "VERIFYING", "CANCEL_REQUESTED"}:
            job.state, job.status_code = "CANCEL_REQUESTED", "INSTALL_STOP_UNCONFIRMED"
            job.verified, job.needs_reprobe = False, True
        return job

    def _report(self, saved: InstallJob, timestamp: str) -> InstallJobReport:
        current = saved.job_id in self._jobs and saved.job_id not in self._recovered
        observed = (
            self._jobs[saved.job_id].model_copy(deep=True)
            if current
            else self._historical_view(saved)
        )
        if (observed.plan_id, observed.plan_hash, observed.environment_id) != (
            saved.plan_id,
            saved.plan_hash,
            saved.environment_id,
        ):
            raise ValueError("INSTALL_LEDGER_INVALID")
        worker = self._workers.get(saved.job_id) if current else None
        alive = bool(worker and worker.is_alive())
        if (current and observed.state in {"INSTALLING", "VERIFYING"} and not alive) or (
            saved.job_id not in self._jobs and saved.state == "AWAITING_EXECUTION"
        ):
            observed.state, observed.status_code = "CANCEL_REQUESTED", "INSTALL_STOP_UNCONFIRMED"
            observed.verified, observed.needs_reprobe = False, True
        observation: Literal[
            "managed-worker-alive", "registered-only", "historical", "stop-unconfirmed"
        ]
        if observed.state == "CANCEL_REQUESTED" or (
            observed.state in {"INSTALLING", "VERIFYING"} and not alive
        ):
            observation = "stop-unconfirmed"
        elif alive:
            observation = "managed-worker-alive"
        elif current and observed.state == "AWAITING_EXECUTION":
            observation = "registered-only"
        else:
            observation = "historical"
        try:
            recorded_at = datetime.fromisoformat(timestamp)
            if recorded_at.tzinfo is None:
                raise ValueError
        except ValueError:
            raise ValueError("INSTALL_LEDGER_INVALID") from None
        summary = InstallJobSummary(
            job_id=saved.job_id,
            environment_id=saved.environment_id,
            plan_id=saved.plan_id,
            plan_hash=saved.plan_hash,
            recorded_at=recorded_at,
            recorded_state=saved.state,
            state=observed.state,
            status_code=observed.status_code,
            origin="current"
            if current
            else "recovered"
            if saved.job_id in self._recovered
            else "external",
            worker_alive=alive,
            observation=observation,
        )
        return InstallJobReport(
            summary=summary, recorded=saved.model_copy(deep=True), observed=observed
        )

    def history(self) -> InstallJobHistory:
        with self._mutex:
            self._verify_root()
            entries = [
                self._report(job, stamp).summary for job, stamp in self._saved_jobs().values()
            ]
            entries.sort(key=lambda item: (item.recorded_at, item.job_id), reverse=True)
            self._verify_root()
            return InstallJobHistory(entries=entries)

    def report(self, job_id: str) -> InstallJobReport:
        with self._mutex:
            self._verify_root()
            job, stamp = self._saved_jobs()[job_id]
            result = self._report(job, stamp)
            self._verify_root()
            return result

    def _record(self, job: InstallJob) -> None:
        try:
            if self._closed:
                raise ValueError("INSTALL_SESSION_CLOSED")
            journal = self._journals.get(job.job_id)
            if journal is None:
                root = self.app_root / "install-jobs"
                if root.is_symlink():
                    raise ValueError("INSTALL_LEDGER_FORBIDDEN")
                root.mkdir(mode=0o700, exist_ok=True)
                path = root / job.job_id
                path.mkdir(mode=0o700)  # Exclusive; never attach to a different writer.
                journal = EventJournal(path / "events.jsonl", job.job_id, "application")
                self._journals[job.job_id] = journal
            payload = job.model_dump(by_alias=True)
            plan = self._plans.get(job.plan_id)
            if plan is not None and plan.value.new_environment:
                payload["creationRequired"] = True
            journal.append("status_changed", None, payload)
        except Exception:
            self._persistence_failed = True
            raise ValueError("INSTALL_LEDGER_WRITE_FAILED") from None

    def _exclude_uncertain_writer(self, job: InstallJob) -> None:
        """Also protect instances opened before another writer's crash.

        A kernel lease can disappear when the app dies while its child survives.
        Check durable intent again under that lease; never infer quiescence from
        an unlocked inode or from a stale in-memory recovery snapshot.
        """
        root = self.app_root / "install-jobs"
        if root.is_symlink() or not root.is_dir():
            raise ValueError("INSTALL_LEDGER_FORBIDDEN")
        paths = list(root.iterdir())
        if len(paths) > 64:
            raise ValueError("INSTALL_JOB_LIMIT")
        for path in paths:
            if path.is_symlink() or not path.is_dir() or str(UUID(path.name)) != path.name:
                raise ValueError("INSTALL_LEDGER_FORBIDDEN")
            if path.name == job.job_id:
                continue
            source = path / "events.jsonl"
            if not source.exists():
                continue
            events = read_events(source, path.name, "application")
            if not events:
                raise ValueError("INSTALL_LEDGER_INVALID")
            previous, _ = read_install_job(events[-1].payload)
            if previous.job_id != path.name:
                raise ValueError("INSTALL_LEDGER_INVALID")
            if previous.environment_id == job.environment_id and previous.state in {
                "INSTALLING",
                "VERIFYING",
                "CANCEL_REQUESTED",
            }:
                raise ValueError("INSTALL_ENVIRONMENT_CONFLICT")

    def _verify_root(self) -> None:
        if self._closed or self._closing or self._close_requested.is_set():
            raise ValueError("INSTALL_SESSION_CLOSED")
        if self._persistence_failed:
            raise ValueError("INSTALL_LEDGER_WRITE_FAILED")
        if (
            not self.app_root.is_absolute()
            or self.app_root.is_symlink()
            or not self.app_root.is_dir()
        ):
            raise ValueError("INSTALL_ROOT_FORBIDDEN")
        if self.root.is_symlink() or (self.root.exists() and not self.root.is_dir()):
            raise ValueError("INSTALL_ROOT_FORBIDDEN")

    def _profile_hash(self) -> str:
        return constraints_hash(PROFILE_ROOT)

    def _source_guard(self) -> None:
        self._verify_root()
        with self._probe_gate:
            probes = bool(self._probes)
        if self._active or self._executing or self._leases or probes:
            raise ValueError("INSTALL_SOURCE_BUSY")
        for job in self._jobs.values():
            if job.state in {"INSTALLING", "VERIFYING", "CANCEL_REQUESTED"}:
                raise ValueError("INSTALL_SOURCE_BUSY")
        ledger = self.app_root / "install-jobs"
        if ledger.exists() or ledger.is_symlink():
            if ledger.is_symlink() or not ledger.is_dir():
                raise ValueError("INSTALL_LEDGER_FORBIDDEN")
            paths = list(ledger.iterdir())
            if len(paths) > 64:
                raise ValueError("INSTALL_JOB_LIMIT")
            for path in paths:
                if path.is_symlink() or not path.is_dir() or str(UUID(path.name)) != path.name:
                    raise ValueError("INSTALL_LEDGER_FORBIDDEN")
                source = path / "events.jsonl"
                if not source.exists():
                    continue
                events = read_events(source, path.name, "application")
                if not events:
                    raise ValueError("INSTALL_LEDGER_INVALID")
                observed, _ = read_install_job(events[-1].payload)
                if observed.job_id != path.name:
                    raise ValueError("INSTALL_LEDGER_INVALID")
                if observed.state in {"INSTALLING", "VERIFYING", "CANCEL_REQUESTED"}:
                    raise ValueError("INSTALL_SOURCE_BUSY")

    def _source_selection(self) -> "SourceSelection":
        if self._runtime is None:
            raise ValueError("INSTALL_RUNTIME_NOT_AVAILABLE")
        if self._sources is None:
            from easyai.services.install_source_selection import SourceSelection

            self._sources = SourceSelection(self._runtime, self._source_guard)
        return self._sources

    def preview_sources(self, request: InstallSourceRequest) -> InstallSourcePreview:
        with self._mutex:
            return self._source_selection().preview(request)

    def confirm_sources(self, request: InstallSourceConfirmation) -> InstallSourceResult:
        with self._mutex:
            return self._source_selection().confirm(request)

    def _wheels(self, selected: set[str] | None = None) -> list[Wheel]:
        return wheels(PROFILE_ROOT, selected)

    def catalog(self) -> PackageCatalog:
        self._verify_root()
        versions = {item["name"]: item["version"] for item in self._wheels(set(OPTIONAL_ROOTS))}
        raw = json.loads(read_regular(PACKAGES_PATH, 50_000))
        capability = self._runtime.snapshot() if self._runtime else None
        self._verify_root()
        return PackageCatalog(
            packages=[
                PackageCard(**item, target_version=versions.get(item["packageId"]))
                for item in raw["packages"]
            ],
            profiles=["teacher-existing", "easyai-cpu"],
            execution_enabled=capability.enabled if capability else False,
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

    def _owned(self, environment_id: str, *, allow_partial: bool = False) -> Path:
        path = self._prefix(environment_id)
        if not path.is_dir():
            raise ValueError("INSTALL_ENVIRONMENT_FORBIDDEN")
        try:
            marker = json.loads(read_regular(path / ".easyai-owned.json", 2048))
        except (OSError, ValueError):
            raise ValueError("INSTALL_ENVIRONMENT_FORBIDDEN") from None
        if marker != {"ownedByEasyAI": True, "environmentId": environment_id}:
            raise ValueError("INSTALL_ENVIRONMENT_FORBIDDEN")
        if not allow_partial:
            require_ready(self.app_root, environment_id, path)
        return path

    def _probe(self, path: Path, nonce: str, receipt: ProbeReceipt) -> InstallInspection:
        if self._inspector is None:
            receipt.quiescent = True  # No operation was dispatched.
            raise ValueError("INSTALL_INSPECTION_NOT_ENABLED")
        with self._probe_gate:
            if self._close_requested.is_set():
                receipt.quiescent = True
                raise ValueError("INSTALL_SESSION_CLOSED")
            if any(probe.prefix == path for probe in self._probes):
                receipt.quiescent = True  # This invocation has dispatched nothing.
                raise ValueError("INSTALL_STOP_UNCONFIRMED")
            receipt.prefix = path
            receipt.quiescent = False
            self._probes.add(receipt)
        try:
            owned = getattr(self._inspector, "inspect_owned", None)
            if owned is not None:
                report: InstallInspection = owned(path, nonce, receipt)
            else:
                report = self._inspector(path, nonce)
                # Legacy internal synchronous inspectors return only after their
                # work is complete. Exceptions never imply such a receipt.
                receipt.quiescent = True
            if not receipt.quiescent:
                raise ValueError("INSTALL_STOP_UNCONFIRMED")
            return report
        finally:
            with self._probe_gate:
                if receipt.quiescent:
                    self._probes.discard(receipt)

    def _inspect(
        self,
        environment_id: str,
        *,
        allow_partial: bool = False,
        receipt: ProbeReceipt | None = None,
    ) -> InstallInspection:
        receipt = receipt or ProbeReceipt()
        receipt.quiescent = True  # Local path validation has dispatched no new probe.
        path = self._owned(environment_id, allow_partial=allow_partial)
        nonce = str(uuid4())
        report = self._probe(path, nonce, receipt)
        if report.nonce != nonce or report.prefix != str(path):
            raise ValueError("INSTALL_INSPECTION_INVALID")
        return report

    def _baseline(
        self, environment_id: str, new: bool, receipt: ProbeReceipt | None = None
    ) -> tuple[str, dict[str, str]]:
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
        report = self._inspect(environment_id, receipt=receipt)
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
            wheels = self._wheels(set(request.package_ids))
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
            blockers.extend(code for name, code in UNSUPPORTED.items() if name in selected)
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
            self._verify_root()  # A close request may have arrived during a read-only inspector.
            resolved = not blockers
            capability = (
                (
                    self._runtime.snapshot(selected)
                    if selected.intersection(OPTIONAL_ROOTS)
                    else self._runtime.snapshot()
                )
                if self._runtime
                else None
            )
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
                installed_bytes=sum(int(item["unpackedBytes"] or 0) for item in wheels)
                if resolved and all(item["unpackedBytes"] is not None for item in wheels)
                else None,
                size_status="locked-wheel-estimate" if resolved else "unresolved",
                platform="linux-x86_64-cp311",
                blockers=blockers,
                execution_enabled=bool(capability and capability.enabled and resolved),
                runtime_fingerprint=capability.fingerprint if capability else None,
                bootstrap_bytes=capability.bootstrap_bytes if capability else None,
                disk_budget_bytes=capability.disk_budget_bytes if capability else None,
                execution_seconds=capability.seconds if capability else None,
                requires_network=not bool(capability and capability.fingerprint),
            )
            if capability and capability.fingerprint and resolved:
                value.download_bytes = 0  # All approved sources are already local.
                value.installed_bytes = None  # Bootstrap extraction footprint is not measured.
            value.plan_hash = digest(value.model_dump(exclude={"plan_hash"}))
            self._plans = {
                key: item
                for key, item in self._plans.items()
                if item.deadline > self._clock() or key in self._by_plan
            }
            if len(self._plans) >= 64:
                raise ValueError("INSTALL_PLAN_LIMIT")
            self._verify_root()  # Includes the potentially slow source snapshot/hash window.
            self._plans[value.plan_id] = _Plan(value.model_copy(deep=True), self._clock() + 600)
            return value

    def _fresh(self, plan: InstallPlan, receipt: ProbeReceipt | None = None) -> None:
        if self._runtime is not None:
            selected = {item.package_id for item in plan.package_changes if item.requested}
            capability = (
                self._runtime.snapshot(selected)
                if selected.intersection(OPTIONAL_ROOTS)
                else self._runtime.snapshot()
            )
            if capability.fingerprint != plan.runtime_fingerprint or (
                plan.execution_enabled and not capability.enabled
            ):
                raise ValueError("INSTALL_PLAN_STALE")
        fingerprint, _ = self._baseline(plan.environment_id, plan.new_environment, receipt)
        self._verify_root()
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
                status_code="INSTALL_EXECUTION_QUEUED"
                if plan.execution_enabled
                else "INSTALL_EXECUTION_NOT_ENABLED",
                execution_enabled=plan.execution_enabled,
                logs=[
                    "PLAN_CONFIRMED",
                    "INSTALL_EXECUTION_QUEUED"
                    if plan.execution_enabled
                    else "INSTALL_EXECUTION_NOT_ENABLED",
                ],
            )
            # Share the existing short commit lock with source commits and
            # execution WAL. Count durable slots under it, through exclusive
            # mkdir and the first event; an empty crash directory still counts.
            registration = ProjectLock(self.app_root / ".install-source.lock")
            try:
                try:
                    registration.verify()
                except Exception:
                    raise ValueError("INSTALL_SOURCE_BUSY") from None
                self._verify_root()
                if len(self._ledger_slots()) >= 64:
                    raise ValueError("INSTALL_JOB_LIMIT")
                registration.verify()
                self._record(job)  # Durable reservation before becoming visible.
            finally:
                registration.close()
            self._jobs[job.job_id] = job
            self._by_plan[plan.plan_id] = job.job_id
            self._active[plan.environment_id] = job.job_id
            self._cancel[job.job_id] = threading.Event()
            if plan.execution_enabled:
                if self._runtime is None:
                    raise ValueError("INSTALL_EXECUTION_NOT_ENABLED")
                runtime = self._runtime

                def work() -> None:
                    try:
                        with runtime.job(self._cancel[job.job_id]):
                            self.execute(
                                job.job_id, runtime.executor, provisioner=runtime.provisioner
                            )
                    except Exception:
                        with self._mutex:
                            # No external exception text; uncertain writers retain lease.
                            if job.state not in {"CANCELLED", "SUCCEEDED", "FAILED"}:
                                job.state = (
                                    "CANCEL_REQUESTED" if job.job_id in self._leases else "FAILED"
                                )
                                job.status_code = (
                                    "INSTALL_STOP_UNCONFIRMED"
                                    if job.job_id in self._leases
                                    else "INSTALL_EXECUTION_FAILED"
                                )
                                if job.job_id not in self._leases:
                                    self._active.pop(job.environment_id, None)
                                job.verified, job.needs_reprobe = False, True
                                try:
                                    self._record(job)
                                except Exception:
                                    job.status_code = "INSTALL_LEDGER_WRITE_FAILED"

                worker = threading.Thread(
                    target=work, name="easyai-install-" + job.job_id, daemon=True
                )
                self._workers[job.job_id] = worker  # Unique registration under confirmation mutex.
                try:
                    worker.start()
                except Exception:
                    self._workers.pop(job.job_id)
                    self._active.pop(job.environment_id, None)
                    job.state, job.status_code = "FAILED", "INSTALL_EXECUTION_FAILED"
                    self._record(job)
            return job.model_copy(deep=True)

    def get(self, job_id: str) -> InstallJob:
        with self._mutex:
            self._verify_root()
            return self._jobs[job_id].model_copy(deep=True)

    def cancel(self, job_id: str) -> InstallJob:
        with self._mutex:
            self._verify_root()
            return self._cancel_job(job_id)

    def _cancel_job(self, job_id: str) -> InstallJob:
        job = self._jobs[job_id]
        if job_id in self._recovered:
            return job.model_copy(deep=True)  # No PID-based stop or automatic replay.
        previous = job.state
        if job.state == "AWAITING_EXECUTION":
            job.state, job.status_code = "CANCELLED", "INSTALL_CANCELLED_NO_EXECUTION"
            self._active.pop(job.environment_id, None)
        elif job.state in {"INSTALLING", "VERIFYING", "CANCEL_REQUESTED"}:
            job.state, job.status_code = "CANCEL_REQUESTED", "INSTALL_STOP_UNCONFIRMED"
            self._cancel[job_id].set()
        if previous != job.state:
            if len(job.logs) < 128:
                job.logs.append(job.status_code)
            self._record(job)
        return job.model_copy(deep=True)

    def execute(
        self,
        job_id: str,
        executor: InstallExecutor,
        *,
        provisioner: EnvironmentProvisioner | None = None,
    ) -> InstallJob:
        """Internal lifecycle used by the unique confirmed runtime worker, never arbitrary HTTP input."""
        with self._mutex:
            self._verify_root()
            job = self._jobs[job_id]
            if job.state != "AWAITING_EXECUTION":
                raise ValueError("INSTALL_JOB_CONFLICT")
            saved = self._plans[job.plan_id]
            if saved.deadline <= self._clock():
                raise ValueError("INSTALL_PLAN_STALE")
            plan = saved.value
            if plan.new_environment and (provisioner is None or self._inspector is None):
                raise ValueError("INSTALL_PROVISIONER_NOT_ENABLED")
            if plan.new_environment and sys.platform == "win32":
                raise ValueError("INSTALL_CREATION_PLATFORM_UNVERIFIED")
            creation = (
                OwnedCreation(self.app_root, plan.environment_id, job_id, plan.plan_hash)
                if plan.new_environment
                else None
            )
            prefix = (
                self._prefix(plan.environment_id) if creation else self._owned(plan.environment_id)
            )
            lease = creation.reserve() if creation else ProjectLock(prefix / ".easyai-install.lock")
            if lease.fd is None:
                lease.close()
                raise ValueError("INSTALL_ENVIRONMENT_CONFLICT")
            try:
                lease.verify()
                self._exclude_uncertain_writer(job)
            except BaseException:
                lease.close()
                raise
            try:
                configuration_lease = ProjectLock(self.app_root / ".install-source.lock")
            except BaseException:
                lease.close()
                raise
            try:
                configuration_lease.verify()
            except BaseException:
                configuration_lease.close()
                lease.close()
                raise ValueError("INSTALL_SOURCE_BUSY") from None
            self._leases[job_id] = lease
            self._executing.add(threading.current_thread())
            previous_status = job.status_code
            previous_changes = job.changes_possible
            job.state, job.status_code, job.changes_possible = "INSTALLING", "INSTALL_STARTED", True
            token = self._cancel[job_id]
            try:
                self._record(job)  # Write-ahead: never start an unrecorded writer.
            except BaseException:
                self._leases.pop(job_id).close()
                self._executing.discard(threading.current_thread())
                raise
            finally:
                configuration_lease.close()  # WAL is visible before a configuration commit can check it.

        def progress() -> None:
            lease.verify()
            if (
                self._runtime is not None
                and plan.execution_enabled
                and plan.disk_budget_bytes is not None
            ):
                self._runtime.budget(prefix, plan.disk_budget_bytes)
            if creation is not None and creation.prefix_identity is not None:
                creation.verify()
            with self._mutex:
                if len(job.logs) < 128:
                    job.logs.append("INSTALL_PROGRESS")

        quiescent = True  # The durable intent has dispatched no process yet.
        baseline_phase = False
        restore_awaiting = False
        failure_code = "INSTALL_REPROBE_FAILED"
        try:
            if saved.deadline <= self._clock():
                failure_code = "INSTALL_PLAN_STALE"
                raise ValueError(failure_code)
            baseline_phase = True
            baseline_probe = ProbeReceipt(cancel=token, quiescent=True)
            try:
                # The write-ahead record and kernel lease already cover this
                # baseline probe too; it can fail with an unknown child owner.
                self._fresh(plan, baseline_probe)
            finally:
                quiescent = baseline_probe.quiescent
            if saved.deadline <= self._clock():
                quiescent, failure_code = True, "INSTALL_PLAN_STALE"
                raise ValueError(failure_code)
            baseline_phase = False
            if creation is not None:
                quiescent, failure_code = True, "INSTALL_PROVISION_FAILED"
                creation.allocate()
                creation.verify()
                if token.is_set():
                    outcome = "cancelled"
                else:
                    if saved.deadline <= self._clock():
                        failure_code = "INSTALL_PLAN_STALE"
                        raise ValueError(failure_code)
                    assert provisioner is not None
                    quiescent = False
                    outcome = provisioner.create(
                        prefix, plan.model_copy(deep=True), token, progress
                    )
                    quiescent = outcome in {"completed", "cancelled", "failed"}
                if not quiescent:
                    raise ValueError("INSTALL_STOP_UNCONFIRMED")
                if outcome == "failed":
                    raise ValueError(failure_code)
                if token.is_set() or outcome == "cancelled":
                    raise _ProvisionCancelled
                creation.verify()
                assert self._inspector is not None
                nonce = str(uuid4())
                probe = ProbeReceipt(cancel=token)
                quiescent = False
                try:
                    bootstrap = self._probe(prefix, nonce, probe)
                finally:
                    quiescent = probe.quiescent
                if (
                    bootstrap.nonce != nonce
                    or bootstrap.prefix != str(prefix)
                    or not bootstrap.python_version.startswith("3.11.")
                ):
                    raise ValueError("INSTALL_PROVISION_PROBE_FAILED")
                creation.verify()
                if token.is_set():
                    raise _ProvisionCancelled
                if saved.deadline <= self._clock() or self._profile_hash() != plan.constraints_hash:
                    failure_code = "INSTALL_PLAN_STALE"
                    raise ValueError(failure_code)
                creation.mark_owned()
                failure_code = "INSTALL_REPROBE_FAILED"
            if token.is_set():
                quiescent = True
                raise _ProvisionCancelled
            if saved.deadline <= self._clock():
                quiescent, failure_code = True, "INSTALL_PLAN_STALE"
                raise ValueError(failure_code)
            if creation is not None:
                creation.verify()
            quiescent = False
            outcome = executor.install(prefix, plan.model_copy(deep=True), token, progress)
            quiescent = outcome in {"completed", "cancelled", "failed"}
            if not quiescent:
                raise ValueError("INSTALL_STOP_UNCONFIRMED")
            if outcome == "failed":
                failure_code = "INSTALL_EXECUTION_FAILED"
                raise ValueError(failure_code)
            if token.is_set() or outcome == "cancelled":
                with self._mutex:
                    job.state, job.status_code = "CANCELLED", "INSTALL_CANCELLED_REPROBE_REQUIRED"
            else:
                with self._mutex:
                    job.state, job.status_code = "VERIFYING", "INSTALL_REPROBE_STARTED"
                    if len(job.logs) < 128:
                        job.logs.append("INSTALL_REPROBE_STARTED")
                    self._record(job)
                expected = {item.package_id: item.target_version for item in plan.package_changes}
                probe = ProbeReceipt(
                    cancel=token,
                    import_names=tuple(
                        module for name, module in IMPORTS.items() if name in expected
                    ),
                )
                quiescent = False
                try:
                    report = self._inspect(
                        plan.environment_id, allow_partial=creation is not None, receipt=probe
                    )
                finally:
                    quiescent = probe.quiescent
                if creation is not None:
                    creation.verify()
                if (
                    not report.python_version.startswith("3.11.")
                    or not report.tensor_ok
                    or any(
                        not report.imports.get(module)
                        for name, module in IMPORTS.items()
                        if name in expected
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
                        if creation is not None:
                            creation.mark_ready()
                        job.state, job.status_code, job.verified, job.needs_reprobe = (
                            "SUCCEEDED",
                            "INSTALL_VERIFIED",
                            True,
                            False,
                        )
        except _ProvisionCancelled:
            with self._mutex:
                job.state, job.status_code = "CANCELLED", "INSTALL_CANCELLED_REPROBE_REQUIRED"
        except Exception:
            with self._mutex:
                job.state = "FAILED" if quiescent else "CANCEL_REQUESTED"
                job.status_code = failure_code if quiescent else "INSTALL_STOP_UNCONFIRMED"
            if baseline_phase and quiescent:
                with self._mutex:
                    if token.is_set() or self._close_requested.is_set():
                        job.state, job.status_code = "CANCELLED", "INSTALL_CANCELLED_NO_EXECUTION"
                    else:
                        job.state, job.status_code = "AWAITING_EXECUTION", previous_status
                        restore_awaiting = True
                    job.changes_possible = previous_changes
                raise  # Preserve known-quiet pre-install stale/invalid baseline failures.
        finally:
            with self._mutex:
                if quiescent:
                    if not restore_awaiting:
                        self._active.pop(job.environment_id, None)
                    self._leases.pop(job_id).close()
                if len(job.logs) < 128:
                    job.logs.append(job.status_code)
                try:
                    self._record(job)
                except ValueError:
                    job.state, job.status_code = "FAILED", "INSTALL_LEDGER_WRITE_FAILED"
                    job.verified, job.needs_reprobe = False, True
                finally:
                    self._executing.discard(threading.current_thread())
        return job.model_copy(deep=True)

    def close(self) -> None:
        deadline = time.monotonic() + 3
        self._close_requested.set()  # Reject new operations even while a probe holds the mutex.
        with self._probe_gate:
            for probe in self._probes:
                probe.cancel.set()
        if self._runtime is not None:
            self._runtime.request_cancel()  # Inspector owners also observe this outside the mutex.
        if not self._mutex.acquire(timeout=max(0, deadline - time.monotonic())):
            raise ValueError("INSTALL_STOP_UNCONFIRMED")
        try:
            if self._closed:
                return
            if not self._closing:
                for job_id in list(self._active.values()):
                    if (
                        self._jobs[job_id].state == "AWAITING_EXECUTION"
                        and job_id not in self._workers
                    ):
                        self._cancel[job_id].set()
                    elif not self._persistence_failed:
                        self._cancel_job(job_id)
                    else:
                        self._cancel[job_id].set()
                self._closing = True
            threads = set(self._workers.values()) | self._executing
        finally:
            self._mutex.release()
        for thread in threads:
            if thread is threading.current_thread():
                raise ValueError("INSTALL_STOP_UNCONFIRMED")
            thread.join(max(0, deadline - time.monotonic()))
        if not self._mutex.acquire(timeout=max(0, deadline - time.monotonic())):
            raise ValueError("INSTALL_STOP_UNCONFIRMED")
        try:
            with self._probe_gate:
                probes_pending = bool(self._probes)
            if (
                any(t.is_alive() for t in threads)
                or self._executing
                or self._leases
                or probes_pending
            ):
                raise ValueError("INSTALL_STOP_UNCONFIRMED")
            for journal in self._journals.values():
                journal.close()
            self._journals.clear()
            self._closed = True
        finally:
            self._mutex.release()
