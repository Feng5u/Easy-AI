"""Durable SSH run coordination core. No network adapter, remote commands or credentials.

A future SFTP/portable-owner adapter must implement the bounded typed port below.
This module never infers remote exit from a disconnected/closed SSH connection.
"""

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
import time
from typing import TYPE_CHECKING, Any, BinaryIO, Literal, Protocol
from uuid import uuid4

from easyai.domain.connections import AuthenticatedConnection
from easyai.domain.contracts import Event
from easyai.domain.remote_run import (
    RemoteRunCheckpoint,
    RemoteRunIdentity,
    RemoteRunObservation,
    RemoteStream,
)
from easyai.security.remote_cache import check_file, open_directory, verify_directory
from easyai.security.project_lock import ProjectLock
from easyai.services.event_journal import EventJournal, MAX_LINE_BYTES

if TYPE_CHECKING:
    from easyai.services.remote_artifacts import ArtifactSnapshot

STREAMS = {
    "events": "remote-events.jsonl",
    "stdout": "remote-stdout.log",
    "stderr": "remote-stderr.log",
}
TERMINAL = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
CHUNK = 65536
MAX_BYTES = 128 * 1024 * 1024
StreamName = Literal["events", "stdout", "stderr"]


class RemoteProtocolError(ValueError):
    pass


class RemoteUnavailable(Exception):
    """Adapter timeout/disconnect, with no claim about the remote process."""


@dataclass(frozen=True)
class RemoteChunk:
    identity: RemoteRunIdentity
    stream: StreamName
    generation: str
    offset: int
    prefix_sha256: str
    data: bytes


class RemoteRunTransport(Protocol):
    """All calls must have adapter deadlines and cancellation/quiescence ownership.

    stage returns identity only after a complete verified atomic publish; never
    merges/overwrites an existing different run. start must remotely claim launchId
    atomically and detach a fixed owner. Missing owner is None, never a relaunch.
    read returns exactly the requested immutable prefix, including a SHA256 of all
    bytes preceding offset (not merely the latest chunk). cancel requests only the
    same owner, is idempotent, and its ACK does not imply exit. No PID kill proxy.
    A transport's close must stop I/O only; it MUST NOT cancel detached execution.
    No concrete SSH/SFTP implementation is supplied or claimed by this slice.
    """

    @property
    def quiescent(self) -> bool: ...

    def stage(self, identity: RemoteRunIdentity, *, timeout: float) -> RemoteRunIdentity: ...
    def start(self, identity: RemoteRunIdentity, *, timeout: float) -> RemoteRunIdentity: ...
    def inspect(
        self, identity: RemoteRunIdentity, *, timeout: float
    ) -> RemoteRunObservation | None: ...
    def read(
        self,
        identity: RemoteRunIdentity,
        stream: StreamName,
        offset: int,
        length: int,
        *,
        timeout: float,
    ) -> RemoteChunk: ...
    def cancel(self, identity: RemoteRunIdentity, *, timeout: float) -> RemoteRunIdentity: ...
    def close(self) -> None: ...


@dataclass
class _Binding:
    auth: AuthenticatedConnection
    transport: RemoteRunTransport
    guard: Callable[[], AuthenticatedConnection | None]


@dataclass
class _Retiring:
    transport: RemoteRunTransport
    started: bool = False
    done: bool = False
    succeeded: bool = False

    @property
    def ready(self) -> bool:
        return self.done and self.succeeded and self.transport.quiescent


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise RemoteProtocolError("REMOTE_DUPLICATE_KEY")
        result[key] = value
    return result


