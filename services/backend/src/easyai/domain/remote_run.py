"""Pinned remote execution identity; connection leases and credentials are not durable identity."""

import hashlib
import json
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from easyai.domain.contracts import Contract, RunConfig
from easyai.domain.connections import AuthenticatedConnection
from easyai.domain.environment import Fingerprint, Identifier, RemotePath
from easyai.domain.ssh import SshEndpoint

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
RemoteState = Literal[
    "STARTING", "RUNNING", "CANCELLING", "CLEANUP_PENDING", "COMPLETED", "FAILED", "CANCELLED"
]


class RemoteRunIdentity(Contract):
    model_config = ConfigDict(frozen=True)
    project_id: Identifier
    target_id: Identifier
    run_id: Identifier
    launch_id: Identifier
    username: str = Field(min_length=1, max_length=128, pattern=r"^[^\x00-\x20\x7f]+$")
    endpoint: SshEndpoint
    host_fingerprint: Fingerprint
    run_root: RemotePath
    program_hash: Digest
    code_hash: Digest
    bundle_hash: Digest
    config_hash: Digest


class RemoteStream(Contract):
    model_config = ConfigDict(frozen=True)
    generation: Identifier
    size_bytes: int = Field(ge=0, le=128 * 1024 * 1024)
    sha256: Digest


class RemoteStreams(Contract):
    events: RemoteStream
    stdout: RemoteStream
    stderr: RemoteStream


class RemoteRunObservation(Contract):
    identity: RemoteRunIdentity
    heartbeat: int = Field(ge=1)
    state: RemoteState
    sealed: bool
    exit_code: int | None = None
    streams: RemoteStreams

    @model_validator(mode="after")
    def terminal_is_sealed(self) -> Self:
        terminal = self.state in ("COMPLETED", "FAILED", "CANCELLED")
        if terminal != self.sealed or terminal != (self.exit_code is not None):
            raise ValueError("REMOTE_EXIT_EVIDENCE_INVALID")
        return self


class RemoteRunCheckpoint(Contract):
    protocol_version: Literal[1] = 1
    identity: RemoteRunIdentity
    start_outcome: Literal["not_attempted", "unknown", "acknowledged"] = "not_attempted"
    cancel_state: Literal["none", "pending", "acknowledged", "resolved"] = "none"
    execution_state: Literal[
        "CREATED",
        "STAGING",
        "STARTING",
        "RUNNING",
        "CANCELLING",
        "CLEANUP_PENDING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    ] = "CREATED"
    connection_state: Literal["connected", "disconnected"] = "disconnected"
    # COMPLETED is only execution exit evidence. Artifact verification is a later gate.
    artifacts_verified: Literal[False] = False
    last_connection_id: Identifier | None = None
    last_observation: RemoteRunObservation | None = None

    @model_validator(mode="after")
    def checkpoint_identity(self) -> Self:
        if self.last_observation is not None and (
            self.last_observation.identity != self.identity
            or self.last_observation.state != self.execution_state
            or self.start_outcome != "acknowledged"
        ):
            raise ValueError("REMOTE_CHECKPOINT_IDENTITY_INVALID")
        if (
            self.execution_state in ("COMPLETED", "FAILED", "CANCELLED")
            and self.last_observation is None
        ):
            raise ValueError("REMOTE_CHECKPOINT_EXIT_MISSING")
        return self


def identity_from_config(
    config: RunConfig, auth: AuthenticatedConnection, launch_id: str
) -> RemoteRunIdentity:
    """Use the authoritative generated run snapshot, never renderer-supplied hash overrides."""
    if (
        config.runner != "ssh"
        or config.project_id != auth.project_id
        or config.project_id != auth.scope.project_id
        or auth.authenticated is not True
    ):
        raise ValueError("REMOTE_CONFIG_IDENTITY_INVALID")
    # No local ~ expansion or client path resolution is performed.
    from easyai.domain.environment import remote_path

    for value in (config.run_root, config.data_root, config.python_executable):
        remote_path(value)
    if config.environment_prefix is not None:
        remote_path(config.environment_prefix)
    raw = json.dumps(
        config.model_dump(mode="json", by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return RemoteRunIdentity(
        project_id=config.project_id,
        target_id=config.target_id,
        run_id=config.run_id,
        launch_id=launch_id,
        username=auth.username,
        endpoint=auth.scope.endpoint,
        host_fingerprint=auth.scope.host_fingerprint,
        run_root=config.run_root,
        program_hash=config.program_hash,
        code_hash=config.code_hash,
        bundle_hash=config.bundle_hash,
        config_hash=hashlib.sha256(raw).hexdigest(),
    )
