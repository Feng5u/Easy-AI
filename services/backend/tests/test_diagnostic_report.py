"""Old-snapshot interpretation and allowlisted reports; no training or outbound I/O."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.domain.contracts import Event
from easyai.services.run_views import RunViews
from easyai.services.runtime_diagnostics import explain_name, frozen_objects
from test_run_service import prepare


def failure(owned):
    run = prepare(owned)
    view = RunViews(owned[1])
    source = view.source(run.run_id)
    span = next(item for item in source.source_map if item.kind == "semantic")
    path = str(Path(run.config.run_root) / "code/train.py")
    event = Event(
        run_id=run.run_id,
        seq=1,
        source="runtime",
        source_seq=1,
        timestamp="test",
        type="runtime_error",
        payload={
            "exceptionType": "NameError",
            "variableName": "train_data",
            "message": "password=synthetic-secret alice@private.invalid /private/home",
            "generatedFile": path,
            "generatedCodeHash": source.code_hash,
            "frames": [{"filename": path, "lineno": span.start_line, "function": "main"}],
            "applicationLocation": {"nameState": "unregistered", "secret": "synthetic-secret"},
        },
    )
    delivered = owned[1]._journal(run.run_id).ingest(event)
    assert delivered is not None
    return run, view, source, delivered


@pytest.mark.parametrize(
    "variant,state,check",
    [
        ("original", "registered", "passed"),
        ("unregistered", "unregistered", "failed"),
        ("missing", "not_matched", "passed"),
        ("ambiguous", "ambiguous", "failed"),
        ("unmapped", "unavailable", "passed"),
        ("other_exception", "unavailable", "passed"),
    ],
)
def test_interpretation_uses_only_frozen_registry_and_requires_verified_location(
    owned, variant, state, check
):
    _, _, source, event = failure(owned)
    data = source.snapshot.workspaces.data.blocks.blocks
    if variant == "unregistered":
        data[1]["extraState"]["easyai"]["registered"] = False
    elif variant == "ambiguous":
        data[3]["fields"]["NAME"] = "train_data"
    elif variant == "missing":
        event.payload["variableName"] = "password=synthetic-secret"
    elif variant == "other_exception":
        event.payload["exceptionType"] = "RuntimeError"
    source.objects, source.reference_check = frozen_objects(source.snapshot)
    before = event.model_dump_json()
    result = explain_name(
        event, source, {"precision": "none" if variant == "unmapped" else "semantic"}
    )
    assert result == {"nameState": state, "referenceCheck": check}
    assert event.model_dump_json() == before
    serialized = json.dumps([item.model_dump(by_alias=True) for item in source.objects])
    assert len(source.objects) == 6
    assert "train_data" not in serialized and "NAME" not in serialized
    assert "synthetic-secret" not in json.dumps(result)


def test_report_is_authenticated_readonly_and_never_serializes_raw_payload_or_names(owned):
    run, view, source, event = failure(owned)
    before = owned[1]._journal(run.run_id).after(0)
    edited = owned[2].model_copy(deep=True)
    edited.workspaces.data.blocks.blocks[1]["fields"]["NAME"] = "CurrentRenamed"
    owned[0].save(edited, edited.revision)
    report = view.report(run.run_id, event.seq).model_dump(by_alias=True)
    assert set(report) == {
        "reportVersion",
        "scope",
        "code",
        "runId",
        "eventSeq",
        "codeHash",
        "projectRevision",
        "precision",
        "nameState",
        "referenceCheck",
        "objectsTotal",
        "registeredTotal",
    }
    assert report["nameState"] == "registered" and report["referenceCheck"] == "passed"
    assert report["objectsTotal"] == report["registeredTotal"] == 6
    assert (
        report["codeHash"] == source.code_hash
        and report["projectRevision"] == source.project_revision
    )
    text = json.dumps(report)
    for secret in (
        "train_data",
        "CurrentRenamed",
        "private",
        "password",
        "synthetic-secret",
        "frames",
        "train.py",
    ):
        assert secret not in text
    client = TestClient(create_app("report-token", runs=owned[1]))
    route = f"/api/v1/runs/{run.run_id}/diagnostics/{event.seq}/report"
    assert client.get(route).status_code == 401
    client.headers.update({"Authorization": "Bearer report-token"})
    assert client.get(route).json() == report
    assert client.get(route.replace(f"/{event.seq}/report", "/0/report")).status_code == 422
    assert client.get(route.replace(f"/{event.seq}/report", "/99/report")).status_code == 404
    assert owned[1]._journal(run.run_id).after(0) == before
    # Evidence is now unverified: refuse claims, still export only fixed safe summary.
    (Path(run.config.run_root) / "bundle.json").write_text("{}")
    degraded = view.report(run.run_id, event.seq).model_dump(by_alias=True)
    assert degraded["precision"] == "none" and degraded["nameState"] == "unavailable"
    assert degraded["referenceCheck"] == "unavailable"
    assert degraded["objectsTotal"] is degraded["registeredTotal"] is None
    assert owned[1]._journal(run.run_id).after(0) == before


def test_invalid_old_graph_is_explicitly_unavailable_and_not_replaced_by_current(owned):
    snapshot = owned[2].model_copy(deep=True)
    snapshot.workspaces.model.blocks.blocks[0]["type"] = "unknown.block"
    assert frozen_objects(snapshot) == ([], "unavailable")
