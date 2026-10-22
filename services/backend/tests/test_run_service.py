"""Snapshot protocol tests use real owned files; no fake training Runner."""

import json
import sys
from pathlib import Path

import pytest

from easyai.domain.contracts import ProjectDocument
from easyai.services.run_service import RunService


def prepare(owned, key="one", revision=None, phash=None):
    project, service, doc, expected, data = owned
    return service.prepare(
        project, revision or doc.revision, phash or expected, key, Path(sys.executable), data
    )


def test_snapshot_is_exact_immutable_and_editing_project_does_not_change_old_source(owned):
    project, service, doc, _, _ = owned
    run = prepare(owned)
    snapshot = Path(run.config.run_root) / "snapshot/project.easyai.json"
    before = snapshot.read_bytes()
    edited = doc.model_copy(deep=True)
    edited.name = "later edit"
    project.save(edited, doc.revision)
    assert snapshot.read_bytes() == before
    assert ProjectDocument.model_validate_json(before).name != edited.name
    assert service.get(run.run_id).config.project_revision == doc.revision
    service._verify_snapshot(run.run_id)


def test_revision_hash_idempotency_and_global_active_guards(owned):
    with pytest.raises(ValueError, match="REVISION_CONFLICT"):
        prepare(owned, revision=999)
    with pytest.raises(ValueError, match="HASH_CONFLICT"):
        prepare(owned, phash="0" * 64)
    first = prepare(owned)
    assert prepare(owned).run_id == first.run_id
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        prepare(owned, phash="0" * 64)
    with pytest.raises(ValueError, match="ACTIVE_CONFLICT"):
        prepare(owned, key="different")
    assert owned[1].cancel(first.run_id).status == "CANCELLED"
    assert owned[1].cancel(first.run_id).status == "CANCELLED"
    assert prepare(owned, key="different").run_id != first.run_id


@pytest.mark.parametrize(
    "file",
    ["code/train.py", "code/easyai_runtime.py", "snapshot/project.easyai.json", "run-config.json"],
)
def test_tampered_snapshot_bundle_and_config_cannot_start(owned, file):
    run = prepare(owned)
    target = Path(run.config.run_root) / file
    if file == "run-config.json":
        config = json.loads(target.read_bytes())
        config["seed"] += 1
        target.write_text(json.dumps(config))
    else:
        target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError):
        owned[1].start(run.run_id)
    assert owned[1].get(run.run_id).status == "CREATED"


def test_restart_keeps_idempotency_without_automatically_starting_process(owned):
    project, service, _, _, _ = owned
    first = prepare(owned)
    root = service.root
    service.close()
    recovered = RunService(root)
    try:
        assert recovered.get(first.run_id).status == "CREATED"
        assert recovered.get(first.run_id).connection_state == "disconnected"
        assert (
            recovered.prepare(
                project,
                first.config.project_revision,
                first.config.program_hash,
                "one",
                Path(sys.executable),
                Path(first.config.data_root),
            ).run_id
            == first.run_id
        )
        assert recovered.events(first.run_id)[0].payload["status"] == "CREATED"
    finally:
        recovered.close()


def test_store_has_single_owner_and_returns_detached_contracts(owned):
    service = owned[1]
    with pytest.raises(ValueError, match="RUN_STORE_HELD"):
        RunService(service.root)
    run = prepare(owned)
    run.status = "SUCCEEDED"
    assert service.get(run.run_id).status == "CREATED"


def test_authenticated_sse_replays_persisted_events_after_cursor(owned):
    from fastapi.testclient import TestClient
    from easyai.api import create_app

    service = owned[1]
    run = prepare(owned)
    client = TestClient(create_app("test-token", service))
    url = f"/api/v1/runs/{run.run_id}"
    assert client.get(url + "/events").status_code == 401
    headers = {"Authorization": "Bearer test-token"}
    assert client.post(url + "/cancel", headers=headers).json()["status"] == "CANCELLED"
    response = client.get(url + "/events?after=1", headers=headers)
    assert response.status_code == 200 and response.headers["content-type"].startswith(
        "text/event-stream"
    )
    assert "id: 1\n" not in response.text and "id: 2\n" in response.text
    records = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [r["seq"] for r in records] == [2]
    assert records[0]["payload"]["status"] == "CANCELLED"
    assert client.get(url + "/events?after=-1", headers=headers).status_code == 422
    assert client.get("/api/v1/runs/missing/events", headers=headers).status_code == 404


def test_selected_venv_python_entry_is_preserved_not_resolved_to_base(owned, tmp_path):
    import venv

    interpreter_root = tmp_path / "独立 venv"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(interpreter_root)
    selected = interpreter_root / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    project, service, doc, phash, data = owned
    run = service.prepare(project, doc.revision, phash, "venv-entry", selected, data)
    assert run.config.python_executable == str(selected)
    if sys.platform != "win32":
        assert selected.resolve() != selected


@pytest.mark.parametrize("directory", ["logs", "metrics"])
def test_recovered_child_directory_symlink_cannot_create_or_write_outside(
    owned, tmp_path, directory
):
    service = owned[1]
    run = prepare(owned)
    service.close()
    child = Path(run.config.run_root) / directory
    child.rename(child.with_name(directory + "-preserved"))
    outside = tmp_path / "outside"
    outside.mkdir()
    child.symlink_to(outside, target_is_directory=True)
    recovered = RunService(service.root)
    try:
        with pytest.raises(ValueError, match="RUN_PATH_FORBIDDEN"):
            recovered.events(run.run_id)
        assert list(outside.iterdir()) == []
    finally:
        recovered.close()
