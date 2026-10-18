"""App-owned pinned public host keys; no private keys, agents or user SSH config."""

import base64
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
import os
import stat
from pathlib import Path
import threading
import time
from typing import Callable, Iterator, Protocol
from uuid import uuid4

import paramiko  # type: ignore[import-untyped]

from easyai.domain.ssh import HostKeyObservation, SshEndpoint

MAX_STORE_BYTES = 1024 * 1024
MAX_PUBLIC_BYTES = 16384
MAX_PENDING = 32


class PublicKey(Protocol):
    def get_name(self) -> str: ...
    def asbytes(self) -> bytes: ...


@dataclass(frozen=True)
class PublicIdentity:
    algorithm: str
    raw: bytes

    @property
    def fingerprint(self) -> str:
        return "SHA256:" + base64.b64encode(hashlib.sha256(self.raw).digest()).decode().rstrip("=")

    @classmethod
    def from_key(cls, key: PublicKey) -> "PublicIdentity":
        return cls.parse(key.get_name(), key.asbytes())

    @classmethod
    def parse(cls, algorithm: str, raw: bytes) -> "PublicIdentity":
        if (
            algorithm
            not in {
                "ssh-ed25519",
                "ssh-rsa",
                "ecdsa-sha2-nistp256",
                "ecdsa-sha2-nistp384",
                "ecdsa-sha2-nistp521",
            }
            or not 1 <= len(raw) <= MAX_PUBLIC_BYTES
        ):
            raise ValueError("SSH_HOST_KEY_INVALID")
        try:
            parsed = paramiko.PKey.from_type_string(algorithm, raw)
            if parsed.asbytes() != raw or (algorithm == "ssh-rsa" and parsed.get_bits() < 2048):
                raise ValueError("Invalid public key")
        except Exception:
            raise ValueError("SSH_HOST_KEY_INVALID") from None
        return cls(algorithm, raw)


@dataclass(frozen=True)
class _Pending:
    endpoint: SshEndpoint
    identity: PublicIdentity
    expires: float


