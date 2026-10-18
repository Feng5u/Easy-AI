"""Sealed-run SFTP downloads. No remote writes, commands, deserialization or public path API.

SFTP v3 cannot express O_NOFOLLOW. Protected owner directories, lstat/handle
checks and hashes constrain reads; a malicious same-UID concurrent replacement
is outside this protocol's guarantees. This is not a run-success gate.
"""

from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import threading
import time
from typing import Any, Callable
from uuid import uuid4

import paramiko  # type: ignore[import-untyped]
from pydantic import TypeAdapter

from easyai.domain.contracts import ArtifactRecord, Event, SourceSpan
from easyai.domain.remote_run import (
    ArtifactManifest,
    RemoteRunCheckpoint,
    RemoteRunIdentity,
    RemoteRunObservation,
)
from easyai.security.remote_cache import check_file, open_directory, verify_directory
from easyai.services.run_views import validate_png
from easyai.services.ssh_client import VerifiedSshSession

CHUNK = 65536
MAX_MANIFEST = 65536
MAX_FILE = 100 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024


class ArtifactFailure(ValueError):
    pass


def _reject() -> None:
    raise ArtifactFailure("REMOTE_ARTIFACT_INVALID")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _reject()
        result[key] = value
    return result


def _decode(raw: bytes, limit: int = MAX_MANIFEST) -> Any:
    if len(raw) > limit:
        _reject()
    return json.loads(
        raw,
        object_pairs_hook=_unique,
        parse_constant=lambda _: _reject(),
    )


def _encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _path(record: ArtifactRecord) -> None:
    value = record.relative_path
    parts = value.split("/")
    if (
        len(parts) < 2
        or parts[0] != "outputs"
        or "\\" in value
        or ":" in value
        or len(value.encode()) > 4096
        or any(part in ("", ".", "..") or len(part.encode()) > 255 for part in parts)
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or not 0 <= record.size_bytes <= MAX_FILE
    ):
        _reject()
    suffix = PurePosixPath(value).suffix
    allowed = {
        "figure": ({".png"}, {"image/png"}, 8 * 1024 * 1024),
        "model": ({".pt", ".pth"}, {"application/octet-stream"}, MAX_FILE),
        "log": ({".txt", ".log"}, {"text/plain"}, 1024 * 1024),
        "metrics": ({".json", ".csv"}, {"application/json", "text/csv"}, 1024 * 1024),
    }
    suffixes, mimes, limit = allowed[record.kind]
    if suffix not in suffixes or record.mime_type not in mimes or record.size_bytes > limit:
        _reject()


@dataclass(frozen=True)
class ArtifactSnapshot:
    """Construct from coordinator evidence and the immutable local bundle, never renderer DTOs."""

    observation: RemoteRunObservation
    source_seq: int
    records: tuple[ArtifactRecord, ...]

    @classmethod
    def verified(
        cls,
        checkpoint: RemoteRunCheckpoint,
        events: list[Event],
        bundle_manifest: bytes,
        source_map: bytes,
    ) -> "ArtifactSnapshot":
        observation = checkpoint.last_observation
        if observation is None or not observation.sealed:
            _reject()
        assert observation is not None
        identity = checkpoint.identity
        bundle = _decode(bundle_manifest)
        if (
            set(bundle) != {"files", "programHash", "codeHash", "bundleHash"}
            or bundle["bundleHash"] != identity.bundle_hash
            or hashlib.sha256(_encoded(bundle["files"])).hexdigest() != identity.bundle_hash
            or bundle["programHash"] != identity.program_hash
            or bundle["codeHash"] != identity.code_hash
            or bundle["files"]["code/train.py"] != identity.code_hash
            or hashlib.sha256(source_map).hexdigest() != bundle["files"]["code/source-map.json"]
        ):
            _reject()
        spans = TypeAdapter(list[SourceSpan]).validate_python(_decode(source_map, 8 * 1024 * 1024))
        blocks = {span.origin.block_id for span in spans}
        runtime = [event for event in events if event.source == "runtime"]
        records = []
        ids: set[str] = set()
        paths: set[str] = set()
        total = 0
        for index, event in enumerate(runtime, 1):
            if event.run_id != identity.run_id or event.source_seq != index:
                _reject()
            if event.type != "artifact_created":
                continue
            record = ArtifactRecord.model_validate(event.payload)
            _path(record)
            if (
                record.run_id != identity.run_id
                or record.producer_block_id != event.block_id
                or record.producer_block_id not in blocks
                or any(block not in blocks for block in record.contributor_block_ids)
                or len(set(record.contributor_block_ids)) != len(record.contributor_block_ids)
                or not 1 <= len(record.artifact_id) <= 256
                or record.artifact_id in ids
                or record.relative_path in paths
            ):
                _reject()
            ids.add(record.artifact_id)
            paths.add(record.relative_path)
            total += record.size_bytes
            records.append(record.model_copy(deep=True))
        if not runtime or len(records) > 256 or total > MAX_TOTAL:
            _reject()
        return cls(observation.model_copy(deep=True), len(runtime), tuple(records))

    def manifest(self, raw: bytes) -> ArtifactManifest:
        value = ArtifactManifest.model_validate(_decode(raw))
        if (
            value.identity != self.observation.identity
            or value.source_seq != self.source_seq
            or value.events_sha256 != self.observation.streams.events.sha256
            or value.artifacts != list(self.records)
        ):
            _reject()
        return value


