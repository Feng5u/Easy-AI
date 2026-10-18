"""One short-lived authenticated lease, no credential store or auto reconnect."""

from dataclasses import dataclass, field
import math
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Protocol
from uuid import uuid4

from easyai.domain.connections import AuthenticationRequest, AuthenticatedConnection, SessionControl
from easyai.domain.environment import EnvironmentRequest, EnvironmentScope
from easyai.domain.ssh import SshEndpoint
from easyai.domain.ssh import IdentityRequest, SshFailure
from easyai.services.environment_service import EnvironmentService
from easyai.services.environment_transport import SshProbeTransport
from easyai.services.ssh_client import SshClient, VerifiedSshSession
from easyai.services.ssh_identity import IdentityGrant, SshIdentityService

if TYPE_CHECKING:
    from easyai.domain.remote_run import RemoteRunCheckpoint, RemoteRunIdentity
    from easyai.services.remote_artifacts import SftpArtifactSync
    from easyai.services.remote_bundle import RemoteBundle
    from easyai.services.owner_transport import OwnerSshTransport


class Timer(Protocol):
    def start(self) -> None: ...
    def cancel(self) -> None: ...


def _timer(seconds: float, callback: Callable[[], None]) -> Timer:
    timer = threading.Timer(seconds, callback)
    timer.daemon = True
    return timer


def _failure_code(error: Exception) -> str:
    allowed = {
        "SSH_AUTH_REQUEST_INVALID",
        "SSH_TARGET_REFERENCE_STALE",
        "SSH_SESSION_BUSY",
        "SSH_AUTH_REQUEST_RETIRED",
        "SSH_AUTH_REQUEST_LIMIT",
        "SSH_IDENTITY_AUTHORIZATION_STALE",
        "SSH_TIMEOUT",
        "SSH_AUTH_CANCELLED",
        "SSH_HOST_KEY_CHANGED",
        "SSH_AUTH_FAILED",
        "SSH_CONNECTION_FAILED",
        "SSH_HANDSHAKE_FAILED",
        "SSH_CANCELLED",
        "SSH_HOST_KEY_CONFIRMATION_REQUIRED",
        "SSH_AUTHENTICATION_REQUIRED",
        "SSH_SESSION_CLOSED",
        "SSH_USERNAME_INVALID",
        "SSH_SECRET_CLEANUP_FAILED",
        "SSH_CLEANUP_UNCONFIRMED",
        "SSH_IDENTITY_PROJECT_CHANGED",
        "SSH_TRUST_PERMISSIONS_UNSAFE",
        "SSH_TRUST_PATH_INVALID",
        "SSH_TRUST_PLATFORM_UNVERIFIED",
        "SSH_TRUST_STORE_INVALID",
        "SSH_TRUST_STORE_BUSY",
        "SSH_HOST_KEY_INVALID",
    }
    code = str(error)
    return (
        code
        if isinstance(error, (SshFailure, ValueError)) and code in allowed
        else "SSH_AUTH_FAILED"
    )


@dataclass
class _Authentication:
    request: AuthenticationRequest
    grant: IdentityGrant
    generation: int
    deadline: float
    cancel: threading.Event = field(default_factory=threading.Event)
    running: bool = True
    session: VerifiedSshSession | None = None
    timer: Timer | None = None


@dataclass
class _Lease:
    operation: _Authentication
    scope: EnvironmentScope
    session: VerifiedSshSession
    environments: EnvironmentService
    expires_at: float
    timer: Timer


@dataclass
class _Retiring:
    session: VerifiedSshSession
    environments: EnvironmentService | None
    done: threading.Event = field(default_factory=threading.Event)


