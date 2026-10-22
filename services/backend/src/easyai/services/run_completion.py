"""One success policy for local and SSH executions; I/O verification stays runner specific."""

from typing import Callable
from easyai.domain.contracts import ArtifactRecord, Event
from easyai.domain.program import ProgramIR


def artifacts_complete(
    program: ProgramIR, events: list[Event], verified: Callable[[ArtifactRecord], bool]
) -> bool:
    epochs = 1 if program.execution_mode == "quick" else program.training.epochs
    metrics = [event.payload for event in events if event.type == "epoch_completed"]
    completion = [event.payload for event in events if event.type == "pipeline_completed"]
    if [item["epoch"] for item in metrics] != list(range(1, epochs + 1)) or len(completion) != 1:
        return False
    if (
        completion[0].get("epochs") != epochs
        or completion[0].get("executionMode") != program.execution_mode
    ):
        return False
    expected: set[tuple[str, str, str | None, int | None]] = {
        (program.training.origin.block_id, "model", None, None)
    }
    for phase, figures in (
        ("before", program.training.before),
        ("epoch_end", program.training.body),
        ("after", program.training.after),
    ):
        for figure in figures:
            for epoch in range(1, epochs + 1) if phase == "epoch_end" else [None]:
                expected.add((figure.id, "figure", phase, epoch))
    actual: set[tuple[str, str, str | None, int | None]] = set()
    ids: set[str] = set()
    paths: set[str] = set()
    for event in events:
        if event.type != "artifact_created":
            continue
        record = ArtifactRecord.model_validate(event.payload)
        if (
            record.artifact_id in ids
            or record.relative_path in paths
            or record.size_bytes == 0
            or not verified(record)
        ):
            return False
        ids.add(record.artifact_id)
        paths.add(record.relative_path)
        actual.add((record.producer_block_id, record.kind, record.phase, record.epoch))
    return expected <= actual
