"""Bounded regular-file reads for local persistence, including hostile FIFOs."""

import os
import stat
from pathlib import Path


def read_regular(path: Path, max_bytes: int, *, prefix: bool = False) -> bytes:
    if max_bytes <= 0:
        raise ValueError("FILE_READ_LIMIT_INVALID")
    descriptor = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0),
    )
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("FILE_NOT_REGULAR")
        if not prefix and info.st_size > max_bytes:
            raise ValueError("FILE_SIZE_LIMIT")
        content = stream.read(max_bytes if prefix else max_bytes + 1)
        if not prefix and len(content) > max_bytes:
            raise ValueError("FILE_SIZE_LIMIT")
        return content


def digest_regular(path: Path, max_bytes: int) -> str:
    """Hash bounded binary artifacts without loading them into application memory."""
    import hashlib

    descriptor = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0),
    )
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("FILE_NOT_REGULAR")
        if info.st_size > max_bytes:
            raise ValueError("FILE_SIZE_LIMIT")
        result = hashlib.sha256()
        count = 0
        while chunk := stream.read(min(65536, max_bytes - count + 1)):
            count += len(chunk)
            if count > max_bytes:
                raise ValueError("FILE_SIZE_LIMIT")
            result.update(chunk)
        return result.hexdigest()
