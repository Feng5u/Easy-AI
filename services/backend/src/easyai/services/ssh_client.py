"""Single-hop SSH identity gate. No agent, implicit keys, shell or persisted secrets."""

import socket
import logging
import threading
import time
from typing import Any, Callable, Protocol, cast

import paramiko  # type: ignore[import-untyped]

from easyai.domain.ssh import HostKeyObservation, SshEndpoint, SshFailure
from easyai.security.host_keys import HostKeyStore, PublicIdentity, PublicKey


class Socket(Protocol):
    def close(self) -> None: ...
    def settimeout(self, value: float) -> None: ...


class Transport(Protocol):
    banner_timeout: float
    auth_timeout: float
    handshake_timeout: float

    def start_client(self, event: threading.Event) -> None: ...
    def get_remote_server_key(self) -> PublicKey: ...
    def is_active(self) -> bool: ...
    def is_authenticated(self) -> bool: ...
    def auth_password(
        self, username: str, password: str, event: threading.Event, fallback: bool
    ) -> Any: ...
    def auth_publickey(self, username: str, key: Any, event: threading.Event) -> Any: ...
    def open_session(self, timeout: float) -> Any: ...
    def close(self) -> None: ...


def _dial(endpoint: SshEndpoint, timeout: float) -> Socket:
    # socket's timeout bounds TCP connect; OS hostname resolution may have its own
    # resolver deadline. No promise of a hard DNS deadline is made by this layer.
    return socket.create_connection((endpoint.host, endpoint.port), timeout=timeout)


def _transport(connection: Socket) -> Transport:
    channel = "easyai.ssh.protocol"
    logger = logging.getLogger(channel)
    logger.disabled = True
    logger.propagate = False
    transport = paramiko.Transport(connection)
    transport.set_log_channel(channel)
    transport.set_hexdump(False)
    return cast(Transport, transport)


def _auth_failure_code(error: Exception) -> str:
    code = str(error)
    return (
        code
        if code
        in {
            "SSH_USERNAME_INVALID",
            "SSH_SESSION_CLOSED",
            "SSH_CANCELLED",
            "SSH_TIMEOUT",
            "SSH_AUTH_FAILED",
            "SSH_HOST_KEY_CHANGED",
            "SSH_HOST_KEY_CONFIRMATION_REQUIRED",
        }
        else "SSH_AUTH_FAILED"
    )


