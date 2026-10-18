"""Durable, single-writer JSONL events; replay never starts a training process."""

import json
import os
import stat
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from easyai.domain.contracts import Event
from easyai.security.project_lock import ProjectLock
from easyai.security.remote_cache import LocalDirectory, LocalOwnerLock

MAX_LINE_BYTES = 64 * 1024


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JOURNAL_DUPLICATE_KEY")
        result[key] = value
    return result


def _encoded(event: Event) -> bytes:
    content = (
        json.dumps(
            event.model_dump(by_alias=True),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    if len(content) > MAX_LINE_BYTES:
        raise ValueError("JOURNAL_LINE_LIMIT")
    return content


class EventJournal:
    def __init__(
        self,
        path: Path,
        run_id: str,
        kind: Literal["runtime", "application"],
        *,
        directory: LocalDirectory | None = None,
    ):
        if not isinstance(run_id, str) or not run_id or kind not in ("runtime", "application"):
            raise ValueError("JOURNAL_IDENTITY_INVALID")
        if path.is_symlink():
            raise ValueError("JOURNAL_PATH_FORBIDDEN")
        if directory is not None and path.parent.absolute() != directory.path:
            raise ValueError("JOURNAL_DIRECTORY_IDENTITY_INVALID")
        self._directory = directory
        self.path = (
            path.absolute()
            if directory is not None
            else path.parent.resolve(strict=True) / path.name
        )
        self.run_id = run_id
        self.kind = kind
        self.recovery_info: dict[str, int] | None = None
        self._mutex = threading.Lock()
        self._events: list[Event] = []
        self._runtime: dict[int, Event] = {}
        self._failed = False
        self._fd: int | None = None
        self._lock: LocalOwnerLock = (
            directory.owner_lock(self.path.name + ".writer.lock")
            if directory is not None
            else ProjectLock(self.path.with_name(self.path.name + ".writer.lock"))
        )
        if self._lock.fd is None:
            self._lock.close()
            raise ValueError("JOURNAL_WRITER_HELD")
        try:
            if directory is not None:
                self._fd = directory.open_file(self.path.name, "update")
            else:
                self._fd = os.open(
                    self.path,
                    os.O_CREAT
                    | os.O_RDWR
                    | os.O_APPEND
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_BINARY", 0)
                    | getattr(os, "O_NONBLOCK", 0),
                    0o600,
                )
            os.set_inheritable(self._fd, False)
            if not stat.S_ISREG(os.fstat(self._fd).st_mode):
                raise ValueError("JOURNAL_PATH_FORBIDDEN")
            self._verify()
            self._recover()
            if directory is not None:
                directory.sync_file(self._fd)
                directory.sync()
        except BaseException:
            self.close()
            raise

    def _verify(self) -> int:
        if self._fd is None:
            raise ValueError("JOURNAL_CLOSED")
        if self._failed:
            raise ValueError("JOURNAL_WRITE_UNCERTAIN")
        self._lock.verify()
        if self._directory is not None:
            self._directory.verify_file(self.path.name, self._fd)
            return self._fd
        current, held = self.path.lstat(), os.fstat(self._fd)
        if not stat.S_ISREG(current.st_mode) or (current.st_dev, current.st_ino) != (
            held.st_dev,
            held.st_ino,
        ):
            raise ValueError("JOURNAL_PATH_REPLACED")
        return self._fd

    def _accept(self, event: Event) -> None:
        if event.run_id != self.run_id or event.seq != len(self._events) + 1:
            raise ValueError("JOURNAL_SEQUENCE_OR_RUN_INVALID")
        if self.kind == "runtime":
            if event.source != "runtime" or event.source_seq != event.seq:
                raise ValueError("JOURNAL_SOURCE_INVALID")
        elif event.source == "application":
            if event.source_seq is not None:
                raise ValueError("JOURNAL_SOURCE_INVALID")
        if event.source == "runtime":
            if event.source_seq != len(self._runtime) + 1:
                raise ValueError("JOURNAL_SOURCE_SEQUENCE_INVALID")
            self._runtime[event.source_seq] = event
        self._events.append(event)

    def _recover(self) -> None:
        fd = self._verify()
        # Bounded reads even for an overlong unfinished tail. Validate all complete
        # records before changing the file; a corrupt complete record is never repaired.
        complete = 0
        with os.fdopen(os.dup(fd), "rb") as stream:
            stream.seek(0)
            while True:
                raw = stream.readline(MAX_LINE_BYTES + 1)
                if not raw:
                    break
                length = len(raw)
                overlong = length > MAX_LINE_BYTES
                while not raw.endswith(b"\n") and len(raw) == MAX_LINE_BYTES + 1:
                    raw = stream.readline(MAX_LINE_BYTES + 1)
                    length += len(raw)
                    if not raw:
                        break
                if not raw.endswith(b"\n"):
                    self.recovery_info = {"discardedBytes": length, "completeBytes": complete}
                    break
                if overlong:
                    raise ValueError("JOURNAL_LINE_LIMIT")
                value = json.loads(raw, object_pairs_hook=_object)
                event = Event.model_validate(value)
                _encoded(event)  # Also reject non-finite arbitrary payload values.
                self._accept(event)
                complete += length
        if self.recovery_info is not None:
            os.ftruncate(fd, complete)
            self._sync(fd)

    def _sync(self, descriptor: int) -> None:
        if self._directory is not None:
            self._directory.sync_file(descriptor)
        else:
            os.fsync(descriptor)

    def _write(self, event: Event) -> Event:
        content = _encoded(event)
        fd = self._verify()
        try:
            if self._directory is not None:
                os.lseek(
                    fd, 0, os.SEEK_END
                )  # Permanent writer lock + journal mutex serialize appends.
            remaining = memoryview(content)
            while remaining:
                count = os.write(fd, remaining)
                if count <= 0:
                    raise OSError("Journal write made no progress")
                remaining = remaining[count:]
            self._sync(fd)
        except BaseException:
            self._failed = True
            raise
        self._accept(event)
        return event.model_copy(deep=True)

    def append(self, event_type: str, block_id: str | None, payload: dict[str, Any]) -> Event:
        with self._mutex:
            self._verify()
            seq = len(self._events) + 1
            event = Event.model_validate(
                {
                    "runId": self.run_id,
                    "seq": seq,
                    "source": self.kind,
                    "sourceSeq": seq if self.kind == "runtime" else None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": event_type,
                    "blockId": block_id,
                    "payload": payload,
                }
            ).model_copy(deep=True)
            return self._write(event)

    def ingest(self, runtime_event: Event) -> Event | None:
        with self._mutex:
            self._verify()
            if self.kind != "application":
                raise ValueError("JOURNAL_INGEST_REQUIRES_APPLICATION")
            incoming = Event.model_validate(runtime_event.model_dump()).model_copy(deep=True)
            if incoming.run_id != self.run_id or incoming.source != "runtime":
                raise ValueError("JOURNAL_SOURCE_OR_RUN_INVALID")
            source_seq = incoming.source_seq
            if source_seq is None:
                raise ValueError("JOURNAL_SOURCE_SEQUENCE_INVALID")
            previous = self._runtime.get(source_seq)
            if previous is not None:
                if previous.model_dump(exclude={"seq"}) != incoming.model_dump(exclude={"seq"}):
                    raise ValueError("JOURNAL_SOURCE_CONFLICT")
                return None
            if source_seq != len(self._runtime) + 1:
                raise ValueError("JOURNAL_SOURCE_SEQUENCE_INVALID")
            return self._write(incoming.model_copy(update={"seq": len(self._events) + 1}))

    def after(self, seq: int) -> list[Event]:
        with self._mutex:
            self._verify()
            if type(seq) is not int or seq < 0:
                raise ValueError("JOURNAL_CURSOR_INVALID")
            return [event.model_copy(deep=True) for event in self._events[seq:]]

    def close(self) -> None:
        with self._mutex:
            try:
                if self._fd is not None:
                    fd, self._fd = self._fd, None
                    os.close(fd)
            finally:
                self._lock.close()


def read_events(
    path: Path,
    run_id: str,
    kind: Literal["runtime", "application"] = "runtime",
    *,
    max_bytes: int | None = None,
    max_records: int | None = None,
) -> list[Event]:
    """Replay complete execution records without taking its writer or truncating a live tail."""
    descriptor = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NONBLOCK", 0),
    )
    records: list[Event] = []
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("JOURNAL_PATH_FORBIDDEN")
        if max_bytes is not None and info.st_size > max_bytes:
            raise ValueError("JOURNAL_READ_LIMIT")
        consumed = 0

        def bounded_line() -> bytes:
            nonlocal consumed
            raw = stream.readline(MAX_LINE_BYTES + 1)
            consumed += len(raw)
            if max_bytes is not None and consumed > max_bytes:
                raise ValueError("JOURNAL_READ_LIMIT")
            return raw

        while True:
            raw = bounded_line()
            if not raw:
                break
            overlong = len(raw) > MAX_LINE_BYTES
            while not raw.endswith(b"\n") and len(raw) == MAX_LINE_BYTES + 1:
                raw = bounded_line()
                if not raw:
                    break
            if not raw.endswith(b"\n"):
                break  # Only the execution owner may repair an unfinished tail.
            if overlong:
                raise ValueError("JOURNAL_LINE_LIMIT")
            event = Event.model_validate(json.loads(raw, object_pairs_hook=_object))
            _encoded(event)
            if (
                event.run_id != run_id
                or event.source != kind
                or event.seq != len(records) + 1
                or event.source_seq != (event.seq if kind == "runtime" else None)
            ):
                raise ValueError("JOURNAL_SEQUENCE_OR_RUN_INVALID")
            records.append(event)
            if max_records is not None and len(records) > max_records:
                raise ValueError("JOURNAL_READ_LIMIT")
    return records


def read_runtime_events(path: Path, run_id: str) -> list[Event]:
    return read_events(path, run_id)
