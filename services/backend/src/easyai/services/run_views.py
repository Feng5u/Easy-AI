"""Read-only views over registered immutable runs and bounded local output files."""

import binascii
import codecs
import hashlib
import os
import stat
import struct
from pathlib import Path, PurePosixPath, PureWindowsPath

from pydantic import TypeAdapter

from easyai.domain.contracts import ArtifactRecord, Event, ProjectDocument, SourceSpan
from easyai.domain.desktop import RunLogs, RunSource, DiagnosticReport
from easyai.security.files import read_regular
from easyai.services.run_service import RunService, TERMINAL

IMAGE_LIMIT = 8 * 1024 * 1024
LOG_CHUNK = 32 * 1024


def validate_png(content: bytes) -> None:
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("ARTIFACT_PNG_INVALID")
    offset, chunks, image_data = 8, 0, False
    while offset + 12 <= len(content):
        length = struct.unpack(">I", content[offset : offset + 4])[0]
        end = offset + 12 + length
        if end > len(content):
            raise ValueError("ARTIFACT_PNG_INVALID")
        kind = content[offset + 4 : offset + 8]
        data = content[offset + 8 : offset + 8 + length]
        crc = struct.unpack(">I", content[offset + 8 + length : end])[0]
        if binascii.crc32(kind + data) & 0xFFFFFFFF != crc:
            raise ValueError("ARTIFACT_PNG_INVALID")
        if chunks == 0:
            if kind != b"IHDR" or length != 13:
                raise ValueError("ARTIFACT_PNG_INVALID")
            width, height = struct.unpack(">II", data[:8])
            if not 1 <= width <= 8192 or not 1 <= height <= 8192 or width * height > 16777216:
                raise ValueError("ARTIFACT_PNG_DIMENSIONS_INVALID")
        elif kind == b"IHDR":
            raise ValueError("ARTIFACT_PNG_INVALID")
        image_data = image_data or kind == b"IDAT"
        if kind == b"IEND":
            if length != 0 or end != len(content) or not image_data:
                raise ValueError("ARTIFACT_PNG_INVALID")
            return
        chunks += 1
        offset = end
    raise ValueError("ARTIFACT_PNG_INVALID")


def read_log(path: Path, after: int, done: bool) -> tuple[str, int]:
    if type(after) is not int or after < 0:
        raise ValueError("LOG_CURSOR_INVALID")
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_BINARY", 0),
        )
    except FileNotFoundError:
        if after:
            raise ValueError("LOG_CURSOR_INVALID") from None
        return "", 0
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("FILE_NOT_REGULAR")
        if after > info.st_size:
            raise ValueError("LOG_CURSOR_INVALID")
        stream.seek(after)
        raw = stream.read(LOG_CHUNK)
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        text = decoder.decode(raw, final=done and after + len(raw) == info.st_size)
        pending, _ = decoder.getstate()
        return text, after + len(raw) - len(pending)


