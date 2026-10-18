"""Offline API-compatible SSH/SFTP endpoints; socket dialing is forbidden.

The exec fixture parses the fixed argv and executes only test-owned stdlib
bundles on this host. This is not an SSH or SFTP server compatibility test.
"""

from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import threading
import time

import pytest

from easyai.domain.remote_run import identity_digest, identity_from_config
from easyai.runners.ssh import RemoteProtocolError, RemoteUnavailable, SshRunCoordinator
from easyai.services.owner_transport import OwnerSshTransport, UID_CODE
from easyai.services.remote_bundle import RemoteBundle
from test_portable_owner import Bundle
from test_ssh_run_coordinator import auth_for


class File:
    def __init__(self, path, mode, endpoint):
        self.path, self.endpoint = path, endpoint
        if mode == "wx":
            self.stream = path.open("xb")
        else:
            assert mode == "rb"
            self.stream = path.open("rb")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def stat(self):
        return os.fstat(self.stream.fileno())

    def chmod(self, mode):
        assert mode == 0o600
        os.fchmod(self.stream.fileno(), mode)

    def read(self, count):
        assert 0 < count <= 65536
        self.endpoint.read_sizes.append(count)
        self.endpoint.hook("read", self.path)
        return self.stream.read(count)

    def write(self, raw):
        assert len(raw) <= 65536
        self.endpoint.hook("write", self.path)
        self.stream.write(raw)

    def flush(self):
        self.stream.flush()

    def seek(self, offset):
        self.stream.seek(offset)


class Sftp:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def lstat(self, path):
        self.endpoint.hook("lstat", Path(path))
        return Path(path).lstat()

    def listdir(self, path):
        return os.listdir(path)

    def mkdir(self, path, mode):
        assert mode == 0o700
        self.endpoint.hook("mkdir", Path(path))
        Path(path).mkdir(mode=mode, exist_ok=False)

    def open(self, path, mode, *, bufsize):
        assert bufsize == 0
        return File(Path(path), mode, self.endpoint)

    def rename(self, source, destination):
        self.endpoint.renames += 1
        self.endpoint.hook("before_rename", Path(destination))
        if Path(destination).exists() or Path(destination).is_symlink():
            raise FileExistsError(errno.EEXIST, "fixture nonreplace")
        os.rename(source, destination)
        self.endpoint.hook("after_rename", Path(destination))

    def close(self):
        self.endpoint.hook("sftp_close", None)


class Channel:
    def __init__(self, endpoint):
        self.endpoint, self.timeout = endpoint, None
        self.out, self.err = bytearray(), bytearray()
        self.closed, self.eof_received, self.code = False, False, None

    def settimeout(self, value):
        self.timeout = value

    def invoke_subsystem(self, name):
        assert self.timeout and name == "sftp"
        self.endpoint.hook("sftp_ack", None)

    def exec_command(self, shell):
        assert self.timeout
        argv = shlex.split(shell)
        assert argv[:4] == ["/usr/bin/timeout", "--signal=TERM", "--kill-after=2s", "3s"]
        argv = argv[4:]
        assert argv[0] == self.endpoint.bundle.python and argv[1:3] == ["-I", "-B"]
        if argv[3] == "-c":
            assert argv[4] == UID_CODE
            self.endpoint.uid_calls += 1
        else:
            assert argv[3] == self.endpoint.root + "/code/supervisor.py"
            assert argv[4] in ("--start", "--inspect", "--cancel")
            assert argv[5:] == [
                "--run-dir",
                self.endpoint.root,
                "--expected-identity",
                identity_digest(self.endpoint.bundle.identity),
            ]
            self.endpoint.commands.append(argv[4])
        self.endpoint.hook("before_exec", argv)
        # Only the explicitly test-owned bundle and selected local base Python.
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=4)
        self.out.extend(result.stdout)
        self.err.extend(result.stderr)
        self.code, self.eof_received = result.returncode, True
        self.endpoint.hook("after_exec", argv)

    def shutdown_write(self):
        pass

    def recv_ready(self):
        return bool(self.out)

    def recv(self, count):
        raw = bytes(self.out[:count])
        del self.out[:count]
        return raw

    def recv_stderr_ready(self):
        return bool(self.err)

    def recv_stderr(self, count):
        raw = bytes(self.err[:count])
        del self.err[:count]
        return raw

    def exit_status_ready(self):
        return self.code is not None

    def recv_exit_status(self):
        return self.code

    def close(self):
        self.closed = True


