"""Opt-in offline install policy. Missing configuration never grants execution.

Only an operator-supplied private manifest can authorize this host capability.
No URL resolver, credential input, cache download or conda installation exists.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import stat
import sys
import threading
from typing import Callable, Literal, Iterator
from uuid import uuid4

from pydantic import Field, field_validator
from easyai.domain.contracts import Contract
from easyai.domain.install import Digest, InstallPlan
from easyai.security.files import read_regular, digest_regular
from easyai.security.remote_cache import _directory
from easyai.services.install_process import (
    HEADER,
    ManagedInstallCommand,
    ManagedInstallInspector,
    OfflineWheelInstaller,
    _event,
)
from easyai.services.install_service import PROFILE_ROOT, digest
from easyai.services.install_sources import wheels

CONDA_VERSION = "25.9.1"
FILE_LIMIT = 1024 * 1024 * 1024


class Archive(Contract):
    path: str = Field(max_length=4096)
    sha256: Digest
    bytes: int = Field(ge=1, le=FILE_LIMIT)


class OfflineConfiguration(Contract):
    schema_version: Literal[1]
    conda_version: Literal["25.9.1"]
    launcher: Archive
    module_root: str = Field(max_length=4096)
    module_tree_sha256: Digest
    bootstrap: list[Archive] = Field(min_length=2, max_length=128)
    wheelhouse: str = Field(max_length=4096)
    disk_budget_bytes: int = Field(ge=1, le=10 * FILE_LIMIT)
    seconds: int = Field(ge=1, le=3600)
    execution_authorized: bool = False
    authorization_expires: datetime

    @field_validator("execution_authorized", mode="before")
    @classmethod
    def strict_authorization(cls, value: object) -> bool:
        if type(value) is not bool:
            raise ValueError("INSTALL_EXECUTION_NOT_AUTHORIZED")
        return value


@dataclass(frozen=True)
class Capability:
    fingerprint: str | None = None
    enabled: bool = False
    bootstrap_bytes: int | None = None
    disk_budget_bytes: int | None = None
    seconds: int | None = None


def private_file(path: Path, limit: int) -> bytes:
    return private_snapshot(path, limit)[0]


def private_snapshot(path: Path, limit: int) -> tuple[bytes, tuple[int, ...]]:
    protected(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_size > limit
        ):
            raise ValueError("INSTALL_RUNTIME_CONFIG_INVALID")
        raw = source.read(limit + 1)
        if len(raw) != info.st_size or os.fstat(source.fileno()) != info:
            # Compare stable fields below instead of allowing a replacement fd.
            after = os.fstat(source.fileno())
            if len(raw) != info.st_size or (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ) != (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns):
                raise ValueError("INSTALL_RUNTIME_CONFIG_INVALID")
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("INSTALL_RUNTIME_CONFIG_INVALID")
        return raw, (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
            info.st_uid,
            info.st_mode,
        )


def protected(path: Path, *, directory: bool = False) -> os.stat_result:
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("INSTALL_SOURCE_INVALID")
    anchor_uid = Path(path.anchor).lstat().st_uid
    for parent in reversed(path.parents):
        _directory(parent.lstat(), final=False, anchor_uid=anchor_uid)
    info = path.lstat()
    if (
        info.st_uid not in {0, os.getuid(), anchor_uid}
        or info.st_mode & 0o022
        or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
    ):
        raise ValueError("INSTALL_SOURCE_INVALID")
    return info


def archive(item: Archive) -> tuple[int, int, int, int, int]:
    path = Path(item.path)
    before = protected(path)
    if before.st_size != item.bytes or digest_regular(path, FILE_LIMIT) != item.sha256:
        raise ValueError("INSTALL_SOURCE_CHANGED")
    after = protected(path)

    def stamp(i: os.stat_result) -> tuple[int, int, int, int, int]:
        return i.st_dev, i.st_ino, i.st_size, i.st_mtime_ns, i.st_ctime_ns

    if stamp(before) != stamp(after):
        raise ValueError("INSTALL_SOURCE_CHANGED")
    return stamp(after)


def tree(root: Path) -> str:
    protected(root, directory=True)
    records: list[tuple[str, str]] = []
    total = count = 0
    for directory, names, files in os.walk(root, followlinks=False):
        count += len(names) + len(files)
        if count > 10000:
            raise ValueError("INSTALL_SOURCE_LIMIT")
        for name in sorted(names):
            protected(Path(directory) / name, directory=True)
        for name in sorted(files):
            path = Path(directory) / name
            info = protected(path)
            total += info.st_size
            if total > FILE_LIMIT:
                raise ValueError("INSTALL_SOURCE_LIMIT")
            records.append((str(path.relative_to(root)), digest_regular(path, FILE_LIMIT)))
    return digest(sorted(records))


class CondaBootstrap:
    """Exact 25.9.1 CLI contract; no force/clone/removal/solver/network fallback."""

    def __init__(self, runtime: "InstallRuntime"):
        self.runtime = runtime

    def create(
        self, prefix: Path, plan: InstallPlan, cancel: threading.Event, progress: Callable[[], None]
    ) -> Literal["completed", "cancelled", "unknown", "failed"]:
        config = self.runtime.validated(plan)
        if (
            prefix != self.runtime.root / "training-environments" / plan.environment_id
            or not plan.new_environment
        ):
            raise ValueError("INSTALL_ENVIRONMENT_FORBIDDEN")
        claim = json.loads(
            read_regular(
                self.runtime.root / "environment-creations" / plan.environment_id / "claim.json",
                4096,
            )
        )
        if (
            claim.get("environmentId") != plan.environment_id
            or claim.get("planHash") != plan.plan_hash
        ):
            raise ValueError("INSTALL_CREATION_PATH_REPLACED")
        before = protected(prefix, directory=True)
        if any(prefix.iterdir()):
            raise ValueError("INSTALL_BOOTSTRAP_PREFIX_NOT_EMPTY")
        work = self.runtime.commands.root / ("bootstrap-" + str(uuid4()))
        work.mkdir(mode=0o700)
        for name in ("home", "pkgs", "envs", "tmp"):
            (work / name).mkdir(mode=0o700)
        spec = work / "explicit.txt"
        spec.write_text(
            "@EXPLICIT\n"
            + "".join(Path(a.path).as_uri() + "#" + a.sha256 + "\n" for a in config.bootstrap)
        )
        spec.chmod(0o600)
        condarc = work / "condarc"
        condarc.write_text(
            "channels: []\ncreate_default_packages: []\nauto_update_conda: false\nnotify_outdated_conda: false\nnumber_channel_notices: 0\nregister_envs: false\n"
        )
        argv = [
            "conda",
            "--no-plugins",
            "create",
            "--offline",
            "--no-default-packages",
            "--copy",
            "--json",
            "--yes",
            "--prefix",
            str(prefix),
            "--file",
            str(spec),
        ]
        # -S excludes site/.pth; only the fully hashed, explicit module root is
        # added. The approved base interpreter/stdlib remains a trust boundary.
        source = HEADER + "sys.path.insert(0," + repr(config.module_root) + ")\nimport conda\n"
        source += "assert conda.__version__==" + repr(CONDA_VERSION) + "\n"
        source += (
            "assert os.path.realpath(conda.__file__)=="
            + repr(str(Path(config.module_root) / "conda/__init__.py"))
            + "\n"
        )
        source += (
            "import conda.base.context as cfg\n"
            "_set_path=cfg.Context._set_search_path\n"
            "def _private_path(self,_ignored,**kw):\n return _set_path(self,("
            + repr(str(condarc))
            + ",),**kw)\n"
            "cfg.Context._set_search_path=_private_path\ncfg.context.__init__()\n"
        )
        source += "import runpy\nsys.argv=" + repr(argv) + "\n"
        source += (
            "try: runpy.run_module('conda',run_name='__main__')\nexcept SystemExit as e:\n if e.code not in (None,0): raise\n"
            + _event("pipeline_completed")
        )
        progress()  # Service claim/lease/inode guard immediately before exec.
        self.runtime.validated(plan)
        if (protected(prefix, directory=True).st_dev, prefix.stat().st_ino) != (
            before.st_dev,
            before.st_ino,
        ) or any(prefix.iterdir()):
            raise ValueError("INSTALL_BOOTSTRAP_PREFIX_NOT_EMPTY")
        outcome, _ = self.runtime.commands.run(
            [config.launcher.path, "-I", "-S", "-B", "-c", source],
            prefix,
            cancel,
            progress,
            environment={
                "PATH": str(Path(config.launcher.path).parent) + ":/usr/bin:/bin",
                "HOME": str(work / "home"),
                "TMPDIR": str(work / "tmp"),
                "XDG_CONFIG_HOME": str(work / "home"),
                "XDG_CACHE_HOME": str(work / "home"),
                "CONDARC": str(condarc),
                "CONDA_NO_PLUGINS": "true",
                "CONDA_OFFLINE": "true",
                "CONDA_PKGS_DIRS": str(work / "pkgs"),
                "CONDA_ENVS_PATH": str(work / "envs"),
            },
        )
        progress()
        if (prefix.stat().st_dev, prefix.stat().st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("INSTALL_CREATION_PATH_REPLACED")
        return outcome


class InstallRuntime:
    def __init__(self, root: Path):
        self.root = root
        self.configuration_path = root / "install-runtime.json"
        commands = root / "install-processes"
        commands.mkdir(mode=0o700, exist_ok=True)
        protected(commands, directory=True)
        self.commands = ManagedInstallCommand(commands)
        self._local = threading.local()
        self.inspector = ManagedInstallInspector(
            self.commands, lambda: getattr(self._local, "cancel", threading.Event())
        )
        self.provisioner = CondaBootstrap(self)
        self.executor = self

    @contextmanager
    def job(self, cancel: threading.Event) -> Iterator[None]:
        self._local.cancel = cancel
        try:
            yield
        finally:
            del self._local.cancel

    def request_cancel(self) -> None:
        self.commands.request_cancel()

    def snapshot(self, selected: set[str] | None = None) -> Capability:
        if not self.configuration_path.exists() and not self.configuration_path.is_symlink():
            return Capability()
        config, fingerprint = self._read(selected)
        enabled = config.execution_authorized and config.authorization_expires > datetime.now(
            timezone.utc
        )
        return Capability(
            fingerprint,
            enabled,
            sum(a.bytes for a in config.bootstrap),
            config.disk_budget_bytes,
            config.seconds,
        )

    def _read(self, selected: set[str] | None = None) -> tuple[OfflineConfiguration, str]:
        return self.inspect_source(self.configuration_path, selected)

    def inspect_source(
        self, path: Path, selected: set[str] | None = None
    ) -> tuple[OfflineConfiguration, str]:
        raw, identity = private_snapshot(path, 65536)
        config = OfflineConfiguration.model_validate_json(raw)
        if (
            sys.platform != "linux"
            or platform.machine().lower() not in {"x86_64", "amd64"}
            or config.authorization_expires.tzinfo is None
        ):
            raise ValueError("INSTALL_PROFILE_PLATFORM_UNSUPPORTED")
        launcher = archive(config.launcher)
        module_root = Path(config.module_root)
        if (
            tree(module_root) != config.module_tree_sha256
            or not (module_root / "conda/__init__.py").is_file()
        ):
            raise ValueError("INSTALL_LAUNCHER_SOURCE_CHANGED")
        names = [Path(a.path).name for a in config.bootstrap]
        if (
            len(set(names)) != len(names)
            or not any(n.startswith("python-3.11.17-") for n in names)
            or not any(n.startswith("pip-") for n in names)
            or any(not n.endswith((".conda", ".tar.bz2")) for n in names)
        ):
            raise ValueError("INSTALL_BOOTSTRAP_SOURCE_INVALID")
        stamps = [archive(a) for a in config.bootstrap]
        selected_wheels = wheels(PROFILE_ROOT, selected)
        wheelhouse = Path(config.wheelhouse)
        protected(wheelhouse, directory=True)
        wheel_stamps = [
            archive(
                Archive(
                    path=str(wheelhouse / w["filename"]),
                    sha256=w["sha256"],
                    bytes=w["downloadBytes"],
                )
            )
            for w in selected_wheels
        ]
        if (
            sum(a.bytes for a in config.bootstrap)
            + sum(w["downloadBytes"] for w in selected_wheels)
            > config.disk_budget_bytes
        ):
            raise ValueError("INSTALL_DISK_BUDGET_EXCEEDED")
        if private_snapshot(path, 65536) != (raw, identity):
            raise ValueError("INSTALL_SOURCE_CHANGED")
        return config, digest(
            {
                "configuration": config.model_dump(mode="json"),
                "configurationIdentity": identity,
                "launcher": launcher,
                "moduleIdentity": (module_root.stat().st_dev, module_root.stat().st_ino),
                "bootstrap": stamps,
                "wheels": wheel_stamps,
            }
        )

    def validated(self, plan: InstallPlan) -> OfflineConfiguration:
        selected = {item.package_id for item in plan.package_changes if item.requested}
        config, fingerprint = self._read(selected)
        if (
            not config.execution_authorized
            or config.authorization_expires <= datetime.now(timezone.utc)
            or not plan.execution_enabled
            or plan.runtime_fingerprint != fingerprint
        ):
            raise ValueError("INSTALL_RUNTIME_CHANGED")
        self.commands.seconds = config.seconds
        return config

    def budget(self, prefix: Path, limit: int) -> None:
        total = count = 0
        for root in (prefix, self.commands.root):
            for directory, names, files in os.walk(root, followlinks=False):
                count += len(names) + len(files)
                if count > 100000:
                    raise ValueError("INSTALL_DISK_BUDGET_EXCEEDED")
                for name in files:
                    total += (Path(directory) / name).lstat().st_size
                    if total > limit:
                        raise ValueError("INSTALL_DISK_BUDGET_EXCEEDED")

    def install(
        self, prefix: Path, plan: InstallPlan, cancel: threading.Event, progress: Callable[[], None]
    ) -> Literal["completed", "cancelled", "unknown", "failed"]:
        config = self.validated(plan)
        return OfflineWheelInstaller(
            self.commands, Path(config.wheelhouse), authorized=True
        ).install(prefix, plan, cancel, progress)
