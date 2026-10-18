"""Public host identity contracts. Authentication material is never a DTO."""

import ipaddress
import re
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from easyai.domain.contracts import Contract


class SshFailure(RuntimeError):
    """Sanitized operation code; never preserve SDK exception messages."""


def canonical_host(value: str) -> str:
    if not value or len(value) > 253 or value != value.strip() or "%" in value:
        raise ValueError("SSH_HOST_INVALID")
    try:
        return ipaddress.ip_address(value).compressed
    except ValueError:
        pass
    if re.fullmatch(r"[0-9.]+", value):
        raise ValueError("SSH_HOST_INVALID")
    try:
        host = value.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise ValueError("SSH_HOST_INVALID") from None
    if (
        not host
        or len(host) > 253
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        )
    ):
        raise ValueError("SSH_HOST_INVALID")
    return host


class SshEndpoint(Contract):
    model_config = ConfigDict(frozen=True)
    host: str
    port: int = Field(default=22, ge=1, le=65535)

    @field_validator("host")
    @classmethod
    def host_name(cls, value: str) -> str:
        return canonical_host(value)

    @property
    def known_host_name(self) -> str:
        return self.host if self.port == 22 else f"[{self.host}]:{self.port}"


class HostKeyObservation(Contract):
    endpoint: SshEndpoint
    algorithm: str
    fingerprint: str
    trust_state: Literal["trusted", "unknown", "changed"]
    challenge_id: str | None = None
    previous_fingerprint: str | None = None


class HostKeyConfirmation(Contract):
    challenge_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    fingerprint: str = Field(pattern=r"^SHA256:[A-Za-z0-9+/]{43}$")
