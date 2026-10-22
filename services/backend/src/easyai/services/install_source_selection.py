"""Native-source receipts and configuration registration; never grants execution."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Callable
from uuid import uuid4

from easyai.domain.install import (
    InstallSourceArtifact,
    InstallSourceConfirmation,
    InstallSourcePreview,
    InstallSourceRequest,
    InstallSourceResult,
)
from easyai.security.project_lock import ProjectLock
from easyai.security.files import read_regular
from easyai.services.install_runtime import InstallRuntime, private_snapshot, protected
from easyai.services.install_service import PROFILE_ROOT, PACKAGES_PATH, digest
from easyai.services.install_sources import wheels, UNSUPPORTED


class SourceSelection:
    """One in-memory receipt, called under the existing InstallService mutex."""

    def __init__(self, runtime: InstallRuntime, guard: Callable[[], None]):
        self.runtime, self.guard = runtime, guard
        self.pending: tuple[InstallSourcePreview, Path, str, object, object] | None = None
        self.applied: tuple[InstallSourceResult, object] | None = None
        self.uncertain = False
        self.deadline = 0.0

    def destination(self) -> object:
        path = self.runtime.configuration_path
        if not path.exists() and not path.is_symlink():
            return None
        raw, identity = private_snapshot(path, 65536)
        return hashlib.sha256(raw).hexdigest(), identity

    def root_identity(self) -> tuple[int, int, int, int]:
        info = protected(self.runtime.root, directory=True)
        return info.st_dev, info.st_ino, info.st_uid, info.st_mode

    def preview(self, request: InstallSourceRequest) -> InstallSourcePreview:
        self.guard()
        if self.uncertain:
            raise ValueError("INSTALL_SOURCE_COMMIT_UNCONFIRMED")
        self.pending = self.applied = None
        selected = set(request.package_ids)
        catalog = json.loads(read_regular(PACKAGES_PATH, 50000))
        allowed = {item["packageId"] for item in catalog["packages"]}
        if len(selected) != len(request.package_ids) or not selected <= allowed:
            raise ValueError("INSTALL_PACKAGE_FORBIDDEN")
        unsupported = sorted(selected.intersection(UNSUPPORTED))
        if unsupported:
            raise ValueError(UNSUPPORTED[unsupported[0]])
        records = wheels(PROFILE_ROOT, selected)
        if not selected <= {w["name"] for w in records}:
            raise ValueError("INSTALL_DEPENDENCIES_UNRESOLVED")
        root, previous = self.root_identity(), self.destination()
        path = Path(request.manifest_path)
        config, fingerprint = self.runtime.inspect_source(path, selected)
        raw, _ = private_snapshot(path, 65536)
        now = datetime.now(timezone.utc)
        if config.authorization_expires <= now:
            raise ValueError("INSTALL_SOURCE_EXPIRED")
        if self.runtime.inspect_source(path, selected)[1] != fingerprint:
            raise ValueError("INSTALL_SOURCE_CHANGED")
        artifacts = [
            InstallSourceArtifact(name=Path(a.path).name, sha256=a.sha256, bytes=a.bytes)
            for a in config.bootstrap
        ]
        wheel_artifacts = [
            InstallSourceArtifact(name=w["filename"], sha256=w["sha256"], bytes=w["downloadBytes"])
            for w in records
        ]
        preview = InstallSourcePreview(
            preview_id=str(uuid4()),
            preview_hash="0" * 64,
            package_ids=request.package_ids,
            source_name=path.name,
            manifest_sha256=hashlib.sha256(raw).hexdigest(),
            launcher=InstallSourceArtifact(
                name=Path(config.launcher.path).name,
                sha256=config.launcher.sha256,
                bytes=config.launcher.bytes,
            ),
            module_name=Path(config.module_root).name,
            module_tree_sha256=config.module_tree_sha256,
            bootstrap=artifacts,
            wheels=wheel_artifacts,
            source_bytes=sum(a.bytes for a in artifacts + wheel_artifacts),
            disk_budget_bytes=config.disk_budget_bytes,
            execution_seconds=config.seconds,
            authorization_expires=config.authorization_expires,
            declared_execution_authorized=config.execution_authorized,
            expires_at=min(now + timedelta(seconds=60), config.authorization_expires),
        )
        preview.preview_hash = digest(
            {
                "preview": preview.model_dump(mode="json", exclude={"preview_hash"}),
                "validatedSource": fingerprint,
                "previous": previous,
                "root": root,
            }
        )
        self.guard()
        if self.uncertain:
            raise ValueError("INSTALL_SOURCE_COMMIT_UNCONFIRMED")
        if self.destination() != previous or self.root_identity() != root:
            raise ValueError("INSTALL_SOURCE_CHANGED")
        self.pending = (preview, path, fingerprint, previous, root)
        self.deadline = time.monotonic() + max(
            0, (preview.expires_at - datetime.now(timezone.utc)).total_seconds()
        )
        return preview.model_copy(deep=True)

    def confirm(self, request: InstallSourceConfirmation) -> InstallSourceResult:
        self.guard()
        if self.uncertain:
            raise ValueError("INSTALL_SOURCE_COMMIT_UNCONFIRMED")
        if self.pending is None:
            raise ValueError("INSTALL_SOURCE_PREVIEW_REQUIRED")
        preview, path, fingerprint, previous, root = self.pending
        if (request.preview_id, request.preview_hash) != (preview.preview_id, preview.preview_hash):
            raise ValueError("INSTALL_SOURCE_PREVIEW_STALE")
        if self.applied:
            result, identity = self.applied
            if self.destination() != identity:
                raise ValueError("INSTALL_SOURCE_CHANGED")
            return result.model_copy(deep=True)
        if datetime.now(timezone.utc) >= preview.expires_at or time.monotonic() >= self.deadline:
            raise ValueError("INSTALL_SOURCE_EXPIRED")
        lease = ProjectLock(self.runtime.root / ".install-source.lock")
        temporary: Path | None = None
        try:
            lease.verify()
            if self.destination() != previous or self.root_identity() != root:
                raise ValueError("INSTALL_SOURCE_CHANGED")
            config, current = self.runtime.inspect_source(path, set(preview.package_ids))
            if current != fingerprint or datetime.now(timezone.utc) >= preview.expires_at:
                raise ValueError("INSTALL_SOURCE_CHANGED")
            # Importing a file is not a new source/execution authorization. The
            # independent operator gate must authorize the registered config.
            config.execution_authorized = False
            raw = config.model_dump_json(by_alias=True).encode()
            fd, name = tempfile.mkstemp(prefix=".install-source-", dir=self.runtime.root)
            temporary = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if self.runtime.inspect_source(path, set(preview.package_ids))[1] != fingerprint:
                raise ValueError("INSTALL_SOURCE_CHANGED")
            self.guard()
            if (
                datetime.now(timezone.utc) >= preview.expires_at
                or time.monotonic() >= self.deadline
            ):
                raise ValueError("INSTALL_SOURCE_EXPIRED")
            lease.verify()
            if self.destination() != previous or self.root_identity() != root:
                raise ValueError("INSTALL_SOURCE_CHANGED")
            self.uncertain = True
            os.replace(temporary, self.runtime.configuration_path)
            temporary = None
            descriptor = os.open(self.runtime.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            registered = self.runtime.snapshot(set(preview.package_ids))
            if registered.fingerprint is None or registered.enabled:
                raise ValueError("INSTALL_SOURCE_CHANGED")
            result = InstallSourceResult(
                preview_id=preview.preview_id,
                manifest_sha256=preview.manifest_sha256,
                runtime_fingerprint=registered.fingerprint,
                authorization_expires=config.authorization_expires,
            )
            self.applied = result, self.destination()
            self.uncertain = False
            return result.model_copy(deep=True)
        except Exception:
            if self.uncertain:
                raise ValueError("INSTALL_SOURCE_COMMIT_UNCONFIRMED") from None
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            lease.close()
