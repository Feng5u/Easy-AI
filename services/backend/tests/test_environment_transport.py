"""In-memory SSH channel protocol, never a network handshake or real credential."""

from concurrent.futures import ThreadPoolExecutor
import shlex
import socket
import threading

import pytest

from easyai.domain.environment import EnvironmentScope
from easyai.domain.ssh import SshEndpoint
from easyai.services.environment_transport import (
    EnvironmentFailure,
    ReadOnlyCommand,
    SshProbeTransport,
)


class Channel:
    def __init__(
        self, out=b'{"synthetic":true}', err=b"", eof=True, closed=False, code=0, blocked=False
    ):
        self.out, self.err = bytearray(out), bytearray(err)
        self.eof_received, self.closed, self.code = eof, closed, code
        self.stdin = bytearray()
        self.stdin_eof = False
        self.entered, self.release = threading.Event(), threading.Event()
        self.blocked = blocked
        self.command = None
        self.receives = [0, 0]

    def settimeout(self, value):
        self.timeout = value

    def exec_command(self, command):
        self.command = command
        self.entered.set()
        if self.blocked:
            assert self.release.wait(2)
            raise RuntimeError("DO_NOT_LEAK_SDK_EXCEPTION")

    def send_ready(self):
        return True

    def send(self, value):
        self.stdin.extend(value)
        return len(value)

    def shutdown_write(self):
        self.stdin_eof = True

    def recv_ready(self):
        return bool(self.out)

    def recv_stderr_ready(self):
        return bool(self.err)

    def recv(self, size):
        self.receives[0] += 1
        raw = bytes(self.out[:size])
        del self.out[:size]
        return raw

    def recv_stderr(self, size):
        self.receives[1] += 1
        raw = bytes(self.err[:size])
        del self.err[:size]
        return raw

    def exit_status_ready(self):
        return True

    def recv_exit_status(self):
        assert not self.out and not self.err and self.eof_received
        return self.code

    def close(self):
        self.closed = True
        self.release.set()


class Session:
    def __init__(self, channel):
        self.endpoint = SshEndpoint(host="synthetic.invalid")
        self.host_fingerprint = "SHA256:" + "A" * 43
        self.channel = channel
        self.authenticated = True
        self.opens = 0
        self.closed = False

    def validate_probe_session(self):
        if not self.authenticated:
            raise RuntimeError("DO_NOT_LEAK_UNAUTHENTICATED")

    def open_probe_channel(self, timeout):
        self.validate_probe_session()
        self.opens += 1
        return self.channel

    def close(self):
        self.closed = True
        self.channel.close()


def adapter(channel=None, clock=None):
    session = Session(channel or Channel())
    scope = EnvironmentScope(
        project_id="11111111-1111-4111-8111-111111111111",
        connection_id="22222222-2222-4222-8222-222222222222",
        endpoint=session.endpoint,
        host_fingerprint=session.host_fingerprint,
    )
    return SshProbeTransport(scope, session, **({"clock": clock} if clock else {})), session


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("Synthetic channel suite must not dial")

    monkeypatch.setattr(socket, "create_connection", fail)


def test_exact_posix_quoting_bounded_stdin_and_both_streams_drained_before_status():
    channel = Channel(out=b"o" * 20000, err=b"e" * 19000)
    transport, session = adapter(channel)
    literal = "/synthetic/python; $(not-executed) ' spaced"
    result = transport.execute(
        ReadOnlyCommand((literal, "-I", "-B", "-c", "print('fixed source')"), b"x" * 1300),
        threading.Event(),
    )
    assert result.stdout == b"o" * 20000 and result.stderr == b"e" * 19000
    argv = shlex.split(channel.command)
    assert argv[:4] == ["/usr/bin/timeout", "--signal=TERM", "--kill-after=2s", "5s"]
    assert argv[-5:] == [literal, "-I", "-B", "-c", "print('fixed source')"]
    assert channel.stdin == b"x" * 1300 and channel.stdin_eof
    assert min(channel.receives) >= 3 and channel.closed and not session.closed


@pytest.mark.parametrize("kind", ["auth", "endpoint", "fingerprint"])
def test_unverified_auth_or_changed_target_cannot_open_channel(kind):
    transport, session = adapter()
    if kind == "auth":
        session.authenticated = False
    elif kind == "endpoint":
        session.endpoint = SshEndpoint(host="other.invalid")
    else:
        session.host_fingerprint = "SHA256:" + "B" * 43
    with pytest.raises(
        EnvironmentFailure, match="(AUTHENTICATION_REQUIRED|TARGET_CHANGED)"
    ) as raised:
        transport.execute(ReadOnlyCommand(("/synthetic/python",)), threading.Event())
    assert session.opens == 0 and session.closed and "DO_NOT_LEAK" not in str(raised.value)


