"""Snapshot-bound SFTP downloads. No remote writes, commands, deserialization or public path API.

SFTP v3 cannot express O_NOFOLLOW. Protected owner directories, lstat/handle
checks and hashes constrain reads; a malicious same-UID concurrent replacement
is outside this protocol's guarantees. This is not a run-success gate.
"""

from dataclasses import dataclass
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
from pydantic import TypeAdapter, ValidationError

from easyai.domain.contracts import (
    ArtifactRecord,
    ArtifactSyncFailure,
    ArtifactSyncStage,
    Event,
    SourceSpan,
)
from easyai.domain.remote_run import (
    ArtifactManifest,
    RemoteRunCheckpoint,
    RemoteRunIdentity,
    RemoteRunObservation,
)
from easyai.security.remote_cache import LocalWriterLock, local_directory
from easyai.services.run_views import validate_png
from easyai.services.ssh_client import VerifiedSshSession

CHUNK = 65536
MAX_MANIFEST = 65536
MAX_FILE = 100 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024


class ArtifactFailure(ValueError):
    def __init__(
        self,
        message: str,
        *,
        failure: ArtifactSyncFailure | None = None,
        cleanup_failure: ArtifactSyncFailure | None = None,
    ):
        super().__init__(message)
        self.failure, self.cleanup_failure = failure, cleanup_failure


class ArtifactEvidenceFailure(ArtifactFailure):
    pass


def sync_failure(error: Exception, stage: ArtifactSyncStage) -> ArtifactSyncFailure:
    """Only owned typed details survive. Never inspect/serialize SDK exception text."""
    if isinstance(error, ArtifactFailure) and error.failure is not None:
        return error.failure.model_copy(deep=True)
    if isinstance(
        error, (ArtifactEvidenceFailure, ValidationError, UnicodeError, json.JSONDecodeError)
    ):
        return ArtifactSyncFailure(stage=stage, code="SYNC_INVALID_EVIDENCE")
    if isinstance(error, OSError):
        return ArtifactSyncFailure(stage=stage, code="SYNC_IO_FAILED")
    return ArtifactSyncFailure(stage=stage, code="SYNC_UNKNOWN")


def _reject(stage: ArtifactSyncStage | None = None) -> None:
    raise ArtifactEvidenceFailure(
        "REMOTE_ARTIFACT_INVALID",
        failure=ArtifactSyncFailure(stage=stage, code="SYNC_INVALID_EVIDENCE") if stage else None,
    )


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
        receipt_prefix_sha256: str | None = None,
    ) -> "ArtifactSnapshot":
        observation = checkpoint.last_observation
        if observation is None or (not observation.sealed and observation.artifact_receipt is None):
            _reject()
        assert observation is not None
        receipt = observation.artifact_receipt
        if receipt is not None and receipt.events_sha256 != receipt_prefix_sha256:
            _reject("event_prefix")
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
        if receipt is not None and (
            receipt.source_seq > len(runtime)
            or any(event.type == "artifact_created" for event in runtime[receipt.source_seq :])
            or (observation.sealed and receipt.source_seq != len(runtime))
        ):
            _reject()
        if not runtime or len(records) > 256 or total > MAX_TOTAL:
            _reject()
        return cls(observation.model_copy(deep=True), len(runtime), tuple(records))

    def manifest(self, raw: bytes) -> ArtifactManifest:
        value = ArtifactManifest.model_validate(_decode(raw))
        receipt = self.observation.artifact_receipt
        if receipt is not None and hashlib.sha256(raw).hexdigest() != receipt.sha256:
            _reject("receipt_digest")
        if (
            value.identity != self.observation.identity
            or value.source_seq != (receipt.source_seq if receipt else self.source_seq)
            or value.events_sha256
            != (receipt.events_sha256 if receipt else self.observation.streams.events.sha256)
            or value.artifacts != list(self.records)
        ):
            _reject("receipt_records")
        return value


