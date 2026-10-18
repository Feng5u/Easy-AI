"""Bounded read-only command transport for a dedicated authenticated SSH session.

No PTY, agent forwarding, install commands, remote script files or raw shell API.
Closing an SSH channel is NOT evidence that a remote process has exited. Fixed
commands additionally require /usr/bin/timeout on the Linux target; no fallback.
"""

from dataclasses import dataclass
import math
import shlex
import threading
import time
from typing import Any, Callable, Protocol

from easyai.domain.environment import EnvironmentScope
from easyai.domain.ssh import SshEndpoint

MAX_STDOUT = 65536
MAX_STDERR = 32768


class EnvironmentFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class ReadOnlyCommand:
    argv: tuple[str, ...]
    stdin: bytes = b""
    seconds: float = 5

    def shell_command(self) -> str:
        if (
            not self.argv
            or not math.isfinite(self.seconds)
            or not 0 < self.seconds <= 20
            or len(self.stdin) > 8192
            or any("\0" in arg for arg in self.argv)
        ):
            raise EnvironmentFailure("ENVIRONMENT_COMMAND_INVALID")
        argv = (
            "/usr/bin/timeout",
            "--signal=TERM",
            "--kill-after=2s",
            f"{self.seconds:g}s",
            "/usr/bin/env",
            "PYTHONDONTWRITEBYTECODE=1",
            "CONDA_NO_PLUGINS=true",
            *self.argv,
        )
        value = shlex.join(argv)
        if len(value.encode()) > 32768:
            raise EnvironmentFailure("ENVIRONMENT_COMMAND_INVALID")
        return value


@dataclass(frozen=True)
class CommandResult:
    stdout: bytes
    stderr: bytes
    exit_code: int


class ProbeTransport(Protocol):
    scope: EnvironmentScope

    @property
    def quiescent(self) -> bool: ...

    def execute(self, command: ReadOnlyCommand, cancel: threading.Event) -> CommandResult: ...
    def close(self) -> None: ...


class ProbeSession(Protocol):
    @property
    def endpoint(self) -> SshEndpoint: ...
    @property
    def host_fingerprint(self) -> str: ...
    def validate_probe_session(self) -> None: ...
    def open_probe_channel(self, timeout: float) -> Any: ...
    def close(self) -> None: ...


class SshProbeTransport:
    def __init__(
        self,
        scope: EnvironmentScope,
        session: ProbeSession,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.scope = scope
        self._session = session
        self._clock = clock
        self._busy = threading.Lock()
        self._closed = threading.Event()

    @property
    def quiescent(self) -> bool:
        acquired = self._busy.acquire(blocking=False)
        if not acquired:
            return False
        self._busy.release()
        return not self._closed.is_set() or bool(getattr(self._session, "closed_quiescent", False))

    def close(self) -> None:
        self._closed.set()
        try:
            self._session.close()
        except Exception:
            pass

    def _verify(self) -> None:
        if self._closed.is_set():
            raise EnvironmentFailure("ENVIRONMENT_SESSION_CLOSED")
        if (
            self._session.endpoint != self.scope.endpoint
            or self._session.host_fingerprint != self.scope.host_fingerprint
        ):
            raise EnvironmentFailure("ENVIRONMENT_TARGET_CHANGED")
        try:
            self._session.validate_probe_session()
        except Exception:
            raise EnvironmentFailure("ENVIRONMENT_AUTHENTICATION_REQUIRED") from None

    def execute(self, command: ReadOnlyCommand, cancel: threading.Event) -> CommandResult:
        shell = command.shell_command()
        if not self._busy.acquire(blocking=False):
            raise EnvironmentFailure("ENVIRONMENT_BUSY")
        handed_off = False
        try:
            self._verify()
            if cancel.is_set():
                raise EnvironmentFailure("ENVIRONMENT_CANCELLED")
            finished = threading.Event()
            result: list[CommandResult | Exception] = []
            channels: list[Any] = []

            def worker() -> None:
                try:
                    channel = self._session.open_probe_channel(timeout=2)
                    channels.append(channel)
                    channel.settimeout(0.1)
                    channel.exec_command(shell)
                    out, err = bytearray(), bytearray()
                    sent, eof = 0, False
                    while True:
                        if cancel.is_set() or self._closed.is_set():
                            raise EnvironmentFailure("ENVIRONMENT_CANCELLED")
                        if sent < len(command.stdin) and channel.send_ready():
                            count = channel.send(command.stdin[sent : sent + 512])
                            if count <= 0:
                                raise EnvironmentFailure("ENVIRONMENT_CHANNEL_CLOSED")
                            sent += count
                        if sent == len(command.stdin) and not eof:
                            channel.shutdown_write()
                            eof = True
                        for ready, receive, destination, limit in (
                            (channel.recv_ready, channel.recv, out, MAX_STDOUT),
                            (channel.recv_stderr_ready, channel.recv_stderr, err, MAX_STDERR),
                        ):
                            if ready():
                                destination.extend(receive(8192))
                                if len(destination) > limit:
                                    raise EnvironmentFailure("ENVIRONMENT_OUTPUT_LIMIT")
                        if (
                            (channel.eof_received or channel.closed)
                            and not channel.recv_ready()
                            and not channel.recv_stderr_ready()
                        ):
                            if not channel.eof_received or not eof:
                                raise EnvironmentFailure("ENVIRONMENT_EXIT_UNCONFIRMED")
                            if not channel.exit_status_ready():
                                if channel.closed:
                                    raise EnvironmentFailure("ENVIRONMENT_EXIT_UNCONFIRMED")
                                finished.wait(0.005)
                                continue
                            code = channel.recv_exit_status()
                            if not 0 <= code <= 255:
                                raise EnvironmentFailure("ENVIRONMENT_EXIT_UNCONFIRMED")
                            result.append(CommandResult(bytes(out), bytes(err), code))
                            break
                        finished.wait(0.005)
                except Exception as error:
                    result.append(
                        error
                        if isinstance(error, EnvironmentFailure)
                        else EnvironmentFailure("ENVIRONMENT_COMMAND_FAILED")
                    )
                finally:
                    try:
                        for channel in channels:
                            try:
                                channel.close()
                            except Exception:
                                pass
                    finally:
                        self._busy.release()
                        finished.set()

            deadline = self._clock() + command.seconds + 3
            thread = threading.Thread(target=worker, name="easyai-environment-channel", daemon=True)
            thread.start()
            handed_off = True
            failure = None
            while not finished.wait(0.02):
                if cancel.is_set() or self._closed.is_set():
                    failure = "ENVIRONMENT_CANCELLED"
                    break
                if self._clock() >= deadline:
                    failure = "ENVIRONMENT_TIMEOUT"
                    break
            if failure is not None:
                # Dedicated probe connection only; never shared with a training run.
                self.close()
                thread.join(2)
                if thread.is_alive():
                    raise EnvironmentFailure("ENVIRONMENT_CLEANUP_UNCONFIRMED")
                raise EnvironmentFailure(failure)
            if cancel.is_set() or self._closed.is_set():
                self.close()
                raise EnvironmentFailure("ENVIRONMENT_CANCELLED")
            self._verify()
            value = result[0]
            if isinstance(value, Exception):
                self.close()
                raise value from None
            return value
        except Exception:
            self.close()
            raise
        finally:
            if not handed_off:
                self._busy.release()