class Endpoint:
    def __init__(self, bundle):
        self.bundle, self.root = bundle, bundle.identity.run_root
        self.endpoint, self.host_fingerprint = (
            bundle.identity.endpoint,
            bundle.identity.host_fingerprint,
        )
        self.io_lock = threading.Lock()
        self.closed = False
        self.close_error = False
        self.renames = self.uid_calls = 0
        self.commands, self.read_sizes = [], []
        self.hook = lambda action, target: None

    def open_probe_channel(self, timeout):
        if self.closed:
            raise ValueError("closed fixture")
        return Channel(self)

    def validate_probe_session(self):
        if self.closed:
            raise ValueError("closed fixture")

    def close(self):
        self.closed = True

    @property
    def closed_quiescent(self):
        return self.closed and not self.close_error and not self.io_lock.locked()

    def transport(self, mutex=None, guard=None, allow_start=True):
        return OwnerSshTransport(
            self,
            self.bundle,
            mutex or threading.RLock(),
            guard or self.validate_probe_session,
            lambda channel: Sftp(self),
            allow_start=allow_start,
        )


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *a, **k: pytest.fail("No network in owner adapter suite"),
    )


@pytest.fixture
def prepared(tmp_path):
    source = Bundle(tmp_path)
    # Shell metacharacters remain literal POSIX path characters after argv quoting.
    remote = tmp_path / "远端 run ' ; $(touch SHOULD_NOT_EXIST)"
    config = source.config.model_copy(update={"run_root": str(remote)})
    identity = identity_from_config(config, source.auth, source.identity.launch_id)
    (source.root / "run-config.json").write_text(config.model_dump_json(by_alias=True))
    (source.root / "remote-identity.json").write_text(identity.model_dump_json(by_alias=True))
    frozen = RemoteBundle.freeze(source.root, config, identity)
    endpoint = Endpoint(frozen)
    try:
        yield source, frozen, endpoint
    finally:
        # All cleanup targets are explicit test-owned local files/processes.
        if (remote / "remote-launch.json").exists():
            (remote / "fixture-finish").touch()
            cli = [
                frozen.python,
                "-I",
                "-B",
                str(remote / "code/supervisor.py"),
                "--cancel",
                "--run-dir",
                str(remote),
                "--expected-identity",
                identity_digest(identity),
            ]
            subprocess.run(cli, stdin=subprocess.DEVNULL, capture_output=True, timeout=4)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    if json.loads((remote / "owner-status.json").read_bytes())["sealed"]:
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(0.02)


def wait_observation(transport, identity, *, terminal=False):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        observed = transport.inspect(identity, timeout=3)
        if observed is not None and (
            observed.sealed if terminal else observed.streams.stdout.size_bytes > 0
        ):
            return observed
        time.sleep(0.02)
    pytest.fail("Test-owned owner did not publish observation")


def test_atomic_stage_is_frozen_nonreplace_and_preserves_active_run(prepared):
    source, bundle, endpoint = prepared
    (source.root / "README.md").write_text("changed after freeze")
    transport = endpoint.transport()
    assert transport.stage(bundle.identity, timeout=3) == bundle.identity
    assert endpoint.renames == 1
    root = Path(bundle.identity.run_root)
    assert (root / "README.md").read_bytes() == dict(bundle.files)["README.md"]
    (root / "unknown-user-file").write_text("preserve")
    assert transport.stage(bundle.identity, timeout=3) == bundle.identity
    assert endpoint.renames == 1 and (root / "unknown-user-file").read_text() == "preserve"
    assert not (root.parent / "SHOULD_NOT_EXIST").exists()
    assert all((root / name).stat().st_mode & 0o777 == 0o600 for name, _ in bundle.files)


