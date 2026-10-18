"""Private upload intent ledger. No local source paths, selections, sessions or secrets."""

import hashlib
import os
from pathlib import Path
from pathlib import PurePosixPath
from typing import Callable, Literal, Self
from uuid import uuid4

from pydantic import Field, model_validator
from easyai.domain.contracts import Contract
from easyai.domain.environment import Identifier, Fingerprint, RemotePath
from easyai.domain.remote_run import Digest
from easyai.domain.ssh import SshEndpoint
from easyai.services.data_transfer_errors import TransferFailure
from easyai.services.data_transfer_source import TransferSource
from easyai.security.remote_cache import local_directory, limited_names
from easyai.services.remote_artifacts import _encoded, _decode


class UploadFile(Contract):
    path: str = Field(min_length=1, max_length=512)
    bytes: int = Field(ge=0, le=100 * 1024 * 1024)
    sha256: Digest


def relative(value: str) -> None:
    parts = value.split("/")
    if (
        len(value.encode()) > 512
        or len(parts) > 13
        or PurePosixPath(value).is_absolute()
        or any(
            p in ("", ".", "..")
            or p.startswith(".")
            or len(p.encode()) > 255
            or any(c in p for c in "\\:")
            or any(ord(c) < 32 or ord(c) == 127 for c in p)
            for p in parts
        )
    ):
        raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")


class UploadIntent(Contract):
    protocol_version: Literal[1] = 1
    project_id: Identifier
    slot_id: Identifier
    target_id: Identifier
    target_revision: int = Field(ge=1)
    endpoint: SshEndpoint
    username: str = Field(min_length=1, max_length=128)
    host_fingerprint: Fingerprint
    home: RemotePath
    uid: int = Field(ge=0, le=4294967294)
    directories: list[str] = Field(max_length=256)
    files: list[UploadFile] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def bounded(self) -> Self:
        paths = [record.path for record in self.files]
        for path in [*paths, *self.directories]:
            relative(path)
            for parent in PurePosixPath(path).parents:
                if str(parent) != "." and str(parent) not in self.directories:
                    raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
        if (
            len(set(paths)) != len(paths)
            or len(set(self.directories)) != len(self.directories)
            or set(paths) & set(self.directories)
            or sum(f.bytes for f in self.files) > 256 * 1024 * 1024
        ):
            raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
        if len(self.raw()) > 60000:
            raise TransferFailure("DATA_TRANSFER_MANIFEST_LIMIT")
        return self

    def raw(self) -> bytes:
        return _encoded(self.model_dump(mode="json", by_alias=True))

    @property
    def root(self) -> str:
        return self.home + "/.easyai/projects/" + self.project_id + "/data/" + self.slot_id

    def completion(self) -> bytes:
        return _encoded(
            {
                "protocolVersion": 1,
                "projectId": self.project_id,
                "transferId": self.slot_id,
                "uid": self.uid,
                "files": [f.model_dump(mode="json") for f in self.files],
            }
        )


class UploadRecord(Contract):
    intent: UploadIntent
    attempts: list[Identifier] = Field(min_length=1, max_length=16)
    last_completed: bool = False


def source_files(source: TransferSource, check: Callable[[], None]) -> list[UploadFile]:
    result = []
    for record in sorted(source.files, key=lambda f: f.name):
        digest, count = hashlib.sha256(), 0
        with source.open(record, check) as stream:
            while raw := stream.read(65536):
                check()
                count += len(raw)
                if count > record.size:
                    raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
                digest.update(raw)
        if count != record.size:
            raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
        result.append(UploadFile(path=record.name, bytes=count, sha256=digest.hexdigest()))
    return result


