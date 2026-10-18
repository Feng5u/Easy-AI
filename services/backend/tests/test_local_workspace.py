"""Owned local workflow tests; import probes/launches never run real torch here."""

import struct
import sys
import os
import json
import signal
import threading
import time
from pathlib import Path

import pytest

from easyai.compiler.pipeline import compile_project
from easyai.domain.desktop import RunStartRequest
from easyai.services.local_workspace import LocalWorkspace, preflight_data


@pytest.fixture
def workspace(tmp_path):
    store = LocalWorkspace(tmp_path / "owned-state")
    try:
        yield store
    finally:
        store.close()


def idx(root: Path) -> None:
    raw = root / "MNIST/raw"
    raw.mkdir(parents=True)
    for split in ("train", "t10k"):
        (raw / f"{split}-images-idx3-ubyte").write_bytes(
            struct.pack(">IIII", 2051, 1, 28, 28) + bytes(784)
        )
        (raw / f"{split}-labels-idx1-ubyte").write_bytes(struct.pack(">II", 2049, 1) + b"\x00")


def created(workspace, tmp_path):
    root = tmp_path / "学生 project"
    root.mkdir()
    selection = workspace.select("project", root)
    return root, workspace.create(selection.selection_id, "入门实验")


def test_create_open_save_and_no_existing_data_overwrite(workspace, tmp_path):
    root = tmp_path / "existing directory"
    root.mkdir()
    (root / "data").mkdir()
    sentinel = root / "data/prepared"
    sentinel.write_bytes(b"teacher-prepared")
    choice = workspace.select("project", root)
    assert workspace.current() is None
    session = workspace.create(choice.selection_id, "课堂项目")
    assert not session.read_only and sentinel.read_bytes() == b"teacher-prepared"
    assert workspace.current() == session
    assert workspace.open(choice.selection_id) == session
    with pytest.raises(ValueError, match="PROJECT_ALREADY_EXISTS"):
        workspace.create(choice.selection_id, "overwrite")
    changed = session.project.model_copy(deep=True)
    changed.name = "new name"
    saved = workspace.save(changed.project_id, changed, changed.revision)
    assert saved.project.revision == 2 and saved.project.name == "new name"
    with pytest.raises(ValueError, match="PROJECT_REVISION_CONFLICT"):
        workspace.save(changed.project_id, changed, 1)
    assert sentinel.read_bytes() == b"teacher-prepared"


def test_external_project_lock_is_reported_readonly(tmp_path):
    first = LocalWorkspace(tmp_path / "first-store")
    second = LocalWorkspace(tmp_path / "second-store")
    try:
        root, original = created(first, tmp_path)
        selected = second.select("project", root / "project.easyai.json")
        opened = second.open(selected.selection_id)
        assert opened.read_only and opened.reason == "PROJECT_LOCK_HELD"
        with pytest.raises(ValueError, match="PROJECT_READ_ONLY"):
            second.save(original.project.project_id, original.project, 1)
        assert first.current() == original
    finally:
        first.close()
        second.close()


def test_unsupported_project_is_preserved_and_selection_roles_are_enforced(workspace, tmp_path):
    root = tmp_path / "future"
    root.mkdir()
    raw = b'{"schemaVersion":999,"unknown":"keep"}'
    (root / "project.easyai.json").write_bytes(raw)
    choice = workspace.select("project", root)
    unsupported = workspace.open(choice.selection_id)
    assert unsupported.project is None and unsupported.read_only
    assert unsupported.raw_text == raw.decode()
    assert (root / "project.easyai.json").read_bytes() == raw and not (root / ".easyai").exists()
    data = workspace.select("data", root)
    with pytest.raises(ValueError, match="KIND_MISMATCH"):
        workspace.open(data.selection_id)
    with pytest.raises(KeyError):
        workspace.open("unregistered-id")
    with pytest.raises(ValueError, match="SELECTION_INVALID"):
        workspace.select("python", Path("relative-python"))


