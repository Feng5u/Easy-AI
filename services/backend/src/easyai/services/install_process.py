"""Internal, disabled-by-default install adapter using the existing process owner.

No HTTP caller exists. Only an explicitly authorized, already owned target and an
already supplied offline wheelhouse can be used. No dependency resolver/download,
conda provisioner, shell command, PID recovery or environment deletion is added.
"""

from collections.abc import Callable
import json
import hashlib
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
from easyai.services.install_service import PROFILE_ROOT

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


class ManagedInstallCommand:
    """One synchronous internal command, owned cancellation and durable raw logs."""

    def __init__(self, root: Path, seconds: float = 60):
        if not 0 < seconds <= 3600:
            raise ValueError("INSTALL_TIMEOUT_INVALID")
        self.root = root
        self.seconds = seconds
        self.last_root: Path | None = None

    def run(
        self,
        argv: list[str],
        cwd: Path,
        cancel: threading.Event,
        progress: Callable[[], None],
    ) -> tuple[Literal["completed", "cancelled", "unknown", "failed"], list[Event]]:
        if os.name != "posix":
            raise ValueError("INSTALL_PROCESS_PLATFORM_UNVERIFIED")
        if cancel.is_set():
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
            environment={"MPLCONFIGDIR": str(path), "PYTHONDONTWRITEBYTECODE": "1"},
            cancel_grace=0.05,
            max_log_bytes=LOG_LIMIT,
        )
        deadline = time.monotonic() + self.seconds
        try:
            supervisor.start()
            while supervisor.wait(0.02) is None:
                if cancel.is_set() or time.monotonic() >= deadline:
                    supervisor.request_cancel()
                    # Wait for owner-confirmed drain/exit, not merely accepted cancel.
                    supervisor.wait(2)
                    break
                progress()
            with supervisor.snapshot() as (state, done, code):
                if not done:
                    return "unknown", []
                events = supervisor.events()
                if cancel.is_set():
                    return "cancelled", events
                if state == "COMPLETED" and code == 0:
                    return "completed", events
                return "failed", events
        finally:
            # Existing supervisor owns group escalation and both pipe drainers.
            # A cleanup error propagates; InstallService retains its environment lease.
            supervisor.close()


def owned_python(prefix: Path) -> Path:
    python = prefix / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not prefix.is_absolute() or prefix.is_symlink() or not python.is_file():
        raise ValueError("INSTALL_PYTHON_UNAVAILABLE")
    return python


class OfflineWheelInstaller:
    """Real pip command implementation; remains gated and is never called by API.

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
            plan.new_environment
            or plan.blockers
            or not self.wheelhouse.is_absolute()
            or self.wheelhouse.is_symlink()
            or not self.wheelhouse.is_dir()
        ):
            raise ValueError("INSTALL_OFFLINE_TARGET_INVALID")
        # Copy the reviewed lock bytes into this command's trusted, private root.
        # A unique immutable pathname avoids another attempt replacing its input.
        lock = self.commands.root / f"{uuid4()}.lock"
        lock_bytes = read_regular(PROFILE_ROOT / "easyai-cpu-linux-cp311.lock", 100_000)
        if (
            hashlib.sha256(
                read_regular(PROFILE_ROOT / "easyai-cpu-sources.json", 100_000) + lock_bytes
            ).hexdigest()
            != plan.constraints_hash
        ):
            raise ValueError("INSTALL_PLAN_STALE")
        with lock.open("xb") as stream:
            stream.write(lock_bytes)
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

    def __init__(self, commands: ManagedInstallCommand):
        self.commands = commands

    def __call__(self, prefix: Path, nonce: str) -> InstallInspection:
        packages = json.loads(read_regular(PROFILE_ROOT / "easyai-cpu-sources.json", 100_000))
        names = [item["name"] for item in packages["packages"]]
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
            + "for name in ('torch','torchvision','matplotlib'):\n"
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
            threading.Event(),
            lambda: None,
        )
        reports = [event.payload for event in events if event.type == "progress"]
        if outcome != "completed" or len(reports) != 1:
            raise ValueError("INSTALL_INSPECTION_FAILED")
        report = InstallInspection.model_validate(reports[0])
        if report.nonce != nonce or report.prefix != str(prefix):
            raise ValueError("INSTALL_INSPECTION_INVALID")
        return report
