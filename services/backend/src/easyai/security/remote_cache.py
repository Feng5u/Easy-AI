"""POSIX app-owned cache directories. Never repair permissions or follow symlinks."""

import os
from pathlib import Path
import stat


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
