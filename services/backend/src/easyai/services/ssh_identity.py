"""One bounded, project-scoped, pre-auth identity operation per workspace."""

from dataclasses import dataclass, field
import threading
import time
from typing import Callable

from easyai.domain.ssh import (
    HostKeyObservation,
    IdentityConfirmRequest,
    IdentityProbeRequest,
    IdentityRequest,
    IdentityResult,
)
from easyai.services.ssh_client import SshClient


@dataclass
class _Operation:
    request: IdentityProbeRequest
    cancel: threading.Event = field(default_factory=threading.Event)
    running: bool = True
    observation: HostKeyObservation | None = None


class SshIdentityService:
    def __init__(
        self,
        client: SshClient,
        mutex: threading.RLock,
        verify_project: Callable[[str], None],
        clock: Callable[[], float] = time.monotonic,
    ):
        self._client = client
        self._mutex = mutex
        self._verify_project = verify_project
        self._clock = clock
        self._active: _Operation | None = None
        self._retired: dict[tuple[str, str], float] = {}

    @staticmethod
    def _key(request: IdentityRequest) -> tuple[str, str]:
        return request.project_id, request.request_id

    def _retire(self, request: IdentityRequest) -> None:
        now = self._clock()
        self._retired = {key: expiry for key, expiry in self._retired.items() if expiry > now}
        key = self._key(request)
        if key not in self._retired and len(self._retired) >= 64:
            raise ValueError("SSH_IDENTITY_REQUEST_LIMIT")
        self._retired[key] = now + 600

    def _discard(self, operation: _Operation) -> None:
        operation.cancel.set()
        if operation.observation and operation.observation.challenge_id:
            self._client.store.discard(operation.observation.challenge_id)
        operation.observation = None

    def invalidate(self) -> None:
        with self._mutex:
            if self._active:
                self._discard(self._active)

    def cancel(self, request: IdentityRequest) -> None:
        with self._mutex:
            if self._active and self._key(self._active.request) == self._key(request):
                self._discard(self._active)
            # Cancellation arriving before probe registration is a tombstone.
            self._retire(request)

    def probe(self, request: IdentityProbeRequest) -> IdentityResult:
        with self._mutex:
            self._verify_project(request.project_id)
            self._retired = {
                key: expiry for key, expiry in self._retired.items() if expiry > self._clock()
            }
            if self._key(request) in self._retired:
                raise ValueError("SSH_IDENTITY_REQUEST_RETIRED")
            if self._active and self._active.running:
                raise ValueError("SSH_IDENTITY_BUSY")
            self._retire(request)  # Each request id can initiate at most one probe.
            if self._active:
                self._discard(self._active)
            operation = _Operation(request)
            self._active = operation
        try:
            observed = self._client.probe(request.endpoint, operation.cancel)
            with self._mutex:
                operation.observation = observed
                try:
                    self._verify_project(request.project_id)
                    if observed.endpoint != request.endpoint:
                        raise ValueError("SSH_IDENTITY_RESPONSE_INVALID")
                    if operation.cancel.is_set() or self._active is not operation:
                        raise ValueError("SSH_IDENTITY_CANCELLED")
                except BaseException:
                    self._discard(operation)
                    raise
                return IdentityResult(
                    project_id=request.project_id,
                    request_id=request.request_id,
                    observation=observed,
                )
        finally:
            with self._mutex:
                operation.running = False

    def confirm(self, request: IdentityConfirmRequest) -> IdentityResult:
        with self._mutex:
            self._verify_project(request.project_id)
            operation = self._active
            if (
                operation is None
                or operation.running
                or operation.cancel.is_set()
                or self._key(operation.request) != self._key(request)
                or operation.observation is None
                or operation.observation.endpoint != operation.request.endpoint
                or operation.observation.trust_state != "unknown"
                or operation.observation.challenge_id != request.confirmation.challenge_id
                or operation.observation.fingerprint != request.confirmation.fingerprint
            ):
                raise ValueError("SSH_IDENTITY_CONFIRMATION_STALE")
            observed = self._client.store.confirm(
                request.confirmation.challenge_id, request.confirmation.fingerprint
            )
            if observed.endpoint != operation.request.endpoint or observed.trust_state != "trusted":
                raise ValueError("SSH_IDENTITY_RESPONSE_INVALID")
            operation.observation = observed
            return IdentityResult(
                project_id=request.project_id,
                request_id=request.request_id,
                observation=observed,
            )
