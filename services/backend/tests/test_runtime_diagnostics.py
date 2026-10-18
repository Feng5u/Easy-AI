"""Stdlib-only error fixtures; no training, arbitrary execution API or live SSH."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app

from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import Event, SourceSpan
from easyai.domain.desktop import RunSource
from easyai.services.run_views import RunViews
from easyai.services.runtime_diagnostics import locate_failure
from test_run_service import prepare


def fixture_failure(tmp_path, owned):
    code_dir = tmp_path / "error-fixture"
    code_dir.mkdir()
    for name in ("entry.py", "easyai_runtime.py"):
        shutil.copyfile(SOURCE_ROOT / "runtime" / name, code_dir / name)
    code = "def outer():\n    def inner():\n        missing_variable\n    inner()\nouter()\n"
    generated = code_dir / "train.py"
    generated.write_text(code)
    process = subprocess.run(
        [sys.executable, str(code_dir / "entry.py")], capture_output=True, text=True, check=False
    )
    assert process.returncode == 1 and "NameError" in process.stderr
    record = json.loads(process.stdout.removeprefix("@@EASYAI_EVENT@@"))
    event = Event(
        run_id="fixture",
        seq=1,
        source="runtime",
        source_seq=1,
        timestamp="test",
        type="runtime_error",
        block_id="training",
        payload=record["payload"],
    )
    snapshot = owned[2]
    model = snapshot.workspaces.model.blocks.blocks[0]["id"]
    training = snapshot.workspaces.training.blocks.blocks[0]["id"]
    source = RunSource(
        project_revision=snapshot.revision,
        program_hash="a" * 64,
        code_hash=hashlib.sha256(generated.read_bytes()).hexdigest(),
        code=code,
        snapshot=snapshot,
        source_map=[
            SourceSpan(
                start_line=1,
                end_line=5,
                origin={"blockId": training, "workspace": "training"},
                kind="scaffold",
            ),
            SourceSpan(
                start_line=2,
                end_line=4,
                origin={"blockId": training, "workspace": "training"},
                kind="semantic",
            ),
            SourceSpan(
                start_line=3,
                end_line=3,
                origin={"blockId": model, "workspace": "model"},
                kind="semantic",
            ),
        ],
    )
    return event, source, str(generated)


def test_actual_name_error_frames_select_innermost_generated_frame_and_narrowest_span(
    tmp_path, owned
):
    event, source, generated = fixture_failure(tmp_path, owned)
    original = event.model_dump_json()
    assert event.payload["variableName"] == "missing_variable"
    assert event.payload["generatedCodeHash"] == source.code_hash
    assert event.payload["frames"][-1] == {"filename": generated, "lineno": 3, "function": "inner"}
    result = locate_failure(event, source, generated)
    assert result["precision"] == "semantic" and result["line"] == 3
    assert result["origin"] == source.source_map[-1].origin.model_dump(by_alias=True)
    assert event.model_dump_json() == original
    # A deeper external file with the same basename must not displace our own frame.
    event.payload["frames"].append(
        {"filename": "/external/train.py", "lineno": 1, "function": "external"}
    )
    assert locate_failure(event, source, generated) == result


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("runtime_hash", "RUNTIME_CODE_UNVERIFIED"),
        ("generated_file", "FILE_IDENTITY_MISMATCH"),
        ("external_only", "NO_GENERATED_FRAME"),
        ("library_only", "NO_GENERATED_FRAME"),
        ("legacy", "FRAMES_MISSING"),
        ("line", "LINE_OUT_OF_RANGE"),
        ("bool_line", "FRAMES_INVALID"),
        ("foreign_origin", "SOURCE_MAP_INVALID"),
    ],
)
def test_uncertain_evidence_never_guesses_event_block(tmp_path, owned, mutation, reason):
    event, source, generated = fixture_failure(tmp_path, owned)
    if mutation == "runtime_hash":
        event.payload["generatedCodeHash"] = "f" * 64
    elif mutation == "generated_file":
        event.payload["generatedFile"] = "/external/train.py"
    elif mutation in {"external_only", "library_only"}:
        event.payload["frames"] = [
            {
                "filename": "/external/"
                + ("train.py" if mutation == "external_only" else "lib.py"),
                "lineno": 3,
                "function": "inner",
            }
        ]
    elif mutation == "legacy":
        event.payload.pop("frames")
    elif mutation == "line":
        event.payload["frames"] = [{"filename": generated, "lineno": 999, "function": "inner"}]
    elif mutation == "bool_line":
        event.payload["frames"][-1]["lineno"] = True
    elif mutation == "foreign_origin":
        source.source_map[-1].origin.block_id = "private-foreign-id"
    original = event.model_dump_json()
    result = locate_failure(event, source, generated)
    assert result["precision"] == "none" and result["origin"] is None and result["line"] is None
    assert result["reason"] == reason
    assert "external" not in json.dumps(result) and "private" not in json.dumps(result)
    assert event.model_dump_json() == original


def test_scaffold_and_missing_mapping_are_explicit(tmp_path, owned):
    event, source, generated = fixture_failure(tmp_path, owned)
    source.source_map = source.source_map[:1]
    assert locate_failure(event, source, generated)["precision"] == "scaffold"
    source.source_map = []
    result = locate_failure(event, source, generated)
    assert result["precision"] == "none" and result["reason"] == "NO_SOURCE_SPAN"


@pytest.mark.parametrize(
    "mutation", ["code", "map", "manifest_empty", "manifest_list", "manifest_files"]
)
def test_real_old_run_view_verifies_files_preserves_raw_journal_and_rejects_tampering(
    owned, mutation
):
    run = prepare(owned)
    service = owned[1]
    view = RunViews(service)
    source = view.source(run.run_id)
    span = next(span for span in source.source_map if span.kind == "semantic")
    expected = str(Path(run.config.run_root) / "code/train.py")
    raw = Event(
        run_id=run.run_id,
        seq=1,
        source="runtime",
        source_seq=1,
        timestamp="test",
        type="runtime_error",
        block_id="incorrect-coarse-root",
        payload={
            "exceptionType": "NameError",
            "variableName": "missing",
            "message": "private raw",
            "applicationLocation": {"origin": {"blockId": "spoofed-private-origin"}},
            "generatedFile": expected,
            "generatedCodeHash": source.code_hash,
            "frames": [{"filename": expected, "lineno": span.start_line, "function": "main"}],
        },
    )
    service._journal(run.run_id).ingest(raw)
    service.cancel(run.run_id)  # Settled without ever launching a process; bound the SSE response.
    before = service._journal(run.run_id).after(0)
    if mutation == "code":
        client = TestClient(create_app("diagnostic-test-token", runs=service))
        route = f"/api/v1/runs/{run.run_id}/events"
        assert client.get(route).status_code == 401
        response = client.get(route, headers={"Authorization": "Bearer diagnostic-test-token"})
        assert response.status_code == 200
        delivered = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        failure = next(event for event in delivered if event["type"] == "runtime_error")
        assert failure["payload"]["applicationLocation"]["origin"] == span.origin.model_dump(
            by_alias=True
        )
        assert failure["payload"]["applicationLocation"]["eventSeq"] == failure["seq"]
    result = next(event for event in view.events(run.run_id) if event.type == "runtime_error")
    assert result.payload["applicationLocation"]["origin"] == span.origin.model_dump(by_alias=True)
    assert result.payload["message"] == "private raw"
    assert service._journal(run.run_id).after(0) == before
    # Mutating the actual immutable old generated file invalidates source validation.
    if mutation == "code":
        Path(expected).write_text(source.code + "\n# tampered\n")
    elif mutation == "map":
        target = Path(run.config.run_root) / "code/source-map.json"
        target.write_bytes(target.read_bytes() + b" ")
    else:
        malformed = {"manifest_empty": {}, "manifest_list": [], "manifest_files": {"files": None}}
        (Path(run.config.run_root) / "bundle.json").write_text(json.dumps(malformed[mutation]))
    result = next(event for event in view.events(run.run_id) if event.type == "runtime_error")
    assert result.payload["applicationLocation"]["precision"] == "none"
    assert result.payload["applicationLocation"]["reason"] == "SOURCE_UNVERIFIED"
    assert service._journal(run.run_id).after(0) == before
