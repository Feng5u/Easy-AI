"""Host-local SSH storage contract; currently a POSIX backend only.

Never repair existing permissions, follow symlinks or substitute weaker I/O.
"""

import os
from pathlib import Path
import stat
from typing import Literal, Protocol


def check_file(info: os.stat_result) -> None:
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError("REMOTE_CACHE_FILE_UNSAFE")


def _directory(info: os.stat_result, *, final: bool, anchor_uid: int) -> None:
    owners = {os.geteuid()} if final else {0, os.geteuid(), anchor_uid}
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid not in owners
        or (info.st_mode & 0o022 and (final or not info.st_mode & stat.S_ISVTX))
    ):
        raise ValueError("REMOTE_CACHE_DIRECTORY_UNSAFE")


def open_directory(path: Path) -> int:
    if os.name != "posix" or not path.is_absolute():
        raise ValueError("REMOTE_CACHE_PLATFORM_UNVERIFIED")
    descriptors = []
    try:
        descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(descriptor)
        anchor_uid = os.fstat(descriptor).st_uid
        _directory(os.fstat(descriptor), final=path == Path(path.anchor), anchor_uid=anchor_uid)
        for index, part in enumerate(path.parts[1:]):
            descriptor = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            descriptors.append(descriptor)
            _directory(
                os.fstat(descriptor), final=index == len(path.parts) - 2, anchor_uid=anchor_uid
            )
        result = os.dup(descriptors[-1])
        os.set_inheritable(result, False)
        return result
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def verify_directory(path: Path, held: int) -> None:
    descriptor = open_directory(path)
    try:
        before, after = os.fstat(held), os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError("REMOTE_CACHE_REPLACED")
    finally:
        os.close(descriptor)


# Only this module owns host-specific cache syscalls. Remote Linux filesystem
# checks in the SSH adapter are a separate protocol and must not use this API.
Access = Literal["read", "update", "exclusive"]


def require_local_cache() -> None:
    """Reject before binding/preparing a run, without importing a native backend.

    This is a capability gate, not a product/platform acceptance declaration.
    No Windows implementation or weaker path-based fallback is currently enabled.
    """
    if os.name != "posix":
        raise ValueError("REMOTE_CACHE_PLATFORM_UNVERIFIED")


class LocalDirectory(Protocol):
    path: Path

    def verify(self) -> None: ...
    def child(self, name: str, *, create: bool = False) -> "LocalDirectory": ...
    def new_child(self, name: str) -> "LocalDirectory": ...
    def names(self) -> list[str]: ...
    def open_file(self, name: str, access: Access = "read") -> int: ...
    def verify_file(self, name: str, descriptor: int) -> None: ...
    # Caller must flush/sync_file the completed temporary before publication.
    # A failed sync is an uncertain publication, never a successful receipt.
    def publish(self, source: str, target: str, *, replace: bool = False) -> None: ...
    def remove(self, name: str, *, missing_ok: bool = False) -> None: ...
    def sync(self) -> None: ...
    def sync_file(self, descriptor: int) -> None: ...
    def writer_lock(self, name: str) -> "LocalWriterLock": ...
    def owner_lock(self, name: str) -> "LocalOwnerLock": ...
    def close(self) -> None: ...


class LocalWriterLock(Protocol):
    def verify(self) -> None: ...
    def close(self) -> None: ...


class LocalOwnerLock(Protocol):
    fd: int | None
    reason: str | None

    def verify(self) -> None: ...
    def close(self) -> None: ...


