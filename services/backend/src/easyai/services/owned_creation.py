"""Exclusive filesystem reservation for new owned environments; never removes paths.

The bootstrap adapter must support an existing empty directory. This module does
not run conda or install Python. An incomplete reservation is deliberately never
promoted or reused merely because its kernel lease has become available.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
from typing import Any
from uuid import UUID

from easyai.security.files import read_regular
from easyai.security.project_lock import ProjectLock
from easyai.services.event_journal import read_events
from easyai.domain.install import InstallJob


def read_install_job(payload: dict[str, Any]) -> tuple[InstallJob, bool]:
    value = dict(payload)
    required = value.pop("creationRequired", False)
    if type(required) is not bool:
        raise ValueError("INSTALL_LEDGER_INVALID")
    return InstallJob.model_validate(value), required


def sync_directory(path: Path) -> None:
    # The creation executor is POSIX-only. No unsupported durability fallback.
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_ino == 0:
        raise ValueError("INSTALL_CREATION_PATH_FORBIDDEN")
    return info.st_dev, info.st_ino


def exclusive_json(path: Path, value: object) -> None:
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"))
        stream.flush()
        os.fsync(stream.fileno())


@dataclass
class OwnedCreation:
    application_root: Path
    environment_id: str
    job_id: str
    plan_hash: str

    def __post_init__(self) -> None:
        if any(str(UUID(value)) != value for value in (self.environment_id, self.job_id)):
            raise ValueError("INSTALL_CREATION_ID_INVALID")
        if len(self.plan_hash) != 64 or any(c not in "0123456789abcdef" for c in self.plan_hash):
            raise ValueError("INSTALL_CREATION_ID_INVALID")
        if not self.application_root.is_absolute():
            raise ValueError("INSTALL_CREATION_PATH_FORBIDDEN")
        self.app_identity = identity(self.application_root)
        self.claims = self.application_root / "environment-creations"
        self.claim = self.claims / self.environment_id
        self.environments = self.application_root / "training-environments"
        self.prefix = self.environments / self.environment_id
        self.value = {
            "version": 1,
            "environmentId": self.environment_id,
            "jobId": self.job_id,
            "planHash": self.plan_hash,
            "appDevice": self.app_identity[0],
            "appInode": self.app_identity[1],
        }
        self.claim_identity: tuple[int, int] | None = None
        self.claims_identity: tuple[int, int] | None = None
        self.environments_identity: tuple[int, int] | None = None
        self.prefix_identity: tuple[int, int] | None = None
        self.lease: ProjectLock | None = None
        self.owned = False

    def reserve(self) -> ProjectLock:
        if identity(self.application_root) != self.app_identity:
            raise ValueError("INSTALL_CREATION_PATH_REPLACED")
        if self.prefix.exists() or self.prefix.is_symlink():
            raise ValueError("INSTALL_PLAN_STALE")
        self.claims.mkdir(mode=0o700, exist_ok=True)
        self.claims_identity = identity(self.claims)
        self.claim.mkdir(mode=0o700)  # Never take over an old/unknown reservation.
        self.claim_identity = identity(self.claim)
        exclusive_json(self.claim / "claim.json", self.value)
        lease = ProjectLock(self.claim / "environment.lock")
        if lease.fd is None:
            lease.close()
            raise ValueError("INSTALL_ENVIRONMENT_CONFLICT")
        self.lease = lease
        return lease

    def verify(self) -> None:
        if (
            self.lease is None
            or identity(self.application_root) != self.app_identity
            or identity(self.claims) != self.claims_identity
            or identity(self.claim) != self.claim_identity
            or json.loads(read_regular(self.claim / "claim.json", 4096)) != self.value
        ):
            raise ValueError("INSTALL_CREATION_PATH_REPLACED")
        self.lease.verify()
        if (
            self.environments_identity is not None
            and identity(self.environments) != self.environments_identity
        ):
            raise ValueError("INSTALL_CREATION_PATH_REPLACED")
        if self.prefix_identity is not None and identity(self.prefix) != self.prefix_identity:
            raise ValueError("INSTALL_CREATION_PATH_REPLACED")
        if self.owned and (
            json.loads(read_regular(self.prefix / ".easyai-origin.json", 4096)) != self.value
            or json.loads(read_regular(self.prefix / ".easyai-owned.json", 2048))
            != {"ownedByEasyAI": True, "environmentId": self.environment_id}
        ):
            raise ValueError("INSTALL_CREATION_PATH_REPLACED")

    def allocate(self) -> Path:
        self.verify()
        self.environments.mkdir(mode=0o700, exist_ok=True)
        self.environments_identity = identity(self.environments)
        self.prefix.mkdir(mode=0o700)  # Refuse a race winner, even an empty directory.
        self.prefix_identity = identity(self.prefix)
        self.verify()
        return self.prefix

    def mark_owned(self) -> None:
        self.verify()
        # Persist local origin before the compatible two-field ownership marker.
        # Losing the external claim must never turn a partial new env into legacy.
        exclusive_json(self.prefix / ".easyai-origin.json", self.value)
        sync_directory(self.prefix)
        exclusive_json(
            self.prefix / ".easyai-owned.json",
            {"ownedByEasyAI": True, "environmentId": self.environment_id},
        )
        sync_directory(self.prefix)
        self.owned = True
        self.verify()

    def mark_ready(self) -> None:
        self.verify()
        exclusive_json(
            self.claim / "ready.json",
            {
                "claim": self.value,
                "device": self.prefix_identity[0] if self.prefix_identity else None,
                "inode": self.prefix_identity[1] if self.prefix_identity else None,
            },
        )
        self.verify()


def require_ready(application_root: Path, environment_id: str, prefix: Path) -> None:
    """Legacy owned dirs have no reservation; new partial dirs must stay quarantined."""
    claims = application_root / "environment-creations"
    if claims.is_symlink():
        raise ValueError("INSTALL_CREATION_PATH_FORBIDDEN")
    claim = claims / environment_id
    if not claim.exists() and not claim.is_symlink():
        if (prefix / ".easyai-origin.json").exists() or (
            prefix / ".easyai-origin.json"
        ).is_symlink():
            raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE")
        jobs = application_root / "install-jobs"
        if jobs.is_symlink():
            raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE")
        if jobs.exists():
            paths = list(jobs.iterdir())
            if len(paths) > 64:
                raise ValueError("INSTALL_JOB_LIMIT")
            for path in paths:
                if path.is_symlink() or not path.is_dir() or str(UUID(path.name)) != path.name:
                    raise ValueError("INSTALL_LEDGER_INVALID")
                source = path / "events.jsonl"
                if not source.exists():
                    continue
                for event in read_events(source, path.name, "application"):
                    job, required = read_install_job(event.payload)
                    if job.environment_id == environment_id and required:
                        raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE")
        return
    identity(claim)
    try:
        value = json.loads(read_regular(claim / "claim.json", 4096))
        ready = json.loads(read_regular(claim / "ready.json", 8192))
        if json.loads(read_regular(prefix / ".easyai-origin.json", 4096)) != value:
            raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE")
    except FileNotFoundError:
        raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE") from None
    current = identity(prefix)
    if ready != {"claim": value, "device": current[0], "inode": current[1]}:
        raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE")
    try:
        if value["environmentId"] != environment_id or str(UUID(value["jobId"])) != value["jobId"]:
            raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE")
        events = read_events(
            application_root / "install-jobs" / value["jobId"] / "events.jsonl",
            value["jobId"],
            "application",
        )
        if not events:
            raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE")
        job, required = read_install_job(events[-1].payload)
        if (
            job.job_id != value["jobId"]
            or job.environment_id != environment_id
            or job.plan_hash != value["planHash"]
            or job.state != "SUCCEEDED"
            or not job.verified
            or not required
        ):
            raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE")
    except (KeyError, FileNotFoundError):
        raise ValueError("INSTALL_ENVIRONMENT_INCOMPLETE") from None