class _Reader:
    """Private fixed-record / validated-ID reader; no caller supplied remote path."""

    def __init__(self, sftp: Any, identity: RemoteRunIdentity | str, guard: Callable[[], None]):
        self.sftp, self.guard = sftp, guard
        self.root = identity if isinstance(identity, str) else identity.run_root
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
        root = PurePosixPath(self.root)
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
        with self.sftp.open(str(PurePosixPath(self.root) / name), "rb", bufsize=0) as source:
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
        self.path, self.directory = path, local_directory(path)
        self.lock: LocalWriterLock | None = None
        try:
            self.lock = self.directory.writer_lock(".artifact-writer.lock")
        except BaseException:
            self.close()
            raise

    def verify(self) -> None:
        self.directory.verify()
        assert self.lock is not None
        self.lock.verify()

    def bind(self, identity: RemoteRunIdentity, *, create: bool = True) -> None:
        raw = _encoded(identity.model_dump(mode="json", by_alias=True))
        name, descriptor = self.temporary()
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(raw)
                output.flush()
                self.directory.sync_file(output.fileno())
            try:
                if not create:
                    raise FileExistsError()
                self.directory.publish(name, ".artifact-identity.json")
            except FileExistsError:
                pass
            descriptor = self.directory.open_file(".artifact-identity.json")
            with os.fdopen(descriptor, "rb") as source:
                current = RemoteRunIdentity.model_validate(_decode(source.read(MAX_MANIFEST + 1)))
            if current != identity:
                _reject()
            try:
                existing = self.directory.open_file("artifact-index.json")
            except FileNotFoundError:
                return
            with os.fdopen(existing, "rb") as source:
                value = _decode(source.read(MAX_MANIFEST + 1))
            if RemoteRunIdentity.model_validate(value["identity"]) != identity:
                _reject()
        finally:
            self.directory.remove(name)

    def temporary(self) -> tuple[str, int]:
        self.verify()
        name = ".artifact-part-" + str(uuid4())
        return name, self.directory.open_file(name, "exclusive")

    def blob(self, digest: str, size: int) -> bytes:
        self.verify()
        descriptor = self.directory.open_file("blob-" + digest)
        with os.fdopen(descriptor, "rb") as source:
            info = os.fstat(source.fileno())
            if info.st_size != size or size > MAX_FILE:
                _reject()
            raw = source.read(size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            _reject()
        return raw

    def close(self) -> None:
        if self.lock is not None:
            self.lock.close()
            self.lock = None
        self.directory.close()


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
        sftp_factory: Callable[[Any], Any] | None = None,
    ):
        self.session, self.identity = session, identity
        self.mutex, self.guard, self.factory = mutex, guard, sftp_factory or paramiko.SFTPClient
        self._worker: threading.Thread | None = None
        self._retained = False

    @property
    def quiescent(self) -> bool:
        return self._worker is None or (not self._worker.is_alive() and not self._retained)

    def sync(
        self,
        snapshot: ArtifactSnapshot,
        cache_path: Path,
        cancel: threading.Event,
        *,
        seconds: float = 20,
        progress: Callable[[int, int, int], None] | None = None,
    ) -> list[ArtifactRecord]:
        if snapshot.observation.identity != self.identity or not 0 < seconds <= 20:
            _reject()
        if not self.session.io_lock.acquire(blocking=False):
            raise ArtifactFailure(
                "REMOTE_ARTIFACT_BUSY", failure=ArtifactSyncFailure(stage="scope", code="SYNC_BUSY")
            )
        done, abandoned = threading.Event(), threading.Event()
        values: list[list[ArtifactRecord]] = []
        failed = threading.Event()
        deadline = time.monotonic() + seconds
        channels: list[Any] = []
        selected = tuple(
            record
            for record in snapshot.records
            if snapshot.observation.sealed or record.kind != "model"
        )
        total_bytes = sum(record.size_bytes for record in selected)
        received_bytes = verified_bytes = 0
        phase: ArtifactSyncStage = "scope"
        failures: list[ArtifactSyncFailure] = []
        cleanup_failures: list[ArtifactSyncFailure] = []
        cleanup_phase: ArtifactSyncStage | None = None
        watcher_closing = threading.Event()

        def close_owned(resource: Any, stage: ArtifactSyncStage) -> None:
            nonlocal cleanup_phase
            with self.mutex:
                cleanup_phase = stage
            try:
                resource.close()
            finally:
                with self.mutex:
                    cleanup_phase = None

        def report() -> None:
            check()
            if progress is not None:
                progress(received_bytes, verified_bytes, total_bytes)

        def check() -> None:
            with self.mutex:
                if abandoned.is_set() or cancel.is_set() or time.monotonic() >= deadline:
                    raise ArtifactFailure(
                        "REMOTE_ARTIFACT_CANCELLED",
                        failure=ArtifactSyncFailure(
                            stage=phase,
                            code="SYNC_DEADLINE"
                            if time.monotonic() >= deadline and not cancel.is_set()
                            else "SYNC_CANCELLED",
                        ),
                    )
                if (
                    self.session.endpoint != self.identity.endpoint
                    or self.session.host_fingerprint != self.identity.host_fingerprint
                ):
                    _reject()
                try:
                    self.guard()
                except Exception:
                    raise ArtifactFailure(
                        "REMOTE_ARTIFACT_AUTH_STALE",
                        failure=ArtifactSyncFailure(stage="scope", code="SYNC_AUTH_STALE"),
                    ) from None

        interrupted, finished = threading.Event(), threading.Event()

        def interrupt() -> None:
            while not finished.wait(0.01):
                if abandoned.is_set() or cancel.is_set() or time.monotonic() >= deadline:
                    for owned_channel in channels:
                        watcher_closing.set()
                        try:
                            owned_channel.close()
                        except Exception:
                            interrupted.set()  # No SDK text from background threads.
                        finally:
                            watcher_closing.clear()
                    return

        watcher = threading.Thread(target=interrupt, name="easyai-artifact-interrupt", daemon=True)

        def worker() -> None:
            nonlocal received_bytes, verified_bytes, phase, cleanup_phase
            channel, sftp, cache = None, None, None
            try:
                check()
                channel = self.session.open_probe_channel(timeout=min(2, seconds))
                channels.append(channel)
                channel.settimeout(min(2, seconds))
                check()
                channel.invoke_subsystem("sftp")
                sftp = self.factory(channel)
                check()
                phase = "receipt_read"
                reader = _Reader(sftp, self.identity, check)
                receipt = snapshot.observation.artifact_receipt
                if receipt is None:
                    # Legacy sealed protocol has a stable status/manifest pair.
                    status = RemoteRunObservation.model_validate(
                        _decode(reader.record("owner-status.json"))
                    )
                    if status != snapshot.observation:
                        _reject()
                # New receipts are immutable and already bound to the committed
                # coordinator observation. Re-reading a mutable heartbeat here
                # would race every live snapshot and add no artifact authority.
                manifest_name = (
                    "remote-artifacts-" + receipt.sha256 + ".json"
                    if receipt
                    else "remote-artifacts.json"
                )
                manifest_raw = reader.record(manifest_name)
                phase = "receipt_records"
                manifest = snapshot.manifest(manifest_raw)
                reader.uid = manifest.uid
                # Recheck bootstrap records now that UID is bound to the owner receipt.
                if receipt is None:
                    reader._parents("owner-status.json")
                reader._parents(manifest_name)
                phase = "cache_open"
                cache = _Cache(cache_path)
                cache.bind(self.identity)
                # A stale snapshot must never replace a newer committed index.
                try:
                    descriptor = cache.directory.open_file("artifact-index.json")
                except FileNotFoundError:
                    pass
                else:
                    with os.fdopen(descriptor, "rb") as source:
                        prior = _decode(source.read(MAX_MANIFEST + 1))
                    prior_records = TypeAdapter(list[ArtifactRecord]).validate_python(
                        prior["artifacts"]
                    )
                    expected = {item.artifact_id: item for item in selected}
                    if (
                        type(prior.get("sourceSeq", 0)) is not int
                        or prior.get("sourceSeq", 0) > snapshot.source_seq
                    ):
                        _reject()
                    if len(prior_records) > 256 or len(
                        {item.artifact_id for item in prior_records}
                    ) != len(prior_records):
                        _reject()
                    for item in prior_records:
                        if (
                            item.artifact_id not in expected
                            or item.model_copy(
                                update={"sync_state": expected[item.artifact_id].sync_state}
                            )
                            != expected[item.artifact_id]
                        ):
                            _reject()
                report()
                ready = []
                for record in selected:
                    phase = "artifact_verify"
                    check()
                    try:
                        _content(record, cache.blob(record.sha256, record.size_bytes))
                    except FileNotFoundError:
                        pass
                    else:
                        verified_bytes += record.size_bytes
                        report()
                        ready.append(record.model_copy(update={"sync_state": "ready"}, deep=True))
                        continue
                    name, descriptor = cache.temporary()
                    try:
                        with os.fdopen(descriptor, "w+b") as target:

                            def consume(raw: bytes) -> None:
                                nonlocal received_bytes
                                target.write(raw)
                                received_bytes += len(raw)
                                report()

                            phase = "artifact_read"
                            reader.read(record.relative_path, record.size_bytes, consume)
                            phase = "artifact_verify"
                            target.flush()
                            target.seek(0)
                            _content(record, target.read(record.size_bytes + 1))
                            cache.directory.sync_file(target.fileno())
                        with self.mutex:
                            check()
                            cache.verify()
                            try:
                                cache.directory.publish(name, "blob-" + record.sha256)
                            except FileExistsError:
                                _content(record, cache.blob(record.sha256, record.size_bytes))
                            cache.directory.sync()
                        verified_bytes += record.size_bytes
                        report()
                        ready.append(record.model_copy(update={"sync_state": "ready"}, deep=True))
                    finally:
                        # Only the random temporary created by this worker is removable.
                        cache.directory.remove(name)
                # Cleanup the dedicated remote channel before publishing readiness.
                # A failed SDK close leaves only verified unindexed blobs behind.
                phase = "channel_cleanup"
                close_owned(sftp, "channel_cleanup")
                sftp = None
                close_owned(channel, "channel_cleanup")
                channel = None
                phase = "cache_commit"
                with self.mutex:
                    check()
                    cache.verify()
                    for record in ready:
                        _content(record, cache.blob(record.sha256, record.size_bytes))
                    index = _encoded(
                        {
                            "identity": self.identity.model_dump(mode="json", by_alias=True),
                            "sourceSeq": snapshot.source_seq,
                            "artifacts": [
                                record.model_dump(mode="json", by_alias=True) for record in ready
                            ],
                        }
                    )
                    if len(index) > MAX_MANIFEST:
                        _reject()
                    name, descriptor = cache.temporary()
                    try:
                        with os.fdopen(descriptor, "wb") as manifest_target:
                            manifest_target.write(index)
                            manifest_target.flush()
                            cache.directory.sync_file(manifest_target.fileno())
                        check()
                        cache.directory.publish(name, "artifact-index.json", replace=True)
                        values.append(ready)
                    finally:
                        cache.directory.remove(name, missing_ok=True)
            except Exception as error:
                with self.mutex:
                    failures.append(sync_failure(error, phase))
                    failed.set()
            finally:
                cleanup_failed = False
                resources: tuple[tuple[Any, ArtifactSyncStage], ...] = (
                    (sftp, "channel_cleanup"),
                    (channel, "channel_cleanup"),
                    (cache, "cache_cleanup"),
                )
                for resource, cleanup_stage in resources:
                    if resource is not None:
                        try:
                            close_owned(resource, cleanup_stage)
                        except Exception:
                            failed.set()
                            cleanup_failed = True
                            cleanup_failures.append(
                                ArtifactSyncFailure.model_validate(
                                    {"stage": cleanup_stage, "code": "SYNC_IO_FAILED"}
                                )
                            )
                finished.set()
                with self.mutex:
                    cleanup_phase = "watcher_cleanup"
                watcher.join()  # Keep the physical gate until the interrupt owner also exits.
                with self.mutex:
                    cleanup_phase = None
                cleanup_failed = cleanup_failed or interrupted.is_set()
                if interrupted.is_set():
                    cleanup_failures.append(
                        ArtifactSyncFailure(stage="watcher_cleanup", code="SYNC_IO_FAILED")
                    )
                quiet = all(getattr(item, "closed", False) is True for item in channels)
                if cleanup_failed or not quiet:
                    failed.set()
                    try:
                        close_owned(self.session, "channel_cleanup")
                    except Exception:
                        quiet = False
                    if not quiet:
                        quiet = bool(getattr(self.session, "closed_quiescent", False))
                self._retained = not quiet
                if not quiet and not cleanup_failures:
                    cleanup_failures.append(
                        ArtifactSyncFailure(
                            stage="channel_cleanup", code="SYNC_CLEANUP_UNCONFIRMED"
                        )
                    )
                if quiet:
                    self.session.io_lock.release()
                done.set()

        thread = threading.Thread(target=worker, name="easyai-artifact-sftp", daemon=True)
        self._worker = thread
        try:
            watcher.start()
            thread.start()
        except BaseException:
            finished.set()
            if watcher.ident is not None:
                watcher.join()
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
                with self.mutex:
                    # An elapsed wait budget does not replace a failure already
                    # observed by the owned worker. Cleanup remains unconfirmed.
                    primary = (
                        failures[0]
                        if failures
                        else cleanup_failures[0]
                        if cleanup_failures
                        else ArtifactSyncFailure(
                            stage=phase,
                            code="SYNC_DEADLINE"
                            if time.monotonic() >= deadline and not cancel.is_set()
                            else "SYNC_CANCELLED",
                        )
                    )
                    pending_stage = cleanup_phase or (
                        "watcher_cleanup" if watcher_closing.is_set() else "unknown"
                    )
                    cleanup_detail = ArtifactSyncFailure(
                        stage=pending_stage, code="SYNC_CLEANUP_UNCONFIRMED"
                    )
                raise ArtifactFailure(
                    "REMOTE_ARTIFACT_CLEANUP_UNCONFIRMED",
                    failure=primary.model_copy(deep=True),
                    cleanup_failure=cleanup_detail,
                )
        with self.mutex:
            if failed.is_set() or not values:
                raise ArtifactFailure(
                    "REMOTE_ARTIFACT_FAILED",
                    failure=failures[0]
                    if failures
                    else (
                        cleanup_failures[0]
                        if cleanup_failures
                        else ArtifactSyncFailure(stage=phase, code="SYNC_UNKNOWN")
                    ),
                    cleanup_failure=cleanup_failures[0] if cleanup_failures else None,
                )
            return values[0]

    @staticmethod
    def read_ready(
        cache_path: Path,
        identity: RemoteRunIdentity,
        artifact_id: str,
        expected: ArtifactRecord | None = None,
    ) -> bytes:
        """Opaque ID lookup; revalidate every blob rather than trusting a ready index."""
        cache = _Cache(cache_path)
        try:
            cache.bind(identity, create=False)
            descriptor = cache.directory.open_file("artifact-index.json")
            with os.fdopen(descriptor, "rb") as source:
                value = _decode(source.read(MAX_MANIFEST + 1))
            if (
                set(value)
                not in ({"identity", "artifacts"}, {"identity", "sourceSeq", "artifacts"})
                or RemoteRunIdentity.model_validate(value["identity"]) != identity
            ):
                _reject()
            records = TypeAdapter(list[ArtifactRecord]).validate_python(value["artifacts"])
            matching = [record for record in records if record.artifact_id == artifact_id]
            if len(records) > 256 or len(matching) != 1:
                _reject()
            record = matching[0]
            if (
                expected is not None
                and record.model_copy(update={"sync_state": expected.sync_state}) != expected
            ):
                _reject()
            _path(record)
            if record.run_id != identity.run_id or record.sync_state != "ready":
                _reject()
            raw = cache.blob(record.sha256, record.size_bytes)
            _content(record, raw)
            return raw
        finally:
            cache.close()
