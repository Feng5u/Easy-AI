"""Freeze an authoritative run bundle before acquiring any remote I/O."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

from easyai.compiler.bundle import runtime_sources
from easyai.domain.contracts import RunConfig
from easyai.domain.environment import remote_path
from easyai.domain.remote_run import RemoteRunIdentity
from easyai.security.remote_cache import LocalDirectory, local_directory
from easyai.services.remote_artifacts import _decode, _encoded
from easyai.runtime.dataset_inputs import require_guarded_code

BUNDLE_FILES = frozenset(
    {
        "code/train.py",
        "code/source-map.json",
        "code/entry.py",
        "code/easyai_runtime.py",
        "code/supervisor.py",
        "code/managed.py",
        "code/dataset_inputs.py",
        "code/portable_journal.py",
        "program.ir.json",
        "README.md",
        "ENVIRONMENT.md",
    }
)
MAX_FILE = 8 * 1024 * 1024
MAX_BUNDLE = 32 * 1024 * 1024


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _local(directory: LocalDirectory, name: str, limit: int) -> bytes:
    fd = directory.open_file(name)
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        directory.verify_file(name, source.fileno())
        if before.st_size > limit:
            raise ValueError("REMOTE_BUNDLE_LIMIT")
        raw = source.read(limit + 1)
        after = os.fstat(source.fileno())
        directory.verify_file(name, source.fileno())
    if len(raw) != before.st_size or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("REMOTE_BUNDLE_SOURCE_CHANGED")
    return raw


@dataclass(frozen=True)
class RemoteBundle:
    """Internal snapshot; callers supply persisted compiler bundle/config, never renderer bytes."""

    identity: RemoteRunIdentity
    python: str
    files: tuple[tuple[str, bytes], ...]

    def python_argv(self) -> tuple[str, ...]:
        config = RunConfig.model_validate(_decode(dict(self.files)["run-config.json"]))
        if config.conda_executable is not None and config.environment_prefix is not None:
            return (
                config.conda_executable,
                "run",
                "-p",
                config.environment_prefix,
                "--no-capture-output",
                self.python,
            )
        return (self.python,)

    @classmethod
    def freeze(cls, root: Path, config: RunConfig, identity: RemoteRunIdentity) -> "RemoteBundle":
        config = RunConfig.model_validate(config.model_dump())
        identity = RemoteRunIdentity.model_validate(identity.model_dump())
        for path in (config.python_executable, config.run_root, config.data_root):
            remote_path(path)
        if (config.environment_prefix is None) != (config.conda_executable is None):
            raise ValueError("REMOTE_LAUNCHER_INVALID")
        if config.environment_prefix is not None:
            remote_path(config.environment_prefix)
        if config.conda_executable is not None:
            remote_path(config.conda_executable)
        for path in (config.python_executable, config.run_root):
            if not path.startswith("/") or any(
                part in ("", ".", "..") for part in path.split("/")[1:]
            ):
                raise ValueError("REMOTE_BUNDLE_PATH_INVALID")
        raw_config = _encoded(config.model_dump(mode="json", by_alias=True))
        if (
            config.runner != "ssh"
            or digest(raw_config) != identity.config_hash
            or any(
                getattr(config, name) != getattr(identity, name)
                for name in (
                    "run_id",
                    "project_id",
                    "target_id",
                    "run_root",
                    "program_hash",
                    "code_hash",
                    "bundle_hash",
                )
            )
        ):
            raise ValueError("REMOTE_BUNDLE_IDENTITY_INVALID")
        descriptor = local_directory(root.absolute())
        code = None
        try:
            code = descriptor.child("code")
            persisted_config = RunConfig.model_validate(
                _decode(_local(descriptor, "run-config.json", 65536))
            )
            persisted_identity = RemoteRunIdentity.model_validate(
                _decode(_local(descriptor, "remote-identity.json", 65536))
            )
            if persisted_config != config or persisted_identity != identity:
                raise ValueError("REMOTE_BUNDLE_SNAPSHOT_MISMATCH")
            expected_code = {
                name.removeprefix("code/") for name in BUNDLE_FILES if name.startswith("code/")
            }
            if set(code.names()) != expected_code:
                raise ValueError("REMOTE_BUNDLE_UNHASHED_CODE")
            manifest_raw = _local(descriptor, "bundle.json", 65536)
            manifest = _decode(manifest_raw)
            if (
                set(manifest) != {"files", "bundleHash", "codeHash", "programHash"}
                or set(manifest["files"]) != BUNDLE_FILES
                or digest(_encoded(manifest["files"])) != identity.bundle_hash
                or any(
                    manifest[name] != value
                    for name, value in (
                        ("bundleHash", identity.bundle_hash),
                        ("codeHash", identity.code_hash),
                        ("programHash", identity.program_hash),
                    )
                )
                or manifest["files"]["code/train.py"] != identity.code_hash
            ):
                raise ValueError("REMOTE_BUNDLE_MANIFEST_INVALID")
            files = {}
            for name in sorted(BUNDLE_FILES):
                raw = _local(
                    code if name.startswith("code/") else descriptor,
                    name.removeprefix("code/"),
                    MAX_FILE,
                )
                if digest(raw) != manifest["files"][name]:
                    raise ValueError("REMOTE_BUNDLE_HASH_INVALID")
                files[name] = raw
            require_guarded_code(files["code/train.py"].decode("utf-8"))
            from easyai.compiler.artifact_budget import validate_artifact_budget
            from easyai.domain.program import ProgramIR

            validate_artifact_budget(ProgramIR.model_validate_json(files["program.ir.json"]))
            for name, source in runtime_sources().items():
                if files[name] != source.encode("utf-8"):
                    raise ValueError("REMOTE_BUNDLE_HELPER_INVALID")
            files.update(
                {
                    "bundle.json": manifest_raw,
                    "run-config.json": raw_config,
                    "remote-identity.json": _encoded(
                        identity.model_dump(mode="json", by_alias=True)
                    ),
                }
            )
            if sum(map(len, files.values())) > MAX_BUNDLE:
                raise ValueError("REMOTE_BUNDLE_LIMIT")
            descriptor.verify()
            code.verify()
            return cls(identity, config.python_executable, tuple(sorted(files.items())))
        finally:
            if code is not None:
                code.close()
            descriptor.close()