class RunViews:
    def __init__(self, runs: RunService):
        self.runs = runs

    def events(self, run_id: str, after: int = 0) -> list[Event]:
        from easyai.services.runtime_diagnostics import (
            locate_failure,
            missing_location,
            explain_name,
        )

        events = self.runs.events(run_id, after)
        failures = [event for event in events if event.type == "runtime_error"]
        if not failures:
            return events
        run = self.runs.get(run_id)
        source = None
        try:
            source = self.source(run_id)
        except (OSError, ValueError):
            pass  # No path or exception text enters the derived failure reason.
        expected = str(
            (
                PurePosixPath(run.config.run_root)
                if run.config.runner == "ssh"
                else Path(run.config.run_root)
            )
            / "code"
            / "train.py"
        )
        result = []
        for event in events:
            if event.type != "runtime_error":
                result.append(event)
                continue
            location = missing_location(event, run.config.code_hash, "SOURCE_UNVERIFIED")
            if source is not None:
                try:
                    location = locate_failure(event, source, expected)
                    location.update(explain_name(event, source, location))
                except (ValueError, RecursionError):
                    location = missing_location(event, run.config.code_hash, "SOURCE_MAP_INVALID")
            # Derived transport metadata only; never mutate or rewrite the raw journal.
            result.append(
                event.model_copy(
                    update={
                        "payload": {
                            **event.payload,
                            "applicationLocation": location,
                        }
                    },
                    deep=True,
                )
            )
        return result

    def source(self, run_id: str) -> RunSource:
        run = self.runs.get(run_id)
        self.runs._verify_snapshot(run_id)
        code = read_regular(self.runs._safe_path(run_id, "code/train.py"), 8 * 1024 * 1024)
        if hashlib.sha256(code).hexdigest() != run.config.code_hash:
            raise ValueError("CODE_HASH_CONFLICT")
        from easyai.services.runtime_diagnostics import frozen_objects

        snapshot = ProjectDocument.model_validate_json(
            read_regular(
                self.runs._safe_path(run_id, "snapshot/project.easyai.json"), 5 * 1024 * 1024
            )
        )
        objects, reference_check = frozen_objects(snapshot)
        return RunSource(
            project_revision=run.config.project_revision,
            program_hash=run.config.program_hash,
            code_hash=run.config.code_hash,
            code=code.decode("utf-8"),
            source_map=TypeAdapter(list[SourceSpan]).validate_json(
                read_regular(self.runs._safe_path(run_id, "code/source-map.json"), 8 * 1024 * 1024)
            ),
            snapshot=snapshot,
            objects=objects,
            reference_check=reference_check,
        )

    def report(self, run_id: str, event_seq: int) -> DiagnosticReport:
        run = self.runs.get(run_id)
        event = next(
            (
                event
                for event in self.events(run_id, event_seq - 1)
                if event.seq == event_seq and event.type == "runtime_error"
            ),
            None,
        )
        if event is None:
            raise KeyError("DIAGNOSTIC_NOT_FOUND")
        location = event.payload["applicationLocation"]
        try:
            source = self.source(run_id)
        except (OSError, ValueError):
            source = None
        return DiagnosticReport(
            code="RUNTIME_NAME_ERROR"
            if event.payload.get("exceptionType") == "NameError"
            else "RUNTIME_EXCEPTION",
            run_id=run_id,
            event_seq=event_seq,
            code_hash=run.config.code_hash,
            project_revision=run.config.project_revision,
            precision=location["precision"],
            name_state=location.get("nameState", "unavailable"),
            reference_check=location.get("referenceCheck", "unavailable"),
            objects_total=len(source.objects)
            if source and source.reference_check != "unavailable"
            else None,
            registered_total=sum(item.registered for item in source.objects)
            if source and source.reference_check != "unavailable"
            else None,
        )

    def logs(self, run_id: str, stdout_after: int = 0, stderr_after: int = 0) -> RunLogs:
        run = self.runs.get(run_id)
        if run.config.runner == "ssh":
            return self.runs.remote.logs(run_id, stdout_after, stderr_after)
        done = run.status in TERMINAL
        stdout, out_cursor = read_log(
            self.runs._safe_path(run_id, "logs/train.log"), stdout_after, done
        )
        stderr, err_cursor = read_log(
            self.runs._safe_path(run_id, "logs/stderr.log"), stderr_after, done
        )

        def at_eof(relative: str, cursor: int) -> bool:
            path = self.runs._safe_path(run_id, relative)
            try:
                info = path.lstat()
            except FileNotFoundError:
                return cursor == 0
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("FILE_NOT_REGULAR")
            return cursor >= info.st_size

        return RunLogs(
            stdout=stdout,
            stderr=stderr,
            stdout_after=out_cursor,
            stderr_after=err_cursor,
            done=done
            and at_eof("logs/train.log", out_cursor)
            and at_eof("logs/stderr.log", err_cursor),
        )

    def artifacts(self, run_id: str) -> list[ArtifactRecord]:
        if self.runs.get(run_id).config.runner == "ssh":
            return self.runs.remote.artifacts(run_id)
        records = TypeAdapter(list[ArtifactRecord]).validate_json(
            read_regular(self.runs._safe_path(run_id, "artifacts.json"), 8 * 1024 * 1024)
        )
        ids = [record.artifact_id for record in records]
        if len(set(ids)) != len(ids) or any(record.run_id != run_id for record in records):
            raise ValueError("ARTIFACT_IDENTITY_INVALID")
        return records

    def image(self, run_id: str, artifact_id: str) -> bytes:
        if self.runs.get(run_id).config.runner == "ssh":
            return self.runs.remote.image(run_id, artifact_id)
        item = next(
            (record for record in self.artifacts(run_id) if record.artifact_id == artifact_id), None
        )
        if item is None:
            raise KeyError("ARTIFACT_NOT_FOUND")
        relative = PurePosixPath(item.relative_path)
        if (
            item.kind != "figure"
            or item.mime_type != "image/png"
            or item.sync_state != "ready"
            or not 0 < item.size_bytes <= IMAGE_LIMIT
            or not relative.parts
            or relative.parts[0] != "outputs"
            or relative.suffix.lower() != ".png"
            or relative.is_absolute()
            or PureWindowsPath(item.relative_path).drive
            or ".." in relative.parts
            or any(ord(char) < 32 or char in ":\\" for char in item.relative_path)
        ):
            raise ValueError("ARTIFACT_PATH_OR_TYPE_FORBIDDEN")
        content = read_regular(self.runs._safe_path(run_id, item.relative_path), IMAGE_LIMIT)
        if len(content) != item.size_bytes or hashlib.sha256(content).hexdigest() != item.sha256:
            raise ValueError("ARTIFACT_HASH_CONFLICT")
        validate_png(content)
        return content