def _name(value: str) -> str:
    if (
        not value
        or value in (".", "..")
        or len(value.encode("utf-8")) > 255
        or any(char in "/\\:" or ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError("REMOTE_CACHE_COMPONENT_INVALID")
    return value


class _PosixDirectory:
    def __init__(self, path: Path):
        require_local_cache()
        self.path = path
        self._fd = open_directory(path)

    def verify(self) -> None:
        if self._fd < 0:
            raise ValueError("REMOTE_CACHE_CLOSED")
        verify_directory(self.path, self._fd)

    def child(self, name: str, *, create: bool = False) -> LocalDirectory:
        self.verify()
        name = _name(name)
        if create:
            try:
                os.mkdir(name, 0o700, dir_fd=self._fd)
                self.sync()
            except FileExistsError:
                pass  # Open below still rejects links and unsafe existing directories.
        result = _PosixDirectory(self.path / name)
        try:
            self.verify()
        except BaseException:
            result.close()
            raise
        return result

    def new_child(self, name: str) -> LocalDirectory:
        self.verify()
        name = _name(name)
        os.mkdir(name, 0o700, dir_fd=self._fd)  # Exclusive claim; never merge existing output.
        # Hold the first opened identity before the directory flush boundary.
        # Never reopen by name after that receipt and adopt a different child.
        result = self.child(name)
        try:
            self.sync()
            result.verify()
            self.verify()
            return result
        except BaseException:
            result.close()
            raise

    def names(self) -> list[str]:
        self.verify()
        return os.listdir(self._fd)

    def open_file(self, name: str, access: Access = "read") -> int:
        self.verify()
        name = _name(name)
        modes = {
            "read": os.O_RDONLY,
            "update": os.O_RDWR | os.O_CREAT,
            "exclusive": os.O_RDWR | os.O_CREAT | os.O_EXCL,
        }
        if access not in modes:
            raise ValueError("REMOTE_CACHE_ACCESS_INVALID")
        descriptor = os.open(
            name, modes[access] | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=self._fd
        )
        try:
            os.set_inheritable(descriptor, False)
            self.verify_file(name, descriptor)
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor

    def verify_file(self, name: str, descriptor: int) -> None:
        self.verify()
        current = os.stat(_name(name), dir_fd=self._fd, follow_symlinks=False)
        held = os.fstat(descriptor)
        check_file(current)
        check_file(held)
        if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino):
            raise ValueError("REMOTE_CACHE_FILE_REPLACED")

    def publish(self, source: str, target: str, *, replace: bool = False) -> None:
        # Source and any existing destination must be safe before the operation.
        descriptor = self.open_file(source)
        os.close(descriptor)
        source, target = _name(source), _name(target)
        if replace:
            try:
                descriptor = self.open_file(target)
            except FileNotFoundError:
                pass
            else:
                os.close(descriptor)
            self.verify()
            os.replace(source, target, src_dir_fd=self._fd, dst_dir_fd=self._fd)
        else:
            os.link(source, target, src_dir_fd=self._fd, dst_dir_fd=self._fd, follow_symlinks=False)
        self.sync()  # Publication is not acknowledged if directory fsync fails.

    def remove(self, name: str, *, missing_ok: bool = False) -> None:
        self.verify()
        try:
            os.unlink(_name(name), dir_fd=self._fd)
        except FileNotFoundError:
            if not missing_ok:
                raise

    def sync(self) -> None:
        self.verify()
        os.fsync(self._fd)

    def sync_file(self, descriptor: int) -> None:
        self.verify()
        check_file(os.fstat(descriptor))
        os.fsync(descriptor)

    def writer_lock(self, name: str) -> LocalWriterLock:
        return _PosixWriterLock(self, name)

    def owner_lock(self, name: str) -> LocalOwnerLock:
        from easyai.security.project_lock import ProjectLock

        self.verify()
        result = ProjectLock(self.path / _name(name))
        try:
            self.verify()
        except BaseException:
            result.close()
            raise
        return result

    def close(self) -> None:
        if self._fd >= 0:
            descriptor, self._fd = self._fd, -1
            os.close(descriptor)


class _PosixWriterLock:
    def __init__(self, directory: _PosixDirectory, name: str):
        import fcntl  # Native dependency is loaded only after the platform gate.

        self.directory, self.name = directory, _name(name)
        self.descriptor = directory.open_file(name, "update")
        try:
            fcntl.flock(self.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.verify()
        except BaseException:
            self.close()
            raise

    def verify(self) -> None:
        if self.descriptor < 0:
            raise ValueError("REMOTE_CACHE_LOCK_CLOSED")
        self.directory.verify_file(self.name, self.descriptor)

    def close(self) -> None:
        if self.descriptor >= 0:
            descriptor, self.descriptor = self.descriptor, -1
            os.close(descriptor)  # Never unlink or replace the permanent lock inode.


def local_directory(path: Path) -> LocalDirectory:
    require_local_cache()
    return _PosixDirectory(path)


def limited_names(directory: LocalDirectory, limit: int) -> list[str]:
    """Bound enumeration before list allocation for user-selected upload trees."""
    if not isinstance(directory, _PosixDirectory) or not 1 <= limit <= 1024:
        raise ValueError("REMOTE_CACHE_PLATFORM_UNVERIFIED")
    directory.verify()
    result: list[str] = []
    with os.scandir(directory._fd) as entries:
        for entry in entries:
            if len(result) >= limit:
                raise ValueError("DATA_TRANSFER_SOURCE_LIMIT")
            result.append(entry.name)
    directory.verify()
    return sorted(result)
