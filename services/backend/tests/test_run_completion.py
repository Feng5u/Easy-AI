"""Completion protocol regressions from real Blockly JSON; no training is run."""

import ast
import json

import pytest

from easyai.compiler.pipeline import compile_project
from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import ArtifactRecord, Event, ProjectDocument
from easyai.services.run_completion import artifacts_complete


def protocol_case(layout="direct", mode="full"):
    def document(name):
        return json.loads((SOURCE_ROOT / f"packages/contracts/fixtures/{name}.json").read_bytes())

    raw = document("mnist-figures" if layout == "legacy" else "mnist-direct-plots")
    loop = raw["workspaces"]["training"]["blocks"]["blocks"][0]
    if layout == "mixed":
        old = document("mnist-figures")["workspaces"]["training"]["blocks"]["blocks"][0]
        legacy = old["inputs"]["body"]["block"]

        def separate_ids(value):
            if isinstance(value, dict):
                if "type" in value and "id" in value:
                    value["id"] = "legacy-" + value["id"]
                for child in value.values():
                    separate_ids(child)
            elif isinstance(value, list):
                for child in value:
                    separate_ids(child)

        separate_ids(legacy)
        legacy["next"] = loop["inputs"]["body"]
        loop["inputs"]["body"] = {"block": legacy}
    loop["fields"]["EPOCHS"] = 2
    raw["settings"]["executionMode"] = mode
    compiled = compile_project(ProjectDocument.model_validate(raw))
    assert compiled.result.runnable, compiled.result.diagnostics
    program = compiled.program
    epochs = 1 if mode == "quick" else 2
    events = []

    def event(kind, payload, block_id=None):
        sequence = len(events) + 1
        events.append(
            Event(
                run_id="completion-protocol-fixture",
                seq=sequence,
                source="runtime",
                source_seq=sequence,
                timestamp="2026-11-16T00:00:00Z",
                type=kind,
                block_id=block_id,
                payload=payload,
            )
        )

    # Protocol-only epoch records, never presented as training measurements.
    for epoch in range(1, epochs + 1):
        event(
            "epoch_completed",
            dict(
                epoch=epoch,
                train_loss=0.0,
                test_accuracy=0.0,
                train_samples=1,
                test_samples=1,
                elapsed_seconds=0.0,
            ),
        )
    # Read the emitted artifact calls instead of copying the completion policy.
    # This catches disagreement between the compiler and either Runner's verifier.
    for call in ast.walk(ast.parse(compiled.result.code)):
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "context"
            and call.func.attr == "artifact"
        ):
            continue
        kind, producer, contributors = [ast.literal_eval(arg) for arg in call.args[1:4]]
        phase = ast.literal_eval(call.args[4]) if len(call.args) > 4 else None
        for epoch in range(1, epochs + 1) if phase == "epoch_end" else [None]:
            artifact_id = f"artifact-{len(events)}"
            record = ArtifactRecord(
                artifact_id=artifact_id,
                run_id="completion-protocol-fixture",
                kind=kind,
                relative_path=f"outputs/{artifact_id}.{'png' if kind == 'figure' else 'pth'}",
                mime_type="image/png" if kind == "figure" else "application/octet-stream",
                size_bytes=1,
                sha256="0" * 64,
                producer_block_id=producer,
                contributor_block_ids=contributors,
                phase=phase,
                epoch=epoch,
                sync_state="ready",
            )
            event("artifact_created", record.model_dump(by_alias=True), producer)
    event("pipeline_completed", {"epochs": epochs, "executionMode": mode})
    return program, events


@pytest.mark.parametrize("layout", ["direct", "legacy", "mixed"])
@pytest.mark.parametrize("mode", ["full", "quick"])
def test_emitted_artifacts_complete_new_legacy_and_mixed_figures(layout, mode):
    program, events = protocol_case(layout, mode)
    verified = []
    assert artifacts_complete(program, events, lambda record: verified.append(record) is None)
    assert len(verified) == sum(event.type == "artifact_created" for event in events)


@pytest.mark.parametrize("phase", ["before", "epoch_end", "after", None])
def test_missing_phase_image_or_model_still_blocks_completion(phase):
    program, events = protocol_case()
    index = next(
        i
        for i, event in enumerate(events)
        if event.type == "artifact_created" and event.payload.get("phase") == phase
    )
    del events[index]
    assert not artifacts_complete(program, events, lambda record: True)


@pytest.mark.parametrize("damage", ["producer", "phase", "epoch", "empty", "duplicate"])
def test_invalid_artifact_identity_or_content_still_blocks_completion(damage):
    program, events = protocol_case()
    image = next(
        event
        for event in events
        if event.type == "artifact_created" and event.payload.get("phase") == "epoch_end"
    )
    if damage == "producer":
        image.payload["producerBlockId"] = program.training.body[0].id
        image.block_id = program.training.body[0].id
    elif damage == "phase":
        image.payload["phase"] = "after"
    elif damage == "epoch":
        image.payload["epoch"] = 3
    elif damage == "empty":
        image.payload["sizeBytes"] = 0
    else:
        events.append(image.model_copy(deep=True))
    assert not artifacts_complete(program, events, lambda record: True)


def test_failed_file_verification_still_blocks_completion():
    program, events = protocol_case()
    assert not artifacts_complete(program, events, lambda record: record.kind != "figure")
