"""Short-lived authenticated connection metadata. Secrets are input-only."""

from typing import Literal, Self

from pydantic import ConfigDict, Field, SecretStr, model_validator

from easyai.domain.contracts import Contract
from easyai.domain.environment import EnvironmentScope, Identifier, Fingerprint
from easyai.domain.ssh import SshEndpoint


class ConnectionProfileInput(Contract):
    alias: str = Field(min_length=1, max_length=80, pattern=r"^[^\x00-\x1f\x7f]+$")
    endpoint: SshEndpoint
    username: str = Field(min_length=1, max_length=128, pattern=r"^[^\x00-\x20\x7f]+$")


class ConnectionProfile(ConnectionProfileInput):
    target_id: Identifier
    revision: int = Field(ge=1)


class ConnectionProfileUpdate(ConnectionProfileInput):
    expected_revision: int = Field(ge=1)


class ConnectionTargetReference(Contract):
    target_id: Identifier
    expected_revision: int = Field(ge=1)


class ProfileReference(Contract):
    target_id: Identifier | None = None
    target_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def complete_reference(self) -> Self:
        if (self.target_id is None) != (self.target_revision is None):
            raise ValueError("SSH_TARGET_REFERENCE_INVALID")
        return self


class AuthenticationRequest(ProfileReference):
    model_config = ConfigDict(frozen=True)
    project_id: Identifier
    request_id: Identifier
    identity_request_id: Identifier
    expected_fingerprint: Fingerprint
    username: str = Field(min_length=1, max_length=128)


class PasswordAuthenticationInput(Contract):
    request: AuthenticationRequest
    password: SecretStr = Field(min_length=1, max_length=1024, repr=False, exclude=True)

    def forget(self) -> None:
        # Drop this object's reference. Immutable strings/HTTP buffers cannot be
        # promised to be erased; nothing is persisted or returned to a client.
        self.password = SecretStr("")


class SessionControl(Contract):
    project_id: Identifier
    connection_id: Identifier


class AuthenticatedConnection(ProfileReference):
    project_id: Identifier
    request_id: Identifier
    identity_request_id: Identifier
    scope: EnvironmentScope
    username: str = Field(min_length=1, max_length=128)
    authenticated: Literal[True] = True
    method: Literal["password"] = "password"
    expires_in_seconds: int = Field(ge=1, le=300)
