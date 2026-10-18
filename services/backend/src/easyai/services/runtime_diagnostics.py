"""Derived traceback locations; raw journal events and cursors remain immutable."""

from typing import Any

from easyai.compiler.decode import decode
from easyai.compiler.source_map import locate_line
from easyai.domain.contracts import BlockIR, Event
from easyai.domain.desktop import RunSource


def missing_location(event: Event, code_hash: str, reason: str) -> dict[str, Any]:
    return {
        "version": 1,
        "runId": event.run_id,
        "eventSeq": event.seq,
        "codeHash": code_hash,
        "precision": "none",
        "reason": reason,
        "origin": None,
        "line": None,
    }


def locate_failure(event: Event, source: RunSource, expected_file: str) -> dict[str, Any]:
    result = missing_location(event, source.code_hash, "FRAMES_MISSING")
    payload = event.payload
    if payload.get("generatedCodeHash") != source.code_hash:
        return {**result, "reason": "RUNTIME_CODE_UNVERIFIED"}
    if payload.get("generatedFile") != expected_file:
        return {**result, "reason": "FILE_IDENTITY_MISMATCH"}
    frames = payload.get("frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= 16:
        return result
    line: int | None = None
    for frame in reversed(frames):
        if not isinstance(frame, dict):
            return {**result, "reason": "FRAMES_INVALID"}
        filename, number = frame.get("filename"), frame.get("lineno")
        if (
            not isinstance(filename, str)
            or type(number) is not int
            or number < 1
            or not isinstance(frame.get("function"), str)
        ):
            return {**result, "reason": "FRAMES_INVALID"}
        if filename == expected_file and line is None:
            line = number
    if line is None:
        return {**result, "reason": "NO_GENERATED_FRAME"}
    lines = len(source.code.splitlines())
    if line > lines:
        return {**result, "reason": "LINE_OUT_OF_RANGE"}
    roots, _ = decode(source.snapshot)
    origins: set[tuple[str, str]] = set()
    pending: list[BlockIR] = list(roots)
    while pending:
        block = pending.pop()
        origins.add((block.origin.block_id, block.origin.workspace))
        for children in block.inputs.values():
            pending.extend(children)
    if any(
        span.end_line > lines or (span.origin.block_id, span.origin.workspace) not in origins
        for span in source.source_map
    ):
        return {**result, "reason": "SOURCE_MAP_INVALID"}
    hit = locate_line(source.source_map, line)
    if hit is None:
        return {**result, "reason": "NO_SOURCE_SPAN"}
    return {
        **result,
        "precision": hit.kind,
        "reason": "VERIFIED_GENERATED_FRAME",
        "origin": hit.origin.model_dump(by_alias=True),
        "line": line,
    }
