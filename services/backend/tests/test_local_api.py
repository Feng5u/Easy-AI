"""Authenticated Main-only HTTP contracts, without torch or a training launch."""

import json
import select
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.services.local_workspace import LocalWorkspace
from test_run_views import png, register_image


def test_authenticated_native_selection_create_save_compile_and_roles(tmp_path):
    workspace = LocalWorkspace(tmp_path / "owned-state")
    client = TestClient(create_app("test-token", workspace=workspace))
    headers = {"Authorization": "Bearer test-token"}
    root = tmp_path / "chosen project"
    root.mkdir()
    try:
        assert client.get("/api/v1/local/session").status_code == 401
        assert client.get("/api/v1/local/session", headers=headers).json() is None
        selected = client.post(
            "/api/v1/local/selections", json={"kind": "project", "path": str(root)}, headers=headers
        )
        assert selected.status_code == 200
        identity = selected.json()["selectionId"]
        created = client.post(
            "/api/v1/projects",
            json={"selectionId": identity, "name": "课堂项目", "template": "mnist-cnn"},
            headers=headers,
        )
        assert created.status_code == 200
        project = created.json()["project"]
        assert not created.json()["readOnly"]
        assert (
            client.post(
                "/api/v1/projects",
                json={"selectionId": identity, "name": "overwrite"},
                headers=headers,
            ).status_code
            == 409
        )
        project["name"] = "changed"
        saved = client.put(
            f"/api/v1/projects/{project['projectId']}",
            json={"project": project, "expectedRevision": 1},
            headers=headers,
        )
        assert saved.status_code == 200 and saved.json()["project"]["revision"] == 2
        assert (
            client.put(
                f"/api/v1/projects/{project['projectId']}",
                json={"project": project, "expectedRevision": 1},
                headers=headers,
            ).status_code
            == 412
        )
        current = saved.json()["project"]
        compiled = client.post(
            f"/api/v1/projects/{project['projectId']}/compile",
            json={"project": current, "requestId": 3},
            headers=headers,
        )
        assert compiled.status_code == 200 and compiled.json()["runnable"]
        assert client.get("/api/v1/local/activity", headers=headers).json() == {"activeRunIds": []}
        assert (
            client.post(
                "/api/v1/projects/open", json={"selectionId": "unknown"}, headers=headers
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/v1/local/selections",
                json={"kind": "project", "path": "relative"},
                headers=headers,
            ).status_code
            == 422
        )
        wrong = client.post(
            "/api/v1/local/selections", json={"kind": "data", "path": str(root)}, headers=headers
        ).json()
        assert (
            client.post(
                "/api/v1/projects/open", json={"selectionId": wrong["selectionId"]}, headers=headers
            ).status_code
            == 422
        )
    finally:
        workspace.close()


def test_run_views_routes_are_authenticated_bound_to_ids_and_return_png(owned):
    run, _ = register_image(owned, png())
    client = TestClient(create_app("test-token", owned[1]))
    headers = {"Authorization": "Bearer test-token"}
    base = f"/api/v1/runs/{run.run_id}"
    assert client.get(base + "/source").status_code == 401
    source = client.get(base + "/source", headers=headers)
    assert (
        source.status_code == 200
        and source.json()["projectRevision"] == run.config.project_revision
    )
    assert source.json()["codeHash"] == run.config.code_hash
    assert client.get(base + "/logs?stdoutAfter=-1", headers=headers).status_code == 422
    assert client.get(base + "/logs", headers=headers).json()["stdoutAfter"] == 0
    records = client.get(base + "/artifacts", headers=headers).json()
    assert len(records) == 1 and records[0]["artifactId"] == "image-id"
    image = client.get(base + "/artifacts/image-id/content", headers=headers)
    assert image.status_code == 200 and image.content == png()
    assert image.headers["content-type"] == "image/png"
    assert image.headers["x-content-type-options"] == "nosniff"
    assert client.get(base + "/artifacts/missing/content", headers=headers).status_code == 404


def test_storage_root_handshake_starts_local_routes_and_exits_on_eof(tmp_path):
    token = "ab" * 32
    child = subprocess.Popen(
        [sys.executable, "-m", "easyai.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert child.stdin is not None and child.stdout is not None
    child.stdin.write(
        json.dumps({"token": token, "storageRoot": str(tmp_path / "main-state")}).encode() + b"\n"
    )
    child.stdin.flush()
    try:
        if sys.platform != "win32":
            assert select.select([child.stdout], [], [], 10)[0], "sidecar ready timed out"
        ready = json.loads(child.stdout.readline())
        from urllib.request import Request, urlopen

        with urlopen(
            Request(
                f"http://127.0.0.1:{ready['port']}/api/v1/local/session",
                headers={"Authorization": f"Bearer {token}"},
            ),
            timeout=3,
        ) as response:
            assert json.load(response) is None
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=3)
        assert child.returncode == 0


def test_run_post_uses_typed_selections_idempotency_and_snapshot_boundary(tmp_path, monkeypatch):
    from test_local_workspace import idx

    workspace = LocalWorkspace(tmp_path / "owned-state")
    client = TestClient(create_app("test-token", workspace=workspace))
    headers = {"Authorization": "Bearer test-token", "Idempotency-Key": "one-request"}
    root = tmp_path / "chosen-project"
    root.mkdir()
    try:
        native = workspace.select("project", root)
        session = workspace.create(native.selection_id, "pipeline")
        project = session.project
        idx(root / "data")
        python = workspace.select("python", Path(sys.executable))
        data = workspace.select("data", root / "data")
        from easyai.compiler.pipeline import compile_project

        body = {
            "expectedRevision": project.revision,
            "expectedProgramHash": compile_project(project).result.program_hash,
            "pythonSelectionId": python.selection_id,
            "dataSelectionId": data.selection_id,
        }
        url = f"/api/v1/projects/{project.project_id}/runs"
        assert (
            client.post(url, json=body, headers={"Authorization": "Bearer test-token"}).status_code
            == 422
        )
        assert (
            client.post(
                url, json=body | {"pythonSelectionId": "unregistered"}, headers=headers
            ).status_code
            == 404
        )
        assert (
            client.post(
                url, json=body | {"pythonSelectionId": data.selection_id}, headers=headers
            ).status_code
            == 422
        )
        monkeypatch.setattr("easyai.services.local_workspace.probe_python", lambda *args: {})
        # Stop at the process launch boundary: prepare is real and persists the
        # snapshot/config, while this pure HTTP suite cannot execute training code.
        monkeypatch.setattr(workspace.runs, "start", workspace.runs.get)
        accepted = client.post(url, json=body, headers=headers)
        assert accepted.status_code == 202
        run = accepted.json()
        identity = run["runId"]
        assert Path(run["config"]["runRoot"], "snapshot/project.easyai.json").is_file()
        assert client.get("/api/v1/local/activity", headers=headers).json() == {
            "activeRunIds": [identity]
        }
        assert client.post(url, json=body, headers=headers).json()["runId"] == identity
        assert (
            client.post(f"/api/v1/runs/{identity}/cancel", headers=headers).json()["status"]
            == "CANCELLED"
        )
        project.name = "later edit"
        workspace.save(project.project_id, project, 1)
        assert client.post(url, json=body, headers=headers).json()["status"] == "CANCELLED"
        assert (
            client.post(url, json=body | {"expectedRevision": 99}, headers=headers).status_code
            == 409
        )
    finally:
        workspace.close()
