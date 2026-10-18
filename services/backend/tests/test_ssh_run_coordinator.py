"""Offline coordinator protocol; synthetic owners, and local stdlib process fixtures only."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import socket
import subprocess
import sys
import threading
import time
from uuid import uuid4

import pytest

from easyai.domain.connections import AuthenticatedConnection
from easyai.domain.environment import EnvironmentScope
from easyai.domain.remote_run import (
    RemoteRunIdentity,
    RemoteRunObservation,
    RemoteStream,
    RemoteStreams,
)
from easyai.domain.ssh import SshEndpoint
from easyai.runners.ssh import (
    RemoteChunk,
    RemoteProtocolError,
    RemoteUnavailable,
    SshRunCoordinator,
)
from easyai.runtime.supervisor import ManagedSupervisor


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline coordinator fixture must not dial SSH or any network")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def identity():
    return RemoteRunIdentity(
        project_id=str(uuid4()),
        target_id=str(uuid4()),
        run_id=str(uuid4()),
        launch_id=str(uuid4()),
        username="synthetic",
        endpoint=SshEndpoint(host="synthetic.invalid"),
        host_fingerprint="SHA256:" + "A" * 43,
        run_root="/synthetic/.easyai/run",
        program_hash="1" * 64,
        code_hash="2" * 64,
        bundle_hash="3" * 64,
        config_hash="4" * 64,
    )


def auth_for(owner):
    return AuthenticatedConnection(
        project_id=owner.project_id,
        request_id=str(uuid4()),
        identity_request_id=str(uuid4()),
        scope=EnvironmentScope(
            project_id=owner.project_id,
            connection_id=str(uuid4()),
            endpoint=owner.endpoint,
            host_fingerprint=owner.host_fingerprint,
        ),
        username=owner.username,
        expires_in_seconds=300,
    )


class Owner:
    def __init__(self, identity):
        self.identity = identity
        self.data = {name: b"" for name in ("events", "stdout", "stderr")}
        self.generations = {name: str(uuid4()) for name in self.data}
        self.seq = 0
        self.heartbeat = 0
        self.state = "RUNNING"
        self.exit_code = None
        self.exists = False
        self.start_calls = self.stage_calls = self.cancel_calls = self.inspect_calls = 0
        self.read_hook = None
        self.start_hook = None
        self.cancel_hook = None
        self.inspect_hook = None
        self.quiet = True

    def event(self, kind, payload=None):
        self.seq += 1
        value = {
            "protocolVersion": 1,
            "runId": self.identity.run_id,
            "seq": self.seq,
            "source": "runtime",
            "sourceSeq": self.seq,
            "timestamp": "2026-10-18T00:00:00+00:00",
            "type": kind,
            "blockId": None,
            "payload": payload or {},
        }
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
        self.data["events"] += raw
        return raw

    def finish(self, state="COMPLETED", code=0):
        self.event("pipeline_completed" if state == "COMPLETED" else "pipeline_cancelled")
        self.event("process_exited", {"exitCode": code})
        self.state, self.exit_code = state, code
        self.heartbeat += 1

    def observe(self):
        if not self.exists:
            return None
        if self.exit_code is None:
            self.heartbeat += 1
        streams = {
            name: RemoteStream(
                generation=self.generations[name], size_bytes=len(raw), sha256=digest(raw)
            )
            for name, raw in self.data.items()
        }
        result = RemoteRunObservation(
            identity=self.identity,
            heartbeat=max(1, self.heartbeat),
            state=self.state,
            sealed=self.exit_code is not None,
            exit_code=self.exit_code,
            streams=RemoteStreams(**streams),
        )
        return self.inspect_hook(result) if self.inspect_hook else result


class Transport:
    def __init__(self, owner):
        self.owner = owner
        self.closed = False

    @property
    def quiescent(self):
        return self.owner.quiet

    def stage(self, identity, *, timeout):
        assert 0 < timeout <= 5
        assert identity == self.owner.identity
        self.owner.stage_calls += 1
        return identity

    def start(self, identity, *, timeout):
        assert 0 < timeout <= 5
        assert identity == self.owner.identity
        self.owner.start_calls += 1
        self.owner.exists = True
        self.owner.event("runtime_started")
        if self.owner.start_hook:
            self.owner.start_hook()
        return identity

    def inspect(self, identity, *, timeout):
        assert 0 < timeout <= 5
        assert identity == self.owner.identity
        self.owner.inspect_calls += 1
        return self.owner.observe()

    def read(self, identity, stream, offset, length, *, timeout):
        assert 0 < timeout <= 5
        assert identity == self.owner.identity
        if self.owner.read_hook:
            self.owner.read_hook()
        raw = self.owner.data[stream]
        return RemoteChunk(
            identity,
            stream,
            self.owner.generations[stream],
            offset,
            digest(raw[:offset]),
            raw[offset : offset + length],
        )

    def cancel(self, identity, *, timeout):
        assert 0 < timeout <= 5
        assert identity == self.owner.identity
        self.owner.cancel_calls += 1
        if self.owner.cancel_hook:
            self.owner.cancel_hook()
        return identity

    def close(self):
        self.closed = True  # Transport close never closes the execution owner.


@pytest.fixture
def setup(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    owner = Owner(identity())
    coordinator = SshRunCoordinator(store, owner.identity)
    current = [auth_for(owner.identity)]
    port = Transport(owner)
    coordinator.attach(current[0], port, lambda: current[0])
    yield coordinator, owner, port, current, store
    if not coordinator._closed:
        coordinator.close()


def reconnect(coordinator, owner, current):
    coordinator.disconnect()
    current[0] = auth_for(owner.identity)
    port = Transport(owner)
    coordinator.attach(current[0], port, lambda: current[0])
    return port


def test_start_once_with_durable_intent_and_no_artifact_success_claim(setup):
    coordinator, owner, port, current, store = setup

    def check_intent():
        state = json.loads((coordinator.root / "checkpoint.json").read_bytes())
        assert state["startOutcome"] == "unknown"

    owner.start_hook = check_intent
    first = coordinator.start()
    assert first.execution_state == "RUNNING" and first.start_outcome == "acknowledged"
    coordinator.start()
    coordinator.poll()
    assert owner.start_calls == owner.stage_calls == 1
    assert len(coordinator.events()) == 1
    owner.finish()
    state = coordinator.poll()
    assert state.execution_state == "COMPLETED" and state.artifacts_verified is False
    coordinator.request_cancel()
    assert owner.cancel_calls == 0 and coordinator.checkpoint().execution_state == "COMPLETED"


def test_start_consumed_then_lost_ack_restart_only_inspects_and_not_found_stays_unknown(setup):
    coordinator, owner, port, current, store = setup

    def lost():
        raise RemoteUnavailable("synthetic SDK message must not escape")

    owner.start_hook = lost
    with pytest.raises(RemoteProtocolError, match="STATE_UNKNOWN") as raised:
        coordinator.start()
    assert raised.value.__context__ is None
    assert coordinator.checkpoint().start_outcome == "unknown" and owner.start_calls == 1
    coordinator.close()
    owner.exists = False
    restored = SshRunCoordinator(store, owner.identity)
    try:
        current[0] = auth_for(owner.identity)
        restored.attach(current[0], Transport(owner), lambda: current[0])
        with pytest.raises(RemoteProtocolError, match="STATE_UNKNOWN"):
            restored.start()
        assert owner.start_calls == owner.stage_calls == 1
        assert restored.checkpoint().start_outcome == "unknown"
        owner.exists = True
        reconnect(restored, owner, current)
        assert restored.poll().execution_state == "RUNNING"
        assert len(restored.events()) == 1
        changed = owner.identity.model_copy(update={"launch_id": str(uuid4())})
        with pytest.raises(RemoteProtocolError):
            SshRunCoordinator(store, changed)
    finally:
        restored.close()


def test_cancel_before_start_is_durable_and_blocks_late_start(setup):
    coordinator, owner, *_ = setup
    coordinator.disconnect()
    state = coordinator.request_cancel()
    assert state.cancel_state == "pending" and state.execution_state == "CREATED"
    current = auth_for(owner.identity)
    coordinator.attach(current, Transport(owner), lambda: current)
    with pytest.raises(RemoteProtocolError):
        coordinator.start()
    assert owner.start_calls == owner.stage_calls == owner.cancel_calls == 0


def test_disconnect_resume_reauth_not_restart_and_pending_cancel_keeps_completed_race(setup):
    coordinator, owner, port, current, _ = setup
    coordinator.start()
    coordinator.disconnect()
    state = coordinator.request_cancel()
    assert state.execution_state == "RUNNING" and state.connection_state == "disconnected"
    owner.data["stdout"] += "合成日志，不是训练效果\n".encode()
    owner.finish()
    reconnect(coordinator, owner, current)
    state = coordinator.poll()
    assert state.execution_state == "COMPLETED" and owner.cancel_calls == 0
    assert owner.start_calls == 1 and len(coordinator.events()) == 3
    assert coordinator.log_bytes("stdout", 0).decode() == "合成日志，不是训练效果\n"
    coordinator.poll()
    assert len(coordinator.events()) == 3


@pytest.mark.parametrize("change", ["username", "project", "fingerprint", "host"])
def test_reauth_requires_exact_original_target_and_user_before_any_io(change, setup):
    coordinator, owner, port, current, _ = setup
    coordinator.start()
    coordinator.disconnect()
    auth = auth_for(owner.identity)
    if change == "username":
        auth = auth.model_copy(update={"username": "other"})
    else:
        updates = {
            "project": {"project_id": str(uuid4())},
            "fingerprint": {"host_fingerprint": "SHA256:" + "B" * 43},
            "host": {"endpoint": SshEndpoint(host="other.invalid")},
        }[change]
        auth = auth.model_copy(update={"scope": auth.scope.model_copy(update=updates)})
    before = owner.inspect_calls
    with pytest.raises(RemoteProtocolError, match="IDENTITY_MISMATCH"):
        coordinator.attach(auth, Transport(owner), lambda: auth)
    assert owner.inspect_calls == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("launch_id", str(uuid4())),
        ("run_id", str(uuid4())),
        ("run_root", "/other/run"),
        ("code_hash", "f" * 64),
    ],
)
def test_wrong_execution_owner_receipt_cannot_import_or_cancel(field, value, setup):
    coordinator, owner, *_ = setup
    coordinator.start()
    before = coordinator.events()
    owner.inspect_hook = lambda value_: value_.model_copy(
        update={"identity": owner.identity.model_copy(update={field: value})}
    )
    coordinator.request_cancel()
    with pytest.raises(RemoteProtocolError):
        coordinator.poll()
    assert coordinator.events() == before and owner.cancel_calls == 0


def test_cancel_ack_is_not_exit_and_timeout_keeps_durable_retry(setup):
    coordinator, owner, _, current, _ = setup
    coordinator.start()
    coordinator.request_cancel()

    def lost():
        raise RemoteUnavailable()

    owner.cancel_hook = lost
    with pytest.raises(RemoteProtocolError):
        coordinator.poll()
    assert coordinator.checkpoint().cancel_state == "pending"
    assert coordinator.checkpoint().execution_state == "RUNNING"
    owner.cancel_hook = None
    reconnect(coordinator, owner, current)
    coordinator.poll()
    assert coordinator.checkpoint().cancel_state == "acknowledged"
    assert coordinator.checkpoint().execution_state == "RUNNING" and owner.cancel_calls == 2
    owner.finish("CANCELLED", 130)
    assert coordinator.poll().execution_state == "CANCELLED" and owner.start_calls == 1


def test_late_old_lease_read_is_not_imported_and_busy_owner_prevents_overlap(setup):
    coordinator, owner, port, current, _ = setup
    coordinator.start()
    owner.event("progress", {"message": "synthetic late event"})
    entered, release = threading.Event(), threading.Event()

    def block():
        entered.set()
        assert release.wait(3)

    owner.read_hook = block
    with ThreadPoolExecutor(1) as pool:
        task = pool.submit(coordinator.poll)
        assert entered.wait(2)
        current[0] = None
        coordinator.disconnect()
        fresh = auth_for(owner.identity)
        with pytest.raises(RemoteProtocolError, match="IO_BUSY"):
            coordinator.attach(fresh, Transport(owner), lambda: fresh)
        release.set()
        with pytest.raises(RemoteProtocolError, match="STATE_UNKNOWN"):
            task.result(3)
    assert len(coordinator.events()) == 1
    assert coordinator.checkpoint().execution_state == "RUNNING"
    owner.read_hook = None
    reconnect(coordinator, owner, current)
    coordinator.poll()
    assert len(coordinator.events()) == 2 and owner.start_calls == 1


def test_retiring_transport_must_be_quiescent_before_reauth_or_store_release(setup):
    coordinator, owner, _, current, _ = setup
    coordinator.start()
    owner.quiet = False
    coordinator.disconnect()
    with pytest.raises(RemoteProtocolError, match="CLEANUP_UNCONFIRMED"):
        coordinator.attach(current[0], Transport(owner), lambda: current[0])
    with pytest.raises(RemoteProtocolError, match="CLEANUP_UNCONFIRMED"):
        coordinator.close()
    owner.quiet = True
    current[0] = auth_for(owner.identity)
    coordinator.attach(current[0], Transport(owner), lambda: current[0])
    coordinator.poll()


@pytest.mark.parametrize("mode", ["rewrite", "truncate", "rotate"])
def test_stream_origin_prefix_and_monotonic_length_are_verified(mode, setup):
    coordinator, owner, *_ = setup
    owner.data["stdout"] = b"original-prefix"
    coordinator.start()
    if mode == "rewrite":
        owner.data["stdout"] = b"modified-prefix plus append"
    elif mode == "truncate":
        owner.data["stdout"] = b"short"
    else:
        owner.generations["stdout"] = str(uuid4())
    with pytest.raises(RemoteProtocolError):
        coordinator.poll()
    assert coordinator.checkpoint().execution_state == "RUNNING"
    assert coordinator.log_bytes("stdout", 0) == b"original-prefix"


def test_partial_utf8_event_and_logs_survive_disconnect_and_replay_without_duplication(setup):
    import codecs

    coordinator, owner, _, current, _ = setup
    coordinator.start()
    raw = owner.event("progress", {"message": "中文半字符"})
    prefix = owner.data["events"][: -len(raw)]
    split = raw.index("中".encode()) + 1
    owner.data["events"] = prefix + raw[:split]
    owner.data["stdout"] = "中文".encode()[:1]
    coordinator.poll()
    assert len(coordinator.events()) == 1
    decoder = codecs.getincrementaldecoder("utf-8")()
    assert decoder.decode(coordinator.log_bytes("stdout", 0)) == ""
    coordinator.disconnect()
    owner.data["events"] = prefix + raw
    owner.data["stdout"] = "中文".encode()
    reconnect(coordinator, owner, current)
    coordinator.poll()
    assert len(coordinator.events()) == 2
    assert decoder.decode(coordinator.log_bytes("stdout", 1)) == "中文"
    coordinator.poll()
    assert len(coordinator.events()) == 2


@pytest.mark.parametrize(
    "mode", ["gap", "duplicate", "partial_sealed", "missing_exit", "exit_mismatch"]
)
def test_invalid_event_or_terminal_evidence_never_publishes_terminal(mode, setup):
    coordinator, owner, *_ = setup
    coordinator.start()
    if mode in ("gap", "duplicate"):
        raw = owner.event("progress")
        parsed = json.loads(raw)
        parsed["seq"] = parsed["sourceSeq"] = 3 if mode == "gap" else 1
        owner.data["events"] = (
            owner.data["events"][: -len(raw)] + json.dumps(parsed).encode() + b"\n"
        )
    else:
        owner.finish()
        if mode == "partial_sealed":
            owner.data["events"] += b'{"unfinished":'
        elif mode == "missing_exit":
            owner.data["events"] = b"\n".join(owner.data["events"].split(b"\n")[:-2]) + b"\n"
        else:
            owner.exit_code = 9
    with pytest.raises(RemoteProtocolError):
        coordinator.poll()
    assert coordinator.checkpoint().execution_state == "RUNNING"
    assert len(coordinator.events()) == 1


def test_single_writer_and_cached_identity_are_not_adopted_or_overwritten(setup):
    coordinator, owner, _, current, store = setup
    with pytest.raises(RemoteProtocolError, match="TARGET_BUSY"):
        SshRunCoordinator(store, owner.identity)
    coordinator.start()
    coordinator.close()
    other = owner.identity.model_copy(update={"launch_id": str(uuid4()), "run_id": str(uuid4())})
    with pytest.raises(RemoteProtocolError, match="OWNER_CONFLICT"):
        SshRunCoordinator(store, other)
    restored = SshRunCoordinator(store, owner.identity)
    try:
        current[0] = auth_for(owner.identity)
        restored.attach(current[0], Transport(owner), lambda: current[0])
        restored.poll()
        assert owner.start_calls == 1 and len(restored.events()) == 1
    finally:
        restored.close()


class ProcessTransport(Transport):
    """Test-only local process adapter, never a production SSH implementation."""

    def __init__(self, owner, supervisor):
        super().__init__(owner)
        self.supervisor = supervisor

    def start(self, identity, *, timeout):
        assert 0 < timeout <= 5
        self.owner.start_calls += 1
        self.owner.exists = True
        self.supervisor.start()
        return identity

    def inspect(self, identity, *, timeout):
        assert 0 < timeout <= 5
        assert identity == self.owner.identity
        if not self.owner.exists:
            return None
        code = self.supervisor.wait(0)
        for stream, name in {
            "events": "runtime-events.jsonl",
            "stdout": "train.log",
            "stderr": "stderr.log",
        }.items():
            path = self.supervisor.run_root / "logs" / name
            self.owner.data[stream] = path.read_bytes() if path.exists() else b""
        if code is not None and self.owner.exit_code is None:
            self.owner.state = self.supervisor.status
            self.owner.exit_code = code
            self.owner.heartbeat += 1
        return self.owner.observe()

    def cancel(self, identity, *, timeout):
        assert 0 < timeout <= 5
        assert identity == self.owner.identity
        self.owner.cancel_calls += 1
        self.supervisor.request_cancel()
        return identity


def wait_for(predicate, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    pytest.fail("Local process fixture deadline exceeded")


@pytest.mark.parametrize("cancel", [False, True])
def test_actual_local_supervisor_process_disconnect_resume_and_owned_cancel_only(tmp_path, cancel):
    store = tmp_path / "store"
    store.mkdir()
    run = tmp_path / "execution"
    run.mkdir()
    owner = Owner(identity())
    script = r"""
