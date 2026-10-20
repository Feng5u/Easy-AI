"""Fixed portable-owner SSH protocol and non-overwriting SFTP bundle publication.

No public shell/path API. SFTP v3 provides neither O_NOFOLLOW nor durable remote
fsync; protected directories/readback/nonreplace rename do not eliminate a
malicious same-UID race or establish crash durability on an untested server.
"""

import errno
import hashlib
import math
from pathlib import PurePosixPath
import shlex
import threading
import time
from typing import Any, Callable, TypeVar
from uuid import uuid4

import paramiko  # type: ignore[import-untyped]

from easyai.domain.remote_run import RemoteRunIdentity, RemoteRunObservation, identity_digest
from easyai.runners.ssh import RemoteChunk, RemoteProtocolError, RemoteUnavailable, StreamName
from easyai.services.remote_artifacts import _Reader, _decode
from easyai.services.remote_bundle import MAX_FILE, RemoteBundle
from easyai.services.ssh_client import VerifiedSshSession

CHUNK = 65536
FLOWS = {
    "events": "logs/runtime-events.jsonl",
    "stdout": "logs/train.log",
    "stderr": "logs/stderr.log",
}
UID_CODE = 'import json,os,sys;print(json.dumps({"nonce":sys.argv[1],"uid":os.geteuid(),"platform":sys.platform}))'
T = TypeVar("T")


