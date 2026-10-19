"""Fixed, bounded SSH install-helper protocol. Never a public command executor."""

import json
import shlex
import threading
import time
from typing import Any, Callable

from easyai.services.remote_install import resource
from easyai.services.ssh_client import VerifiedSshSession


class InstallSshTransport:
    def __init__(
        self,
        session: VerifiedSshSession,
        mutex: threading.RLock,
        guard: Callable[[], None],
        launcher: str,
    ):
        self.session, self.mutex, self.guard, self.launcher = session, mutex, guard, launcher
        self._operation_gate = threading.Lock()
        self._cleanup_owner: tuple[Any, threading.Event] | None = None

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self._operation_gate.acquire(blocking=False):
            raise ValueError("INSTALL_REMOTE_BUSY")
        try:
            return self._call_owned(request)
        finally:
            self._operation_gate.release()

    def _call_owned(self, request: dict[str, Any]) -> dict[str, Any]:
        if request["action"] not in {
            "snapshot",
            "reserve",
            "verify",
            "allocate",
            "mark-owned",
            "mark-ready",
            "run",
            "inspect",
            "cancel",
            "release",
        }:
            raise ValueError("INSTALL_REMOTE_OPERATION_FORBIDDEN")
        source = resource("install_owner.py")
        # Python source and request come exclusively from the fixed backend adapter.
        # The renderer only references a saved target/connection, never this payload.
        payload = (
            "__easyai_install_source__="
            + repr(source)
            + "\n"
            + source
            + "\n_request="
            + repr(request)
            + "\nprint(json.dumps(dispatch(_request),separators=(',',':')))\n"
        ).encode()
        if len(payload) > 2 * 1024 * 1024:
            raise ValueError("INSTALL_REMOTE_PROTOCOL_LIMIT")
        pending = self._cleanup_owner
        if pending is not None:
            previous, done = pending
            if not done.is_set() or not (previous.closed or self.session.closed_quiescent):
                raise ValueError("INSTALL_REMOTE_CLEANUP_UNCONFIRMED")
            self._cleanup_owner = None
            self.session.io_lock.release()
        if not self.session.io_lock.acquire(blocking=False):
            raise ValueError("INSTALL_REMOTE_BUSY")
        channel = None
        try:
            with self.mutex:
                self.guard()
            channel = self.session.open_probe_channel(timeout=2)
            channel.settimeout(0.1)
            # __name__ deliberately differs from __main__: only explicit dispatch
            # below runs; the helper CLI cannot consume this source stream twice.
            fixed = "import sys;exec(compile(sys.stdin.buffer.read(),'<easyai-install>','exec'),{'__name__':'easyai_install_rpc'})"
            channel.exec_command(
                shlex.join(
                    (
                        "/usr/bin/timeout",
                        "--signal=TERM",
                        "--kill-after=2s",
                        "20s",
                        self.launcher,
                        "-I",
                        "-S",
                        "-B",
                        "-c",
                        fixed,
                    )
                )
            )
            deadline = time.monotonic() + 22
            sent, eof = 0, False
            out, err = bytearray(), bytearray()
            while True:
                with self.mutex:
                    self.guard()
                if time.monotonic() > deadline:
                    raise ValueError("INSTALL_REMOTE_UNAVAILABLE")
                if sent < len(payload) and channel.send_ready():
                    count = channel.send(payload[sent : sent + 32768])
                    if count <= 0:
                        raise ValueError("INSTALL_REMOTE_UNAVAILABLE")
                    sent += count
                if sent == len(payload) and not eof:
                    channel.shutdown_write()
                    eof = True
                for ready, receive, sink in (
                    (channel.recv_ready, channel.recv, out),
                    (channel.recv_stderr_ready, channel.recv_stderr, err),
                ):
                    if ready():
                        sink.extend(receive(32768))
                        if len(sink) > 2 * 1024 * 1024:
                            raise ValueError("INSTALL_REMOTE_PROTOCOL_LIMIT")
                if (
                    channel.eof_received
                    and not channel.recv_ready()
                    and not channel.recv_stderr_ready()
                    and channel.exit_status_ready()
                ):
                    if channel.recv_exit_status() != 0:
                        raise ValueError("INSTALL_REMOTE_UNAVAILABLE")
                    break
                if channel.closed:
                    raise ValueError("INSTALL_REMOTE_UNAVAILABLE")
                time.sleep(0.002)
            value = json.loads(out)
            if not isinstance(value, dict) or value.get("error"):
                raise ValueError("INSTALL_REMOTE_UNAVAILABLE")
            with self.mutex:
                self.guard()
            return value
        except Exception:
            # A channel close is never a remote owner exit receipt. No raw SDK,
            # source paths, credentials or process output cross the API boundary.
            raise ValueError("INSTALL_REMOTE_UNAVAILABLE") from None
        finally:
            if channel is None:
                self.session.io_lock.release()  # No SDK channel was acquired.
            else:
                done = threading.Event()

                def cleanup() -> None:
                    try:
                        channel.close()
                    except Exception:
                        pass
                    finally:
                        done.set()

                owner = threading.Thread(
                    target=cleanup, name="easyai-install-channel-close", daemon=True
                )
                self._cleanup_owner = (channel, done)
                owner.start()
                done.wait(0.2)
                if done.is_set() and (channel.closed or self.session.closed_quiescent):
                    self._cleanup_owner = None
                    self.session.io_lock.release()
                else:
                    # Retain both the actual SDK owner and its I/O gate. Neither
                    # a successful JSON reply nor accepted close proves cleanup.
                    raise ValueError("INSTALL_REMOTE_CLEANUP_UNCONFIRMED")
