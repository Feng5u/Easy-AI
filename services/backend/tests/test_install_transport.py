"""Synthetic channel protocol, especially unknown SDK cleanup; no connection."""

import ast
import json
import threading
from types import SimpleNamespace

import pytest
from easyai.services.install_transport import InstallSshTransport
from easyai.services.remote_install import resource


class Channel:
    def __init__(self, quiet):
        self.closed = False
        self.eof_received = False
        self.quiet = quiet
        self.sent = bytearray()
        self.out = json.dumps({"nonce": "fixture"}).encode()

    def settimeout(self, value):
        pass

    def exec_command(self, value):
        self.command = value

    def send_ready(self):
        return True

    def send(self, value):
        self.sent.extend(value)
        return len(value)

    def shutdown_write(self):
        self.eof_received = True

    def recv_ready(self):
        return bool(self.out)

    def recv(self, size):
        value, self.out = self.out, b""
        return value

    def recv_stderr_ready(self):
        return False

    def recv_stderr(self, size):
        return b""

    def exit_status_ready(self):
        return len(self.sent) > 0

    def recv_exit_status(self):
        return 0

    def close(self):
        self.closed = self.quiet


def fixture(quiet):
    channel = Channel(quiet)
    session = SimpleNamespace(
        io_lock=threading.Lock(), closed_quiescent=False, open_probe_channel=lambda **k: channel
    )
    transport = InstallSshTransport(session, threading.RLock(), lambda: None, "/synthetic/python")
    return transport, channel, session


def test_fixed_stdin_namespace_keeps_exact_source_and_quiet_cleanup_releases_gate():
    transport, channel, session = fixture(True)
    assert transport.call({"action": "snapshot", "nonce": "fixture"}) == {"nonce": "fixture"}
    assert not session.io_lock.locked()
    tree = ast.parse(channel.sent.decode())
    assignment = tree.body[0]
    assert assignment.targets[0].id == "__easyai_install_source__"
    assert ast.literal_eval(assignment.value) == resource("install_owner.py")
    assert "--signal=TERM" in channel.command and "-I -S -B -c" in channel.command


def test_unknown_sdk_close_keeps_actual_owner_and_shared_gate():
    transport, channel, session = fixture(False)
    with pytest.raises(ValueError, match="INSTALL_REMOTE_CLEANUP_UNCONFIRMED"):
        transport.call({"action": "snapshot", "nonce": "fixture"})
    assert session.io_lock.locked() and transport._cleanup_owner[0] is channel
    with pytest.raises(ValueError, match="INSTALL_REMOTE_CLEANUP_UNCONFIRMED"):
        transport.call({"action": "snapshot", "nonce": "fixture"})
    # A later real closed flag is the missing SDK evidence; only then release.
    channel.closed = True
    channel.quiet = True
    channel.out = b'{"nonce":"fixture"}'
    assert transport.call({"action": "snapshot", "nonce": "fixture"})["nonce"] == "fixture"
    assert not session.io_lock.locked()


def test_same_adapter_serializes_cleanup_recycle_and_active_request():
    transport, channel, session = fixture(True)
    old = Channel(True)
    old.closed = True
    done = threading.Event()
    done.set()
    session.io_lock.acquire()
    transport._cleanup_owner = (old, done)
    entered, release = threading.Event(), threading.Event()
    original_send = channel.send

    def held_send(value):
        entered.set()
        assert release.wait(2)
        return original_send(value)

    channel.send = held_send
    results = []

    def first():
        results.append(transport.call({"action": "snapshot", "nonce": "fixture"}))

    worker = threading.Thread(target=first)
    worker.start()
    assert entered.wait(1)
    with pytest.raises(ValueError, match="INSTALL_REMOTE_BUSY"):
        transport.call({"action": "snapshot", "nonce": "fixture"})
    assert session.io_lock.locked()
    release.set()
    worker.join(2)
    assert not worker.is_alive() and results == [{"nonce": "fixture"}]
    assert not session.io_lock.locked()