def test_standard_owner_start_inspect_read_cancel(prepared):
    source, bundle, endpoint = prepared
    identity = bundle.identity
    transport = endpoint.transport()
    transport.stage(identity, timeout=3)
    assert transport.start(identity, timeout=3) == identity
    observed = wait_observation(transport, identity)
    assert not observed.sealed
    raw = bytearray()
    # Read a byte at a time to exercise incremental prefix hashing and UTF8 halves.
    for offset in range(observed.streams.stdout.size_bytes):
        chunk = transport.read(identity, "stdout", offset, 1, timeout=3)
        assert chunk.prefix_sha256 == hashlib.sha256(raw).hexdigest()
        raw.extend(chunk.data)
    assert "标准库" in raw.decode()
    assert transport.cancel(identity, timeout=3) == identity
    final = wait_observation(transport, identity, terminal=True)
    assert final.state == "CANCELLED" and final.exit_code == 130
    assert endpoint.commands.count("--start") == 1
    with pytest.raises(RemoteUnavailable):
        transport.start(identity, timeout=3)


@pytest.mark.parametrize("mutation", ["content", "symlink", "extra_module", "writable", "identity"])
def test_existing_run_conflicts_never_overwrite(prepared, mutation):
    source, bundle, endpoint = prepared
    transport = endpoint.transport()
    transport.stage(bundle.identity, timeout=3)
    root = Path(bundle.identity.run_root)
    path = root / "code/train.py"
    if mutation == "content":
        path.write_text("unknown")
    elif mutation == "symlink":
        path.unlink()
        path.symlink_to(source.root / "code/train.py")
    elif mutation == "extra_module":
        (root / "code/unknown.py").write_text("unknown")
    elif mutation == "writable":
        path.chmod(0o666)
    else:
        (root / "remote-identity.json").write_text("unknown")
    before = path.lstat()
    with pytest.raises(RemoteUnavailable):
        transport.stage(bundle.identity, timeout=3)
    assert path.lstat() == before and endpoint.renames == 1
    assert not endpoint.commands


def test_upload_failure_leaves_only_one_immutable_partial_and_no_execution(prepared):
    source, bundle, endpoint = prepared

    def hook(action, target):
        if action == "write":
            raise OSError("synthetic write failure")

    endpoint.hook = hook
    with pytest.raises(RemoteUnavailable):
        endpoint.transport().stage(bundle.identity, timeout=3)
    root = Path(bundle.identity.run_root)
    assert not root.exists()
    partial = root.parent / (".easyai-stage-" + bundle.identity.launch_id)
    assert partial.is_dir()
    endpoint2 = Endpoint(bundle)
    with pytest.raises(RemoteUnavailable):
        endpoint2.transport().stage(bundle.identity, timeout=3)
    assert list(root.parent.glob(".easyai-stage-*")) == [partial]
    assert not endpoint.commands and not endpoint2.commands


def test_rename_consumed_ack_loss_only_adopts_complete_original_identity(prepared):
    source, bundle, endpoint = prepared

    def hook(action, target):
        if action == "after_rename":
            raise TimeoutError("synthetic ACK loss")

    endpoint.hook = hook
    with pytest.raises(RemoteUnavailable):
        endpoint.transport().stage(bundle.identity, timeout=3)
    endpoint2 = Endpoint(bundle)
    assert endpoint2.transport().stage(bundle.identity, timeout=3) == bundle.identity
    assert endpoint.renames == 1 and endpoint2.renames == 0