import json, pathlib, sys, time
root = pathlib.Path(sys.argv[1])
def emit(kind, payload=None):
    print("@@EASYAI_EVENT@@" + json.dumps({"type": kind, "blockId": None, "payload": payload or {}}, ensure_ascii=False), flush=True)
emit("runtime_started")
print("本机标准库进程夹具，无训练", flush=True)
(root / "fixture-ready").write_text("ready")
while not (root / "finish").exists():
    if (root / "cancel.request.json").exists():
        emit("pipeline_cancelled")
        sys.exit(130)
    time.sleep(0.01)
emit("pipeline_completed")
"""
    supervisor = ManagedSupervisor(
        run,
        owner.identity.run_id,
        [sys.executable, "-I", "-B", "-c", script, str(run)],
        run,
        cancel_grace=0.2,
    )
    unrelated = subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", "import time; time.sleep(10)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    coordinator = SshRunCoordinator(store, owner.identity)
    current = [auth_for(owner.identity)]
    try:
        coordinator.attach(current[0], ProcessTransport(owner, supervisor), lambda: current[0])
        coordinator.start()
        wait_for(lambda: (run / "fixture-ready").exists())
        coordinator.poll()
        coordinator.disconnect()
        assert supervisor.status == "RUNNING" and supervisor.wait(0) is None
        if cancel:
            coordinator.request_cancel()
        else:
            (run / "finish").write_text("allowed by local fixture")
            assert supervisor.wait(3) == 0
        current[0] = auth_for(owner.identity)
        coordinator.attach(current[0], ProcessTransport(owner, supervisor), lambda: current[0])
        coordinator.poll()
        if cancel:
            assert coordinator.checkpoint().execution_state != "CANCELLED"
            assert supervisor.wait(3) is not None
            coordinator.poll()
        assert coordinator.checkpoint().execution_state == ("CANCELLED" if cancel else "COMPLETED")
        assert owner.start_calls == 1 and unrelated.poll() is None
        assert coordinator.events()[-1].type == "process_exited"
        assert "无训练" in coordinator.log_bytes("stdout", 0).decode()
        assert coordinator.checkpoint().artifacts_verified is False
    finally:
        coordinator.close()
        supervisor.close()
        unrelated.terminate()
        unrelated.wait(timeout=3)


def test_unquiescent_failure_detaches_io_and_cannot_reenter_or_release_owner(setup):
    coordinator, owner, port, current, store = setup
    coordinator.start()

    def failed(observation):
        owner.quiet = False
        raise RemoteUnavailable()

    owner.inspect_hook = failed
    with pytest.raises(RemoteProtocolError, match="STATE_UNKNOWN"):
        coordinator.poll()
    assert port.closed and coordinator._binding is None
    before = owner.inspect_calls
    with pytest.raises((RemoteProtocolError, RemoteUnavailable)):
        coordinator.poll()
    assert owner.inspect_calls == before
    fresh = auth_for(owner.identity)
    with pytest.raises(RemoteProtocolError, match="CLEANUP_UNCONFIRMED"):
        coordinator.attach(fresh, Transport(owner), lambda: fresh)
    with pytest.raises(RemoteProtocolError, match="CLEANUP_UNCONFIRMED"):
        coordinator.close()
    owner.quiet = True
    owner.inspect_hook = None
    current[0] = fresh
    coordinator.attach(fresh, Transport(owner), lambda: current[0])
    coordinator.poll()
    assert owner.start_calls == 1


def test_rejected_log_bytes_are_not_published_and_retry_recovers_verified_prefix(setup):
    from dataclasses import replace

    coordinator, owner, port, current, store = setup
    owner.data["stdout"] = b"good"
    coordinator.start()
    owner.data["stdout"] += b"REAL"

    class CorruptTransport(Transport):
        def read(self, identity, stream, offset, length, *, timeout):
            value = super().read(identity, stream, offset, length, timeout=timeout)
            return replace(value, data=b"FAKE") if stream == "stdout" else value

    coordinator.disconnect()
    current[0] = auth_for(owner.identity)
    coordinator.attach(current[0], CorruptTransport(owner), lambda: current[0])
    with pytest.raises(RemoteProtocolError):
        coordinator.poll()
    assert coordinator.log_bytes("stdout", 0) == b"good"
    assert (coordinator.root / "remote-stdout.log").read_bytes() == b"good"
    reconnect(coordinator, owner, current)
    coordinator.poll()
    assert coordinator.log_bytes("stdout", 0) == b"goodREAL"


def test_reconnect_requires_new_connection_id_even_after_controller_restart(setup):
    coordinator, owner, port, current, store = setup
    coordinator.start()
    coordinator.disconnect()
    with pytest.raises(RemoteProtocolError, match="REAUTH_REQUIRED"):
        coordinator.attach(current[0], Transport(owner), lambda: current[0])
    coordinator.close()
    restored = SshRunCoordinator(store, owner.identity)
    try:
        with pytest.raises(RemoteProtocolError, match="REAUTH_REQUIRED"):
            restored.attach(current[0], Transport(owner), lambda: current[0])
        current[0] = auth_for(owner.identity)
        restored.attach(current[0], Transport(owner), lambda: current[0])
        restored.poll()
        assert owner.start_calls == 1
    finally:
        restored.close()


def test_unsafe_cache_permissions_and_checkpoint_replacement_refuse_without_chmod(tmp_path):
    import os

    owner = Owner(identity())
    store = tmp_path / "store"
    store.mkdir()
    cache = store / owner.identity.target_id
    cache.mkdir(mode=0o777)
    os.chmod(cache, 0o777)  # Test-owned fixture only, never a product repair.
    with pytest.raises(ValueError, match="UNSAFE"):
        SshRunCoordinator(store, owner.identity)
    assert cache.stat().st_mode & 0o777 == 0o777
    cache.rmdir()
    coordinator = SshRunCoordinator(store, owner.identity)
    current = auth_for(owner.identity)
    coordinator.attach(current, Transport(owner), lambda: current)
    coordinator.start()
    coordinator.close()
    checkpoint = cache / "checkpoint.json"
    original = checkpoint.read_bytes()
    parsed = json.loads(original)
    parsed.update(startOutcome="not_attempted", executionState="CREATED", lastObservation=None)
    checkpoint.unlink()
    checkpoint.write_text(json.dumps(parsed))
    os.chmod(checkpoint, 0o666)
    with pytest.raises(ValueError, match="UNSAFE"):
        SshRunCoordinator(store, owner.identity)
    assert owner.start_calls == 1 and checkpoint.stat().st_mode & 0o777 == 0o666
    os.chmod(checkpoint, 0o600)
    restored = SshRunCoordinator(store, owner.identity)
    try:
        assert restored.checkpoint().start_outcome == "unknown"
        fresh = auth_for(owner.identity)
        restored.attach(fresh, Transport(owner), lambda: fresh)
        restored.start()
        assert owner.start_calls == 1
    finally:
        restored.close()


def test_committed_cache_hash_and_symlink_ancestors_are_not_trusted_on_reopen(setup, tmp_path):
    coordinator, owner, port, current, store = setup
    owner.data["stdout"] = b"verified"
    coordinator.start()
    coordinator.close()
    (coordinator.root / "remote-stdout.log").write_bytes(b"modified")
    with pytest.raises(RemoteProtocolError, match="COMMITTED_HASH"):
        SshRunCoordinator(store, owner.identity)
    alias = tmp_path / "alias"
    alias.symlink_to(store, target_is_directory=True)
    with pytest.raises(ValueError):
        SshRunCoordinator(alias, owner.identity)


def test_authoritative_run_config_hash_factory_and_logical_timeout(tmp_path):
    from easyai.domain.contracts import RunConfig
    from easyai.domain.remote_run import identity_from_config

    owner = Owner(identity())
    auth = auth_for(owner.identity)
    config = RunConfig(
        run_id=owner.identity.run_id,
        project_id=owner.identity.project_id,
        project_revision=1,
        program_hash=owner.identity.program_hash,
        code_hash=owner.identity.code_hash,
        bundle_hash=owner.identity.bundle_hash,
        target_id=owner.identity.target_id,
        runner="ssh",
        data_root="/synthetic/data",
        run_root=owner.identity.run_root,
        python_executable="/synthetic/python",
        execution_mode="full",
        seed=42,
        num_workers=0,
    )
    generated = identity_from_config(config, auth, owner.identity.launch_id)
    raw = json.dumps(
        config.model_dump(mode="json", by_alias=True), sort_keys=True, separators=(",", ":")
    ).encode()
    assert generated.config_hash == digest(raw)
    assert (
        generated.config_hash
        != identity_from_config(
            config.model_copy(update={"data_root": "/other/data"}), auth, generated.launch_id
        ).config_hash
    )
    with pytest.raises(ValueError):
        identity_from_config(
            config.model_copy(update={"runner": "local"}), auth, generated.launch_id
        )
    clock = [0.0]
    store = tmp_path / "clock-store"
    store.mkdir()
    coordinator = SshRunCoordinator(store, owner.identity, clock=lambda: clock[0])
    try:
        coordinator.attach(auth, Transport(owner), lambda: auth)
        owner.start_hook = lambda: clock.__setitem__(0, 30.0)
        with pytest.raises(RemoteProtocolError, match="STATE_UNKNOWN"):
            coordinator.start()
        assert coordinator.checkpoint().start_outcome == "unknown" and owner.start_calls == 1
    finally:
        coordinator.close()


def test_crash_after_start_marker_before_checkpoint_recovers_inspect_only(setup):
    coordinator, owner, port, current, store = setup
    publish = coordinator._start_marker

    def crash():
        publish()
        raise SystemExit("synthetic process-crash boundary")

    coordinator._start_marker = crash
    with pytest.raises(SystemExit):
        coordinator.start()
    coordinator.close()
    assert owner.start_calls == 0
    restored = SshRunCoordinator(store, owner.identity)
    try:
        assert restored.checkpoint().start_outcome == "unknown"
        assert restored.checkpoint().execution_state == "STARTING"
        fresh = auth_for(owner.identity)
        restored.attach(fresh, Transport(owner), lambda: fresh)
        with pytest.raises(RemoteProtocolError, match="STATE_UNKNOWN"):
            restored.start()
        assert owner.start_calls == 0
        assert restored.checkpoint().start_outcome == "unknown"
    finally:
        restored.close()


def test_transport_close_failure_retains_owner_even_when_no_io_is_running(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    owner = Owner(identity())
    coordinator = SshRunCoordinator(store, owner.identity)

    class FailedClose(Transport):
        def close(self):
            raise RuntimeError("synthetic failed close")

    port = FailedClose(owner)
    auth = auth_for(owner.identity)
    coordinator.attach(auth, port, lambda: auth)
    coordinator.start()
    coordinator.disconnect()
    assert port.quiescent and not port.closed
    fresh = auth_for(owner.identity)
    with pytest.raises(RemoteProtocolError, match="CLEANUP_UNCONFIRMED"):
        coordinator.attach(fresh, Transport(owner), lambda: fresh)
    with pytest.raises(RemoteProtocolError, match="CLEANUP_UNCONFIRMED"):
        coordinator.close()
    assert coordinator._retiring is not None and not coordinator._retiring.succeeded
    # Test teardown only: the fake has no OS handles. Do not add a product retry/bypass.
    coordinator._journal.close()
    coordinator._lock.close()
    import os

    os.close(coordinator._fd)
    coordinator._closed = True