class OwnerSshTransport:
    def __init__(
        self,
        session: VerifiedSshSession,
        bundle: RemoteBundle,
        mutex: threading.RLock,
        guard: Callable[[], None],
        sftp_factory: Callable[[Any], Any] | None = None,
        *,
        allow_start: bool = False,
    ):
        self.session, self.bundle = session, bundle
        self.identity = bundle.identity
        self.mutex, self.guard, self.factory = mutex, guard, sftp_factory or paramiko.SFTPClient
        self._busy = threading.Lock()
        self._closed = threading.Event()
        self._start_sent = False
        self._allow_start = allow_start
        self._uid_value: int | None = None
        self._observation: RemoteRunObservation | None = None
        self._cursors: dict[str, tuple[str, int, Any]] = {}

    @property
    def quiescent(self) -> bool:
        if self._busy.locked() or self.session.io_lock.locked():
            return False
        return not self._closed.is_set() or self.session.closed_quiescent

    def close(self) -> None:
        self._closed.set()
        self.session.close()  # I/O only. Never owner cancel, PID kill, or filesystem cleanup.

    def _operation(
        self, identity: RemoteRunIdentity, timeout: float, action: Callable[[Callable[[], None]], T]
    ) -> T:
        if identity != self.identity or not math.isfinite(timeout) or not 0 < timeout <= 20:
            raise RemoteProtocolError("REMOTE_REQUEST_INVALID")
        if not self._busy.acquire(blocking=False):
            raise RemoteUnavailable()
        if not self.session.io_lock.acquire(blocking=False):
            self._busy.release()
            raise RemoteUnavailable()
        done, abandoned = threading.Event(), threading.Event()
        result: list[T] = []
        deadline = time.monotonic() + timeout

        def check() -> None:
            with self.mutex:
                if self._closed.is_set() or abandoned.is_set() or time.monotonic() >= deadline:
                    raise RemoteUnavailable()
                if (
                    self.session.endpoint != identity.endpoint
                    or self.session.host_fingerprint != identity.host_fingerprint
                ):
                    raise RemoteUnavailable()
                self.guard()

        def worker() -> None:
            try:
                check()
                value = action(check)
                with self.mutex:
                    check()
                    result.append(value)
            except Exception:
                self._closed.set()
            finally:
                if self._closed.is_set():
                    self.session.close()
                self.session.io_lock.release()
                self._busy.release()
                done.set()

        thread = threading.Thread(target=worker, name="easyai-owner-io", daemon=True)
        try:
            thread.start()
        except BaseException:
            self.session.io_lock.release()
            self._busy.release()
            raise
        while not done.wait(0.01):
            with self.mutex:
                if time.monotonic() >= deadline or self._closed.is_set():
                    abandoned.set()
            if abandoned.is_set():
                # Closing SDK I/O may itself stall; worker owns both gates until quiet.
                threading.Thread(target=self.close, name="easyai-owner-close", daemon=True).start()
                raise RemoteUnavailable()
        if not result or self._closed.is_set():
            raise RemoteUnavailable()
        with self.mutex:
            try:
                check()
            except Exception:
                raise RemoteUnavailable() from None
            return result[0]

    def _command(self, argv: tuple[str, ...], check: Callable[[], None]) -> Any:
        # SSH exec is a shell string at protocol level. Only fixed argv with POSIX
        # quoting is permitted; no expansion, pipelines, renderer argv, or PTY.
        shell = shlex.join(("/usr/bin/timeout", "--signal=TERM", "--kill-after=2s", "3s", *argv))
        if len(shell.encode()) > 8192:
            raise RemoteProtocolError("REMOTE_COMMAND_LIMIT")
        channel = self.session.open_probe_channel(timeout=1)
        try:
            channel.settimeout(0.1)
            check()
            channel.exec_command(shell)
            channel.shutdown_write()
            out, err = bytearray(), bytearray()
            while True:
                check()
                for ready, receive, sink, limit in (
                    (channel.recv_ready, channel.recv, out, 65536),
                    (channel.recv_stderr_ready, channel.recv_stderr, err, 32768),
                ):
                    if ready():
                        raw = receive(8192)
                        if not isinstance(raw, bytes):
                            raise RemoteUnavailable()
                        sink.extend(raw)
                        if len(sink) > limit:
                            raise RemoteUnavailable()
                if (
                    (channel.eof_received or channel.closed)
                    and not channel.recv_ready()
                    and not channel.recv_stderr_ready()
                ):
                    if not channel.eof_received:
                        raise RemoteUnavailable()
                    if not channel.exit_status_ready():
                        if channel.closed:
                            raise RemoteUnavailable()
                        time.sleep(0.002)
                        continue
                    if channel.recv_exit_status() != 0:
                        raise RemoteUnavailable()
                    break
                time.sleep(0.002)
            check()
            return _decode(bytes(out))
        finally:
            channel.close()

    def _uid(self, check: Callable[[], None]) -> int:
        if self._uid_value is None:
            nonce = str(uuid4())
            value = self._command(
                (*self.bundle.python_argv(), "-I", "-B", "-c", UID_CODE, nonce), check
            )
            if (
                not isinstance(value, dict)
                or set(value) != {"uid", "nonce", "platform"}
                or value["nonce"] != nonce
                or value["platform"] != "linux"
                or type(value["uid"]) is not int
                or not 0 <= value["uid"] <= 4294967294
            ):
                raise RemoteUnavailable()
            self._uid_value = value["uid"]
        return self._uid_value

    def _sftp(self, check: Callable[[], None]) -> tuple[Any, Any]:
        check()
        channel = self.session.open_probe_channel(timeout=1)
        try:
            channel.settimeout(1)
            channel.invoke_subsystem("sftp")
            check()
            return channel, self.factory(channel)
        except BaseException:
            channel.close()
            raise

    def _reader(self, sftp: Any, path: str, uid: int, check: Callable[[], None]) -> _Reader:
        reader = _Reader(sftp, self.identity.model_copy(update={"run_root": path}), check)
        reader.uid = uid
        return reader

    def _verify(self, sftp: Any, path: str, uid: int, check: Callable[[], None]) -> _Reader:
        reader = self._reader(sftp, path, uid, check)
        for name, expected in self.bundle.files:
            received: list[bytes] = []
            reader.read(name, min(MAX_FILE, len(expected)), received.append)
            if b"".join(received) != expected:
                raise RemoteProtocolError("REMOTE_BUNDLE_MISMATCH")
        check()
        if set(sftp.listdir(str(PurePosixPath(path) / "code"))) != {
            name.removeprefix("code/") for name, _ in self.bundle.files if name.startswith("code/")
        }:
            raise RemoteProtocolError("REMOTE_UNHASHED_CODE")
        check()
        return reader

    def _directory(self, sftp: Any, path: str, uid: int, check: Callable[[], None]) -> _Reader:
        reader = self._reader(sftp, path, uid, check)
        anchor = sftp.lstat("/")
        reader.anchor_uid = anchor.st_uid
        reader._stat(anchor, True, ancestor=True)
        current = PurePosixPath("/")
        for part in PurePosixPath(path).parts[1:]:
            check()
            current /= part
            reader._stat(sftp.lstat(str(current)), True, ancestor=str(current) != path)
        check()
        return reader

    def stage(self, identity: RemoteRunIdentity, *, timeout: float) -> RemoteRunIdentity:
        if not self._allow_start:
            raise RemoteUnavailable()

        def action(check: Callable[[], None]) -> RemoteRunIdentity:
            uid = self._uid(check)
            channel, sftp = self._sftp(check)
            try:
                root = PurePosixPath(identity.run_root)
                parent = str(root.parent)
                # At most one partial per immutable launch across lease/process
                # restarts. An incomplete partial is never merged, deleted or retried.
                partial = str(root.parent / (".easyai-stage-" + identity.launch_id))
                probe = self._directory(sftp, parent, uid, check)
                try:
                    existing = sftp.lstat(str(root))
                except OSError as error:
                    if error.errno != errno.ENOENT:
                        raise
                else:
                    probe._stat(existing, True)
                    self._verify(sftp, str(root), uid, check)
                    return identity
                check()
                sftp.mkdir(partial, mode=0o700)
                staged = self._directory(sftp, partial, uid, check)
                sftp.mkdir(partial + "/code", mode=0o700)
                staged._stat(sftp.lstat(partial + "/code"), True)
                for name, raw in self.bundle.files:
                    check()
                    with sftp.open(partial + "/" + name, "wx", bufsize=0) as output:
                        output.chmod(0o600)  # only this just-created exclusive handle
                        staged._stat(output.stat(), False)
                        for offset in range(0, len(raw), CHUNK):
                            check()
                            output.write(raw[offset : offset + CHUNK])
                        output.flush()
                        check()
                self._verify(sftp, partial, uid, check)
                check()
                # Standard v3 rename requires absent destination. No posix_rename,
                # remove/rmdir or overwrite fallback, including an ACK loss.
                sftp.rename(partial, str(root))
                check()
                self._verify(sftp, str(root), uid, check)
                return identity
            finally:
                try:
                    sftp.close()
                finally:
                    channel.close()

        return self._operation(identity, timeout, action)

    def _owner(self, action: str, check: Callable[[], None]) -> Any:
        uid = self._uid(check)
        channel, sftp = self._sftp(check)
        try:
            self._verify(sftp, self.identity.run_root, uid, check)
        finally:
            sftp.close()
            channel.close()
        check()
        if action == "start":
            with self.mutex:
                check()
                if self._start_sent:
                    raise RemoteUnavailable()
                self._start_sent = True  # BEFORE possibly consuming exec, never reset.
        return self._command(
            (
                *self.bundle.python_argv(),
                "-I",
                "-B",
                self.identity.run_root + "/code/supervisor.py",
                "--" + action,
                "--run-dir",
                self.identity.run_root,
                "--expected-identity",
                identity_digest(self.identity),
            ),
            check,
        )

    def start(self, identity: RemoteRunIdentity, *, timeout: float) -> RemoteRunIdentity:
        if not self._allow_start or self._start_sent:
            raise RemoteUnavailable()

        def action(check: Callable[[], None]) -> RemoteRunIdentity:
            value = RemoteRunIdentity.model_validate(self._owner("start", check))
            if value != identity:
                raise RemoteUnavailable()
            return value

        return self._operation(identity, timeout, action)

    def inspect(
        self, identity: RemoteRunIdentity, *, timeout: float
    ) -> RemoteRunObservation | None:
        def action(check: Callable[[], None]) -> RemoteRunObservation | None:
            # A detached serve can take a short interval to publish its first
            # heartbeat. Only repeat read-only inspection, never start.
            until = time.monotonic() + 0.35
            value = self._owner("inspect", check)
            while value is None and time.monotonic() < until:
                time.sleep(0.05)
                check()
                value = self._owner("inspect", check)
            observed = RemoteRunObservation.model_validate(value) if value is not None else None
            if observed is not None and observed.identity != identity:
                raise RemoteUnavailable()
            self._observation = observed
            return observed

        return self._operation(identity, timeout, action)

    def cancel(self, identity: RemoteRunIdentity, *, timeout: float) -> RemoteRunIdentity:
        def action(check: Callable[[], None]) -> RemoteRunIdentity:
            value = RemoteRunIdentity.model_validate(self._owner("cancel", check))
            if value != identity:
                raise RemoteUnavailable()
            return value

        return self._operation(identity, timeout, action)

    def read(
        self,
        identity: RemoteRunIdentity,
        stream: StreamName,
        offset: int,
        length: int,
        *,
        timeout: float,
    ) -> RemoteChunk:
        if (
            stream not in FLOWS
            or type(offset) is not int
            or offset < 0
            or type(length) is not int
            or not 1 <= length <= CHUNK
        ):
            raise RemoteProtocolError("REMOTE_READ_INVALID")
        observed = self._observation
        if observed is None:
            raise RemoteUnavailable()
        stamp = getattr(observed.streams, stream)
        if offset + length > stamp.size_bytes:
            raise RemoteProtocolError("REMOTE_READ_BEYOND_SNAPSHOT")

        def action(check: Callable[[], None]) -> RemoteChunk:
            uid = self._uid(check)
            channel, sftp = self._sftp(check)
            try:
                reader = self._reader(sftp, identity.run_root, uid, check)
                launch = _decode(reader.record("remote-launch.json"))
                if (
                    set(launch) != {"identity", "generations"}
                    or RemoteRunIdentity.model_validate(launch["identity"]) != identity
                    or set(launch["generations"]) != set(FLOWS)
                    or launch["generations"][stream] != stamp.generation
                ):
                    raise RemoteUnavailable()
                name = FLOWS[stream]
                before = reader._parents(name)
                if before.st_size < stamp.size_bytes:
                    raise RemoteUnavailable()
                previous = self._cursors.get(stream)
                if previous is not None and previous[:2] != (stamp.generation, offset):
                    raise RemoteUnavailable()
                hasher = previous[2].copy() if previous else hashlib.sha256()
                with sftp.open(identity.run_root + "/" + name, "rb", bufsize=0) as source:
                    reader._stat(source.stat(), False)
                    remaining = offset if previous is None else 0
                    while remaining:
                        check()
                        raw = source.read(min(CHUNK, remaining))
                        if not isinstance(raw, bytes) or not 0 < len(raw) <= min(CHUNK, remaining):
                            raise RemoteUnavailable()
                        hasher.update(raw)
                        remaining -= len(raw)
                    prefix = hasher.hexdigest()
                    source.seek(offset)
                    parts, remaining = [], length
                    while remaining:
                        check()
                        raw = source.read(remaining)
                        if not isinstance(raw, bytes) or not 0 < len(raw) <= remaining:
                            raise RemoteUnavailable()
                        parts.append(raw)
                        remaining -= len(raw)
                    data = b"".join(parts)
                    after = source.stat()
                    reader._stat(after, False)
                    if after.st_size < stamp.size_bytes:
                        raise RemoteUnavailable()
                if reader._parents(name).st_size < stamp.size_bytes:
                    raise RemoteUnavailable()
                check()
                hasher.update(data)
                self._cursors[stream] = (stamp.generation, offset + length, hasher)
                return RemoteChunk(identity, stream, stamp.generation, offset, prefix, data)
            finally:
                sftp.close()
                channel.close()

        return self._operation(identity, timeout, action)