class SshRunCoordinator:
    """One durable active launch per target under an application-owned store root.

    Reopening cannot clear an uncertain start. New identity on an occupied target
    is rejected; archival/new-run policy is deliberately not implemented here.
    No public API/UI runner is enabled until a real guarded adapter exists.
    """

    def __init__(
        self,
        store_root: Path,
        identity: RemoteRunIdentity,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.identity = RemoteRunIdentity.model_validate(identity.model_dump())
        self._clock, self._deadline = clock, 0.0
        if store_root.is_symlink() or not store_root.is_dir():
            raise RemoteProtocolError("REMOTE_CACHE_PATH_INVALID")
        self.root = store_root.absolute() / identity.target_id
        parent = open_directory(store_root.absolute())
        try:
            try:
                os.mkdir(identity.target_id, 0o700, dir_fd=parent)
            except FileExistsError:
                pass
        finally:
            os.close(parent)
        self._fd = open_directory(self.root)
        self._lock: ProjectLock | None = None
        self._journal: EventJournal | None = None
        self._mutex = threading.RLock()
        self._busy = threading.Lock()
        self._binding: _Binding | None = None
        self._retiring: _Retiring | None = None
        self._closed = False
        try:
            self._lock = ProjectLock(self.root / ".owner.lock")
            if self._lock.fd is None:
                raise RemoteProtocolError("REMOTE_TARGET_BUSY")
            self._verify_store()
            path = self.root / "checkpoint.json"
            if path.exists() or path.is_symlink():
                self._checkpoint = RemoteRunCheckpoint.model_validate_json(
                    self._read_record("checkpoint.json")
                )
                if self._checkpoint.identity != self.identity:
                    raise RemoteProtocolError("REMOTE_TARGET_OWNER_CONFLICT")
            else:
                # Cache without its durable identity cannot be adopted as a new run.
                if any(
                    (self.root / name).exists() or (self.root / name).is_symlink()
                    for name in (*STREAMS.values(), "events.jsonl")
                ):
                    raise RemoteProtocolError("REMOTE_CACHE_IDENTITY_MISSING")
                self._checkpoint = RemoteRunCheckpoint(identity=self.identity)
            marker = self.root / "start-intent.json"
            if marker.exists() or marker.is_symlink():
                marker_identity = RemoteRunIdentity.model_validate_json(
                    self._read_record("start-intent.json")
                )
                if marker_identity != self.identity:
                    raise RemoteProtocolError("REMOTE_START_INTENT_CONFLICT")
                if self._checkpoint.start_outcome == "not_attempted":
                    # Crash after marker fsync and before checkpoint publication:
                    # inspect-only uncertainty, never permission to launch again.
                    self._checkpoint.start_outcome = "unknown"
                    self._checkpoint.execution_state = "STARTING"
            elif self._checkpoint.start_outcome != "not_attempted":
                raise RemoteProtocolError("REMOTE_START_INTENT_MISSING")
            self._verify_committed_cache()
            self._checkpoint.connection_state = "disconnected"
            self._journal = EventJournal(self.root / "events.jsonl", identity.run_id, "application")
            recovered = self._replay_events(
                sealed=self._checkpoint.execution_state in TERMINAL,
                limit=self._checkpoint.last_observation.streams.events.size_bytes
                if self._checkpoint.last_observation
                else 0,
            )
            if self._checkpoint.last_observation is not None:
                self._validate_exit(self._checkpoint.last_observation, recovered)
            for event in recovered:
                self._journal.ingest(event)
            self._persist()
        except BaseException:
            if self._journal is not None:
                self._journal.close()
            if self._lock is not None:
                self._lock.close()
            os.close(self._fd)
            raise

    def _verify_store(self) -> None:
        if self._closed:
            raise RemoteProtocolError("REMOTE_COORDINATOR_CLOSED")
        verify_directory(self.root, self._fd)
        current, held = self.root.lstat(), os.fstat(self._fd)
        if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (
            held.st_dev,
            held.st_ino,
        ):
            raise RemoteProtocolError("REMOTE_CACHE_REPLACED")
        if self._lock is not None:
            self._lock.verify()

    def _read_record(self, name: str) -> bytes:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self._fd)
        with os.fdopen(descriptor, "rb") as source:
            check_file(os.fstat(source.fileno()))
            raw = source.read(CHUNK + 1)
            if len(raw) > CHUNK:
                raise RemoteProtocolError("REMOTE_CACHE_RECORD_LIMIT")
            return raw

    def _start_marker(self) -> None:
        descriptor = os.open(
            "start-intent.json",
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
            0o600,
            dir_fd=self._fd,
        )
        with os.fdopen(descriptor, "wb") as output:
            output.write(self.identity.model_dump_json(by_alias=True).encode())
            output.flush()
            os.fsync(output.fileno())
        os.fsync(self._fd)

    def _verify_committed_cache(self) -> None:
        observed = self._checkpoint.last_observation
        if observed is None:
            return
        for stream, name in STREAMS.items():
            stamp = getattr(observed.streams, stream)
            with self._file(name) as source:
                digest, remaining = hashlib.sha256(), stamp.size_bytes
                while remaining:
                    raw = source.read(min(CHUNK, remaining))
                    if not raw:
                        raise RemoteProtocolError("REMOTE_CACHE_COMMITTED_TRUNCATED")
                    digest.update(raw)
                    remaining -= len(raw)
                if digest.hexdigest() != stamp.sha256:
                    raise RemoteProtocolError("REMOTE_CACHE_COMMITTED_HASH_INVALID")

    def _persist(self) -> None:
        self._verify_store()
        temporary = ".checkpoint-" + str(uuid4())
        descriptor = os.open(
            temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=self._fd
        )
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(self._checkpoint.model_dump_json(by_alias=True).encode())
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, "checkpoint.json", src_dir_fd=self._fd, dst_dir_fd=self._fd)
            os.fsync(self._fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=self._fd)
            except FileNotFoundError:
                pass

    def checkpoint(self) -> RemoteRunCheckpoint:
        with self._mutex:
            self._verify_store()
            return self._checkpoint.model_copy(deep=True)

    def _auth_matches(self, auth: AuthenticatedConnection) -> bool:
        scope = auth.scope
        return (
            auth.authenticated is True
            and auth.method == "password"
            and auth.project_id == self.identity.project_id
            and scope.project_id == self.identity.project_id
            and auth.username == self.identity.username
            and scope.endpoint == self.identity.endpoint
            and scope.host_fingerprint == self.identity.host_fingerprint
        )

    def attach(
        self,
        auth: AuthenticatedConnection,
        transport: RemoteRunTransport,
        guard: Callable[[], AuthenticatedConnection | None],
    ) -> None:
        # Explicit caller action after fresh authentication; no credential reuse.
        with self._mutex:
            self._verify_store()
            if self._retiring is not None:
                if not self._retiring.ready:
                    raise RemoteProtocolError("REMOTE_CLEANUP_UNCONFIRMED")
                self._retiring = None
            if self._binding is not None or self._busy.locked():
                raise RemoteProtocolError("REMOTE_IO_BUSY")
            if not self._auth_matches(auth):
                raise RemoteProtocolError("REMOTE_AUTH_IDENTITY_MISMATCH")
            current = guard()
            if (
                current is None
                or not self._auth_matches(current)
                or current.scope != auth.scope
                or current.request_id != auth.request_id
                or current.identity_request_id != auth.identity_request_id
            ):
                raise RemoteProtocolError("REMOTE_AUTH_EXPIRED")
            if self._checkpoint.last_connection_id == auth.scope.connection_id:
                raise RemoteProtocolError("REMOTE_REAUTH_REQUIRED")
            self._checkpoint.last_connection_id = auth.scope.connection_id
            self._persist()
            self._binding = _Binding(auth.model_copy(deep=True), transport, guard)

    def _retire(self, binding: _Binding) -> _Retiring:
        if self._retiring is None:
            self._retiring = _Retiring(binding.transport)
        elif self._retiring.transport is not binding.transport:
            raise RemoteProtocolError("REMOTE_RETIRING_OWNER_CONFLICT")
        return self._retiring

    def _close_retiring(self, retiring: _Retiring) -> None:
        with self._mutex:
            if retiring.started:
                return
            retiring.started = True
        try:
            retiring.transport.close()  # I/O close only; never execution cancellation.
        except Exception:
            pass
        else:
            retiring.succeeded = True
        finally:
            retiring.done = True

    def disconnect(self) -> None:
        retiring = None
        try:
            with self._mutex:
                binding, self._binding = self._binding, None
                if binding is not None:
                    retiring = self._retire(binding)
                self._checkpoint.connection_state = "disconnected"
                self._persist()
        finally:
            if retiring is not None:
                self._close_retiring(retiring)

    def _guard(self, binding: _Binding) -> None:
        with self._mutex:
            self._verify_store()
            if self._binding is not binding:
                raise RemoteUnavailable()
            current = binding.guard()
            if (
                current is None
                or not self._auth_matches(current)
                or current.scope != binding.auth.scope
                or current.request_id != binding.auth.request_id
                or current.identity_request_id != binding.auth.identity_request_id
            ):
                raise RemoteUnavailable()

    def _call(self, binding: _Binding, method: str, *args: Any) -> Any:
        self._guard(binding)
        if not binding.transport.quiescent:
            raise RemoteUnavailable()
        remaining = min(5.0, self._deadline - self._clock())
        if remaining <= 0:
            raise RemoteUnavailable()
        value = getattr(binding.transport, method)(self.identity, *args, timeout=remaining)
        self._guard(binding)
        if self._clock() >= self._deadline:
            raise RemoteUnavailable()
        if not binding.transport.quiescent:
            raise RemoteUnavailable()
        return value

    def _identity(self, value: RemoteRunIdentity) -> None:
        if not isinstance(value, RemoteRunIdentity) or value != self.identity:
            raise RemoteProtocolError("REMOTE_OWNER_MISMATCH")

    def _operation(self, callback: Callable[[_Binding], None]) -> RemoteRunCheckpoint:
        if not self._busy.acquire(blocking=False):
            raise RemoteProtocolError("REMOTE_IO_BUSY")
        failure: str | None = None
        self._deadline = self._clock() + 20
        try:
            with self._mutex:
                self._verify_store()
                binding = self._binding
            if binding is None:
                raise RemoteUnavailable()
            try:
                callback(binding)
            except Exception as error:
                # No SDK text/tracebacks enter caller-visible exceptions.
                protocol = isinstance(error, RemoteProtocolError)
                with self._mutex:
                    if self._binding is binding:
                        self._binding = None
                    retiring = self._retire(binding)
                try:
                    with self._mutex:
                        self._checkpoint.connection_state = "disconnected"
                        self._persist()
                finally:
                    self._close_retiring(retiring)
                failure = "REMOTE_PROTOCOL_INVALID" if protocol else "REMOTE_STATE_UNKNOWN"
            else:
                failure = None
        finally:
            self._busy.release()
        if failure is not None:
            raise RemoteProtocolError(failure) from None
        return self.checkpoint()

    def start(self) -> RemoteRunCheckpoint:
        def perform(binding: _Binding) -> None:
            with self._mutex:
                if self._checkpoint.cancel_state != "none":
                    raise RemoteProtocolError("REMOTE_CANCEL_PENDING")
                attempted = self._checkpoint.start_outcome != "not_attempted"
            if attempted:
                self._poll(binding)  # Even NOT_FOUND never clears the intent or calls start.
                return
            with self._mutex:
                self._checkpoint.execution_state = "STAGING"
                self._persist()
            self._identity(self._call(binding, "stage"))
            with self._mutex:
                self._guard(binding)
                if self._checkpoint.cancel_state != "none":
                    raise RemoteProtocolError("REMOTE_CANCEL_PENDING")
                self._start_marker()
                self._checkpoint.start_outcome = "unknown"
                self._checkpoint.execution_state = "STARTING"
                self._persist()  # fsync BEFORE any possibly consuming start call.
            self._identity(self._call(binding, "start"))
            self._poll(binding)

        return self._operation(perform)

    def request_cancel(self) -> RemoteRunCheckpoint:
        with self._mutex:
            self._verify_store()
            if self._checkpoint.execution_state not in TERMINAL:
                self._checkpoint.cancel_state = "pending"
                self._persist()  # This ACK means only a durable local intent.
            return self._checkpoint.model_copy(deep=True)

    def poll(self) -> RemoteRunCheckpoint:
        return self._operation(self._poll)

    def _poll(self, binding: _Binding) -> None:
        observed = self._call(binding, "inspect")
        if observed is None:
            raise RemoteUnavailable()
        if not isinstance(observed, RemoteRunObservation):
            raise RemoteProtocolError("REMOTE_OBSERVATION_INVALID")
        observed = RemoteRunObservation.model_validate(observed.model_dump())
        self._identity(observed.identity)
        previous = self._checkpoint.last_observation
        if previous is not None:
            if observed.heartbeat < previous.heartbeat or (
                observed.heartbeat == previous.heartbeat and observed != previous
            ):
                raise RemoteProtocolError("REMOTE_HEARTBEAT_ROLLBACK")
            if previous.sealed and observed != previous:
                raise RemoteProtocolError("REMOTE_TERMINAL_CHANGED")
            for stream in STREAMS:
                before, after = getattr(previous.streams, stream), getattr(observed.streams, stream)
                if before.generation != after.generation or after.size_bytes < before.size_bytes:
                    raise RemoteProtocolError("REMOTE_STREAM_REPLACED")
        for name in STREAMS:
            self._sync_stream(binding, name, getattr(observed.streams, name))
        events = self._replay_events(sealed=observed.sealed)
        self._validate_exit(observed, events)
        assert self._journal is not None
        with self._mutex:
            self._guard(binding)
            for event in events:
                self._journal.ingest(event)  # fsync before checkpoint commit; replay deduplicates.
        with self._mutex:
            self._guard(binding)
            self._checkpoint.start_outcome = "acknowledged"
            self._checkpoint.execution_state = observed.state
            self._checkpoint.last_observation = observed.model_copy(deep=True)
            self._checkpoint.connection_state = "connected"
            if observed.sealed and self._checkpoint.cancel_state != "none":
                self._checkpoint.cancel_state = (
                    "resolved"  # Terminal execution evidence wins the race.
                )
            self._persist()
            cancel = self._checkpoint.cancel_state != "none" and not observed.sealed
        if cancel:
            self._identity(self._call(binding, "cancel"))
            with self._mutex:
                self._guard(binding)
                self._checkpoint.cancel_state = "acknowledged"
                self._persist()  # ACK alone is not CANCELLED. Future polls retry same owner.

    def _file(self, name: str) -> BinaryIO:
        descriptor = os.open(
            name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=self._fd
        )
        try:
            check_file(os.fstat(descriptor))
        except Exception:
            os.close(descriptor)
            raise
        return os.fdopen(descriptor, "r+b")

    def _sync_stream(self, binding: _Binding, stream: str, stamp: RemoteStream) -> None:
        self._guard(binding)
        with self._file(STREAMS[stream]) as output:
            output.seek(0, os.SEEK_END)
            offset = output.tell()
            if offset > stamp.size_bytes or stamp.size_bytes > MAX_BYTES:
                raise RemoteProtocolError("REMOTE_STREAM_TRUNCATED")
            original_size = offset
            try:
                digest = hashlib.sha256()
                output.seek(0)
                while chunk := output.read(CHUNK):
                    digest.update(chunk)
                while offset < stamp.size_bytes:
                    length = min(CHUNK, stamp.size_bytes - offset)
                    chunk = self._call(binding, "read", stream, offset, length)
                    if (
                        not isinstance(chunk, RemoteChunk)
                        or chunk.identity != self.identity
                        or chunk.stream != stream
                        or chunk.generation != stamp.generation
                        or type(chunk.offset) is not int
                        or chunk.offset != offset
                        or chunk.prefix_sha256 != digest.hexdigest()
                        or type(chunk.data) is not bytes
                        or len(chunk.data) != length
                    ):
                        raise RemoteProtocolError("REMOTE_CHUNK_INVALID")
                    # Validate current lease again before accepting any late bytes.
                    with self._mutex:
                        self._guard(binding)
                        output.seek(offset)
                        output.write(chunk.data)
                        output.flush()
                        os.fsync(output.fileno())
                        digest.update(chunk.data)
                        offset += len(chunk.data)
                if digest.hexdigest() != stamp.sha256:
                    raise RemoteProtocolError("REMOTE_STREAM_HASH_MISMATCH")
            except BaseException:
                output.truncate(original_size)
                output.flush()
                os.fsync(output.fileno())
                raise

    def _replay_events(self, *, sealed: bool, limit: int | None = None) -> list[Event]:
        assert self._journal is not None
        events: list[Event] = []
        with self._file(STREAMS["events"]) as source:
            while limit is None or source.tell() < limit:
                raw = source.readline(
                    min(MAX_LINE_BYTES + 1, limit - source.tell())
                    if limit is not None
                    else MAX_LINE_BYTES + 1
                )
                if not raw:
                    break
                if len(raw) > MAX_LINE_BYTES:
                    raise RemoteProtocolError("REMOTE_EVENT_LIMIT")
                if not raw.endswith(b"\n"):
                    if sealed:
                        raise RemoteProtocolError("REMOTE_SEALED_PARTIAL_EVENT")
                    break  # Keep exact bytes, including a partial UTF8 character, for next poll.
                try:
                    value = Event.model_validate(
                        json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
                    )
                except Exception:
                    raise RemoteProtocolError("REMOTE_EVENT_INVALID") from None
                if (
                    value.run_id != self.identity.run_id
                    or value.source != "runtime"
                    or value.seq != len(events) + 1
                    or value.source_seq != value.seq
                    or value.type == "status_changed"
                ):
                    raise RemoteProtocolError("REMOTE_EVENT_SOURCE_INVALID")
                if events and events[-1].type == "process_exited":
                    raise RemoteProtocolError("REMOTE_EVENT_AFTER_EXIT")
                events.append(value)
        return events

    def _validate_exit(self, observed: RemoteRunObservation, events: list[Event]) -> None:
        exited = [event for event in events if event.type == "process_exited"]
        spawn_failed = [event for event in events if event.type == "process_spawn_failed"]
        if observed.spawn_failed:
            if (
                len(events) != 1
                or len(spawn_failed) != 1
                or exited
                or spawn_failed[0].payload != {"code": "PROCESS_SPAWN_FAILED", "spawnFailed": True}
            ):
                raise RemoteProtocolError("REMOTE_SPAWN_EVIDENCE_INVALID")
            return
        if spawn_failed:
            raise RemoteProtocolError("REMOTE_SPAWN_EVIDENCE_INVALID")
        if not observed.sealed:
            if exited:
                raise RemoteProtocolError("REMOTE_EXIT_NOT_SEALED")
            return
        if (
            len(exited) != 1
            or not events
            or exited[0] != events[-1]
            or type(exited[0].payload.get("exitCode")) is not int
            or exited[0].payload["exitCode"] != observed.exit_code
        ):
            raise RemoteProtocolError("REMOTE_EXIT_EVIDENCE_INVALID")
        kinds = [event.type for event in events]
        if observed.state == "COMPLETED" and (
            observed.exit_code != 0
            or kinds.count("pipeline_completed") != 1
            or "pipeline_cancelled" in kinds
            or "runtime_error" in kinds
        ):
            raise RemoteProtocolError("REMOTE_COMPLETION_EVIDENCE_INVALID")
        if (
            observed.state == "CANCELLED"
            and "pipeline_completed" in kinds
            and observed.exit_code == 0
        ):
            raise RemoteProtocolError("REMOTE_CANCELLATION_RACE_INVALID")

    def events(self) -> list[Event]:
        with self._mutex:
            self._verify_store()
            assert self._journal is not None
            return self._journal.after(0)

    def artifact_snapshot(self, bundle_manifest: bytes, source_map: bytes) -> "ArtifactSnapshot":
        """Bind downloads to this coordinator's committed sealed evidence and frozen bundle."""
        from easyai.services.remote_artifacts import ArtifactSnapshot

        with self._mutex:
            self._verify_store()
            self._verify_committed_cache()
            assert self._journal is not None
            return ArtifactSnapshot.verified(
                self._checkpoint.model_copy(deep=True),
                self._journal.after(0),
                bundle_manifest,
                source_map,
            )

    def log_bytes(
        self, stream: Literal["stdout", "stderr"], offset: int, limit: int = CHUNK
    ) -> bytes:
        if (
            stream not in ("stdout", "stderr")
            or type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= CHUNK
        ):
            raise RemoteProtocolError("REMOTE_LOG_CURSOR_INVALID")
        with self._mutex:
            self._verify_store()
            observed = self._checkpoint.last_observation
            committed = getattr(observed.streams, stream).size_bytes if observed else 0
            if offset >= committed:
                return b""
            with self._file(STREAMS[stream]) as source:
                source.seek(offset)
                return source.read(min(limit, committed - offset))

    def close(self) -> None:
        if self._closed:
            return
        if not self._busy.acquire(blocking=False):
            raise RemoteProtocolError("REMOTE_IO_BUSY")
        try:
            self.disconnect()
            with self._mutex:
                if self._retiring is not None and not self._retiring.ready:
                    raise RemoteProtocolError("REMOTE_CLEANUP_UNCONFIRMED")
                if self._journal is not None:
                    self._journal.close()
                if self._lock is not None:
                    self._lock.close()
                os.close(self._fd)
                self._closed = True
        finally:
            self._busy.release()
