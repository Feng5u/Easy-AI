"""Persistent lock inode with kernel ownership, not a PID or stale-file heuristic."""

import errno
import os
import stat
import sys
from pathlib import Path
from uuid import uuid4

MAGIC = b"easyai-project-lock-v1\n"


def _kernel_lock(fd: int, *, unlock: bool = False) -> None:
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK if unlock else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN if unlock else fcntl.LOCK_EX | fcntl.LOCK_NB)


class ProjectLock:
    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None
        self.reason: str | None = None
        self._initialize()
        if path.is_symlink():
            raise ValueError("PROJECT_PATH_FORBIDDEN")
        fd = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
        os.set_inheritable(fd, False)
        locked = False
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("PROJECT_PATH_FORBIDDEN")
            try:
                _kernel_lock(fd)
                locked = True
            except OSError as error:
                if error.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                self.reason = "PROJECT_LOCK_HELD"
                return
            # Read only after acquiring: Windows byte-range locks are mandatory.
            os.lseek(fd, 0, os.SEEK_SET)
            if os.read(fd, len(MAGIC) + 1) != MAGIC:
                # An old app may still own an O_EXCL-only empty lock.
                self.reason = "PROJECT_LOCK_LEGACY_UNVERIFIED"
                return
            self._verify_fd(fd)
            self.fd = fd
            fd = -1
        finally:
            if fd != -1:
                try:
                    if locked:
                        _kernel_lock(fd, unlock=True)
                finally:
                    os.close(fd)

    def _initialize(self) -> None:
        # Publish a fully written marker without replacing an existing inode.
        # A crash before link leaves only our unused temporary file; after link,
        # even a crash before acquisition leaves a valid unlocked kernel lock.
        temp = self.path.with_name(f".{self.path.name}.{uuid4()}.tmp")
        try:
            with temp.open("xb") as stream:
                stream.write(MAGIC)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temp, self.path)
            except FileExistsError:
                pass
        finally:
            temp.unlink(missing_ok=True)

    def verify(self) -> None:
        if self.fd is None:
            raise ValueError("PROJECT_READ_ONLY")
        self._verify_fd(self.fd)

    def _verify_fd(self, fd: int) -> None:
        try:
            current = self.path.lstat()
            held = os.fstat(fd)
            if stat.S_ISLNK(current.st_mode) or (held.st_dev, held.st_ino) != (
                current.st_dev,
                current.st_ino,
            ):
                raise ValueError("PROJECT_LOCK_REPLACED")
        except FileNotFoundError:
            raise ValueError("PROJECT_LOCK_REPLACED") from None

    def close(self) -> None:
        if self.fd is not None:
            fd, self.fd = self.fd, None
            try:
                _kernel_lock(fd, unlock=True)
            finally:
                os.close(fd)
        # Never unlink: waiters and future opens must all lock the same inode.