def test_unknown_start_reconnect_coordinator_only_inspects(prepared, tmp_path):
    source, bundle, endpoint = prepared
    identity = bundle.identity
    store = tmp_path / "coordinator"
    store.mkdir(mode=0o700)
    coordinator = SshRunCoordinator(store, identity)
    current = [auth_for(identity)]

    def hook(action, argv):
        if action == "after_exec" and argv[3] != "-c" and argv[4] == "--start":
            raise TimeoutError("synthetic consumed start ACK lost")

    endpoint.hook = hook
    transport = endpoint.transport()
    try:
        coordinator.attach(current[0], transport, lambda: current[0])
        with pytest.raises(RemoteProtocolError, match="UNKNOWN"):
            coordinator.start()
        assert coordinator.checkpoint().start_outcome == "unknown"
        (Path(identity.run_root) / "fixture-finish").touch()
        endpoint2 = Endpoint(bundle)
        resumed = endpoint2.transport(allow_start=False)
        current[0] = auth_for(identity)
        coordinator.attach(current[0], resumed, lambda: current[0])
        wait_observation(resumed, identity, terminal=True)
        coordinator.start()  # persisted intent permits poll only
        assert coordinator.checkpoint().execution_state == "COMPLETED"
        assert endpoint.commands.count("--start") == 1 and "--start" not in endpoint2.commands
        assert (Path(identity.run_root) / "fixture-starts").read_text().count("\n") == 1
        assert not coordinator.checkpoint().artifacts_verified
    finally:
        coordinator.close()


def test_stalled_sdk_retains_gate_and_old_lease_cannot_publish(prepared):
    source, bundle, endpoint = prepared
    entered, release = threading.Event(), threading.Event()
    valid = [True]
    mutex = threading.RLock()

    def guard():
        if not valid[0]:
            raise ValueError("expired")

    def hook(action, target):
        if action == "write":
            entered.set()
            assert release.wait(3)

    endpoint.hook = hook
    transport = endpoint.transport(mutex, guard)
    with ThreadPoolExecutor(1) as executor:
        operation = executor.submit(transport.stage, bundle.identity, timeout=0.2)
        assert entered.wait(1)
        with mutex:
            valid[0] = False
        with pytest.raises(RemoteUnavailable):
            operation.result(1)
        assert endpoint.io_lock.locked() and not transport.quiescent
        with pytest.raises(RemoteUnavailable):
            endpoint.transport().stage(bundle.identity, timeout=1)
        release.set()
    deadline = time.monotonic() + 1
    while not transport.quiescent and time.monotonic() < deadline:
        time.sleep(0.01)
    assert transport.quiescent
    assert not Path(bundle.identity.run_root).exists()


@pytest.mark.parametrize(
    "mutation", ["hash", "helper", "extra", "symlink", "config", "unsafe_path"]
)
def test_local_snapshot_rejects_untrusted_source(prepared, mutation):
    source, bundle, endpoint = prepared
    config = source.config.model_copy(update={"run_root": bundle.identity.run_root})
    identity = bundle.identity
    if mutation in ("hash", "helper"):
        name = "code/train.py" if mutation == "hash" else "code/supervisor.py"
        (source.root / name).write_text("# changed")
        if mutation == "helper":
            manifest = json.loads((source.root / "bundle.json").read_bytes())
            manifest["files"][name] = hashlib.sha256(b"# changed").hexdigest()
            manifest["bundleHash"] = hashlib.sha256(
                json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            (source.root / "bundle.json").write_text(json.dumps(manifest))
            config = config.model_copy(update={"bundle_hash": manifest["bundleHash"]})
            identity = identity_from_config(config, source.auth, identity.launch_id)
            (source.root / "run-config.json").write_text(config.model_dump_json(by_alias=True))
            (source.root / "remote-identity.json").write_text(
                identity.model_dump_json(by_alias=True)
            )
    elif mutation == "extra":
        (source.root / "code/unknown.py").touch()
    elif mutation == "symlink":
        (source.root / "code/train.py").unlink()
        (source.root / "code/train.py").symlink_to(source.root / "README.md")
    elif mutation == "config":
        config = config.model_copy(update={"seed": 99})
    else:
        config = config.model_copy(update={"python_executable": "/usr//bin/python"})
        identity = identity_from_config(config, source.auth, identity.launch_id)
    with pytest.raises((ValueError, OSError)):
        RemoteBundle.freeze(source.root, config, identity)
    assert endpoint.uid_calls == 0 and not endpoint.commands


def test_owner_rejects_foreign_expected_identity_before_claim(prepared):
    source, bundle, endpoint = prepared
    transport = endpoint.transport()
    transport.stage(bundle.identity, timeout=3)
    root = Path(bundle.identity.run_root)
    for action in ("start", "serve", "inspect", "cancel"):
        command = [
            bundle.python,
            "-I",
            "-B",
            str(root / "code/supervisor.py"),
            "--" + action,
            "--run-dir",
            str(root),
            "--expected-identity",
            "0" * 64,
        ]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=3)
        assert result.returncode != 0
        assert b"REMOTE_OWNER_PROTOCOL_FAILED" in result.stderr
        assert not (root / "remote-launch.json").exists()
        assert not (root / "serve-claim.json").exists()
    assert not (root / "fixture-starts").exists()


