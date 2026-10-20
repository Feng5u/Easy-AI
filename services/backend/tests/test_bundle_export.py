"""Saved snapshot export, no selected Python/data and no training execution."""

import hashlib
import json
from uuid import UUID

from fastapi.testclient import TestClient
import pytest

from easyai.api import create_app
from easyai.compiler.pipeline import compile_project
from easyai.services.local_workspace import LocalWorkspace


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Code export must never probe an environment or launch training")

    monkeypatch.setattr("easyai.services.local_workspace.probe_python", forbidden)
    workspace = LocalWorkspace(tmp_path / "state")
    root = tmp_path / "project"
    root.mkdir()
    project = workspace.create(workspace.select("project", root).selection_id, "saved code").project
    parent = tmp_path / "native export"
    parent.mkdir()
    (parent / "private-unrelated").write_text("not-part-of-the-bundle")
    compilation = compile_project(project)
    try:
        yield workspace, root, project, parent, compilation
    finally:
        workspace.close()


def test_authenticated_export_of_exact_saved_revision_contains_complete_portable_bundle(prepared):
    workspace, root, project, parent, compilation = prepared
    before = (root / "project.easyai.json").read_bytes()
    client = TestClient(create_app("bundle-test-token", workspace=workspace))
    body = dict(
        projectId=project.project_id,
        expectedRevision=project.revision,
        expectedProgramHash=compilation.result.program_hash,
        parentPath=str(parent),
    )
    assert client.post("/api/v1/local/export-bundle", json=body).status_code == 401
    headers = {"Authorization": "Bearer bundle-test-token"}
    assert (
        client.post(
            "/api/v1/local/export-bundle", json={**body, "project": {}}, headers=headers
        ).status_code
        == 422
    )
    response = client.post("/api/v1/local/export-bundle", json=body, headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert str(parent) not in response.text and "parentPath" not in result
    assert (
        result["projectId"] == project.project_id and result["projectRevision"] == project.revision
    )
    exported = parent / result["directoryName"]
    manifest = json.loads((exported / "bundle.json").read_text())
    assert manifest["bundleHash"] == result["bundleHash"]
    assert manifest["programHash"] == result["programHash"] == compilation.result.program_hash
    assert (exported / "code/train.py").read_text() == compilation.result.code
    assert {
        "code/easyai_runtime.py",
        "code/entry.py",
        "code/supervisor.py",
        "code/managed.py",
        "code/portable_journal.py",
        "code/source-map.json",
        "project.easyai.json",
        "program.ir.json",
        "README.md",
        "ENVIRONMENT.md",
    } <= set(manifest["files"])
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((exported / name).read_bytes()).hexdigest() == digest
    assert json.loads((exported / "project.easyai.json").read_text()) == project.model_dump(
        mode="json", by_alias=True
    )
    assert not any(p.name.endswith(".tmp") for p in exported.iterdir())
    assert "not-part-of-the-bundle" not in "".join(
        p.read_text() for p in exported.rglob("*") if p.is_file()
    )
    assert not workspace.runs._ledger.entries
    assert (root / "project.easyai.json").read_bytes() == before


@pytest.mark.parametrize("change", ["revision", "hash", "current"])
def test_stale_identity_refuses_before_creating_any_output(prepared, tmp_path, change):
    workspace, _, project, parent, compilation = prepared
    revision = project.revision
    digest = compilation.result.program_hash
    if change == "revision":
        revision += 1
    elif change == "hash":
        digest = "0" * 64
    else:
        other = tmp_path / "other"
        other.mkdir()
        workspace.create(workspace.select("project", other).selection_id, "other")
    with pytest.raises((ValueError, KeyError)):
        workspace.export_code_bundle(project.project_id, revision, digest, parent)
    assert [p.name for p in parent.iterdir()] == ["private-unrelated"]


def test_never_merges_existing_directory_or_follows_parent_link(prepared, tmp_path, monkeypatch):
    workspace, _, project, parent, compilation = prepared
    chosen = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    monkeypatch.setattr("easyai.services.local_workspace.uuid4", lambda: chosen)
    occupied = parent / f"easyai-code-{chosen}"
    occupied.mkdir()
    marker = occupied / "preserved"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        workspace.export_code_bundle(
            project.project_id, project.revision, compilation.result.program_hash, parent
        )
    assert list(occupied.iterdir()) == [marker] and marker.read_text() == "keep"
    link = tmp_path / "link"
    link.symlink_to(parent, target_is_directory=True)
    with pytest.raises((OSError, ValueError)):
        workspace.export_code_bundle(
            project.project_id, project.revision, compilation.result.program_hash, link
        )


def test_mid_export_failure_preserves_partial_directory_without_completion_manifest(
    prepared, monkeypatch
):
    workspace, _, project, parent, compilation = prepared
    from easyai.security.remote_cache import _PosixDirectory

    original = _PosixDirectory.open_file

    def broken(self, name, access="read"):
        if name == "train.py":
            raise OSError("synthetic disk failure")
        return original(self, name, access)

    monkeypatch.setattr(_PosixDirectory, "open_file", broken)
    with pytest.raises(OSError, match="synthetic disk failure"):
        workspace.export_code_bundle(
            project.project_id, project.revision, compilation.result.program_hash, parent
        )
    outputs = list(parent.glob("easyai-code-*"))
    assert len(outputs) == 1 and not (outputs[0] / "bundle.json").exists()
    assert (parent / "private-unrelated").read_text() == "not-part-of-the-bundle"
    assert not workspace.runs._ledger.entries
