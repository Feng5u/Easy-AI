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
from easyai.security.project_lock import ProjectLock

MAX_PROJECT_BYTES = 5 * 1024 * 1024
# Raw JSON container depth, including Blockly next/block wrappers. This is
# separate from Decoder's semantic input-nesting limit and 500 total blocks.
MAX_JSON_DEPTH = 64


@dataclass
class OpenedProject:
    raw: bytes
    document: ProjectDocument | None
    read_only: bool
    reason: str | None = None


def validate_project_bytes(raw: bytes) -> ProjectDocument:
    """One authoritative read/write gate, including the exact serialized byte size."""
    if len(raw) > MAX_PROJECT_BYTES:
        raise ValueError("PROJECT_SIZE_LIMIT")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("PROJECT_DUPLICATE_JSON_KEY")
            result[key] = item
        return result

    value = json.loads(raw, object_pairs_hook=unique_object)
    pending = [(value, 0)]
    while pending:
        item, level = pending.pop()
        if level > MAX_JSON_DEPTH:
            raise ValueError("PROJECT_DEPTH_LIMIT")
        if isinstance(item, dict):
            pending.extend((child, level + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, level + 1) for child in item)
    document = ProjectDocument.model_validate(value)
    decode(document)
    return document


def read_project(path: Path) -> OpenedProject:
    if path.is_symlink():
        raise ValueError("PROJECT_PATH_FORBIDDEN")
    with path.open("rb") as stream:
        raw = stream.read(MAX_PROJECT_BYTES + 1)
    try:
        return OpenedProject(raw, validate_project_bytes(raw), False)
    except (ValueError, ValidationError, DecodeError, RecursionError) as error:
        reason = str(error) if str(error).startswith("PROJECT_") else type(error).__name__
        return OpenedProject(raw, None, True, reason)


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
        self._save_lock = threading.Lock()
        self._project_lock = ProjectLock(self.lock)

    @property
    def owned(self) -> bool:
        return self._project_lock.fd is not None

    @property
    def lock_reason(self) -> str | None:
        return self._project_lock.reason

    def close(self) -> None:
        with self._save_lock:
            self._project_lock.close()

    def save(self, document: ProjectDocument, expected_revision: int) -> ProjectDocument:
        with self._save_lock:
            return self._save(document, expected_revision)

    def _save(self, document: ProjectDocument, expected_revision: int) -> ProjectDocument:
        self._project_lock.verify()
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
        validate_project_bytes(payload)  # Before touching either backup or project.
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
