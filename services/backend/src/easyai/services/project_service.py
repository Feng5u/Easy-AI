import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from easyai.compiler.decode import DecodeError, decode
from easyai.domain.contracts import ProjectDocument


@dataclass
class OpenedProject:
    raw: bytes
    document: ProjectDocument | None
    read_only: bool
    reason: str | None = None


def read_project(path: Path) -> OpenedProject:
    if path.is_symlink():
        raise ValueError("PROJECT_PATH_FORBIDDEN")
    with path.open("rb") as stream:
        raw = stream.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        return OpenedProject(raw, None, True, "PROJECT_SIZE_LIMIT")
    try:

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError("PROJECT_DUPLICATE_JSON_KEY")
                result[key] = item
            return result

        value = json.loads(raw, object_pairs_hook=unique_object)

        def depth(item: Any, level: int = 0) -> None:
            if level > 64:
                raise ValueError("PROJECT_DEPTH_LIMIT")
            if isinstance(item, dict):
                for child in item.values():
                    depth(child, level + 1)
            elif isinstance(item, list):
                for child in item:
                    depth(child, level + 1)

        depth(value)
        document = ProjectDocument.model_validate(value)
        decode(document)
        return OpenedProject(raw, document, False)
    except (ValueError, ValidationError, DecodeError, RecursionError) as error:
        return OpenedProject(raw, None, True, type(error).__name__)


class ProjectService:
    """Only Main-authorized project directories may be used by API callers."""

    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        self.path = self.root / "project.easyai.json"
        meta = self.root / ".easyai"
        if meta.is_symlink():
            raise ValueError("PROJECT_PATH_FORBIDDEN")
        meta.mkdir(exist_ok=True)
        self.lock = meta / "project.lock"
        self.owned = False
        self._save_lock = threading.Lock()
        try:
            fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            self.owned = True
        except FileExistsError:
            pass

    def close(self) -> None:
        with self._save_lock:
            if self.owned:
                self.lock.unlink()
                self.owned = False

    def save(self, document: ProjectDocument, expected_revision: int) -> ProjectDocument:
        with self._save_lock:
            return self._save(document, expected_revision)

    def _save(self, document: ProjectDocument, expected_revision: int) -> ProjectDocument:
        if not self.owned:
            raise ValueError("PROJECT_READ_ONLY")
        current = read_project(self.path)
        if current.read_only or current.document is None:
            raise ValueError("PROJECT_READ_ONLY")
        if current.document.project_id != document.project_id:
            raise ValueError("PROJECT_ID_CONFLICT")
        if current.document.revision != expected_revision or document.revision != expected_revision:
            raise ValueError("PROJECT_REVISION_CONFLICT")
        decode(document)  # Unknown blocks cannot be silently discarded on save.
        saved = document.model_copy(update={"revision": expected_revision + 1})
        payload = (saved.model_dump_json(by_alias=True, indent=2) + "\n").encode()
        meta = self.root / ".easyai"
        backup = meta / "backup"
        if backup.is_symlink():
            raise ValueError("PROJECT_PATH_FORBIDDEN")
        backup.mkdir(exist_ok=True)
        self.atomic_write(backup / "project.easyai.json.bak", current.raw)
        self.atomic_write(self.path, payload)
        return saved

    @staticmethod
    def atomic_write(target: Path, content: bytes) -> None:
        if target.is_symlink():
            raise ValueError("PROJECT_PATH_FORBIDDEN")
        temp = target.with_name(target.name + f".{uuid4()}.tmp")
        try:
            with temp.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, target)
            if os.name == "posix":
                fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temp.unlink(missing_ok=True)
