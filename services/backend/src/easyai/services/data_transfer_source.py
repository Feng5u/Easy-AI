"""Bounded native-selected source inventory; payload bytes are streamed after confirmation."""

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Callable, Iterator

from easyai.services.data_transfer_errors import TransferFailure
from easyai.domain.data_transfer import TransferBudget
from easyai.security.remote_cache import local_directory, limited_names, LocalDirectory


def stamp(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


@dataclass(frozen=True)
class SourceFile:
    name: str
    size: int
    identity: tuple[int, int, int, int, int]


@dataclass(frozen=True)
class TransferSource:
    root: Path
    root_identity: tuple[int, int]
    directories: tuple[tuple[str, tuple[int, int]], ...]
    files: tuple[SourceFile, ...]

    @classmethod
    def inventory(
        cls, root: Path, budget: TransferBudget, check: Callable[[], None]
    ) -> "TransferSource":
        files: list[SourceFile] = []
        directories = []
        total = 0
        opened = local_directory(root)
        try:
            initial = root.lstat()
            opened.verify()

            def walk(directory: LocalDirectory, prefix: str, depth: int) -> None:
                nonlocal total
                check()
                if depth > 12:
                    raise TransferFailure("DATA_TRANSFER_SOURCE_LIMIT")
                for name in limited_names(directory, 513):
                    check()
                    if (
                        not name
                        or name.startswith(".")
                        or name.lower() in {"id_rsa", "id_ed25519", "id_ecdsa", "credentials"}
                        or name.lower().endswith((".pem", ".key"))
                        or any(c in name for c in "/\\:")
                        or any(ord(c) < 32 or ord(c) == 127 for c in name)
                    ):
                        raise TransferFailure("DATA_TRANSFER_SOURCE_FORBIDDEN")
                    relative = prefix + name
                    if len(relative.encode("utf-8")) > 512:
                        raise TransferFailure("DATA_TRANSFER_SOURCE_LIMIT")
                    path = root / relative
                    info = path.lstat()
                    import stat

                    if stat.S_ISDIR(info.st_mode):
                        child = directory.child(name)
                        try:
                            directories.append((relative, (info.st_dev, info.st_ino)))
                            walk(child, relative + "/", depth + 1)
                        finally:
                            child.close()
                    elif stat.S_ISREG(info.st_mode):
                        with os.fdopen(directory.open_file(name), "rb") as stream:
                            current = os.fstat(stream.fileno())
                            directory.verify_file(name, stream.fileno())
                            if stamp(info) != stamp(current):
                                raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
                        total += current.st_size
                        files.append(SourceFile(relative, current.st_size, stamp(current)))
                        if (
                            len(files) > budget.max_files
                            or total > budget.max_bytes
                            or current.st_size > 100 * 1024 * 1024
                        ):
                            raise TransferFailure("DATA_TRANSFER_SOURCE_LIMIT")
                    else:
                        raise TransferFailure("DATA_TRANSFER_SOURCE_FORBIDDEN")
                    if len(directories) > 256:
                        raise TransferFailure("DATA_TRANSFER_SOURCE_LIMIT")
                directory.verify()

            if root.name.startswith("."):
                raise TransferFailure("DATA_TRANSFER_SOURCE_FORBIDDEN")
            walk(opened, "", 0)
            if not files:
                raise TransferFailure("DATA_TRANSFER_SOURCE_EMPTY")
            return cls(root, (initial.st_dev, initial.st_ino), tuple(directories), tuple(files))
        finally:
            opened.close()

    @contextmanager
    def open(self, record: SourceFile, check: Callable[[], None]) -> Iterator[BinaryIO]:
        check()
        root = local_directory(self.root)
        held = [root]
        try:
            info = self.root.lstat()
            if (info.st_dev, info.st_ino) != self.root_identity:
                raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
            current = root
            prefix = PurePosixPath()
            expected_dirs = dict(self.directories)
            for part in PurePosixPath(record.name).parts[:-1]:
                prefix /= part
                current = current.child(part)
                held.append(current)
                info = current.path.lstat()
                if (info.st_dev, info.st_ino) != expected_dirs[str(prefix)]:
                    raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
            with os.fdopen(current.open_file(PurePosixPath(record.name).name), "rb") as stream:
                if stamp(os.fstat(stream.fileno())) != record.identity:
                    raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
                yield stream
                check()
                current.verify_file(PurePosixPath(record.name).name, stream.fileno())
                if stamp(os.fstat(stream.fileno())) != record.identity:
                    raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
            for directory in held:
                directory.verify()
        finally:
            for directory in reversed(held):
                directory.close()
