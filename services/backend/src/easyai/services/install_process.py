"""Internal install/probe adapters using the existing process owner.

The runtime policy must authorize exact offline sources before dispatch. No direct
HTTP command input, resolver, cache download or environment deletion exists here.
"""

from collections.abc import Callable
import json
import os
from pathlib import Path
import threading
import time
from typing import Literal
from uuid import uuid4

from easyai.domain.contracts import Event
from easyai.domain.install import InstallInspection, InstallPlan
from easyai.runtime.supervisor import ManagedSupervisor
from easyai.security.files import read_regular
from easyai.services.install_service import PROFILE_ROOT, ProbeReceipt
from easyai.services.install_sources import (
    ALLOWED_IMPORTS,
    OPTIONAL_ROOTS,
    constraints_hash,
    lock_bytes,
    wheels,
)

LOG_LIMIT = 1024 * 1024


def _event(kind: str, payload: str = "{}") -> str:
    return (
        "print('@@EASYAI_EVENT@@'+json.dumps({'type':"
        + repr(kind)
        + ",'blockId':None,'payload':"
        + payload
        + "}),file=protocol,flush=True)\n"
    )


HEADER = (
    "import json,os,sys\n"
    "protocol=os.fdopen(os.dup(1),'w',encoding='utf-8')\n"
    # Package output must never be interpreted as supervisor events. Redirect the
    # OS descriptor as well, including output from native package subprocesses.
    "os.dup2(2,1)\nsys.stdout=sys.stderr\n"
) + _event("runtime_started")

# --isolated skips user config/PIP option variables, but global/site config can
# still supply install.target/prefix or additional find-links. Set the documented
# devnull sentinel before importing pip; remove every inherited PIP_* first.
PIP_ENVIRONMENT = (
    "for key in list(os.environ):\n"
    " if key.upper().startswith('PIP_'): del os.environ[key]\n"
    "os.environ['PIP_CONFIG_FILE']=os.devnull\n"
)