def test_eof_before_exit_status_is_supported(prepared, monkeypatch):
    source, bundle, endpoint = prepared
    original = Channel.exit_status_ready
    calls = [0]

    def delayed(self):
        calls[0] += 1
        return calls[0] > 3 and original(self)

    monkeypatch.setattr(Channel, "exit_status_ready", delayed)
    assert endpoint.transport().stage(bundle.identity, timeout=3) == bundle.identity
    assert calls[0] >= 4


@pytest.mark.parametrize(
    "failure",
    ["uid_nonce", "uid_noise", "wrong_identity", "output_limit", "stderr_limit", "missing_eof"],
)
def test_command_protocol_refuses_untrusted_output(prepared, monkeypatch, failure):
    source, bundle, endpoint = prepared
    original = Channel.exec_command

    def bad(self, command):
        original(self, command)
        if failure == "uid_nonce":
            value = json.loads(self.out)
            value["nonce"] = "foreign"
            self.out = bytearray(json.dumps(value).encode())
        elif failure == "uid_noise":
            self.out.extend(b"\nnoise")
        elif failure == "output_limit":
            self.out = bytearray(b"x" * 65537)
        elif failure == "stderr_limit":
            self.err = bytearray(b"x" * 32769)
        elif failure == "missing_eof":
            self.eof_received, self.closed = False, True
        else:
            value = json.loads(self.out)
            value["platform"] = "other"
            self.out = bytearray(json.dumps(value).encode())

    monkeypatch.setattr(Channel, "exec_command", bad)
    with pytest.raises(RemoteUnavailable):
        endpoint.transport().stage(bundle.identity, timeout=2)
    assert not Path(bundle.identity.run_root).exists() and not endpoint.commands


def test_read_generation_and_snapshot_bounds_are_enforced(prepared):
    source, bundle, endpoint = prepared
    identity = bundle.identity
    transport = endpoint.transport()
    transport.stage(identity, timeout=3)
    transport.start(identity, timeout=3)
    observed = wait_observation(transport, identity)
    with pytest.raises(RemoteProtocolError):
        transport.read(identity, "stdout", 0, observed.streams.stdout.size_bytes + 1, timeout=3)
    with pytest.raises(RemoteProtocolError):
        transport.read(identity, "unknown", 0, 1, timeout=3)
    launch = Path(identity.run_root) / "remote-launch.json"
    value = json.loads(launch.read_bytes())
    value["generations"]["stdout"] = "00000000-0000-4000-8000-000000000000"
    launch.write_text(json.dumps(value))
    with pytest.raises(RemoteUnavailable):
        transport.read(identity, "stdout", 0, 1, timeout=3)


def test_identity_swap_after_stage_blocks_owner_execution(prepared):
    source, bundle, endpoint = prepared
    transport = endpoint.transport()
    transport.stage(bundle.identity, timeout=3)
    target = Path(bundle.identity.run_root) / "remote-identity.json"
    target.write_text("{}")
    with pytest.raises(RemoteUnavailable):
        transport.start(bundle.identity, timeout=3)
    assert endpoint.commands == []
    assert target.read_text() == "{}"


