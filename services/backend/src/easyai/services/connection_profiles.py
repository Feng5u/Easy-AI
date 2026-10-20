"""Bounded non-secret server summaries. No connection or credential operations."""

from pathlib import Path
from uuid import uuid4
from typing import Callable, Literal
from contextlib import contextmanager
from collections.abc import Iterator

from pydantic import Field, ValidationError

from easyai.domain.contracts import Contract
from easyai.domain.connections import (
    ConnectionProfile,
    ConnectionProfileInput,
    ConnectionProfileUpdate,
)
from easyai.security.files import read_regular
from easyai.security.project_lock import ProjectLock
from easyai.services.project_service import ProjectService


class _Catalog(Contract):
    version: Literal[1] = 1
    profiles: list[ConnectionProfile] = Field(default_factory=list, max_length=128)


class ConnectionProfiles:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / "connections.json"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError("CONNECTION_PROFILE_STORAGE_INVALID")
        lock = ProjectLock(self.root / ".connections.lock")
        try:
            if lock.fd is None:
                raise ValueError("CONNECTION_PROFILE_STORAGE_HELD")
            lock.verify()
            yield
            lock.verify()
        finally:
            lock.close()

    def _read(self) -> _Catalog:
        try:
            raw = read_regular(self.path, 128 * 1024)
        except FileNotFoundError:
            return _Catalog()
        try:
            value = _Catalog.model_validate_json(raw)
        except (ValidationError, ValueError):
            raise ValueError("CONNECTION_PROFILE_STORAGE_INVALID") from None
        if len({item.target_id for item in value.profiles}) != len(value.profiles):
            raise ValueError("CONNECTION_PROFILE_STORAGE_INVALID")
        return value

    def _write(self, catalog: _Catalog, before_publish: Callable[[], None] | None = None) -> None:
        payload = catalog.model_dump_json(by_alias=True).encode()
        if len(payload) > 128 * 1024:
            raise ValueError("CONNECTION_PROFILE_SIZE_LIMIT")
        if before_publish is not None:
            before_publish()
        ProjectService.atomic_write(self.path, payload)

    def list(self) -> list[ConnectionProfile]:
        with self._locked():
            return self._read().profiles

    def create(self, request: ConnectionProfileInput) -> ConnectionProfile:
        with self._locked():
            catalog = self._read()
            if len(catalog.profiles) >= 128:
                raise ValueError("CONNECTION_PROFILE_LIMIT")
            profile = ConnectionProfile(**request.model_dump(), target_id=str(uuid4()), revision=1)
            catalog.profiles.append(profile)
            self._write(catalog)
            return profile

    def update(
        self,
        target_id: str,
        request: ConnectionProfileUpdate,
        identity_guard: Callable[[ConnectionProfile], None],
        before_publish: Callable[[], None] | None = None,
    ) -> ConnectionProfile:
        with self._locked():
            catalog = self._read()
            for index, old in enumerate(catalog.profiles):
                if old.target_id != target_id:
                    continue
                if old.revision != request.expected_revision:
                    raise ValueError("CONNECTION_PROFILE_REVISION_CONFLICT")
                if old.endpoint != request.endpoint or old.username != request.username:
                    identity_guard(old)
                profile = ConnectionProfile(
                    alias=request.alias,
                    endpoint=request.endpoint,
                    username=request.username,
                    target_id=target_id,
                    revision=old.revision + 1,
                )
                catalog.profiles[index] = profile
                self._write(catalog, before_publish)
                return profile
            raise KeyError("CONNECTION_PROFILE_NOT_FOUND")