class VerifiedSshSession:
    def __init__(
        self,
        endpoint: SshEndpoint,
        identity: PublicIdentity,
        store: HostKeyStore,
        connection: Socket,
        transport: Transport,
    ):
        self._endpoint = endpoint
        self._identity = identity
        self._store = store
        self._socket = connection
        self._transport = transport
        self._closed = threading.Event()
        self._close_done = threading.Event()
        self._close_failed = False
        self._auth_started = False
        self._guard = threading.Lock()
        # One physical SDK operation across environment probes and artifact reads.
        self.io_lock = threading.Lock()

    @property
    def endpoint(self) -> SshEndpoint:
        return self._endpoint

    @property
    def host_fingerprint(self) -> str:
        return self._identity.fingerprint

    def validate_probe_session(self) -> None:
        if (
            self._closed.is_set()
            or not self._transport.is_active()
            or not self._transport.is_authenticated()
        ):
            raise SshFailure("SSH_AUTHENTICATION_REQUIRED")
        current = PublicIdentity.from_key(self._transport.get_remote_server_key())
        if current != self._identity:
            raise SshFailure("SSH_HOST_KEY_CHANGED")
        self._store.require_trusted(self._endpoint, current)

    def open_probe_channel(self, timeout: float) -> Any:
        self.validate_probe_session()
        return self._transport.open_session(timeout=timeout)

    @property
    def closed_quiescent(self) -> bool:
        return self._close_done.is_set() and not self._close_failed and not self.io_lock.locked()

    def _forget_auth_material(self) -> bool:
        # Locked Paramiko 4.0 AuthHandler retains these after its completion
        # event. Preserve authenticated/auth_event; drop only secret references.
        try:
            handler = getattr(self._transport, "auth_handler", None)
            if handler is not None:
                for field in ("password", "private_key"):
                    if hasattr(handler, field):
                        setattr(handler, field, None)
            if hasattr(self._transport, "saved_exception"):
                self._transport.saved_exception = None
        except Exception:
            return False
        return True

    def close(self) -> None:
        with self._guard:
            owner = not self._closed.is_set()
            self._closed.set()
        if not owner:
            self._close_done.wait(2)
            return
        try:
            try:
                self._transport.close()
            except Exception:
                self._close_failed = True
            try:
                self._socket.close()
            except Exception:
                self._close_failed = True
        finally:
            if not self._forget_auth_material():
                self._close_failed = True
            self._close_done.set()

    def _wait(
        self,
        completed: threading.Event,
        timeout: float,
        cancel: threading.Event | None,
        failure: str,
    ) -> None:
        deadline = time.monotonic() + timeout
        while not completed.wait(0.02):
            if self._closed.is_set() or (cancel is not None and cancel.is_set()):
                raise SshFailure("SSH_CANCELLED")
            if not self._transport.is_active():
                raise SshFailure(failure)
            if time.monotonic() >= deadline:
                raise SshFailure("SSH_TIMEOUT")
        if self._closed.is_set() or (cancel is not None and cancel.is_set()):
            raise SshFailure("SSH_CANCELLED")

    def _authenticate(
        self,
        operation: Callable[[threading.Event], Any],
        username: str,
        cancel: threading.Event | None,
        timeout: float | None = None,
    ) -> None:
        failure: str | None = None
        try:
            if not username or len(username) > 128 or any(ord(char) < 33 for char in username):
                raise SshFailure("SSH_USERNAME_INVALID")
            with self._guard:
                if self._auth_started or self._closed.is_set():
                    raise SshFailure("SSH_SESSION_CLOSED")
                self._auth_started = True
            if cancel is not None and cancel.is_set():
                raise SshFailure("SSH_CANCELLED")
            current = PublicIdentity.from_key(self._transport.get_remote_server_key())
            if current != self._identity:
                raise SshFailure("SSH_HOST_KEY_CHANGED")
            self._store.require_trusted(self._endpoint, current)
            completed = threading.Event()
            operation(completed)
            budget = (
                self._transport.auth_timeout
                if timeout is None
                else min(timeout, self._transport.auth_timeout)
            )
            if budget <= 0:
                raise SshFailure("SSH_TIMEOUT")
            self._wait(completed, budget, cancel, "SSH_AUTH_FAILED")
            if not self._transport.is_authenticated():
                raise SshFailure("SSH_AUTH_FAILED")
        except (SshFailure, ValueError) as error:
            failure = _auth_failure_code(error)
        except Exception:
            failure = "SSH_AUTH_FAILED"
        if failure is not None:
            self.close()
            # Raise outside except: do not retain SDK exception/traceback context.
            raise SshFailure(failure) from None
        if not self._forget_auth_material():
            self.close()
            raise SshFailure("SSH_SECRET_CLEANUP_FAILED") from None

    def authenticate_password(
        self,
        username: str,
        password: str,
        cancel: threading.Event | None = None,
        timeout: float | None = None,
    ) -> None:
        try:
            self._authenticate(
                lambda done: self._transport.auth_password(
                    username, password, event=done, fallback=False
                ),
                username,
                cancel,
                timeout,
            )
        finally:
            password = ""

    def authenticate_public_key(
        self, username: str, private_key: Any, cancel: threading.Event | None = None
    ) -> None:
        try:
            self._authenticate(
                lambda done: self._transport.auth_publickey(username, private_key, event=done),
                username,
                cancel,
            )
        finally:
            private_key = None

    def __enter__(self) -> "VerifiedSshSession":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class SshClient:
    def __init__(
        self,
        store: HostKeyStore | Callable[[], HostKeyStore],
        dial: Callable[[SshEndpoint, float], Socket] = _dial,
        transport: Callable[[Socket], Transport] = _transport,
    ):
        self._store = None if callable(store) else store
        self._store_factory = store if callable(store) else None
        self._store_lock = threading.Lock()
        self._dial = dial
        self._make_transport = transport

    @property
    def store(self) -> HostKeyStore:
        with self._store_lock:
            if self._store is None:
                if self._store_factory is None:
                    raise ValueError("SSH_TRUST_PLATFORM_UNVERIFIED")
                self._store = self._store_factory()
            return self._store

    def _open(self, endpoint: SshEndpoint, cancel: threading.Event | None) -> VerifiedSshSession:
        store = self.store  # Capability/trust storage must be verified before any outbound dial.
        connection: Socket | None = None
        transport: Transport | None = None
        try:
            if cancel is not None and cancel.is_set():
                raise SshFailure("SSH_CANCELLED")
            connection = self._dial(endpoint, 10)
            connection.settimeout(10)
            if cancel is not None and cancel.is_set():
                raise SshFailure("SSH_CANCELLED")
            transport = self._make_transport(connection)
            transport.banner_timeout = 10
            transport.handshake_timeout = 10
            transport.auth_timeout = 15
            completed = threading.Event()
            transport.start_client(event=completed)
            # Identity not yet known; this temporary owner only waits/closes.
            session = VerifiedSshSession(
                endpoint, PublicIdentity("", b""), store, connection, transport
            )
            session._wait(completed, 10, cancel, "SSH_HANDSHAKE_FAILED")
            session._identity = PublicIdentity.from_key(transport.get_remote_server_key())
            return session
        except Exception as error:
            if transport is not None:
                try:
                    transport.close()
                except Exception:
                    pass
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
            if isinstance(error, SshFailure):
                raise
            raise SshFailure("SSH_CONNECTION_FAILED") from None

    def probe(
        self, endpoint: SshEndpoint, cancel: threading.Event | None = None
    ) -> HostKeyObservation:
        with self._open(endpoint, cancel) as session:
            return self.store.observe(endpoint, session._identity)

    def connect_verified(
        self, endpoint: SshEndpoint, cancel: threading.Event | None = None
    ) -> VerifiedSshSession:
        session = self._open(endpoint, cancel)
        try:
            self.store.require_trusted(endpoint, session._identity)
            return session
        except Exception:
            session.close()
            raise