class ManagedInstallCommand:
    """One synchronous internal command, owned cancellation and durable raw logs."""

    def __init__(self, root: Path, seconds: float = 60):
        if not 0 < seconds <= 3600:
            raise ValueError("INSTALL_TIMEOUT_INVALID")
        self.root = root
        self.seconds = seconds
        self.last_root: Path | None = None
        self._shutdown = threading.Event()

    def request_cancel(self) -> None:
        self._shutdown.set()

    def run(
        self,
        argv: list[str],
        cwd: Path,
        cancel: threading.Event,
        progress: Callable[[], None],
        *,
        environment: dict[str, str] | None = None,
        receipt: ProbeReceipt | None = None,
    ) -> tuple[Literal["completed", "cancelled", "unknown", "failed"], list[Event]]:
        if receipt is not None:
            receipt.quiescent = True  # No process owner has been created yet.
        if os.name != "posix":
            raise ValueError("INSTALL_PROCESS_PLATFORM_UNVERIFIED")
        if cancel.is_set() or self._shutdown.is_set():
            return "cancelled", []
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError("INSTALL_PROCESS_ROOT_FORBIDDEN")
        identity = str(uuid4())
        path = self.root / identity
        path.mkdir(mode=0o700)  # Exclusive process attempt; never relaunch an old log.
        self.last_root = path
        supervisor = ManagedSupervisor(
            path,
            identity,
            argv,
            cwd,
            environment=environment
            or {
                "PATH": "/usr/bin:/bin",
                "HOME": str(path),
                "TMPDIR": str(path),
                "XDG_CACHE_HOME": str(path),
                "MPLCONFIGDIR": str(path),
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            inherit_environment=False,
            cancel_grace=0.05,
            max_log_bytes=LOG_LIMIT,
        )
        if receipt is not None:
            receipt.owner, receipt.quiescent = supervisor, False
        deadline = time.monotonic() + self.seconds
        try:
            progress()  # Revalidate ownership immediately before the process consumes intent.
            supervisor.start()
            while supervisor.wait(0.02) is None:
                if cancel.is_set() or self._shutdown.is_set() or time.monotonic() >= deadline:
                    supervisor.request_cancel()
                    # Wait for owner-confirmed drain/exit, not merely accepted cancel.
                    supervisor.wait(2)
                    break
                progress()
            with supervisor.snapshot() as (state, done, code):
                if not done:
                    return "unknown", []
                events = supervisor.events()
                if cancel.is_set() or self._shutdown.is_set():
                    return "cancelled", events
                if state == "COMPLETED" and code == 0:
                    return "completed", events
                return "failed", events
        finally:
            # Existing supervisor owns group escalation and both pipe drainers.
            # A cleanup error propagates; InstallService retains its environment lease.
            try:
                supervisor.close()
            finally:
                if receipt is not None:
                    receipt.quiescent = supervisor.quiescent


def owned_python(prefix: Path) -> Path:
    python = prefix / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not prefix.is_absolute() or prefix.is_symlink() or not python.is_file():
        raise ValueError("INSTALL_PYTHON_UNAVAILABLE")
    return python


class OfflineWheelInstaller:
    """Real pip implementation; dispatched only through the plan-bound runtime worker.

    The wheelhouse must already exist by separate authorization. --no-index and
    --require-hashes prohibit resolution from a network source or unpinned wheel.
    Target ownership and fresh fingerprint/lease remain InstallService's job.
    """

    def __init__(
        self, commands: ManagedInstallCommand, wheelhouse: Path, *, authorized: bool = False
    ):
        self.commands = commands
        self.wheelhouse = wheelhouse
        self.authorized = authorized

    def install(
        self, prefix: Path, plan: InstallPlan, cancel: threading.Event, progress: Callable[[], None]
    ) -> Literal["completed", "cancelled", "unknown", "failed"]:
        if not self.authorized:
            raise ValueError("INSTALL_EXECUTION_NOT_AUTHORIZED")
        if (
            plan.blockers
            or not self.wheelhouse.is_absolute()
            or self.wheelhouse.is_symlink()
            or not self.wheelhouse.is_dir()
        ):
            raise ValueError("INSTALL_OFFLINE_TARGET_INVALID")
        if json.loads(read_regular(prefix / ".easyai-owned.json", 2048)) != {
            "ownedByEasyAI": True,
            "environmentId": plan.environment_id,
        }:
            raise ValueError("INSTALL_ENVIRONMENT_FORBIDDEN")
        # Copy the reviewed lock bytes into this command's trusted, private root.
        # A unique immutable pathname avoids another attempt replacing its input.
        lock = self.commands.root / f"{uuid4()}.lock"
        selected = {item.package_id for item in plan.package_changes if item.requested}
        reviewed_lock = lock_bytes(PROFILE_ROOT, selected)
        if constraints_hash(PROFILE_ROOT) != plan.constraints_hash:
            raise ValueError("INSTALL_PLAN_STALE")
        with lock.open("xb") as stream:
            stream.write(reviewed_lock)
            stream.flush()
            os.fsync(stream.fileno())
        argv = [
            "pip",
            "--isolated",
            "--disable-pip-version-check",
            "install",
            "--no-index",
            "--find-links",
            str(self.wheelhouse),
            "--require-hashes",
            "--only-binary=:all:",
            "--no-input",
            "--no-cache-dir",
            "-r",
            str(lock),
        ]
        source = (
            HEADER
            + PIP_ENVIRONMENT
            + "import runpy\nsys.argv="
            + repr(argv)
            + "\n"
            + "try:\n runpy.run_module('pip',run_name='__main__')\n"
            + "except SystemExit as error:\n"
            + " if error.code not in (None,0): raise\n"
            + _event("pipeline_completed")
        )
        outcome, _ = self.commands.run(
            [str(owned_python(prefix)), "-I", "-B", "-c", source], prefix, cancel, progress
        )
        return outcome


class ManagedInstallInspector:
    """Fresh real imports and a CPU convolution, outside the application Python."""

    def __init__(
        self, commands: ManagedInstallCommand, cancel: Callable[[], threading.Event] | None = None
    ):
        self.commands = commands
        self.cancel = cancel or threading.Event

    def __call__(self, prefix: Path, nonce: str) -> InstallInspection:
        return self.inspect_owned(prefix, nonce, ProbeReceipt(cancel=self.cancel()))

    def inspect_owned(self, prefix: Path, nonce: str, receipt: ProbeReceipt) -> InstallInspection:
        receipt.quiescent = True  # Fixed input validation has not spawned an owner.
        if not set(receipt.import_names).issubset(ALLOWED_IMPORTS):
            raise ValueError("INSTALL_INSPECTION_INVALID")
        names = [item["name"] for item in wheels(PROFILE_ROOT, set(OPTIONAL_ROOTS))]
        source = (
            HEADER
            + "import importlib.metadata,platform\n"
            + "versions={}\n"
            + "for name in "
            + repr(names)
            + ":\n"
            + " try: versions[name]=importlib.metadata.version(name)\n"
            + " except importlib.metadata.PackageNotFoundError: pass\n"
            + "imports={}\n"
            + "for name in "
            + repr(receipt.import_names)
            + ":\n"
            + " try: __import__(name); imports[name]=True\n"
            + " except Exception: imports[name]=False\n"
            + "tensor=False\n"
            + "try:\n import torch\n"
            + " tensor=bool(torch.nn.functional.conv2d(torch.ones(1,1,3,3),torch.ones(1,1,2,2)).eq(4).all().item())\n"
            + "except Exception: pass\n"
            + "report={'nonce':"
            + repr(nonce)
            + ",'prefix':sys.prefix,'pythonVersion':platform.python_version(),"
            + "'versions':versions,'imports':imports,'tensorOk':tensor}\n"
            + _event("progress", "report")
            + _event("pipeline_completed")
        )
        outcome, events = self.commands.run(
            [str(owned_python(prefix)), "-I", "-B", "-c", source],
            prefix,
            receipt.cancel,
            lambda: None,
            receipt=receipt,
        )
        reports = [event.payload for event in events if event.type == "progress"]
        if outcome != "completed" or len(reports) != 1:
            raise ValueError("INSTALL_INSPECTION_FAILED")
        report = InstallInspection.model_validate(reports[0])
        if report.nonce != nonce or report.prefix != str(prefix):
            raise ValueError("INSTALL_INSPECTION_INVALID")
        return report
