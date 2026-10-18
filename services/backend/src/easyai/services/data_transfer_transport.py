"""Data-only SFTP writes to a new app-owned slot. No run/bundle or shell input.

SFTP v3 has no nofollow/openat or durable fsync. Protected directory checks and
nonreplace rename do not guarantee safety against a malicious same-UID race or
server crash durability. Unknown partial output is preserved, never adopted.
"""

from contextlib import contextmanager
import errno
import hashlib
from pathlib import PurePosixPath
import threading
import time
from typing import Any, Callable, Iterator, TypedDict

import paramiko  # type: ignore[import-untyped]
from easyai.services.data_transfer_errors import TransferFailure
from easyai.domain.environment import EnvironmentScope, remote_path
from easyai.services.environment_transport import SshProbeTransport, ReadOnlyCommand
from easyai.services.remote_artifacts import _Reader, _encoded
from easyai.services.ssh_client import VerifiedSshSession
from easyai.services.data_transfer_source import TransferSource

CHUNK = 65536


class UploadedFile(TypedDict):
    path: str
    bytes: int
    sha256: str


class DataUploadTransport:
    def __init__(
        self,
        scope: EnvironmentScope,
        session: VerifiedSshSession,
        mutex: threading.RLock,
        guard: Callable[[], None],
        factory: Callable[[Any], Any] | None = None,
    ):
        self.scope, self.session, self.mutex, self.guard = scope, session, mutex, guard
        self.factory = factory or paramiko.SFTPClient
        self.cleanup_pending = False
        self._probe: SshProbeTransport | None = None

    @property
    def quiescent(self) -> bool:
        return not self.cleanup_pending and (self._probe is None or self._probe.quiescent)

    def check(self) -> None:
        with self.mutex:
            self.guard()
            if (
                self.session.endpoint != self.scope.endpoint
                or self.session.host_fingerprint != self.scope.host_fingerprint
            ):
                raise TransferFailure("DATA_TRANSFER_AUTH_STALE")
            self.session.validate_probe_session()

    @contextmanager
    def connection(
        self, cancel: threading.Event, seconds: int
    ) -> Iterator[tuple[Any, Callable[[], None]]]:
        if not self.session.io_lock.acquire(blocking=False):
            raise TransferFailure("DATA_TRANSFER_BUSY")
        deadline = time.monotonic() + seconds
        finished = threading.Event()
        interrupt_failed = threading.Event()
        channel = sftp = None

        def check() -> None:
            if cancel.is_set():
                raise TransferFailure("DATA_TRANSFER_CANCELLED")
            if time.monotonic() >= deadline:
                raise TransferFailure("DATA_TRANSFER_TIMEOUT")
            self.check()

        def interrupt() -> None:
            while not finished.wait(0.02):
                if cancel.is_set() or time.monotonic() >= deadline:
                    if channel is not None:
                        try:
                            channel.close()  # This upload channel only; no owner/process cancel.
                        except Exception:
                            interrupt_failed.set()  # Never echo SDK exceptions from a daemon thread.
                    return

        watcher = threading.Thread(target=interrupt, daemon=True, name="easyai-upload-interrupt")
        try:
            watcher.start()
            check()
            channel = self.session.open_probe_channel(timeout=1)
            channel.settimeout(1)
            check()
            channel.invoke_subsystem("sftp")
            sftp = self.factory(channel)
            check()
            yield sftp, check
            check()
        finally:
            # The job remains active and keeps the shared SDK gate until ALL
            # cleanup returns. A timeout/cancel request is not a terminal receipt.
            cleanup_failed = interrupt_failed.is_set()
            try:
                try:
                    if sftp is not None:
                        sftp.close()
                finally:
                    if channel is not None:
                        channel.close()
            except Exception:
                cleanup_failed = True
                try:
                    self.session.close()
                except Exception:
                    pass
            finally:
                finished.set()
                if watcher.ident is not None:
                    watcher.join()  # Owned worker stays pending rather than release early.
                quiet = channel is None or getattr(channel, "closed", False) is True
                if cleanup_failed:
                    quiet = bool(getattr(self.session, "closed_quiescent", False))
                if quiet:
                    self.session.io_lock.release()
                else:
                    self.cleanup_pending = True  # Keep the gate; no terminal cancellation claim.
                if cleanup_failed or not quiet:
                    raise TransferFailure("DATA_TRANSFER_CLEANUP_PENDING") from None

    def directory(self, sftp: Any, path: str, uid: int, check: Callable[[], None]) -> _Reader:
        reader = _Reader(sftp, path, check)
        reader.uid = uid
        reader.anchor_uid = sftp.lstat("/").st_uid
        current = PurePosixPath("/")
        reader._stat(sftp.lstat("/"), True, ancestor=True)
        for part in PurePosixPath(path).parts[1:]:
            check()
            current /= part
            reader._stat(sftp.lstat(str(current)), True, ancestor=str(current) != path)
        return reader

    def inspect(self, cancel: threading.Event) -> tuple[str, int]:
        self.check()
        probe = SshProbeTransport(self.scope, self.session)
        self._probe = probe
        platform = probe.execute(ReadOnlyCommand(("/usr/bin/uname", "-s"), seconds=3), cancel)
        if platform.exit_code != 0 or platform.stderr or platform.stdout != b"Linux\n":
            raise TransferFailure("DATA_TRANSFER_HOME_INVALID")
        self.check()
        result = probe.execute(ReadOnlyCommand(("/usr/bin/id", "-u"), seconds=3), cancel)
        raw = result.stdout.strip()
        if result.exit_code != 0 or result.stderr or not raw.isdigit() or len(raw) > 10:
            raise TransferFailure("DATA_TRANSFER_HOME_INVALID")
        uid = int(raw)
        if uid > 4294967294:
            raise TransferFailure("DATA_TRANSFER_HOME_INVALID")
        with self.connection(cancel, 5) as (sftp, check):
            home = sftp.normalize(".")  # Resolve remote home, never local expanduser.
            remote_path(home)
            if any(part in ("", ".", "..") for part in home.split("/")[1:]) or len(home) > 512:
                raise TransferFailure("DATA_TRANSFER_HOME_INVALID")
            self.directory(sftp, home, uid, check)
            return home, uid

    @staticmethod
    def write_record(sftp: Any, path: str, raw: bytes, check: Callable[[], None]) -> None:
        check()
        with sftp.open(path, "wx", bufsize=0) as output:
            output.chmod(0o600)
            for offset in range(0, len(raw), CHUNK):
                check()
                output.write(raw[offset : offset + CHUNK])
            output.flush()
        check()

    def managed(
        self,
        sftp: Any,
        project_id: str,
        transfer_id: str,
        home: str,
        uid: int,
        check: Callable[[], None],
    ) -> str:
        managed = home + "/.easyai/projects/" + project_id + "/data"
        current = home
        for part in (".easyai", "projects", project_id):
            current += "/" + part
            check()
            try:
                sftp.lstat(current)
            except OSError as error:
                if error.errno != errno.ENOENT:
                    raise
                sftp.mkdir(current, mode=0o700)
            self.directory(sftp, current, uid, check)
        owner = _encoded({"protocolVersion": 1, "projectId": project_id, "uid": uid})

        def write(path: str, raw: bytes) -> None:
            check()
            with sftp.open(path, "wx", bufsize=0) as output:
                output.chmod(0o600)
                for offset in range(0, len(raw), CHUNK):
                    check()
                    output.write(raw[offset : offset + CHUNK])
                output.flush()
            check()

        try:
            sftp.lstat(managed)
        except OSError as error:
            if error.errno != errno.ENOENT:
                raise
            # Never expose an uninitialized shared data root. Interrupted
            # initialization leaves only this intent's dedicated temporary;
            # later intents use new UUIDs and never adopt or remove it.
            staging = current + "/.data-init-" + transfer_id
            check()
            sftp.mkdir(staging, mode=0o700)
            self.directory(sftp, staging, uid, check)
            write(staging + "/.easyai-owner.json", owner)
            if self.directory(sftp, staging, uid, check).record(".easyai-owner.json") != owner:
                raise TransferFailure("DATA_TRANSFER_TARGET_UNOWNED")
            check()
            self.directory(sftp, current, uid, check)
            sftp.rename(staging, managed)  # Standard nonreplace directory publish.
        managed_reader = self.directory(sftp, managed, uid, check)
        if managed_reader.record(".easyai-owner.json") != owner:
            raise TransferFailure("DATA_TRANSFER_TARGET_UNOWNED")
        return managed

    def upload(
        self,
        source: TransferSource,
        project_id: str,
        transfer_id: str,
        home: str,
        uid: int,
        cancel: threading.Event,
        seconds: int,
        progress: Callable[[str, int, int], None],
        authority: Callable[[], None],
    ) -> None:
        with self.connection(cancel, seconds) as (sftp, transport_check):

            def check() -> None:
                transport_check()
                authority()

            if sftp.normalize(".") != home:
                raise TransferFailure("DATA_TRANSFER_HOME_CHANGED")
            self.directory(sftp, home, uid, check)
            managed = self.managed(sftp, project_id, transfer_id, home, uid, check)

            def write(path: str, raw: bytes) -> None:
                self.write_record(sftp, path, raw, check)

            root = managed + "/" + transfer_id
            check()
            sftp.mkdir(root, mode=0o700)  # Exclusive; no existing slot adoption/overwrite.
            self.directory(sftp, root, uid, check)
            for relative, _ in source.directories:
                check()
                sftp.mkdir(root + "/" + relative, mode=0o700)
                self.directory(sftp, root + "/" + relative, uid, check)
            records: list[UploadedFile] = []
            for index, record in enumerate(source.files):
                check()
                parent = str(PurePosixPath(record.name).parent)
                temporary = (parent + "/" if parent != "." else "") + f".part-{index}"
                digest = hashlib.sha256()
                with source.open(record, check) as local:
                    with sftp.open(root + "/" + temporary, "wx", bufsize=0) as output:
                        output.chmod(0o600)
                        total = 0
                        while chunk := local.read(CHUNK):
                            check()
                            total += len(chunk)
                            if total > record.size:
                                raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
                            output.write(chunk)
                            digest.update(chunk)
                            progress("sent", len(chunk), 0)
                        output.flush()
                    if total != record.size:
                        raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
                reader = self.directory(sftp, root, uid, check)
                verified = hashlib.sha256()
                reader.read(temporary, record.size, verified.update)
                if verified.digest() != digest.digest():
                    raise TransferFailure("DATA_TRANSFER_HASH_MISMATCH")
                check()
                # SFTP v3 nonreplace rename; never posix_rename/remove fallback.
                sftp.rename(root + "/" + temporary, root + "/" + record.name)
                records.append(
                    {"path": record.name, "bytes": record.size, "sha256": digest.hexdigest()}
                )
            progress("verifying", 0, 0)
            reader = self.directory(sftp, root, uid, check)
            for uploaded in records:
                digest = hashlib.sha256()
                reader.read(uploaded["path"], uploaded["bytes"], digest.update)
                if digest.hexdigest() != uploaded["sha256"]:
                    raise TransferFailure("DATA_TRANSFER_HASH_MISMATCH")
                progress("verified", uploaded["bytes"], 1)
            manifest = _encoded(
                {
                    "protocolVersion": 1,
                    "projectId": project_id,
                    "transferId": transfer_id,
                    "uid": uid,
                    "files": records,
                }
            )
            if len(manifest) > 65536:
                raise TransferFailure("DATA_TRANSFER_MANIFEST_LIMIT")
            write(root + "/.complete.part", manifest)
            if self.directory(sftp, root, uid, check).record(".complete.part") != manifest:
                raise TransferFailure("DATA_TRANSFER_HASH_MISMATCH")
            check()
            sftp.rename(root + "/.complete.part", root + "/.easyai-complete.json")
            if self.directory(sftp, root, uid, check).record(".easyai-complete.json") != manifest:
                raise TransferFailure("DATA_TRANSFER_HASH_MISMATCH")
            check()