class ConnectionManager:
    def __init__(
        self,
        client: SshClient,
        identities: SshIdentityService,
        mutex: threading.RLock,
        verify_project: Callable[[str], None],
        clock: Callable[[], float] = time.monotonic,
        timer_factory: Callable[[float, Callable[[], None]], Timer] = _timer,
        sftp_factory: Callable[[Any], Any] | None = None,
        verify_target: Callable[[AuthenticationRequest, SshEndpoint], None] | None = None,
    ):
        self._client, self._identities = client, identities
        self._mutex, self._verify_project = mutex, verify_project
        self._clock, self._timer_factory = clock, timer_factory
        self._sftp_factory = sftp_factory
        self._verify_target = verify_target or (lambda request, endpoint: None)
        self._generation = 0
        self._auth: _Authentication | None = None
        self._lease: _Lease | None = None
        self._retiring: _Retiring | None = None
        self._retired: dict[tuple[str, str], float] = {}

    def _retire_request(self, project: str, request: str) -> None:
        now = self._clock()
        self._retired = {key: expiry for key, expiry in self._retired.items() if expiry > now}
        if (project, request) not in self._retired and len(self._retired) >= 64:
            raise SshFailure("SSH_AUTH_REQUEST_LIMIT")
        self._retired[(project, request)] = now + 600

    def _queue_close(
        self, session: VerifiedSshSession, environments: EnvironmentService | None = None
    ) -> None:
        # Called under the shared lock. The worker never executes SDK calls while
        # owning it, including when the caller still holds an outer RLock level.
        if self._retiring is not None and self._retiring.session is session:
            return
        if self._retiring is not None:
            raise SshFailure("SSH_CLEANUP_UNCONFIRMED")
        retiring = _Retiring(session, environments)
        self._retiring = retiring

        def clean() -> None:
            try:
                if environments is not None:
                    environments.invalidate()
                else:
                    session.close()
            except Exception:
                pass
            finally:
                retiring.done.set()

        threading.Thread(target=clean, name="easyai-ssh-retire", daemon=True).start()

    def _cleanup_busy(self) -> bool:
        retiring = self._retiring
        if retiring is not None:
            quiet = (
                retiring.environments.quiescent
                if retiring.environments is not None
                else retiring.session.closed_quiescent
            )
            if not retiring.done.is_set() or not quiet:
                return True
            self._retiring = None
        return self._auth is not None and self._auth.running

    def _detach_lease(self) -> None:
        lease, self._lease = self._lease, None
        if lease is not None:
            lease.timer.cancel()
            self._queue_close(lease.session, lease.environments)

    def invalidate(self) -> None:
        with self._mutex:
            self._generation += 1
            if self._auth and self._auth.running:
                self._auth.cancel.set()
                if self._auth.session is not None:
                    self._queue_close(self._auth.session)
            self._detach_lease()

    def invalidate_target(self, target_id: str) -> None:
        with self._mutex:
            if (
                self._auth is not None
                and self._auth.running
                and self._auth.request.target_id == target_id
            ) or (self._lease is not None and self._lease.operation.request.target_id == target_id):
                self.invalidate()

    def cancel_identity(self, request: IdentityRequest) -> None:
        with self._mutex:
            auth = self._auth
            if (
                auth is not None
                and auth.request.project_id == request.project_id
                and auth.request.identity_request_id == request.request_id
            ):
                self.cancel_auth(
                    IdentityRequest(
                        project_id=request.project_id, request_id=auth.request.request_id
                    )
                )

    def cancel_auth(self, request: IdentityRequest) -> None:
        with self._mutex:
            auth = self._auth
            if (
                auth
                and auth.request.project_id == request.project_id
                and auth.request.request_id == request.request_id
            ):
                auth.cancel.set()
                if auth.running and auth.session is not None:
                    self._queue_close(auth.session)
                lease = self._lease
                if lease is not None and lease.operation is auth:
                    self._detach_lease()
            self._retire_request(request.project_id, request.request_id)

    def close(self, request: SessionControl) -> None:
        with self._mutex:
            lease = self._lease
            if (
                lease is not None
                and lease.scope.project_id == request.project_id
                and lease.scope.connection_id == request.connection_id
            ):
                self._detach_lease()

    def _auth_guard(self, operation: _Authentication) -> None:
        if self._clock() >= min(operation.deadline, operation.grant.expires_at):
            raise SshFailure("SSH_TIMEOUT")
        if (
            self._auth is not operation
            or operation.cancel.is_set()
            or operation.generation != self._generation
        ):
            raise SshFailure("SSH_AUTH_CANCELLED")
        self._verify_project(operation.request.project_id)
        self._verify_target(operation.request, operation.grant.endpoint)

    def _timeout_auth(self, operation: _Authentication) -> None:
        with self._mutex:
            if (
                self._auth is operation
                and operation.running
                and self._clock() >= operation.deadline
            ):
                operation.cancel.set()
                if operation.session is not None:
                    self._queue_close(operation.session)
                if self._lease is not None and self._lease.operation is operation:
                    self._detach_lease()

    def _expire(self, connection_id: str) -> None:
        with self._mutex:
            lease = self._lease
            if lease is not None and lease.scope.connection_id == connection_id:
                remaining = lease.expires_at - self._clock()
                if remaining <= 0:
                    self._detach_lease()
                else:
                    # Preserve the original deadline; stale callbacks stay scoped to this ID.
                    lease.timer = self._timer_factory(
                        remaining, lambda: self._expire(connection_id)
                    )
                    lease.timer.start()

    def authenticate_password(
        self, request: AuthenticationRequest, password: str
    ) -> AuthenticatedConnection:
        operation: _Authentication | None = None
        session: VerifiedSshSession | None = None
        published = False
        failure: str | None = None
        info: AuthenticatedConnection | None = None
        try:
            if not 1 <= len(password) <= 1024 or any(ord(char) < 33 for char in request.username):
                raise SshFailure("SSH_AUTH_REQUEST_INVALID")
            password.encode("utf-8")
            with self._mutex:
                self._verify_project(request.project_id)
                if self._lease is not None and self._clock() >= self._lease.expires_at:
                    self._detach_lease()
                if self._cleanup_busy() or self._lease is not None:
                    raise SshFailure("SSH_SESSION_BUSY")
                now = self._clock()
                self._retired = {
                    key: expiry for key, expiry in self._retired.items() if expiry > now
                }
                if (request.project_id, request.request_id) in self._retired:
                    raise SshFailure("SSH_AUTH_REQUEST_RETIRED")
                self._retire_request(request.project_id, request.request_id)
                grant = self._identities.consume_auth_grant(
                    request.project_id, request.identity_request_id, request.expected_fingerprint
                )
                self._verify_target(request, grant.endpoint)
                operation = _Authentication(request, grant, self._generation, now + 25)
                self._auth = operation
                timer = self._timer_factory(25, lambda: self._timeout_auth(operation))
                operation.timer = timer
                timer.start()
            session = self._client.connect_verified(grant.endpoint, operation.cancel)
            with self._mutex:
                operation.session = session
                self._auth_guard(operation)
                # A newly pinned different key must never receive this password.
                if (
                    session.endpoint != grant.endpoint
                    or session.host_fingerprint != grant.fingerprint
                ):
                    raise SshFailure("SSH_HOST_KEY_CHANGED")
                remaining = min(operation.deadline, grant.expires_at) - self._clock()
            session.authenticate_password(
                request.username, password, operation.cancel, timeout=remaining
            )
            session.validate_probe_session()
            with self._mutex:
                self._auth_guard(operation)
                scope = EnvironmentScope(
                    project_id=request.project_id,
                    connection_id=str(uuid4()),
                    endpoint=session.endpoint,
                    host_fingerprint=session.host_fingerprint,
                )
                transport = SshProbeTransport(scope, session)
                environments = EnvironmentService(
                    transport, self._mutex, self._environment_guard, self._clock
                )
                expires = self._clock() + 300
                lease_timer = self._timer_factory(300, lambda: self._expire(scope.connection_id))
                lease = _Lease(operation, scope, session, environments, expires, lease_timer)
                self._lease = lease
                operation.session = None
                published = True
                lease_timer.start()
                info = self._info(lease)
        except Exception as error:
            failure = _failure_code(error)
        finally:
            password = ""
            with self._mutex:
                if operation is not None:
                    if operation.timer:
                        operation.timer.cancel()
                    operation.running = False
                    if (
                        failure is not None
                        and self._lease is not None
                        and self._lease.operation is operation
                    ):
                        self._detach_lease()
                    if not published and session is not None:
                        self._queue_close(session)
                    operation.session = None
        if failure is not None:
            # SDK exceptions and their traceback contexts do not enter a Future.
            raise SshFailure(failure) from None
        with self._mutex:
            if self._lease is None or self._lease.operation is not operation:
                failure = "SSH_AUTH_CANCELLED"
            else:
                assert operation is not None
                try:
                    self._auth_guard(operation)
                except Exception as error:
                    failure = _failure_code(error)
                    self._detach_lease()
        if failure is not None:
            raise SshFailure(failure) from None
        assert info is not None
        return info

    def _info(self, lease: _Lease) -> AuthenticatedConnection:
        request = lease.operation.request
        return AuthenticatedConnection(
            project_id=request.project_id,
            request_id=request.request_id,
            identity_request_id=request.identity_request_id,
            target_id=request.target_id,
            target_revision=request.target_revision,
            scope=lease.scope,
            username=request.username,
            expires_in_seconds=max(1, min(300, math.ceil(lease.expires_at - self._clock()))),
        )

    def _valid_lease(self, project_id: str, connection_id: str) -> _Lease | None:
        lease = self._lease
        if (
            lease is None
            or lease.scope.project_id != project_id
            or lease.scope.connection_id != connection_id
        ):
            return None
        if self._clock() >= lease.expires_at:
            self._detach_lease()
            return None
        code = None
        try:
            self._verify_project(project_id)
            self._verify_target(lease.operation.request, lease.scope.endpoint)
            lease.session.validate_probe_session()  # In-memory protocol state + bounded local pin read.
        except Exception:
            code = "SSH_SESSION_INVALID"
        if code:
            self._detach_lease()
            raise SshFailure(code)
        return lease

    def current(self, request: SessionControl) -> AuthenticatedConnection | None:
        with self._mutex:
            lease = self._valid_lease(request.project_id, request.connection_id)
            return self._info(lease) if lease else None

    def _environment_guard(self, scope: EnvironmentScope) -> None:
        lease = self._valid_lease(scope.project_id, scope.connection_id)
        if lease is None or lease.scope != scope:
            raise SshFailure("SSH_SESSION_INVALID")

    def environments(self, request: EnvironmentRequest) -> EnvironmentService:
        with self._mutex:
            lease = self._valid_lease(request.project_id, request.connection_id)
            if lease is None:
                raise SshFailure("SSH_AUTHENTICATION_REQUIRED")
            return lease.environments

    def artifact_sync(
        self, request: SessionControl, identity: "RemoteRunIdentity"
    ) -> "SftpArtifactSync":
        """Internal sealed-run service; no renderer credentials/path or network action here."""
        from easyai.services.remote_artifacts import SftpArtifactSync

        with self._mutex:
            lease = self._valid_lease(request.project_id, request.connection_id)
            if lease is None:
                raise SshFailure("SSH_AUTHENTICATION_REQUIRED")

            def guard() -> None:
                current = self._valid_lease(request.project_id, request.connection_id)
                if (
                    current is not lease
                    or identity.project_id != lease.scope.project_id
                    or identity.endpoint != lease.scope.endpoint
                    or identity.host_fingerprint != lease.scope.host_fingerprint
                    or identity.username != lease.operation.request.username
                ):
                    raise SshFailure("SSH_SESSION_INVALID")

            guard()
            return SftpArtifactSync(
                lease.session, identity, self._mutex, guard, sftp_factory=self._sftp_factory
            )

    def owner_transport(
        self, request: SessionControl, bundle: "RemoteBundle", checkpoint: "RemoteRunCheckpoint"
    ) -> "OwnerSshTransport":
        """Internal factory. Reconnect permission comes from the persisted coordinator intent."""
        from easyai.services.owner_transport import OwnerSshTransport

        identity = bundle.identity
        with self._mutex:
            lease = self._valid_lease(request.project_id, request.connection_id)
            if lease is None or checkpoint.identity != identity:
                raise SshFailure("SSH_SESSION_INVALID")

            def guard() -> None:
                current = self._valid_lease(request.project_id, request.connection_id)
                if (
                    current is not lease
                    or identity.project_id != lease.scope.project_id
                    or identity.endpoint != lease.scope.endpoint
                    or identity.host_fingerprint != lease.scope.host_fingerprint
                    or identity.username != lease.operation.request.username
                ):
                    raise SshFailure("SSH_SESSION_INVALID")

            guard()
            return OwnerSshTransport(
                lease.session,
                bundle,
                self._mutex,
                guard,
                sftp_factory=self._sftp_factory,
                allow_start=checkpoint.start_outcome == "not_attempted"
                and checkpoint.cancel_state == "none",
            )

    def cancel_environment(self, request: EnvironmentRequest) -> None:
        with self._mutex:
            lease = self._valid_lease(request.project_id, request.connection_id)
            if lease is None:
                return
            if lease.environments.cancel_running(request):
                self._detach_lease()

    def wait_idle(self, seconds: float = 3) -> None:
        deadline = time.monotonic() + seconds
        while True:
            with self._mutex:
                if not self._cleanup_busy():
                    return
            if time.monotonic() >= deadline:
                raise SshFailure("SSH_CLEANUP_UNCONFIRMED")
            time.sleep(0.01)
