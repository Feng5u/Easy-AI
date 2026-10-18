"""Real packaged owner and stdlib children on this host only. No SSH, torch or training."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from easyai.compiler.bundle import export_bundle
from easyai.compiler.pipeline import compile_project
from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import ProjectDocument, RunConfig
from easyai.domain.remote_run import RemoteRunObservation, identity_from_config
from easyai.runners.ssh import RemoteChunk, RemoteUnavailable, SshRunCoordinator
from easyai.runtime.supervisor import ManagedSupervisor
from test_ssh_run_coordinator import auth_for, identity as synthetic_identity


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


CHILD = r"""
import argparse, importlib.util, json, os, pathlib, sys, time
from easyai_runtime import emit_event
args = argparse.ArgumentParser()
args.add_argument("--config", required=True)
config = json.loads(pathlib.Path(args.parse_args().config).read_bytes())
root = pathlib.Path(config["runRoot"])
for name in ("easyai", "pydantic", "paramiko", "torch"):
    assert importlib.util.find_spec(name) is None, name
with (root / "fixture-starts").open("a") as output:
    output.write(str(os.getpid()) + "\n")
emit_event("runtime_started", None, {})
print("真实本机标准库进程，无训练", flush=True)
while not (root / "fixture-finish").exists():
    if (root / "cancel.request.json").exists():
        emit_event("pipeline_cancelled", None, {})
        sys.exit(130)
    time.sleep(0.01)