class UploadLedger:
    def __init__(self, application_root: Path):
        parent = local_directory(application_root)
        try:
            self.directory = parent.child("data-transfers", create=True)
        finally:
            parent.close()
        self.lock = None
        self.failed = False
        self.records: dict[str, UploadRecord] = {}
        self.stamps: dict[str, tuple[int, int, int, int, int]] = {}
        try:
            self.lock = self.directory.writer_lock(".writer.lock")
            for name in limited_names(self.directory, 18):
                if name == ".writer.lock":
                    continue
                descriptor = self.directory.open_file(name)
                with os.fdopen(descriptor, "rb") as source:
                    record = UploadRecord.model_validate(_decode(source.read(65537)))
                    info = os.fstat(source.fileno())
                    self.directory.verify_file(name, source.fileno())
                if name != record.intent.slot_id + ".json" or len(self.records) >= 16:
                    raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
                self.records[record.intent.slot_id] = record
                self.stamps[record.intent.slot_id] = (
                    info.st_dev,
                    info.st_ino,
                    info.st_size,
                    info.st_mtime_ns,
                    info.st_ctime_ns,
                )
        except Exception as error:
            self.close()
            raise TransferFailure(
                "DATA_TRANSFER_BUSY"
                if isinstance(error, BlockingIOError)
                else "DATA_TRANSFER_RECOVERY_INVALID"
            ) from None

    def verify_intent(self, slot_id: str, intent: UploadIntent) -> None:
        if (
            self.failed
            or self.lock is None
            or slot_id not in self.records
            or self.records[slot_id].intent != intent
        ):
            raise TransferFailure("DATA_TRANSFER_PERSISTENCE_FAILED")
        self.lock.verify()
        descriptor = self.directory.open_file(slot_id + ".json")
        with os.fdopen(descriptor, "rb") as source:
            info = os.fstat(source.fileno())
            self.directory.verify_file(slot_id + ".json", source.fileno())
            if self.stamps.get(slot_id) != (
                info.st_dev,
                info.st_ino,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            ):
                self.failed = True
                raise TransferFailure("DATA_TRANSFER_PERSISTENCE_FAILED")

    def put(self, record: UploadRecord) -> None:
        if self.failed or self.lock is None:
            raise TransferFailure("DATA_TRANSFER_PERSISTENCE_FAILED")
        self.lock.verify()
        current = self.records.get(record.intent.slot_id)
        if (current and current.intent != record.intent) or (
            current is None and len(self.records) >= 16
        ):
            raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
        if current is not None:
            self.verify_intent(record.intent.slot_id, record.intent)
        name = ".record-" + str(uuid4())
        try:
            raw = _encoded(record.model_dump(mode="json", by_alias=True))
            if len(raw) > 65536:
                raise TransferFailure("DATA_TRANSFER_MANIFEST_LIMIT")
            descriptor = self.directory.open_file(name, "exclusive")
            with os.fdopen(descriptor, "wb") as output:
                output.write(raw)
                output.flush()
                self.directory.sync_file(output.fileno())
            self.directory.publish(
                name, record.intent.slot_id + ".json", replace=current is not None
            )
            self.directory.remove(name, missing_ok=True)
            self.directory.sync()
            descriptor = self.directory.open_file(record.intent.slot_id + ".json")
            with os.fdopen(descriptor, "rb") as source:
                if UploadRecord.model_validate(_decode(source.read(65537))) != record:
                    raise TransferFailure("DATA_TRANSFER_PERSISTENCE_FAILED")
                info = os.fstat(source.fileno())
                self.directory.verify_file(record.intent.slot_id + ".json", source.fileno())
            self.records[record.intent.slot_id] = record.model_copy(deep=True)
            self.stamps[record.intent.slot_id] = (
                info.st_dev,
                info.st_ino,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            )
        except Exception:
            self.failed = True
            raise TransferFailure("DATA_TRANSFER_PERSISTENCE_FAILED") from None
        finally:
            self.directory.remove(name, missing_ok=True)

    def close(self) -> None:
        if self.lock is not None:
            self.lock.close()
            self.lock = None
        self.directory.close()