class _Reader:
    """Private fixed-record / validated-ID reader; no caller supplied remote path."""

    def __init__(self, sftp: Any, identity: RemoteRunIdentity, guard: Callable[[], None]):
        self.sftp, self.identity, self.guard = sftp, identity, guard
        self.uid: int | None = None
        self.anchor_uid: int | None = None
        self.bytes = 0

    def _stat(self, info: Any, directory: bool, *, ancestor: bool = False) -> None:
        mode, uid, size = info.st_mode, info.st_uid, info.st_size
        if type(mode) is not int or type(uid) is not int or type(size) is not int or size < 0:
            _reject()
        permitted = {0, self.uid, self.anchor_uid} if ancestor else {self.uid}
        if self.uid is not None and uid not in permitted:
            _reject()
        if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
            _reject()
        if mode & 0o022 and not (ancestor and mode & stat.S_ISVTX):
            _reject()

    def _parents(self, name: str) -> Any:
        root = PurePosixPath(self.identity.run_root)
        path = PurePosixPath("/")
        anchor = self.sftp.lstat("/")
        if self.anchor_uid is None:
            self.anchor_uid = anchor.st_uid
        self._stat(anchor, True, ancestor=True)
        for part in root.parts[1:]:
            path /= part
            self._stat(self.sftp.lstat(str(path)), True, ancestor=path != root)
            self.guard()
        for part in PurePosixPath(name).parts[:-1]:
            path /= part
            self._stat(self.sftp.lstat(str(path)), True)
            self.guard()
        info = self.sftp.lstat(str(root / name))
        self._stat(info, False)
        return info

    def read(self, name: str, limit: int, consume: Callable[[bytes], Any]) -> None:
        self.guard()
        before = self._parents(name)
        if before.st_size > limit:
            _reject()
        count = 0
        with self.sftp.open(
            str(PurePosixPath(self.identity.run_root) / name), "rb", bufsize=0
        ) as source:
            held = source.stat()
            self._stat(held, False)
            if (held.st_uid, held.st_mode, held.st_size) != (
                before.st_uid,
                before.st_mode,
                before.st_size,
            ):
                _reject()
            while True:
                self.guard()
                raw = source.read(min(CHUNK, limit - count + 1))
                self.guard()
                if not isinstance(raw, bytes):
                    _reject()
                count += len(raw)
                self.bytes += len(raw)
                if count > limit or self.bytes > MAX_TOTAL + 2 * MAX_MANIFEST:
                    _reject()
                if not raw:
                    break
                consume(raw)
            after = source.stat()
            self._stat(after, False)
        final = self._parents(name)

        def attributes(value: Any) -> tuple[int, int, int, float]:
            return value.st_uid, value.st_mode, value.st_size, value.st_mtime

        if (
            count != before.st_size
            or attributes(before) != attributes(after)
            or attributes(before) != attributes(final)
        ):
            _reject()
        self.guard()

    def record(self, name: str) -> bytes:
        parts: list[bytes] = []
        self.read(name, MAX_MANIFEST, parts.append)
        return b"".join(parts)


