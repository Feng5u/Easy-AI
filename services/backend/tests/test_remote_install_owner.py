"""Synthetic local sources and stdlib children only; no SSH/network/package execution."""

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "runtime/install_owner.py"


@pytest.fixture
def owner():
    spec = importlib.util.spec_from_file_location("remote_install_owner_fixture", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def payload(owner, tmp_path):
    root = tmp_path / "owned-root"
    root.mkdir(mode=0o700)
    (root / ".easyai-install-root.json").write_text(
        json.dumps({"ownedByEasyAI": True, "uid": os.getuid(), "protocolVersion": 1})
    )
    sources = tmp_path / "sources"
    sources.mkdir(mode=0o700)
    modules = sources / "modules"
    modules.mkdir(mode=0o700)
    (modules / "fixture.py").write_text("# never imported source fixture\n")
    wheelhouse = sources / "wheels"
    wheelhouse.mkdir(mode=0o700)

    def archive(name):
        path = sources / name
        path.write_bytes(b"synthetic non-executable archive")
        return {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    return {
        "action": "snapshot",
        "nonce": "synthetic-nonce",
        "configuration": {
            "root": str(root),
            "launcher": archive("launcher"),
            "module_root": str(modules),
            "module_tree_sha256": owner.tree(modules)[0],
            "bootstrap": [archive("python.conda"), archive("pip.conda")],
            "wheelhouse": str(wheelhouse),
            "disk_budget_bytes": 16 * 1024 * 1024,
            "seconds": 3,
            "execution_authorized": True,
            "authorization_expires": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
        "wheels": [],
        "environmentId": str(uuid4()),
        "newEnvironment": True,
        "identity": {
            "projectId": str(uuid4()),
            "targetId": str(uuid4()),
            "targetRevision": 1,
            "endpoint": {"host": "synthetic.invalid", "port": 22},
            "hostFingerprint": "SHA256:" + "A" * 43,
            "username": "synthetic",
        },
    }


def writer(payload):
    return {**copy.deepcopy(payload), "jobId": str(uuid4()), "planHash": "a" * 64}


def rpc(owner, payload, action, **extra):
    return owner.dispatch({**payload, "action": action, **extra})


def allocate(owner, payload):
    rpc(owner, payload, "reserve")
    return rpc(owner, payload, "allocate")


def run_request(payload, source):
    return {
        **payload,
        "phase": str(uuid4()),
        "argv": [sys.executable, "-I", "-B", "-c", source],
        "environment": {},
        "helpers": {
            "managed.py": (ROOT / "services/backend/src/easyai/runtime/managed.py").read_text(),
            "portable_journal.py": (ROOT / "runtime/portable_journal.py").read_text(),
        },
        "helperSource": HELPER.read_text(),
        "files": {"requirements.lock": "# fixture only\n"},
    }


def test_snapshot_is_readonly_stable_and_source_inventory_is_real(owner, payload):
    before = sorted(Path(payload["configuration"]["root"]).rglob("*"))
    first = owner.dispatch(payload)
    second = owner.dispatch({**payload, "nonce": "different"})
    assert first["fingerprint"] == second["fingerprint"]
    assert first["sourceFingerprint"] == second["sourceFingerprint"]
    assert first["prefixIdentity"] is None and first["versions"] == {}
    assert first["pythonVersion"].startswith("3.11.") and first["platform"] == "linux-x86_64-cp311"
    assert first["freeBytes"] > payload["configuration"]["disk_budget_bytes"]
    assert sorted(Path(payload["configuration"]["root"]).rglob("*")) == before
    Path(payload["configuration"]["launcher"]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        owner.dispatch(payload)


@pytest.mark.parametrize(
    "variant", ["symlink-root", "bad-marker", "unsafe-directory", "wheel-escape", "disk"]
)
def test_snapshot_rejects_untrusted_sources_without_writes(
    owner, payload, tmp_path, variant, monkeypatch
):
    root = Path(payload["configuration"]["root"])
    if variant == "symlink-root":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        payload["configuration"]["root"] = str(alias)
    elif variant == "bad-marker":
        (root / ".easyai-install-root.json").write_text("{}")
    elif variant == "unsafe-directory":
        root.chmod(0o777)
    elif variant == "wheel-escape":
        payload["wheels"] = [
            {
                "name": "x",
                "version": "1",
                "filename": "../x.whl",
                "sha256": "a" * 64,
                "downloadBytes": 1,
            }
        ]
    else:

        class Space:
            f_bavail, f_frsize = 1, 1

        monkeypatch.setattr(owner.os, "statvfs", lambda _: Space())
    with pytest.raises((ValueError, OSError)):
        owner.dispatch(payload)
    assert not (root / "training-environments").exists()


def test_claim_allocation_markers_ready_and_closed_jobslots(owner, payload):
    payload = writer(payload)
    first = rpc(owner, payload, "reserve")
    assert first["ack"] and rpc(owner, payload, "reserve")["ack"]
    allocated = rpc(owner, payload, "allocate")
    assert rpc(owner, payload, "allocate")["prefixIdentity"] == allocated["prefixIdentity"]
    rpc(owner, payload, "mark-owned")
    assert not rpc(
        owner, {k: v for k, v in payload.items() if k not in {"jobId", "planHash"}}, "snapshot"
    )["ready"]
    rpc(owner, payload, "mark-ready")
    assert not rpc(
        owner, {k: v for k, v in payload.items() if k not in {"jobId", "planHash"}}, "snapshot"
    )["ready"]
    assert rpc(owner, payload, "release")["ack"]
    assert rpc(owner, payload, "release")["ack"]
    snap = {k: v for k, v in payload.items() if k not in {"jobId", "planHash"}}
    snap["newEnvironment"] = False
    assert rpc(owner, snap, "snapshot")["ready"]
    fresh = {**writer(snap), "planHash": "b" * 64}
    assert rpc(owner, fresh, "reserve")["ack"]
    assert not rpc(owner, fresh, "inspect")["dispatched"]
    old = (
        Path(payload["configuration"]["root"])
        / "environment-creations"
        / payload["environmentId"]
        / "jobs"
        / payload["jobId"]
    )
    assert (old / "closed.json").exists() and (old / "claim.json").exists()


def test_unclosed_reservation_never_taken_over_and_foreign_identity_rejected(owner, payload):
    payload = writer(payload)
    allocate(owner, payload)
    with pytest.raises(ValueError, match="RESERVATION_BUSY"):
        rpc(owner, {**payload, "jobId": str(uuid4())}, "reserve")
    forged = copy.deepcopy(payload)
    forged["identity"]["username"] = "foreign"
    with pytest.raises(ValueError, match="CLAIM_MISMATCH"):
        rpc(owner, forged, "inspect")


def test_metadata_is_read_without_import_and_source_fingerprint_ignores_environment(owner, payload):
    payload = writer(payload)
    allocate(owner, payload)
    rpc(owner, payload, "mark-owned")
    base = (
        Path(payload["configuration"]["root"]) / "training-environments" / payload["environmentId"]
    )
    metadata = base / "lib/python3.11/site-packages/Synthetic-1.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text("Name: Synthetic_Package\nVersion: 1.2.3\n")
    (metadata.parent / "synthetic.py").write_text("raise AssertionError('must never import')")
    snapshot = {k: v for k, v in payload.items() if k not in {"jobId", "planHash"}}
    before = rpc(owner, snapshot, "snapshot")
    (metadata / "METADATA").write_text("Name: Synthetic_Package\nVersion: 2.0\n")
    after = rpc(owner, snapshot, "snapshot")
    assert after["versions"] == {"synthetic-package": "2.0"}
    assert before["sourceFingerprint"] == after["sourceFingerprint"]
    assert before["fingerprint"] != after["fingerprint"]


def test_expired_missing_sources_do_not_block_recovery_or_authorize_execution(owner, payload):
    payload = writer(payload)
    rpc(owner, payload, "reserve")
    Path(payload["configuration"]["launcher"]["path"]).unlink()
    payload["configuration"]["execution_authorized"] = False
    payload["configuration"]["authorization_expires"] = "2000-01-01T00:00:00+00:00"
    payload["newEnvironment"] = False  # Recovery reads the original creation mode from claim.
    for action in ("inspect", "cancel"):
        result = rpc(owner, payload, action)
        assert result["outcome"] == "not_dispatched" and result["quiescent"]
    assert rpc(owner, payload, "release")["ack"]
    with pytest.raises((ValueError, OSError)):
        rpc(owner, payload, "allocate")


def test_launch_intent_precedes_detached_spawn_and_retries_only_inspect(
    owner, payload, monkeypatch
):
    payload = writer(payload)
    allocate(owner, payload)
    run = run_request(payload, "raise AssertionError('not executed in captured test')")
    spawns = []

    def capture(argv, **kwargs):
        root = Path(payload["configuration"]["root"])
        job = root / "environment-creations" / payload["environmentId"] / "jobs" / payload["jobId"]
        assert json.loads((job / "last-phase.json").read_bytes())["phase"] == run["phase"]
        phase = root / "install-processes" / payload["jobId"] / run["phase"]
        assert (phase / "intent.json").exists() and (phase / "code/managed.py").exists()
        assert (phase / "requirements.lock").read_text() == "# fixture only\n"
        assert all((phase / name).is_dir() for name in ("home", "pkgs", "envs", "tmp"))
        assert kwargs["start_new_session"] and kwargs["stdin"] == subprocess.DEVNULL
        spawns.append(argv)
        raise OSError("private launch failure /secret")

    monkeypatch.setattr(owner.subprocess, "Popen", capture)
    first = rpc(owner, run, "run")
    assert first["outcome"] == "unknown" and not first["quiescent"]
    assert rpc(owner, run, "run")["outcome"] == "unknown"
    assert len(spawns) == 1
    with pytest.raises(ValueError, match="UNCONFIRMED"):
        rpc(owner, payload, "release")
    assert rpc(owner, payload, "cancel")["outcome"] == "unknown"
    assert (Path(first["phaseRoot"]) / "install-cancel.request.json").exists()
    with pytest.raises(ValueError, match="UNCONFIRMED"):
        rpc(owner, {**run, "phase": str(uuid4())}, "run")


def test_real_stdlib_managed_owner_closes_before_quiet_receipt(owner, payload, monkeypatch):
    payload = writer(payload)
    allocate(owner, payload)
    run = run_request(
        payload,
        'print(\'@@EASYAI_EVENT@@{"type":"pipeline_completed","blockId":null,"payload":{}}\', flush=True)',
    )
    original = owner.subprocess.Popen
    with monkeypatch.context() as patch:
        patch.setattr(owner.subprocess, "Popen", lambda *args, **kwargs: None)
        result = rpc(owner, run, "run")
    assert owner.subprocess.Popen is original
    owner.serve(result["phaseRoot"])
    done = rpc(owner, payload, "inspect")
    assert done["outcome"] == "completed" and done["quiescent"]
    assert [item["type"] for item in done["events"]][-1] == "process_exited"
    assert done["events"][-1]["payload"]["exitCode"] == 0
    with pytest.raises(FileExistsError):
        owner.serve(result["phaseRoot"])
    assert rpc(owner, payload, "release")["ack"]


def test_cli_errors_are_fixed_and_do_not_echo_secret_paths(payload):
    payload = {
        **payload,
        "configuration": {**payload["configuration"], "root": "/private-secret/missing"},
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(HELPER)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=3,
    )
    assert "private-secret" not in result.stdout + result.stderr
    assert json.loads(result.stdout)["error"]["code"] == "INSTALL_OWNER_FAILED"


def test_partial_index_without_intent_never_proves_no_dispatch(owner, payload):
    payload = writer(payload)
    rpc(owner, payload, "reserve")
    path = (
        Path(payload["configuration"]["root"])
        / "environment-creations"
        / payload["environmentId"]
        / "jobs"
        / payload["jobId"]
        / "phases"
        / str(uuid4())
    )
    path.write_text("{}")
    result = rpc(owner, payload, "inspect")
    assert result["outcome"] == "unknown" and not result["quiescent"]


def test_prefix_replacement_budget_and_internal_file_link(owner, payload):
    payload = writer(payload)
    allocated = allocate(owner, payload)
    prefix = (
        Path(payload["configuration"]["root"]) / "training-environments" / payload["environmentId"]
    )
    (prefix / "python3.11").write_text("fixture")
    (prefix / "python").symlink_to("python3.11")
    rpc(owner, payload, "mark-owned")
    assert rpc(owner, payload, "verify")["prefixIdentity"] == allocated["prefixIdentity"]
    (prefix / "escape").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="PREFIX_UNSAFE"):
        rpc(owner, payload, "verify")
    (prefix / "escape").unlink()
    prefix.rename(prefix.with_name("preserved-original"))
    prefix.mkdir()
    with pytest.raises(ValueError, match="PREFIX_REPLACED"):
        rpc(owner, payload, "verify")


def test_in_memory_stdin_module_needs_no_file_and_returns_current_nonce(
    owner, payload, monkeypatch
):
    source = HELPER.read_text()
    namespace = {"__name__": "easyai_install_rpc", "__easyai_install_source__": source}
    exec(compile(source, "<fixed-install-helper>", "exec"), namespace)
    payload = writer(payload)
    allocated = allocate(owner, payload)
    commands = []
    monkeypatch.setattr(owner.subprocess, "Popen", lambda argv, **kwargs: commands.append(argv))
    run = run_request(payload, "raise AssertionError('captured, not executed')")
    first = namespace["dispatch"]({**run, "action": "run"})
    assert len(commands) == 1 and first["prefix"] == allocated["prefix"]
    assert first["jobId"] == payload["jobId"] and first["planHash"] == payload["planHash"]
    replay = namespace["dispatch"]({**payload, "action": "inspect", "nonce": "new-caller"})
    assert replay["nonce"] == "new-caller" and replay["phase"] == run["phase"]
    assert replay["jobId"] == payload["jobId"] and replay["planHash"] == payload["planHash"]


def test_live_cancel_survives_deleted_sources_and_expired_permission(owner, payload, monkeypatch):
    payload = writer(payload)
    allocate(owner, payload)
    child = "import time; print('stdlib ready', flush=True); time.sleep(10)"
    run = run_request(payload, child)
    with monkeypatch.context() as patch:
        patch.setattr(owner.subprocess, "Popen", lambda *args, **kwargs: None)
        result = rpc(owner, run, "run")
    thread = threading.Thread(target=owner.serve, args=(result["phaseRoot"],))
    thread.start()
    deadline = time.monotonic() + 3
    log = Path(result["phaseRoot"]) / "logs/train.log"
    while time.monotonic() < deadline:
        if log.exists() and b"stdlib ready" in log.read_bytes():
            break
        time.sleep(0.01)
    assert log.exists() and b"stdlib ready" in log.read_bytes()
    Path(payload["configuration"]["launcher"]["path"]).unlink()
    payload["configuration"]["execution_authorized"] = False
    payload["configuration"]["authorization_expires"] = "2000-01-01T00:00:00+00:00"
    payload["newEnvironment"] = False
    pending = rpc(owner, payload, "cancel")
    assert not pending["quiescent"] and pending["outcome"] == "unknown"
    thread.join(5)
    assert not thread.is_alive()
    final = rpc(owner, payload, "inspect")
    assert final["quiescent"] and final["outcome"] == "cancelled"
    assert final["events"][-1]["type"] == "process_exited"
    assert rpc(owner, payload, "release")["ack"]


def test_no_dispatch_release_refuses_unindexed_physical_phase(owner, payload):
    payload = writer(payload)
    rpc(owner, payload, "reserve")
    phase = (
        Path(payload["configuration"]["root"])
        / "install-processes"
        / payload["jobId"]
        / str(uuid4())
    )
    phase.mkdir(parents=True)
    assert not rpc(owner, payload, "inspect")["quiescent"]
    with pytest.raises(ValueError, match="UNCONFIRMED"):
        rpc(owner, payload, "release")


@pytest.mark.parametrize("value", [1, "true"])
def test_exact_boolean_root_marker_not_integer_or_text(owner, payload, value):
    root = Path(payload["configuration"]["root"])
    (root / ".easyai-install-root.json").write_text(
        json.dumps({"ownedByEasyAI": value, "uid": os.getuid(), "protocolVersion": 1})
    )
    with pytest.raises(ValueError, match="ROOT_NOT_OWNED"):
        owner.dispatch(payload)


def test_mark_owned_can_finish_its_own_partial_marker_without_overwriting_foreign_origin(
    owner, payload
):
    payload = writer(payload)
    allocate(owner, payload)
    prefix = (
        Path(payload["configuration"]["root"]) / "training-environments" / payload["environmentId"]
    )
    (prefix / ".easyai-owned.json").write_text(
        json.dumps({"ownedByEasyAI": True, "environmentId": payload["environmentId"]})
    )
    rpc(owner, payload, "mark-owned")
    origin = prefix / ".easyai-install-origin.json"
    assert json.loads(origin.read_bytes())["jobId"] == payload["jobId"]
    origin.write_text("{}")
    with pytest.raises(ValueError, match="CLAIM_MISMATCH"):
        rpc(owner, payload, "mark-owned")


@pytest.mark.parametrize("source", ["module", "bootstrap", "wheel"])
def test_all_prepared_source_types_are_actually_hashed(owner, payload, source):
    if source == "module":
        path = Path(payload["configuration"]["module_root"]) / "fixture.py"
    elif source == "bootstrap":
        path = Path(payload["configuration"]["bootstrap"][0]["path"])
    else:
        path = Path(payload["configuration"]["wheelhouse"]) / "synthetic-1-py3-none-any.whl"
        path.write_bytes(b"fixture wheel bytes, not a real wheel")
        payload["wheels"] = [
            {
                "name": "synthetic",
                "version": "1",
                "filename": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "downloadBytes": path.stat().st_size,
            }
        ]
    owner.dispatch(payload)
    path.write_bytes(b"source changed")
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        owner.dispatch(payload)


def test_ready_requires_closed_receipt_and_budget_includes_phase_caches(
    owner, payload, monkeypatch
):
    payload = writer(payload)
    allocate(owner, payload)
    rpc(owner, payload, "mark-owned")
    rpc(owner, payload, "mark-ready")
    snapshot = {k: v for k, v in payload.items() if k not in {"jobId", "planHash"}}
    with pytest.raises(ValueError, match="NOT_READY"):
        rpc(owner, {**snapshot, "newEnvironment": False}, "snapshot")
    run = run_request(payload, "raise AssertionError('captured')")
    monkeypatch.setattr(owner.subprocess, "Popen", lambda *args, **kwargs: None)
    phase = rpc(owner, run, "run")["phaseRoot"]
    with (Path(phase) / "tmp/oversized-cache").open("wb") as stream:
        stream.truncate(payload["configuration"]["disk_budget_bytes"] + 1)
    with pytest.raises(ValueError, match="DISK_BUDGET_EXCEEDED"):
        rpc(owner, payload, "verify")


def test_creation_verify_allows_exact_unallocated_and_bootstrap_partial_stages(owner, payload):
    payload = writer(payload)
    rpc(owner, payload, "reserve")
    before = rpc(owner, payload, "verify")
    assert before["ack"] and before["prefixIdentity"] is None and before["usedBytes"] == 0
    allocated = rpc(owner, payload, "allocate")
    prefix = Path(allocated["prefix"])
    (prefix / "bootstrap-progress").write_text("synthetic partial conda files")
    partial = rpc(owner, payload, "verify")
    assert partial["prefixIdentity"] == allocated["prefixIdentity"] and partial["usedBytes"] > 0
    assert not (prefix / ".easyai-owned.json").exists()
    rpc(owner, payload, "mark-owned")
    rpc(owner, payload, "mark-ready")
    rpc(owner, payload, "release")
    existing = {**payload, "newEnvironment": False, "jobId": str(uuid4()), "planHash": "b" * 64}
    rpc(owner, existing, "reserve")
    (prefix / ".easyai-owned.json").unlink()
    with pytest.raises(ValueError, match="NOT_OWNED"):
        rpc(owner, existing, "verify")


def test_creation_verify_does_not_adopt_unrecorded_prefix(owner, payload):
    payload = writer(payload)
    rpc(owner, payload, "reserve")
    prefix = (
        Path(payload["configuration"]["root"]) / "training-environments" / payload["environmentId"]
    )
    prefix.mkdir(parents=True)
    with pytest.raises(ValueError, match="PREFIX_REPLACED"):
        rpc(owner, payload, "verify")


def test_later_writer_does_not_inherit_prior_healthy_receipt(owner, payload, monkeypatch):
    first = writer(payload)
    allocate(owner, first)
    rpc(owner, first, "mark-owned")
    rpc(owner, first, "mark-ready")
    rpc(owner, first, "release")
    fresh = {**writer(payload), "newEnvironment": False}
    rpc(owner, fresh, "reserve")
    event = "@@EASYAI_EVENT@@" + json.dumps(
        {"type": "pipeline_completed", "blockId": None, "payload": {}}
    )
    run = run_request(fresh, "print(" + repr(event) + ",flush=True)")
    with monkeypatch.context() as patch:
        patch.setattr(owner.subprocess, "Popen", lambda *a, **k: None)
        result = rpc(owner, run, "run")
    owner.serve(result["phaseRoot"])
    rpc(owner, fresh, "release")
    snap = {k: v for k, v in fresh.items() if k not in {"jobId", "planHash"}}
    with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_NOT_READY"):
        rpc(owner, snap, "snapshot")


def test_detached_child_finishes_while_parent_still_holds_writer_lock(owner, payload, monkeypatch):
    """Deterministic handoff barrier: Popen cannot return until child exits.

    The parent retains its writer lock throughout. A separately opened NB lock
    in the child always fails here; no scheduler timing or sleeps are involved.
    The only managed command prints a stdlib synthetic completion event.
    """
    payload = writer(payload)
    allocate(owner, payload)
    event = "@@EASYAI_EVENT@@" + json.dumps(
        {"type": "pipeline_completed", "blockId": None, "payload": {}}
    )
    run = run_request(payload, "print(" + repr(event) + ",flush=True)")
    original = owner.subprocess.Popen
    spawned = []

    def child_before_parent_return(argv, **kwargs):
        import fcntl

        lock_path = (
            Path(payload["configuration"]["root"])
            / "environment-creations"
            / payload["environmentId"]
            / ".writer.lock"
        )
        with lock_path.open("rb") as separate:
            with pytest.raises(BlockingIOError):
                fcntl.flock(separate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        child = original(argv, **kwargs)
        spawned.append(child)
        child.wait(timeout=5)  # Explicit child-exit barrier while parent owns the lock.
        return child

    with monkeypatch.context() as patch:
        patch.setattr(owner.subprocess, "Popen", child_before_parent_return)
        result = rpc(owner, run, "run")
    log = (Path(result["phaseRoot"]) / "owner.log").read_text()
    assert result["outcome"] == "completed" and result["quiescent"], log
    assert (Path(result["phaseRoot"]) / "serve.claim.json").is_file()
    assert result["events"][-1]["payload"]["exitCode"] == 0
    assert rpc(owner, run, "run")["outcome"] == "completed"
    assert len(spawned) == 1  # Existing phase is observed, never started again.
    assert rpc(owner, payload, "release")["ack"]


def test_persisted_cancel_before_serve_never_starts_managed_child(owner, payload, monkeypatch):
    payload = writer(payload)
    allocate(owner, payload)
    sentinel = Path(payload["configuration"]["root"]) / "must-not-run.txt"
    event = "@@EASYAI_EVENT@@" + json.dumps(
        {"type": "pipeline_completed", "blockId": None, "payload": {}}
    )
    run = run_request(
        payload,
        "from pathlib import Path;Path("
        + repr(str(sentinel))
        + ').write_text("ran");print('
        + repr(event)
        + ",flush=True)",
    )
    with monkeypatch.context() as patch:
        patch.setattr(owner.subprocess, "Popen", lambda *a, **k: None)
        staged = rpc(owner, run, "run")
    assert not rpc(owner, payload, "cancel")["quiescent"]
    assert (Path(staged["phaseRoot"]) / "install-cancel.request.json").is_file()
    owner.serve(staged["phaseRoot"])
    result = rpc(owner, payload, "inspect")
    assert not sentinel.exists(), "A pre-cancelled phase executed its child"
    assert result["outcome"] == "cancelled" and result["quiescent"] and not result["dispatched"]
    assert result["events"] == []  # No fabricated process_exited record for a child never started.
    assert rpc(owner, payload, "release")["ack"]


def test_inherited_writer_descriptor_rejects_different_inode(owner, tmp_path):
    import os

    expected, other = tmp_path / "writer.lock", tmp_path / "other.lock"
    with owner.lock(expected):
        descriptor = owner.open_file(other, os.O_CREAT | os.O_RDWR, owned=True)
        with pytest.raises(ValueError, match="INSTALL_LOCK_UNSAFE"):
            with owner.inherited_lock(expected, descriptor):
                pytest.fail("Unrelated descriptor acquired writer authority")
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_inherited_writer_close_does_not_unlock_parent(owner, tmp_path):
    import fcntl
    import os

    path = tmp_path / "writer.lock"
    with owner.lock(path) as parent:
        with owner.inherited_lock(path, os.dup(parent)):
            pass
        with path.open("rb") as other:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with owner.lock(path):
        pass
