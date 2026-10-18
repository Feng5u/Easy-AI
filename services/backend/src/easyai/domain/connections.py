"""Short-lived authenticated connection metadata. Secrets are input-only."""

from typing import Literal

from pydantic import ConfigDict, Field, SecretStr

from easyai.domain.contracts import Contract
from easyai.domain.environment import EnvironmentScope, Identifier, Fingerprint


class AuthenticationRequest(Contract):
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


class AuthenticatedConnection(Contract):
    project_id: Identifier
    request_id: Identifier
    identity_request_id: Identifier
    scope: EnvironmentScope
    username: str = Field(min_length=1, max_length=128)
    authenticated: Literal[True] = True
    method: Literal["password"] = "password"
    expires_in_seconds: int = Field(ge=1, le=300)