@pytest.mark.parametrize("channel", [Channel(out=b"x" * 65537), Channel(err=b"x" * 32769)])
def test_each_stream_limit_closes_the_owned_session(channel):
    transport, session = adapter(channel)
    with pytest.raises(EnvironmentFailure, match="OUTPUT_LIMIT"):
        transport.execute(ReadOnlyCommand(("/synthetic/python",)), threading.Event())
    assert channel.closed and session.closed


@pytest.mark.parametrize("channel", [Channel(eof=False, closed=True), Channel(code=-1)])
def test_close_without_received_eof_and_missing_status_fail_closed(channel):
    transport, session = adapter(channel)
    with pytest.raises(EnvironmentFailure, match="EXIT_UNCONFIRMED"):
        transport.execute(ReadOnlyCommand(("/synthetic/python",)), threading.Event())
    assert session.closed


def test_eof_can_arrive_before_exit_status_without_false_failure():
    channel = Channel()
    polls = [0]

    def ready():
        polls[0] += 1
        return polls[0] > 1

    channel.exit_status_ready = ready
    transport, session = adapter(channel)
    assert (
        transport.execute(ReadOnlyCommand(("/synthetic/python",)), threading.Event()).exit_code == 0
    )
    assert polls[0] >= 2 and not session.closed


@pytest.mark.parametrize("cancelled", [False, True])
def test_blocked_exec_ack_is_released_by_timeout_or_cancel_and_old_session_not_reused(cancelled):
    channel = Channel(blocked=True)
    clock = [0]

    def advancing():
        clock[0] += 10
        return clock[0]

    transport, session = adapter(channel, None if cancelled else advancing)
    cancel = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(transport.execute, ReadOnlyCommand(("/synthetic/python",)), cancel)
        assert channel.entered.wait(1)
        if cancelled:
            cancel.set()
        with pytest.raises(EnvironmentFailure, match="(CANCELLED|TIMEOUT)") as raised:
            future.result(timeout=2)
    assert "DO_NOT_LEAK" not in str(raised.value) and session.closed and channel.closed
    with pytest.raises(EnvironmentFailure, match="SESSION_CLOSED"):
        transport.execute(ReadOnlyCommand(("/synthetic/python",)), threading.Event())


def test_cancelled_before_start_and_invalid_command_do_not_spawn_channel():
    transport, session = adapter()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(EnvironmentFailure, match="CANCELLED"):
        transport.execute(ReadOnlyCommand(("/synthetic/python",)), cancel)
    assert session.opens == 0
    for command in [
        ReadOnlyCommand(("bad\0arg",)),
        ReadOnlyCommand(("/synthetic/python",), stdin=b"x" * 8193),
        ReadOnlyCommand(("/synthetic/python",), seconds=float("nan")),
    ]:
        with pytest.raises(EnvironmentFailure, match="COMMAND_INVALID"):
            command.shell_command()


def test_unconfirmed_worker_cleanup_is_explicit_and_never_allows_parallel_reuse():
    channel = Channel(blocked=True)

    # Simulate an SDK call that does not cooperate with close. Release it in
    # finally so even this negative test leaves no live owned worker behind.
    def stubborn(command):
        channel.entered.set()
        assert channel.release.wait(4)
        raise RuntimeError("DO_NOT_LEAK_STUBBORN_SDK")

    channel.exec_command = stubborn
    transport, session = adapter(channel)

    def close_without_wake():
        session.closed = True
        channel.closed = True

    session.close = close_without_wake
    cancel = threading.Event()
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(transport.execute, ReadOnlyCommand(("/synthetic/python",)), cancel)
            assert channel.entered.wait(1)
            cancel.set()
            with pytest.raises(EnvironmentFailure, match="CLEANUP_UNCONFIRMED"):
                future.result(timeout=3)
            with pytest.raises(EnvironmentFailure, match="BUSY"):
                transport.execute(ReadOnlyCommand(("/synthetic/python",)), threading.Event())
            assert session.opens == 1
    finally:
        channel.release.set()
        assert transport._busy.acquire(timeout=1)
        transport._busy.release()
