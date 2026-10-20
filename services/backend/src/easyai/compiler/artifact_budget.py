"""Pure upper bounds for the existing 256-record / 64 KiB receipt contract."""

import hashlib
import json
from pathlib import PurePosixPath

from easyai.domain.program import FigureSpec, ProgramIR

MAX_ARTIFACTS = 256
MAX_RECEIPT = 65536
# RemotePath<=1024, username<=128, host<=253 Unicode characters, fixed UUIDs,
# hashes and numeric fields. Includes UTF-8/JSON overhead, UID and sourceSeq.
RECEIPT_ENVELOPE = 16384


def figure_contributors(figure: FigureSpec) -> list[str]:
    contributors = []
    for panel in figure.panels:
        contributors.append(panel.origin.block_id)
        if panel.title:
            contributors.append(panel.title.origin.block_id)
        contributors.extend(source.origin.block_id for source in panel.sources)
        if panel.axis:
            contributors.append(panel.axis.origin.block_id)
        if panel.legend:
            contributors.append(panel.legend.block_id)
    if figure.save:
        contributors.append(figure.save.origin.block_id)
    return list(dict.fromkeys(contributors))


def validate_artifact_budget(program: ProgramIR) -> tuple[int, int]:
    training = program.training
    epochs = 1 if program.execution_mode == "quick" else training.epochs
    count = len(training.before) + epochs * len(training.body) + len(training.after) + 1
    if count > MAX_ARTIFACTS:
        raise ValueError("ARTIFACT_PLAN_COUNT_EXCEEDED")
    records = []

    def record(
        kind: str,
        path: str,
        producer: str,
        contributors: list[str],
        phase: str | None = None,
        epoch: int | None = None,
    ) -> None:
        item: dict[str, object] = {
            "artifactId": "0" * 36,
            "runId": "0" * 36,
            "kind": kind,
            "relativePath": path,
            "mimeType": "image/png" if kind == "figure" else "application/octet-stream",
            "sizeBytes": 100 * 1024 * 1024,
            "sha256": "0" * 64,
            "producerBlockId": producer,
            "contributorBlockIds": contributors,
            "syncState": "ready",
        }
        if phase is not None:
            item["phase"] = phase
        if epoch is not None:
            item["epoch"] = epoch
        records.append(item)

    phases: list[tuple[list[FigureSpec], str, int | None]] = [
        (training.before, "before", None),
        (training.after, "after", None),
    ]
    if training.body:
        phases.extend((training.body, "epoch_end", epoch) for epoch in range(1, epochs + 1))
    for figures, phase, epoch in phases:
        for figure in figures:
            key = hashlib.sha256(figure.id.encode("utf-8")).hexdigest()[:16]
            suffix = f"epoch-{epoch:04d}" if epoch is not None else phase
            path = f"outputs/figures/{key}/{suffix}.png"
            if figure.save:
                logical = PurePosixPath(figure.save.relative_path)
                if logical.parts[0] != "outputs":
                    logical = PurePosixPath("outputs") / logical
                path = str(logical.with_name(f"{logical.stem}__{key}__{suffix}.png"))
            record(
                "figure", path, figure.origin.block_id, figure_contributors(figure), phase, epoch
            )
    record("model", "outputs/model.pth", training.origin.block_id, [])
    receipt_size = RECEIPT_ENVELOPE + len(
        json.dumps(
            {"artifacts": records},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    # The local cache index uses ASCII JSON and normalized optional fields;
    # it has its own 64 KiB gate even when the owner's UTF-8 receipt fits.
    index_records = [
        dict(item, phase=item.get("phase"), epoch=item.get("epoch")) for item in records
    ]
    index_size = RECEIPT_ENVELOPE + len(
        json.dumps(
            {"artifacts": index_records},
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")
    )
    size = max(receipt_size, index_size)
    if size > MAX_RECEIPT:
        raise ValueError("ARTIFACT_PLAN_RECEIPT_EXCEEDED")
    return count, size