class HostKeyStore:
    def __init__(self, root: Path, clock: Callable[[], float] = time.monotonic):
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("SSH_TRUST_PATH_INVALID")
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self._verify_chain()
        initial = root.stat()
        self._root_identity = (initial.st_dev, initial.st_ino)
        self.path = self.root / "known_hosts"
        self._clock = clock
        self._mutex = threading.RLock()
        self._pending: dict[str, _Pending] = {}

    def _verify_chain(self) -> None:
        for path in reversed((self.root, *self.root.parents)):
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("SSH_TRUST_PATH_INVALID")

    @contextmanager
    def _directory(self, *, exclusive: bool = False) -> Iterator[int]:
        # dir_fd anchors every read/temp/publication to the verified directory inode.
        # Windows trust persistence stays fail-closed until equivalent handle tests exist.
        if os.name != "posix":
            raise ValueError("SSH_TRUST_PLATFORM_UNVERIFIED")
        import fcntl

        self._verify_chain()
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) != self._root_identity:
                raise ValueError("SSH_TRUST_PATH_INVALID")
            if exclusive:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError("SSH_TRUST_STORE_BUSY") from None
            yield fd
        finally:
            os.close(fd)

    def _verify_publication(self) -> None:
        self._verify_chain()
        info = self.root.stat()
        if (info.st_dev, info.st_ino) != self._root_identity:
            raise ValueError("SSH_TRUST_PATH_INVALID")

    def _read(self, directory: int | None = None) -> dict[str, PublicIdentity]:
        if directory is None:
            with self._directory() as fd:
                return self._read(fd)
        try:
            fd = os.open(
                "known_hosts", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
        except FileNotFoundError:
            return {}
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("FILE_NOT_REGULAR")
            if info.st_size > MAX_STORE_BYTES:
                raise ValueError("SSH_TRUST_STORE_LIMIT")
            raw = stream.read(MAX_STORE_BYTES + 1)
            if len(raw) > MAX_STORE_BYTES:
                raise ValueError("SSH_TRUST_STORE_LIMIT")
        records: dict[str, PublicIdentity] = {}
        try:
            text = raw.decode("ascii")
            for line in text.splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                fields = line.split()
                if len(fields) < 3 or len(line) > 32768:
                    raise ValueError("Invalid host record")
                token, algorithm, encoded = fields[:3]
                if token.startswith("["):
                    host, separator, port = token[1:].partition("]:")
                    if not separator:
                        raise ValueError("Invalid host record")
                    endpoint = SshEndpoint(host=host, port=int(port))
                else:
                    endpoint = SshEndpoint(host=token)
                name = endpoint.known_host_name
                if name in records or len(records) >= 512:
                    raise ValueError("Duplicate or excessive host record")
                records[name] = PublicIdentity.parse(
                    algorithm, base64.b64decode(encoded, validate=True)
                )
        except (ValueError, UnicodeError):
            raise ValueError("SSH_TRUST_STORE_INVALID") from None
        return records

    def _write(self, records: dict[str, PublicIdentity], directory: int) -> None:
        payload = "".join(
            f"{name} {key.algorithm} {base64.b64encode(key.raw).decode()}\n"
            for name, key in sorted(records.items())
        ).encode()
        if len(payload) > MAX_STORE_BYTES:
            raise ValueError("SSH_TRUST_STORE_LIMIT")
        temp = f".known-hosts-{uuid4()}.tmp"
        try:
            fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=directory)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            self._verify_publication()
            os.replace(temp, "known_hosts", src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:
                os.unlink(temp, dir_fd=directory)
            except FileNotFoundError:
                pass

    def observe(self, endpoint: SshEndpoint, identity: PublicIdentity) -> HostKeyObservation:
        with self._mutex:
            records = self._read()
            existing = records.get(endpoint.known_host_name)
            if existing is not None:
                same = existing == identity
                return HostKeyObservation(
                    endpoint=endpoint,
                    algorithm=identity.algorithm,
                    fingerprint=identity.fingerprint,
                    trust_state="trusted" if same else "changed",
                    previous_fingerprint=None if same else existing.fingerprint,
                )
            self._pending = {
                key: value for key, value in self._pending.items() if value.expires > self._clock()
            }
            for key, value in self._pending.items():
                if value.endpoint == endpoint and value.identity == identity:
                    challenge = key
                    break
            else:
                if len(self._pending) >= MAX_PENDING:
                    raise ValueError("SSH_CONFIRMATION_LIMIT")
                challenge = str(uuid4())
                self._pending[challenge] = _Pending(endpoint, identity, self._clock() + 600)
            return HostKeyObservation(
                endpoint=endpoint,
                algorithm=identity.algorithm,
                fingerprint=identity.fingerprint,
                trust_state="unknown",
                challenge_id=challenge,
            )

    def require_trusted(self, endpoint: SshEndpoint, identity: PublicIdentity) -> None:
        observation = self.observe(endpoint, identity)
        if observation.trust_state != "trusted":
            raise ValueError(
                "SSH_HOST_KEY_CHANGED"
                if observation.trust_state == "changed"
                else "SSH_HOST_KEY_CONFIRMATION_REQUIRED"
            )

    def confirm(self, challenge_id: str, fingerprint: str) -> HostKeyObservation:
        with self._mutex:
            pending = self._pending.get(challenge_id)
            if pending is None or pending.expires <= self._clock():
                self._pending.pop(challenge_id, None)
                raise ValueError("SSH_CONFIRMATION_EXPIRED")
            if not hmac.compare_digest(pending.identity.fingerprint, fingerprint):
                raise ValueError("SSH_CONFIRMATION_MISMATCH")
            with self._directory(exclusive=True) as directory:
                records = self._read(directory)
                existing = records.get(pending.endpoint.known_host_name)
                if existing is not None and existing != pending.identity:
                    raise ValueError("SSH_HOST_KEY_CHANGED")
                if existing is None:
                    if len(records) >= 512:
                        raise ValueError("SSH_TRUST_STORE_LIMIT")
                    records[pending.endpoint.known_host_name] = pending.identity
                    self._write(records, directory)
                self._pending.pop(challenge_id, None)
            return self.observe(pending.endpoint, pending.identity)
