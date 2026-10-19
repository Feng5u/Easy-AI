"""Private NTFS host-key transactions; public bytes only, no network or ACL repair."""

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterator, Any
from uuid import uuid4

from easyai.security.windows_store import WindowsDirectory

MAX_STORE_BYTES = 1024 * 1024
# A failed native close has an uncertain ownership outcome. Preserve the owner
# and its original handles/fd; never retry a recycled numeric handle blindly.
# Process restart is the recovery boundary, not an automatic lock-file repair.
_FAILED_CLEANUP: list[tuple[Any, tuple[Any, ...], Any]] = []


def _require_cleanup_confirmed() -> None:
    if _FAILED_CLEANUP:
        raise ValueError("SSH_TRUST_CLEANUP_UNCONFIRMED")


def _close_owners(*owners: Any) -> None:
    failed = False
    for owner in owners:
        if owner is None:
            continue
        state = (owner, tuple(getattr(owner, "_chain", ())), getattr(owner, "fd", None))
        try:
            owner.close()
        except BaseException:
            _FAILED_CLEANUP.append(state)
            failed = True
    if failed:
        raise ValueError("SSH_TRUST_CLEANUP_UNCONFIRMED") from None


class WindowsTrustTransaction:
    def __init__(self, directory: WindowsDirectory):
        self.directory = directory

    def read(self) -> bytes:
        _require_cleanup_confirmed()
        self.directory.verify()
        try:
            descriptor = self.directory.open_file("known_hosts")
        except FileNotFoundError:
            self.directory.verify()
            return b""
        with os.fdopen(descriptor, "rb") as stream:
            self.directory.verify_file("known_hosts", stream.fileno())
            if os.fstat(stream.fileno()).st_size > MAX_STORE_BYTES:
                raise ValueError("SSH_TRUST_STORE_LIMIT")
            raw = stream.read(MAX_STORE_BYTES + 1)
            if len(raw) > MAX_STORE_BYTES:
                raise ValueError("SSH_TRUST_STORE_LIMIT")
            self.directory.verify_file("known_hosts", stream.fileno())
        self.directory.verify()
        return raw

    def write(self, payload: bytes) -> None:
        _require_cleanup_confirmed()
        if len(payload) > MAX_STORE_BYTES:
            raise ValueError("SSH_TRUST_STORE_LIMIT")
        temporary = ".known-hosts-" + str(uuid4()) + ".tmp"
        try:
            with os.fdopen(self.directory.open_file(temporary, "exclusive"), "wb") as stream:
                if stream.write(payload) != len(payload):
                    raise OSError("SSH_TRUST_WRITE_INCOMPLETE")
                stream.flush()
                self.directory.sync_file(stream.fileno())
                self.directory.verify_file(temporary, stream.fileno())
            self.directory.verify()
            # Only the common explicit-confirmation policy supplies these bytes.
            # Replace the complete catalog atomically, never an individual key silently.
            self.directory.publish(temporary, "known_hosts", replace=True)
        finally:
            self.directory.remove(temporary, missing_ok=True)


class WindowsTrustStore:
    def __init__(self, root: Path):
        _require_cleanup_confirmed()
        self.root = root
        # Application state parent must already exist and be private. Do not
        # create/repair arbitrary ancestors or fall back to path-based mkdir.
        parent = WindowsDirectory(root.parent)
        directory = None
        try:
            directory = parent.child(root.name, create=True)
            assert isinstance(directory, WindowsDirectory)
            self.identity = directory.identity()
        finally:
            _close_owners(directory, parent)
        _require_cleanup_confirmed()

    @contextmanager
    def transaction(self, *, exclusive: bool = False) -> Iterator[WindowsTrustTransaction]:
        _require_cleanup_confirmed()
        directory = WindowsDirectory(self.root)
        lock = None
        try:
            if directory.identity() != self.identity:
                raise ValueError("SSH_TRUST_PATH_INVALID")
            if exclusive:
                try:
                    lock = directory.writer_lock(".known-hosts.lock")
                except BlockingIOError:
                    raise ValueError("SSH_TRUST_STORE_BUSY") from None
            yield WindowsTrustTransaction(directory)
            directory.verify()
            if directory.identity() != self.identity:
                raise ValueError("SSH_TRUST_PATH_INVALID")
        finally:
            # Always attempt both, including a failed lock close. Retain uncertain
            # owners and refuse all subsequent transactions in this process.
            _close_owners(lock, directory)
        _require_cleanup_confirmed()