def test_python_selection_preserves_venv_entry_and_does_not_execute(
    workspace, tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Selection must not execute a Python probe")

    monkeypatch.setattr("easyai.services.local_workspace.probe_python", forbidden)
    entry = tmp_path / "selected-python"
    entry.symlink_to(Path(sys.executable))
    selected = workspace.select("python", entry)
    assert workspace._selection(selected.selection_id, "python") == entry


def test_preflight_is_readonly_validates_headers_and_does_not_download(tmp_path):
    with pytest.raises(ValueError, match="DATASET_MISSING_NO_DOWNLOAD"):
        preflight_data(tmp_path, {"MNIST"})
    assert list(tmp_path.iterdir()) == []
    idx(tmp_path)
    preflight_data(tmp_path, {"MNIST"})
    labels = tmp_path / "MNIST/raw/train-labels-idx1-ubyte"
    labels.write_bytes(struct.pack(">II", 2049, 2) + b"\x00")
    with pytest.raises(ValueError, match="DATASET_IDX_INVALID"):
        preflight_data(tmp_path, {"MNIST"})
    with pytest.raises(ValueError, match="DATASET_MISSING_NO_DOWNLOAD"):
        preflight_data(tmp_path, {"CIFAR10"})


def test_start_checks_saved_revision_before_probe_and_reaches_real_run_service(
    workspace, tmp_path, monkeypatch
):
    root, session = created(workspace, tmp_path)
    data = root / "data"
    idx(data)
    python = workspace.select("python", Path(sys.executable))
    binding = workspace.select("data", data)
    request = RunStartRequest(
        expected_revision=1,
        expected_program_hash=compile_project(session.project).result.program_hash,
        python_selection_id=python.selection_id,
        data_selection_id=binding.selection_id,
    )
    calls = []
    monkeypatch.setattr(
        "easyai.services.local_workspace.probe_python", lambda *args: calls.append("probe") or {}
    )
    with pytest.raises(ValueError, match="REVISION_CONFLICT"):
        workspace.start(
            session.project.project_id, request.model_copy(update={"expected_revision": 2}), "key"
        )
    assert calls == []

    # A launch sentinel proves real snapshot/RunService staging, without substituting
    # a production fake Runner or importing torch in this unit suite.
    def sentinel(run_id):
        assert workspace.runs.get(run_id).status == "CREATED"
        raise RuntimeError("launch-boundary")

    monkeypatch.setattr(workspace.runs, "start", sentinel)
    with pytest.raises(RuntimeError, match="launch-boundary"):
        workspace.start(session.project.project_id, request, "key")
    assert calls == ["probe"] and len(workspace.runs._ledger.entries) == 1
    identity = next(iter(workspace.runs._ledger.entries))
    workspace.runs.cancel(identity)
    edited = session.project.model_copy(update={"name": "later edit"})
    workspace.save(edited.project_id, edited, 1)
    assert workspace.start(edited.project_id, request, "key").status == "CANCELLED"
    assert calls == ["probe"]


def test_python_probe_output_is_drained_with_a_hard_cap_without_importing_torch(
    tmp_path, monkeypatch
):
    import subprocess
    from easyai.services.local_workspace import probe_python

    original = subprocess.Popen

    def standard_library_fixture(_argv, **kwargs):
        # Substitute only the import-probe process in this unit test. Its output
        # exceeds the cap and keeps writing, so an after-exit size check would hang.
        return original(
            [sys.executable, "-I", "-B", "-c", "import os\nwhile True: os.write(1,b'x'*4096)"],
            **kwargs,
        )

    monkeypatch.setattr(
        "easyai.services.local_workspace.subprocess.Popen", standard_library_fixture
    )
    with pytest.raises(ValueError, match="ENVIRONMENT_IMPORT_FAILED"):
        probe_python(Path(sys.executable), tmp_path / "app-owned-probe-cache")


def test_python_probe_normal_leader_exit_returns_marker_and_retires_readers(tmp_path, monkeypatch):
    import subprocess
    from easyai.services.local_workspace import probe_python

    original = subprocess.Popen
    marker = {
        "python": sys.executable,
        "prefix": sys.prefix,
        "torch": "fixture",
        "torchvision": "fixture",
        "matplotlib": "fixture",
    }
    before = {thread.ident for thread in threading.enumerate()}

    def standard_library_fixture(_argv, **kwargs):
        return original(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                "print(" + repr("EASYAI_PROBE:" + json.dumps(marker)) + ",flush=True)",
            ],
            **kwargs,
        )

    monkeypatch.setattr(
        "easyai.services.local_workspace.subprocess.Popen", standard_library_fixture
    )
    assert probe_python(Path(sys.executable), tmp_path / "owned-cache") == marker
    assert not [
        thread
        for thread in threading.enumerate()
        if thread.ident not in before and "drain" in thread.name
    ]


@pytest.mark.skipif(os.name != "posix", reason="POSIX owned process group cleanup")
def test_python_probe_reaps_owned_group_when_leader_exits_before_inherited_pipes(tmp_path):
    from easyai.services.local_workspace import probe_python

    identities = tmp_path / "probe-processes.json"
    selected = tmp_path / "fixture-python"
    selected.write_text(
        f"#!{sys.executable}\n"
        "import json,os,subprocess,sys\nfrom pathlib import Path\n"
        "child=subprocess.Popen([sys.executable,'-I','-B','-c','import time; time.sleep(45)'])\n"
        f"Path({str(identities)!r}).write_text(json.dumps({{'leader':os.getpid(),'child':child.pid}}))\n"
        "print('EASYAI_PROBE:'+json.dumps({'python':sys.executable,'prefix':sys.prefix,"
        "'torch':'fixture','torchvision':'fixture','matplotlib':'fixture'}),flush=True)\n"
        "os._exit(0)\n",
        encoding="utf-8",
    )
    selected.chmod(0o700)
    previous = {thread.ident for thread in threading.enumerate()}

    def still_running(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        status = Path(f"/proc/{pid}/stat")
        return not (status.exists() and status.read_text().split()[2] == "Z")

    try:
        with pytest.raises(ValueError, match="ENVIRONMENT_PROBE_TIMEOUT"):
            probe_python(selected, tmp_path / "owned-cache")
        launched = json.loads(identities.read_text())
        deadline = time.monotonic() + 1
        while still_running(launched["child"]) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not still_running(launched["child"]), "probe left its managed grandchild running"
        assert not [
            thread
            for thread in threading.enumerate()
            if thread.ident not in previous and "drain" in thread.name
        ]
    finally:
        if identities.exists():
            launched = json.loads(identities.read_text())
            try:
                os.killpg(launched["leader"], signal.SIGKILL)
            except ProcessLookupError:
                pass