class _Cache:
    def __init__(self, path: Path):
        self.path, self.fd = path, open_directory(path)
        self.lock: int | None = None
        try:
            self.lock = os.open(
                ".artifact-writer.lock",
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o600,
                dir_fd=self.fd,
            )
            check_file(os.fstat(self.lock))
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.close()
            raise

    def verify(self) -> None:
        verify_directory(self.path, self.fd)
        assert self.lock is not None
        held, current = (
            os.fstat(self.lock),
            os.stat(".artifact-writer.lock", dir_fd=self.fd, follow_symlinks=False),
        )
        check_file(current)
        if (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino):
            _reject()

    def bind(self, identity: RemoteRunIdentity, *, create: bool = True) -> None:
        raw = _encoded(identity.model_dump(mode="json", by_alias=True))
        name, descriptor = self.temporary()
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            try:
                if not create:
                    raise FileExistsError()
                os.link(
                    name,
                    ".artifact-identity.json",
                    src_dir_fd=self.fd,
                    dst_dir_fd=self.fd,
                    follow_symlinks=False,
                )
                os.fsync(self.fd)
            except FileExistsError:
                pass
            descriptor = os.open(
                ".artifact-identity.json",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=self.fd,
            )
            with os.fdopen(descriptor, "rb") as source:
                check_file(os.fstat(source.fileno()))
                current = RemoteRunIdentity.model_validate(_decode(source.read(MAX_MANIFEST + 1)))
            if current != identity:
                _reject()
            try:
                existing = os.open(
                    "artifact-index.json",
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=self.fd,
                )
            except FileNotFoundError:
                return
            with os.fdopen(existing, "rb") as source:
                check_file(os.fstat(source.fileno()))
                value = _decode(source.read(MAX_MANIFEST + 1))
            if RemoteRunIdentity.model_validate(value["identity"]) != identity:
                _reject()
        finally:
            os.unlink(name, dir_fd=self.fd)

    def temporary(self) -> tuple[str, int]:
        self.verify()
        name = ".artifact-part-" + str(uuid4())
        return name, os.open(
            name, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=self.fd
        )

    def blob(self, digest: str, size: int) -> bytes:
        self.verify()
        descriptor = os.open(
            "blob-" + digest, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd
        )
        with os.fdopen(descriptor, "rb") as source:
            info = os.fstat(source.fileno())
            check_file(info)
            if info.st_size != size or size > MAX_FILE:
                _reject()
            raw = source.read(size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            _reject()
        return raw

    def close(self) -> None:
        if self.lock is not None:
            os.close(self.lock)
            self.lock = None
        os.close(self.fd)


def _content(record: ArtifactRecord, raw: bytes) -> None:
    if len(raw) != record.size_bytes or hashlib.sha256(raw).hexdigest() != record.sha256:
        _reject()
    if record.kind == "figure":
        validate_png(raw)  # CRC/chunk/EOF/dimensions; no decompression or image decode.
    elif record.kind in ("log", "metrics"):
        raw.decode("utf-8", errors="strict")


class SftpArtifactSync:
    def __init__(
        self,
        session: VerifiedSshSession,
        identity: RemoteRunIdentity,
        mutex: threading.RLock,
        guard: Callable[[], None],
        sftp_factory: Callable[[Any], Any] = paramiko.SFTPClient,
    ):
        self.session, self.identity = session, identity
        self.mutex, self.guard, self.factory = mutex, guard, sftp_factory

    def sync(
        self,
        snapshot: ArtifactSnapshot,
        cache_path: Path,
        cancel: threading.Event,
        *,
        seconds: float = 20,
    ) -> list[ArtifactRecord]:
        if snapshot.observation.identity != self.identity or not 0 < seconds <= 20:
            _reject()
        if not self.session.io_lock.acquire(blocking=False):
            raise ArtifactFailure("REMOTE_ARTIFACT_BUSY")
        done, abandoned = threading.Event(), threading.Event()
        values: list[list[ArtifactRecord]] = []
        failed = threading.Event()
        deadline = time.monotonic() + seconds

        def check() -> None:
            with self.mutex:
                if abandoned.is_set() or cancel.is_set() or time.monotonic() >= deadline:
                    raise ArtifactFailure("REMOTE_ARTIFACT_CANCELLED")
                if (
                    self.session.endpoint != self.identity.endpoint
                    or self.session.host_fingerprint != self.identity.host_fingerprint
                ):
                    _reject()
                try:
                    self.guard()
                except Exception:
                    raise ArtifactFailure("REMOTE_ARTIFACT_AUTH_STALE") from None

        def worker() -> None:
            channel, sftp, cache = None, None, None
            try:
                check()
                channel = self.session.open_probe_channel(timeout=min(2, seconds))
                channel.settimeout(min(2, seconds))
                check()
                channel.invoke_subsystem("sftp")
                sftp = self.factory(channel)
                check()
                reader = _Reader(sftp, self.identity, check)
                status = RemoteRunObservation.model_validate(
                    _decode(reader.record("owner-status.json"))
                )
                if status != snapshot.observation:
                    _reject()
                manifest = snapshot.manifest(reader.record("remote-artifacts.json"))
                reader.uid = manifest.uid
                # Recheck bootstrap records now that UID is bound to the owner receipt.
                reader._parents("owner-status.json")
                reader._parents("remote-artifacts.json")
                cache = _Cache(cache_path)
                cache.bind(self.identity)
                ready = []
                for record in snapshot.records:
                    name, descriptor = cache.temporary()
                    try:
                        with os.fdopen(descriptor, "w+b") as target:
                            reader.read(record.relative_path, record.size_bytes, target.write)
                            target.flush()
                            target.seek(0)
                            _content(record, target.read(record.size_bytes + 1))
                            os.fsync(target.fileno())
                        with self.mutex:
                            check()
                            cache.verify()
                            try:
                                os.link(
                                    name,
                                    "blob-" + record.sha256,
                                    src_dir_fd=cache.fd,
                                    dst_dir_fd=cache.fd,
                                    follow_symlinks=False,
                                )
                            except FileExistsError:
                                _content(record, cache.blob(record.sha256, record.size_bytes))
                            os.fsync(cache.fd)
                        ready.append(record.model_copy(update={"sync_state": "ready"}, deep=True))
                    finally:
                        # Only the random temporary created by this worker is removable.
                        os.unlink(name, dir_fd=cache.fd)
                # Cleanup the dedicated remote channel before publishing readiness.
                # A failed SDK close leaves only verified unindexed blobs behind.
                sftp.close()
                sftp = None
                channel.close()
                channel = None
                with self.mutex:
                    check()
                    cache.verify()
                    for record in ready:
                        _content(record, cache.blob(record.sha256, record.size_bytes))
                    index = _encoded(
                        {
                            "identity": self.identity.model_dump(mode="json", by_alias=True),
                            "artifacts": [
                                record.model_dump(mode="json", by_alias=True) for record in ready
                            ],
                        }
                    )
                    if len(index) > MAX_MANIFEST:
                        _reject()
                    name, descriptor = cache.temporary()
                    try:
                        with os.fdopen(descriptor, "wb") as target:
                            target.write(index)
                            target.flush()
                            os.fsync(target.fileno())
                        # Never follow or silently replace a hostile existing index.
                        try:
                            check_file(
                                os.stat(
                                    "artifact-index.json", dir_fd=cache.fd, follow_symlinks=False
                                )
                            )
                        except FileNotFoundError:
                            pass
                        check()
                        os.replace(
                            name, "artifact-index.json", src_dir_fd=cache.fd, dst_dir_fd=cache.fd
                        )
                        os.fsync(cache.fd)
                        values.append(ready)
                    finally:
                        try:
                            os.unlink(name, dir_fd=cache.fd)
                        except FileNotFoundError:
                            pass
            except Exception:
                failed.set()
            finally:
                for resource in (sftp, channel, cache):
                    if resource is not None:
                        try:
                            resource.close()
                        except Exception:
                            failed.set()
                if failed.is_set():
                    self.session.close()
                self.session.io_lock.release()
                done.set()

        thread = threading.Thread(target=worker, name="easyai-artifact-sftp", daemon=True)
        try:
            thread.start()
        except BaseException:
            self.session.io_lock.release()
            raise
        while not done.wait(0.01):
            with self.mutex:
                # The final guard under this same mutex is the commit boundary.
                # Cancellation after durable publication cannot roll it back or
                # turn a successful committed download into a cancelled result.
                if not values and (cancel.is_set() or time.monotonic() >= deadline):
                    abandoned.set()
            if abandoned.is_set():
                # The SDK close may itself block. Retain the physical gate/cache lock
                # in the worker until it has actually quiesced; never kill the owner.
                threading.Thread(
                    target=self.session.close, name="easyai-artifact-close", daemon=True
                ).start()
                raise ArtifactFailure("REMOTE_ARTIFACT_CLEANUP_UNCONFIRMED")
        with self.mutex:
            if failed.is_set() or not values:
                raise ArtifactFailure("REMOTE_ARTIFACT_FAILED")
            return values[0]

    @staticmethod
    def read_ready(cache_path: Path, identity: RemoteRunIdentity, artifact_id: str) -> bytes:
        """Opaque ID lookup; revalidate every blob rather than trusting a ready index."""
        cache = _Cache(cache_path)
        try:
            cache.bind(identity, create=False)
            descriptor = os.open(
                "artifact-index.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=cache.fd
            )
            with os.fdopen(descriptor, "rb") as source:
                check_file(os.fstat(source.fileno()))
                value = _decode(source.read(MAX_MANIFEST + 1))
            if (
                set(value) != {"identity", "artifacts"}
                or RemoteRunIdentity.model_validate(value["identity"]) != identity
            ):
                _reject()
            records = TypeAdapter(list[ArtifactRecord]).validate_python(value["artifacts"])
            matching = [record for record in records if record.artifact_id == artifact_id]
            if len(records) > 256 or len(matching) != 1:
                _reject()
            record = matching[0]
            _path(record)
            if record.run_id != identity.run_id or record.sync_state != "ready":
                _reject()
            raw = cache.blob(record.sha256, record.size_bytes)
            _content(record, raw)
            return raw
        finally:
            cache.close()
