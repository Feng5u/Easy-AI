"""Explicit read-only preflight. Probe seam never imports torch in this suite."""

import struct
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.domain.desktop import LocalPreflightRequest
from easyai.services.local_workspace import LocalWorkspace


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    workspace = LocalWorkspace(tmp_path / "state")
    root = tmp_path / "课程 project"
    root.mkdir()
    session = workspace.create(workspace.select("project", root).selection_id, "预检")
    data = root / "data"
    raw = data / "MNIST/raw"
    raw.mkdir(parents=True)
    for split in ("train", "t10k"):
        (raw / f"{split}-images-idx3-ubyte").write_bytes(
            struct.pack(">IIII", 2051, 1, 28, 28) + bytes(784)
        )
        (raw / f"{split}-labels-idx1-ubyte").write_bytes(struct.pack(">II", 2049, 1) + b"\0")
    request = LocalPreflightRequest(
        project_id=session.project.project_id,
        expected_revision=1,
        python_selection_id=workspace.select("python", Path(sys.executable)).selection_id,
        data_selection_id=workspace.select("data", data).selection_id,
    )
    calls = []

    def probe(python, cache):
        calls.append(python)
        return dict(
            python=str(python),
            prefix="test-prefix",
            torch="test-torch",
            torchvision="test-vision",
            matplotlib="test-plot",
        )

    monkeypatch.setattr("easyai.services.local_workspace.probe_python", probe)
    try:
        yield workspace, root, request, calls
    finally:
        workspace.close()


def test_explicit_report_reads_data_without_run_or_project_write(prepared):
    workspace, root, request, calls = prepared
    before = {
        path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }
    report = workspace.preflight_local(request)
    assert report.environment.ok and report.data.ok
    assert report.dataset_names == ["MNIST"]
    assert report.versions.torch == "test-torch" and len(calls) == 1
    assert report.python_selection_id == request.python_selection_id
    assert not workspace.runs._ledger.entries
    assert before == {
        path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


@pytest.mark.parametrize("failure", ["missing", "invalid", "symlink", "import"])
def test_environment_and_data_failures_are_independent(prepared, monkeypatch, failure):
    workspace, root, request, calls = prepared
    image = root / "data/MNIST/raw/train-images-idx3-ubyte"
    if failure == "missing":
        image.unlink()
        expected = "DATASET_MISSING_NO_DOWNLOAD"
    elif failure == "invalid":
        image.write_bytes(b"bad")
        expected = "DATASET_IDX_INVALID"
    elif failure == "symlink":
        image.rename(image.with_suffix(".original"))
        image.symlink_to(image.with_suffix(".original"))
        expected = "DATASET_UNREADABLE"
    else:

        def fail(*_):
            raise ValueError("ENVIRONMENT_IMPORT_FAILED")

        monkeypatch.setattr("easyai.services.local_workspace.probe_python", fail)
        expected = "DATASET_READY"
    report = workspace.preflight_local(request)
    assert report.data.code == expected
    assert report.environment.ok == (failure != "import")
    assert report.data.ok == (failure == "import")
    assert not workspace.runs._ledger.entries


def test_unknown_selection_and_wrong_role_never_probe(prepared):
    workspace, _, request, calls = prepared
    with pytest.raises(KeyError, match="LOCAL_SELECTION_NOT_FOUND"):
        workspace.preflight_local(request.model_copy(update={"python_selection_id": "0" * 36}))
    with pytest.raises(ValueError, match="LOCAL_SELECTION_KIND_MISMATCH"):
        workspace.preflight_local(
            request.model_copy(update={"python_selection_id": request.data_selection_id})
        )
    assert not calls


@pytest.mark.parametrize("change", ["project", "revision"])
def test_late_probe_rejected_without_holding_workspace_lock(
    prepared, monkeypatch, tmp_path, change
):
    workspace, _, request, _ = prepared
    entered, release = threading.Event(), threading.Event()

    def blocked(*_):
        entered.set()
        assert release.wait(5)
        return dict(
            python="test", prefix="test", torch="test", torchvision="test", matplotlib="test"
        )

    monkeypatch.setattr("easyai.services.local_workspace.probe_python", blocked)
    with ThreadPoolExecutor() as executor:
        task = executor.submit(workspace.preflight_local, request)
        try:
            assert entered.wait(5)
            with pytest.raises(ValueError, match="LOCAL_PREFLIGHT_BUSY"):
                workspace.preflight_local(request)
            if change == "project":
                other = tmp_path / "other"
                other.mkdir()
                workspace.create(workspace.select("project", other).selection_id, "other")
            else:
                document = workspace.current().project
                workspace.save(document.project_id, document, document.revision)
        finally:
            release.set()
        with pytest.raises(
            (KeyError, ValueError),
            match="PROJECT_NOT_CURRENT|PROJECT_SCOPE_RETIRED|PROJECT_REVISION_CONFLICT",
        ):
            task.result(timeout=5)


def test_authenticated_http_contract_and_no_paths(prepared):
    workspace, _, request, calls = prepared
    client = TestClient(create_app("local-test-token", workspace=workspace))
    body = request.model_dump(mode="json", by_alias=True)
    assert client.post("/api/v1/local/preflight", json=body).status_code == 401
    headers = {"Authorization": "Bearer local-test-token"}
    assert (
        client.post(
            "/api/v1/local/preflight", json={**body, "pythonPath": "/arbitrary"}, headers=headers
        ).status_code
        == 422
    )
    assert not calls
    response = client.post("/api/v1/local/preflight", json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"ok": True, "code": "DATASET_READY"}
    assert response.json()["versions"]["torch"] == "test-torch"
    assert not workspace.runs._ledger.entries


@pytest.mark.parametrize("change", ["project", "aba", "revision"])
def test_http_rechecks_after_worker_before_delivery(prepared, monkeypatch, tmp_path, change):
    import asyncio

    workspace, root, request, _ = prepared
    client = TestClient(create_app("local-test-token", workspace=workspace))
    entered, release = threading.Event(), threading.Event()
    original = asyncio.to_thread

    async def paused(function, *args, **kwargs):
        value = await original(function, *args, **kwargs)
        if function.__name__ == "preflight_local":
            entered.set()
            assert await original(release.wait, 5)
        return value

    monkeypatch.setattr(asyncio, "to_thread", paused)
    with ThreadPoolExecutor() as executor:
        response = executor.submit(
            client.post,
            "/api/v1/local/preflight",
            json=request.model_dump(mode="json", by_alias=True),
            headers={"Authorization": "Bearer local-test-token"},
        )
        try:
            assert entered.wait(5)
            if change == "revision":
                document = workspace.current().project
                workspace.save(document.project_id, document, 1)
            else:
                other = tmp_path / "other"
                other.mkdir()
                workspace.create(workspace.select("project", other).selection_id, "other")
                if change == "aba":
                    workspace.open(workspace.select("project", root).selection_id)
        finally:
            release.set()
        result = response.result(timeout=5)
    assert result.status_code in (404, 412), result.text
    assert "test-torch" not in result.text
