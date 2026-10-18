"""Synthetic sparse files test only the fail-closed layout gate, never training."""

import os
import pickle
from pathlib import Path
import sys

import pytest

from easyai.services.cifar_preflight import inspect_cifar10_layout
from easyai.services.local_workspace import preflight_data
from easyai.services.local_workspace import LocalWorkspace
from easyai.compiler.pipeline import compile_project
from easyai.domain.desktop import LocalPreflightRequest, RunStartRequest
from fastapi.testclient import TestClient
from easyai.api import create_app


@pytest.fixture
def layout(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("CIFAR preflight must never deserialize pickle")

    monkeypatch.setattr(pickle, "load", forbidden)
    monkeypatch.setattr(pickle, "loads", forbidden)
    folder = tmp_path / "cifar-10-batches-py"
    folder.mkdir()
    # Valid-looking protocol2 followed by a malicious reducer. It is never
    # interpreted; the sparse length merely passes the coarse layout bound.
    header = b"\x80\x02cos\nsystem\n(S'NEVER_EXECUTE'\ntR."
    for name in [*(f"data_batch_{i}" for i in range(1, 6)), "test_batch", "batches.meta"]:
        with (folder / name).open("wb") as stream:
            stream.write(header)
            stream.truncate(30_720_000 if name != "batches.meta" else 128)
    return tmp_path, folder


def test_complete_looking_layout_is_never_ready_and_remains_unchanged(layout):
    root, folder = layout
    before = {p.name: (p.stat(), p.open("rb").read(128)) for p in folder.iterdir()}
    with pytest.raises(ValueError, match="DATASET_CIFAR10_SAFE_PROBE_REQUIRED"):
        preflight_data(root, {"CIFAR10"})
    for path in folder.iterdir():
        info, header = before[path.name]
        assert (path.stat().st_size, path.stat().st_mtime_ns) == (info.st_size, info.st_mtime_ns)
        with path.open("rb") as stream:
            assert stream.read(128) == header


@pytest.mark.parametrize("name", ["data_batch_3", "test_batch", "batches.meta"])
def test_requires_both_splits_and_metadata(layout, name):
    root, folder = layout
    (folder / name).unlink()
    with pytest.raises(ValueError, match="DATASET_MISSING_NO_DOWNLOAD"):
        inspect_cifar10_layout(root)


@pytest.mark.parametrize(
    "failure", ["short", "large", "protocol", "link", "directory", "alias", "fifo"]
)
def test_rejects_invalid_format_and_unsafe_files_without_reading_payload(layout, failure):
    root, folder = layout
    path = folder / "test_batch"
    if failure == "short":
        path.write_bytes(b"\x80\x02.")
    elif failure == "large":
        with path.open("r+b") as stream:
            stream.truncate(40_000_001)
    elif failure == "protocol":
        with path.open("r+b") as stream:
            stream.write(b"\x80\x05")
    else:
        path.unlink()
        if failure == "link":
            path.symlink_to(folder / "data_batch_1")
        elif failure == "directory":
            path.mkdir()
        elif failure == "alias":
            os.link(folder / "data_batch_1", path)
        else:
            if not hasattr(os, "mkfifo"):
                pytest.skip("FIFO fixture requires POSIX")
            os.mkfifo(path)
    with pytest.raises(ValueError, match="DATASET_CIFAR10_FORMAT_INVALID|DATA_PATH_FORBIDDEN"):
        inspect_cifar10_layout(root)


def test_cancellation_checkpoint_stops_before_next_file(layout, monkeypatch):
    root, _ = layout
    calls = 0
    opened = []
    original = os.open

    def record(path, flags):
        opened.append(Path(path).name)
        return original(path, flags)

    def checkpoint():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ValueError("PROJECT_SCOPE_RETIRED")

    monkeypatch.setattr(os, "open", record)
    with pytest.raises(ValueError, match="PROJECT_SCOPE_RETIRED"):
        inspect_cifar10_layout(root, checkpoint)
    assert opened == ["data_batch_1"]


def test_dataset_folder_link_is_rejected(layout):
    root, folder = layout
    folder.rename(root / "real")
    folder.symlink_to(root / "real", target_is_directory=True)
    with pytest.raises(ValueError, match="DATA_PATH_FORBIDDEN"):
        inspect_cifar10_layout(root)


def test_authorized_selection_report_and_start_preserve_unverified_gate(layout, monkeypatch):
    root, _ = layout
    workspace = LocalWorkspace(root / "state")
    calls = []

    def probe(python, cache):
        calls.append(python)
        return dict(
            python=str(python),
            prefix="synthetic",
            torch="synthetic",
            torchvision="synthetic",
            matplotlib="synthetic",
        )

    monkeypatch.setattr("easyai.services.local_workspace.probe_python", probe)
    try:
        project_root = root / "project"
        project_root.mkdir()
        original = workspace.create(
            workspace.select("project", project_root).selection_id, "CIFAR gate"
        )
        document = original.project.model_copy(deep=True)
        pending = list(document.workspaces.data.blocks.blocks) + list(
            document.workspaces.model.blocks.blocks
        )
        while pending:
            node = pending.pop()
            fields = node.get("fields", {})
            if node["type"] == "data.dataset_builtin":
                fields["DATASET_NAME"] = "CIFAR10"
            elif node["type"] == "model.conv2d" and fields["IN_CHANNELS"] == 1:
                fields["IN_CHANNELS"] = 3
            elif node["type"] == "model.linear" and fields["IN_FEATURES"] == 1568:
                fields["IN_FEATURES"] = 2048
            for connection in node.get("inputs", {}).values():
                pending.extend(connection.values())
            if "next" in node:
                pending.append(node["next"]["block"])
        saved = workspace.save(document.project_id, document, document.revision).project
        compilation = compile_project(saved)
        assert compilation.result.runnable
        assert "nn.Conv2d(3, 16" in compilation.result.code
        assert "nn.Linear(2048, 128)" in compilation.result.code
        assert compilation.result.code.count("datasets.CIFAR10(") == 2
        assert compilation.result.code.count("download=False") == 2
        request = LocalPreflightRequest(
            project_id=saved.project_id,
            expected_revision=saved.revision,
            python_selection_id=workspace.select("python", Path(sys.executable)).selection_id,
            data_selection_id=workspace.select("data", root).selection_id,
        )
        client = TestClient(create_app("synthetic-cifar-token", workspace=workspace))
        body = request.model_dump(mode="json", by_alias=True)
        assert client.post("/api/v1/local/preflight", json=body).status_code == 401
        response = client.post(
            "/api/v1/local/preflight",
            json=body,
            headers={"Authorization": "Bearer synthetic-cifar-token"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["datasetNames"] == ["CIFAR10"]
        assert response.json()["data"] == {
            "ok": False,
            "code": "DATASET_CIFAR10_SAFE_PROBE_REQUIRED",
        }
        assert response.json()["environment"]["ok"]
        with pytest.raises(ValueError, match="DATASET_CIFAR10_SAFE_PROBE_REQUIRED"):
            workspace.start(
                saved.project_id,
                RunStartRequest(
                    expected_revision=saved.revision,
                    expected_program_hash=compilation.result.program_hash,
                    python_selection_id=request.python_selection_id,
                    data_selection_id=request.data_selection_id,
                ),
                "synthetic-cifar-no-start",
            )
        assert len(calls) == 1 and not workspace.runs._ledger.entries
    finally:
        workspace.close()