emit_event("pipeline_completed", None, {})
"""


class Bundle:
    def __init__(self, tmp_path, source=CHILD, managed_suffix=""):
        self.root = tmp_path / ("执行包 " + str(uuid4()))
        document = ProjectDocument.model_validate_json(
            (SOURCE_ROOT / "packages/contracts/fixtures/mnist.json").read_bytes()
        )
        export_bundle(compile_project(document), self.root)
        # Explicit synthetic nontraining source fixture, never a production runner/result.
        (self.root / "code/train.py").write_text(source)
        if managed_suffix:
            with (self.root / "code/managed.py").open("a") as output:
                output.write(managed_suffix)
        self.python = str(Path(sys.base_prefix) / "bin/python3.11")
        manifest = json.loads((self.root / "bundle.json").read_bytes())
        for name in manifest["files"]:
            manifest["files"][name] = digest((self.root / name).read_bytes())
        manifest["codeHash"] = manifest["files"]["code/train.py"]
        manifest["bundleHash"] = digest(canonical(manifest["files"]))
        (self.root / "bundle.json").write_text(json.dumps(manifest))
        old = synthetic_identity()
        auth = auth_for(old)
        self.config = RunConfig(
            run_id=old.run_id,
            project_id=old.project_id,
            project_revision=1,
            program_hash=manifest["programHash"],
            code_hash=manifest["codeHash"],
            bundle_hash=manifest["bundleHash"],
            target_id=old.target_id,
            runner="ssh",
            data_root="/synthetic/课程数据",
            run_root=str(self.root),
            python_executable=self.python,
            execution_mode="full",
            seed=42,
            num_workers=0,
        )
        self.identity = identity_from_config(self.config, auth, old.launch_id)
        (self.root / "run-config.json").write_text(self.config.model_dump_json(by_alias=True))
        (self.root / "remote-identity.json").write_text(
            self.identity.model_dump_json(by_alias=True)
        )
        self.auth = auth_for(self.identity)

    def cli(self, action, *, check=True):
        result = subprocess.run(
            [
                self.python,
                "-I",
                "-B",
                str(self.root / "code/supervisor.py"),
                "--" + action,
                "--run-dir",
                str(self.root),
            ],
            cwd=self.root.parent,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=5,
        )
        if check:
            assert result.returncode == 0, result.stderr
            return json.loads(result.stdout) if result.stdout else None
        return result

    def observe(self):
        value = self.cli("inspect")
        return RemoteRunObservation.model_validate(value) if value is not None else None

    def wait(self, terminal=False, seconds=5):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = self.observe()
            if value is not None and (
                value.sealed if terminal else value.state in ("RUNNING", "CANCELLING")
            ):
                return value
            time.sleep(0.03)
        pytest.fail("Portable local owner deadline exceeded")

    def cleanup(self):
        if not (self.root / "remote-launch.json").exists():
            return
        (self.root / "fixture-finish").touch()
        try:
            self.cli("cancel", check=False)
            self.wait(terminal=True)
        except (AssertionError, OSError, ValueError):
            # Test-owned process PID comes only from our synthetic child fixture.
            starts = self.root / "fixture-starts"
            if starts.exists():
                import signal

                for pid in starts.read_text().splitlines():
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Portable owner tests cannot dial network")

    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def bundle(tmp_path):
    value = Bundle(tmp_path)
    try:
        yield value
    finally:
        value.cleanup()


class LocalCliTransport:
    """Test-only bridge to real packaged local owner, never installed as an SSH adapter."""

    def __init__(self, bundle):
        self.bundle = bundle
        self.closed = False
        self.last = None
        self.start_calls = 0
        self.lose_ack = False

    @property
    def quiescent(self):
        return True

    def stage(self, identity, *, timeout):
        assert identity == self.bundle.identity  # Stage was explicit Bundle fixture construction.
        return identity

    def start(self, identity, *, timeout):
        self.start_calls += 1
        assert self.bundle.cli("start") == identity.model_dump(by_alias=True)
        if self.lose_ack:
            raise RemoteUnavailable()
        return identity

    def inspect(self, identity, *, timeout):
        assert identity == self.bundle.identity
        self.last = self.bundle.observe()
        return self.last

    def read(self, identity, stream, offset, length, *, timeout):
        name = {"events": "runtime-events.jsonl", "stdout": "train.log", "stderr": "stderr.log"}[
            stream
        ]
        raw = (self.bundle.root / "logs" / name).read_bytes()
        stamp = getattr(self.last.streams, stream)
        return RemoteChunk(
            identity,
            stream,
            stamp.generation,
            offset,
            digest(raw[:offset]),
            raw[offset : offset + length],
        )

    def cancel(self, identity, *, timeout):
        assert self.bundle.cli("cancel") == identity.model_dump(by_alias=True)
        return identity

    def close(self):
        self.closed = True  # Leaves real detached owner/child alive.


def test_bundle_core_is_identical_and_detached_owner_needs_no_application_packages(bundle):
    assert (bundle.root / "code/managed.py").read_bytes() == (
        SOURCE_ROOT / "services/backend/src/easyai/runtime/managed.py"
    ).read_bytes()
    receipt = bundle.cli("start")
    assert receipt == bundle.identity.model_dump(by_alias=True)
    running = bundle.wait()
    assert not running.sealed
    assert (bundle.root / "fixture-starts").read_text().count("\n") == 1
    (bundle.root / "fixture-finish").touch()
    final = bundle.wait(terminal=True)
    assert final.state == "COMPLETED" and final.exit_code == 0
    original = (bundle.root / "owner-status.json").read_bytes()
    time.sleep(0.12)
    assert (
        bundle.observe() == final and (bundle.root / "owner-status.json").read_bytes() == original
    )
    assert "无训练" in (bundle.root / "logs/train.log").read_text()


def test_concurrent_repeated_start_and_direct_serve_never_launch_twice(bundle):
    with ThreadPoolExecutor(4) as pool:
        receipts = list(pool.map(lambda _: bundle.cli("start", check=False), range(4)))
    assert any(item.returncode == 0 for item in receipts)
    bundle.wait()
    assert bundle.cli("start") == bundle.identity.model_dump(by_alias=True)
    assert bundle.cli("serve", check=False).returncode != 0
    assert (bundle.root / "fixture-starts").read_text().count("\n") == 1


@pytest.mark.parametrize("cancel", [False, True])
def test_coordinator_composes_with_real_packaged_owner_lost_ack_reauth_and_cancel(
    bundle, tmp_path, cancel
):
    store = tmp_path / "local-store"
    store.mkdir()
    coordinator = SshRunCoordinator(store, bundle.identity)
    current = [bundle.auth]
    port = LocalCliTransport(bundle)
    port.lose_ack = True
    try:
        coordinator.attach(current[0], port, lambda: current[0])
        with pytest.raises(ValueError, match="STATE_UNKNOWN"):
            coordinator.start()
        bundle.wait()
        assert coordinator.checkpoint().start_outcome == "unknown" and port.start_calls == 1
        coordinator.disconnect()
        if cancel:
            coordinator.request_cancel()
        else:
            (bundle.root / "fixture-finish").touch()
            bundle.wait(terminal=True)
        current[0] = auth_for(bundle.identity)
        resumed = LocalCliTransport(bundle)
        coordinator.attach(current[0], resumed, lambda: current[0])
        coordinator.poll()
        if cancel:
            assert coordinator.checkpoint().execution_state != "CANCELLED"
            bundle.wait(terminal=True)
            coordinator.poll()
        assert coordinator.checkpoint().execution_state == ("CANCELLED" if cancel else "COMPLETED")
        assert (
            resumed.start_calls == 0
            and (bundle.root / "fixture-starts").read_text().count("\n") == 1
        )
        assert coordinator.events()[-1].type == "process_exited"
        assert coordinator.checkpoint().artifacts_verified is False
        assert "无训练" in coordinator.log_bytes("stdout", 0).decode()
    finally:
        coordinator.close()


def test_cancel_after_completion_preserves_sealed_snapshot(bundle):
    bundle.cli("start")
    bundle.wait()
    (bundle.root / "fixture-finish").touch()
    result = bundle.wait(terminal=True)
    raw = (bundle.root / "owner-status.json").read_bytes()
    bundle.cli("cancel")
    assert bundle.observe() == result and (bundle.root / "owner-status.json").read_bytes() == raw
    assert not (bundle.root / "remote-cancel.json").exists()


@pytest.mark.parametrize(
    "target", ["code/managed.py", "code/train.py", "run-config.json", "remote-identity.json"]
)
def test_mutated_bundle_or_config_is_rejected_without_start(bundle, target):
    path = bundle.root / target
    before = path.read_bytes()
    path.write_bytes(before + b"\nmodified")
    result = bundle.cli("start", check=False)
    assert result.returncode != 0
    assert b"REMOTE_OWNER_PROTOCOL_FAILED" in result.stderr
    assert (
        not (bundle.root / "remote-launch.json").exists()
        and not (bundle.root / "fixture-starts").exists()
    )
    path.write_bytes(before)


def test_foreign_cancel_identity_is_never_forwarded_to_child(bundle):
    bundle.cli("start")
    bundle.wait()
    other = bundle.identity.model_copy(update={"launch_id": str(uuid4())})
    (bundle.root / "remote-cancel.json").write_text(
        json.dumps({"identity": other.model_dump(by_alias=True)})
    )
    assert bundle.cli("cancel", check=False).returncode != 0
    time.sleep(0.25)
    assert bundle.observe().state == "RUNNING"
    assert not (bundle.root / "cancel.request.json").exists()
    (bundle.root / "remote-cancel.json").unlink()


def test_stale_or_missing_owner_is_unknown_and_never_restarted(bundle):
    bundle.cli("start")
    bundle.wait()
    # Persist an explicitly stale heartbeat fixture; do not kill any real process.
    beat = json.loads((bundle.root / "owner-heartbeat.json").read_bytes())
    beat["monotonic"] = 0.0
    # Finish owner first so our fixture cannot race its heartbeat publication.
    (bundle.root / "fixture-finish").touch()
    bundle.wait(terminal=True)
    status = json.loads((bundle.root / "owner-status.json").read_bytes())
    status.update(state="RUNNING", sealed=False, exitCode=None)
    (bundle.root / "owner-status.json").write_text(json.dumps(status))
    (bundle.root / "owner-heartbeat.json").write_text(json.dumps(beat))
    assert bundle.cli("inspect") is None
    bundle.cli("start")
    assert (bundle.root / "fixture-starts").read_text().count("\n") == 1
    # Restore the verified terminal record for deterministic fixture cleanup.
    status.update(state="COMPLETED", sealed=True, exitCode=0)
    (bundle.root / "owner-status.json").write_text(json.dumps(status))


@pytest.mark.parametrize("protocol", ["bool_epoch", "unterminated"])
def test_same_bad_child_protocol_fails_local_wrapper_and_portable_owner(tmp_path, protocol):
    if protocol == "bool_epoch":
        text = 'print("@@EASYAI_EVENT@@" + json.dumps({"type":"epoch_completed","blockId":None,"payload":{"epoch":True,"train_loss":0.1,"test_accuracy":0.2,"train_samples":1,"test_samples":1,"elapsed_seconds":0.1}}),flush=True)\n'
    else:
        text = 'print("@@EASYAI_EVENT@@" + json.dumps({"type":"progress","blockId":None,"payload":{}}),end="",flush=True)\n'
    script = (
        "import json\n"
        + text
        + '\nprint("@@EASYAI_EVENT@@"+json.dumps({"type":"pipeline_completed","blockId":None,"payload":{}}),flush=True)\n'
    )
    bundle = Bundle(tmp_path, script)
    local_root = tmp_path / "local"
    local_root.mkdir()
    local = ManagedSupervisor(
        local_root, bundle.identity.run_id, [sys.executable, "-I", "-B", "-c", script], local_root
    )
    try:
        local.start()
        local.wait(3)
        bundle.cli("start")
        result = bundle.wait(terminal=True)
        assert local.status == result.state == "FAILED"
        remote = [
            json.loads(raw)
            for raw in (bundle.root / "logs/runtime-events.jsonl").read_bytes().splitlines()
        ]
        assert [event.type for event in local.events()] == [event["type"] for event in remote]
        assert all(event["type"] != "epoch_completed" for event in remote)
    finally:
        local.close()
        bundle.cleanup()


def test_real_training_spawn_failure_is_sealed_without_fabricating_an_exit(tmp_path):
    # Apply an actual OS process limit only inside this test-owned detached owner.
    # No monkeypatched Popen, no host/user environment change, no training child.
    bundle = Bundle(
        tmp_path,
        managed_suffix="\nimport resource\nresource.setrlimit(resource.RLIMIT_NPROC, (0, 0))\n",
    )
    try:
        bundle.cli("start")
        final = bundle.wait(terminal=True)
        assert final.state == "FAILED" and final.spawn_failed and final.exit_code is None
        events = [
            json.loads(line)
            for line in (bundle.root / "logs/runtime-events.jsonl").read_bytes().splitlines()
        ]
        assert len(events) == 1 and events[0]["type"] == "process_spawn_failed"
        assert events[0]["payload"] == {"code": "PROCESS_SPAWN_FAILED", "spawnFailed": True}
        assert "exitCode" not in events[0]["payload"]
        assert not (bundle.root / "fixture-starts").exists()
        store = tmp_path / "cache"
        store.mkdir()
        coordinator = SshRunCoordinator(store, bundle.identity)
        try:
            coordinator.attach(bundle.auth, LocalCliTransport(bundle), lambda: bundle.auth)
            assert coordinator.poll().execution_state == "FAILED"
            assert coordinator.events()[-1].type == "process_spawn_failed"
            assert coordinator.checkpoint().artifacts_verified is False
        finally:
            coordinator.close()
    finally:
        bundle.cleanup()


def test_start_and_serve_claims_without_live_owner_are_never_reclaimed(bundle):
    generations = {name: str(uuid4()) for name in ("events", "stdout", "stderr")}
    (bundle.root / "remote-launch.json").write_text(
        json.dumps(
            {"identity": bundle.identity.model_dump(by_alias=True), "generations": generations}
        )
    )
    (bundle.root / "serve-claim.json").write_text(
        json.dumps({"identity": bundle.identity.model_dump(by_alias=True)})
    )
    assert bundle.cli("start") == bundle.identity.model_dump(by_alias=True)
    assert bundle.cli("inspect") is None
    assert bundle.cli("serve", check=False).returncode != 0
    assert not (bundle.root / "fixture-starts").exists()
    # This fixture deliberately represents unknown ownership with no process created.
    (bundle.root / "remote-launch.json").unlink()


def test_journal_drains_large_stderr_and_partial_unicode_before_sealing(tmp_path):
    source = """import sys, os\nfrom easyai_runtime import emit_event\nemit_event("runtime_started", None, {})\nsys.stderr.buffer.write(b"x" * (2 * 1024 * 1024)); sys.stderr.flush()\nfor byte in "中文跨字节".encode():\n    os.write(1, bytes([byte]))\nos.write(1, b"\\n")\nemit_event("pipeline_completed", None, {})\n"""
    bundle = Bundle(tmp_path, source)
    try:
        bundle.cli("start")
        final = bundle.wait(terminal=True)
        assert final.state == "COMPLETED" and final.exit_code == 0
        assert final.streams.stderr.size_bytes == 2 * 1024 * 1024
        assert (bundle.root / "logs/train.log").read_bytes() == "中文跨字节\n".encode()
        for name, path in {
            "events": "runtime-events.jsonl",
            "stdout": "train.log",
            "stderr": "stderr.log",
        }.items():
            raw = (bundle.root / "logs" / path).read_bytes()
            stamp = getattr(final.streams, name)
            assert stamp.size_bytes == len(raw) and stamp.sha256 == digest(raw)
    finally:
        bundle.cleanup()


@pytest.mark.parametrize("extra", ["tempfile.py", "__pycache__", "unhashed_package"])
def test_unhashed_code_modules_or_packages_are_rejected_before_any_import(bundle, extra):
    path = bundle.root / "code" / extra
    if extra.endswith(".py"):
        path.write_text(
            "from pathlib import Path\nPath(__file__).parents[1].joinpath('UNHASHED_EXECUTED').touch()\nraise RuntimeError('unhashed module')\n"
        )
    else:
        path.mkdir()
        (path / "__init__.py").write_text("raise RuntimeError('unhashed package')")
    result = bundle.cli("start", check=False)
    assert result.returncode != 0
    assert not (bundle.root / "UNHASHED_EXECUTED").exists()
    assert not (bundle.root / "remote-launch.json").exists()


def test_portable_journal_never_retries_an_uncertain_fsync_write(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "portable_journal_fixture", SOURCE_ROOT / "runtime/portable_journal.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "runtime-events.jsonl"
    journal = module.PortableJournal(path, str(uuid4()))
    original = os.fsync

    def failure(fd):
        if fd == journal._fd:
            raise OSError("synthetic journal fsync failure")
        return original(fd)

    monkeypatch.setattr(os, "fsync", failure)
    try:
        with pytest.raises(OSError):
            journal.append("runtime_started", None, {})
        first = path.read_bytes()
        with pytest.raises(ValueError, match="WRITE_UNCERTAIN"):
            journal.append("runtime_error", None, {"code": "fixed"})
        assert path.read_bytes() == first and journal.after(0) == []
    finally:
        journal.close()