def test_remote_readback_corruption_blocks_publication(prepared):
    source, bundle, endpoint = prepared
    corrupted = [False]

    def hook(action, path):
        if action == "read" and path.name == "README.md" and not corrupted[0]:
            corrupted[0] = True
            path.write_text("bad")

    endpoint.hook = hook
    with pytest.raises(RemoteUnavailable):
        endpoint.transport().stage(bundle.identity, timeout=3)
    assert corrupted[0] and endpoint.renames == 0
    assert not Path(bundle.identity.run_root).exists() and not endpoint.commands


def test_failed_socket_cleanup_stays_nonquiescent(prepared):
    source, bundle, endpoint = prepared
    endpoint.close_error = True  # model VerifiedSession's failed cleanup flag

    def hook(action, target):
        if action == "sftp_close":
            raise OSError("synthetic SDK close error")

    endpoint.hook = hook
    transport = endpoint.transport()
    with pytest.raises(RemoteUnavailable):
        transport.stage(bundle.identity, timeout=3)
    assert endpoint.closed and not transport.quiescent
    renames = endpoint.renames
    with pytest.raises(RemoteUnavailable):
        transport.stage(bundle.identity, timeout=1)
    assert endpoint.renames == renames and not endpoint.commands


def test_resume_reads_prefix_once_then_advances_incrementally(prepared):
    source, bundle, endpoint = prepared
    identity = bundle.identity
    transport = endpoint.transport()
    transport.stage(identity, timeout=3)
    transport.start(identity, timeout=3)
    (Path(identity.run_root) / "fixture-finish").touch()
    wait_observation(transport, identity, terminal=True)
    log = (Path(identity.run_root) / "logs/train.log").read_bytes()
    assert len(log) > 10
    endpoint2 = Endpoint(bundle)
    resumed = endpoint2.transport(allow_start=False)
    resumed.inspect(identity, timeout=3)
    actual_flow_reads = []

    def hook(action, path):
        if action == "read" and path.name == "train.log":
            actual_flow_reads.append(endpoint2.read_sizes[-1])

    endpoint2.hook = hook
    first = resumed.read(identity, "stdout", 10, 1, timeout=3)
    second = resumed.read(identity, "stdout", 11, 1, timeout=3)
    assert first.prefix_sha256 == hashlib.sha256(log[:10]).hexdigest()
    assert second.prefix_sha256 == hashlib.sha256(log[:11]).hexdigest()
    assert actual_flow_reads == [10, 1, 1]
    assert first.data + second.data == log[10:12]


@pytest.mark.parametrize("record", ["run-config.json", "remote-identity.json"])
def test_snapshot_must_match_persisted_authority(prepared, record):
    source, bundle, endpoint = prepared
    config = source.config.model_copy(update={"run_root": bundle.identity.run_root})
    target = source.root / record
    original = target.read_bytes()
    if record == "run-config.json":
        value = json.loads(original)
        value["seed"] += 1
        target.write_text(json.dumps(value))
    else:
        target.unlink()
    with pytest.raises((ValueError, OSError)):
        RemoteBundle.freeze(source.root, config, bundle.identity)
    assert endpoint.uid_calls == 0 and not endpoint.commands


def test_conda_launch_vector_is_frozen_and_requires_paired_prefix(prepared):
    source, _, _ = prepared
    config = source.config.model_copy(
        update={
            "conda_executable": "/synthetic/conda bin",
            "environment_prefix": "/synthetic/class env",
        }
    )
    identity = identity_from_config(config, source.auth, source.identity.launch_id)
    (source.root / "run-config.json").write_text(config.model_dump_json(by_alias=True))
    (source.root / "remote-identity.json").write_text(identity.model_dump_json(by_alias=True))
    frozen = RemoteBundle.freeze(source.root, config, identity)
    assert frozen.python_argv() == (
        "/synthetic/conda bin",
        "run",
        "-p",
        "/synthetic/class env",
        "--no-capture-output",
        config.python_executable,
    )
    invalid = config.model_copy(update={"environment_prefix": None})
    with pytest.raises(ValueError):
        RemoteBundle.freeze(source.root, invalid, identity)
