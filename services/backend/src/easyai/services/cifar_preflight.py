"""Read-only CIFAR10 layout gate. Never deserialize Python dataset batches.

Passing this gate is deliberately insufficient for DATASET_READY: an isolated,
safe official-adapter construction probe remains required by plan section 9.1.
"""

import os
from pathlib import Path
import stat
from typing import Callable


_BATCHES = tuple(f"data_batch_{index}" for index in range(1, 6)) + ("test_batch",)
_FILES = _BATCHES + ("batches.meta",)


def inspect_cifar10_layout(root: Path, checkpoint: Callable[[], None] = lambda: None) -> None:
    """Check both official Python splits, bounded headers and file identities.

    This never scans samples, computes full-data hashes, imports numpy/torch or
    calls pickle. Protocol/size checks only reject obviously unsuitable inputs;
    arbitrary bytes with a plausible header do NOT receive a readiness grant.
    """
    checkpoint()
    folder = root / "cifar-10-batches-py"
    for directory in (root, folder):
        try:
            info = directory.lstat()
        except FileNotFoundError:
            raise ValueError("DATASET_MISSING_NO_DOWNLOAD") from None
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("DATA_PATH_FORBIDDEN")
    identities: set[tuple[int, int]] = set()
    for name in _FILES:
        checkpoint()
        path = folder / name
        try:
            before = path.lstat()
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("DATA_PATH_FORBIDDEN")
            descriptor = os.open(
                path,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_BINARY", 0),
            )
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                identity = (opened.st_dev, opened.st_ino)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or identity != (before.st_dev, before.st_ino)
                    or identity in identities
                ):
                    raise ValueError("DATA_PATH_FORBIDDEN")
                # Official Python batches hold 10,000 RGB uint8 32x32 images;
                # metadata is small. Bounds reject truncated/oversized files
                # without reading image payloads or trusting pickle lengths.
                lower, upper = (30_720_000, 40_000_000) if name in _BATCHES else (16, 65536)
                if not lower <= opened.st_size <= upper:
                    raise ValueError("DATASET_CIFAR10_FORMAT_INVALID")
                header = stream.read(2)
                after = os.fstat(stream.fileno())
                current = path.lstat()
                if (
                    header != b"\x80\x02"
                    or (after.st_size, after.st_mtime_ns) != (opened.st_size, opened.st_mtime_ns)
                    or (current.st_dev, current.st_ino) != identity
                    or not stat.S_ISREG(current.st_mode)
                ):
                    raise ValueError("DATASET_CIFAR10_FORMAT_INVALID")
                identities.add(identity)
        except FileNotFoundError:
            raise ValueError("DATASET_MISSING_NO_DOWNLOAD") from None
    checkpoint()
    # Directory/header checks cannot establish shape, labels, checksums or
    # safe deserialization. In particular, NEVER call torchvision here.
    raise ValueError("DATASET_CIFAR10_SAFE_PROBE_REQUIRED")
