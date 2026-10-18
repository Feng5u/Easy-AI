"""Explicit, session-scoped data uploads. No arbitrary remote target or credentials."""

from typing import Literal
from pydantic import Field, field_validator
from easyai.domain.contracts import Contract
from easyai.domain.connections import SessionControl
from easyai.domain.environment import Identifier, RemotePath
from easyai.domain.remote_run import Digest

TransferError = Literal[
    "DATA_TRANSFER_AUTH_STALE",
    "DATA_TRANSFER_BUSY",
    "DATA_TRANSFER_CANCELLED",
    "DATA_TRANSFER_CLEANUP_PENDING",
    "DATA_TRANSFER_CLEANUP_FAILED",
    "DATA_TRANSFER_CLOSED",
    "DATA_TRANSFER_CONFIRMATION_INVALID",
    "DATA_TRANSFER_CONFIRMATION_REQUIRED",
    "DATA_TRANSFER_FAILED",
    "DATA_TRANSFER_RECOVERY_INVALID",
    "DATA_TRANSFER_PERSISTENCE_FAILED",
    "DATA_TRANSFER_HASH_MISMATCH",
    "DATA_TRANSFER_HOME_CHANGED",
    "DATA_TRANSFER_HOME_INVALID",
    "DATA_TRANSFER_JOB_LIMIT",
    "DATA_TRANSFER_MANIFEST_LIMIT",
    "DATA_TRANSFER_NOT_FOUND",
    "DATA_TRANSFER_PLAN_EXPIRED",
    "DATA_TRANSFER_PROGRESS_INVALID",
    "DATA_TRANSFER_SOURCE_CHANGED",
    "DATA_TRANSFER_SOURCE_EMPTY",
    "DATA_TRANSFER_SOURCE_FORBIDDEN",
    "DATA_TRANSFER_SOURCE_LIMIT",
    "DATA_TRANSFER_START_FAILED",
    "DATA_TRANSFER_TARGET_REQUIRED",
    "DATA_TRANSFER_TARGET_UNOWNED",
    "DATA_TRANSFER_TIMEOUT",
    "DATA_TRANSFER_VERIFICATION_INCOMPLETE",
]


class TransferBudget(Contract):
    max_files: int = Field(default=64, ge=1, le=256)
    max_bytes: int = Field(default=256 * 1024 * 1024, ge=1, le=256 * 1024 * 1024)
    seconds: int = Field(default=120, ge=1, le=120)


class TransferPlanRequest(SessionControl):
    expected_revision: int = Field(ge=1)
    data_selection_id: Identifier
    budget: TransferBudget


class TransferPlan(Contract):
    plan_id: Identifier
    plan_hash: Digest
    project_id: Identifier
    connection_id: Identifier
    target_id: Identifier
    target_revision: int = Field(ge=1)
    source_label: str = Field(max_length=4096)
    target_path: RemotePath
    file_count: int = Field(ge=1, le=256)
    total_bytes: int = Field(ge=0, le=256 * 1024 * 1024)
    budget: TransferBudget
    expires_in_seconds: int = Field(ge=1, le=60)
    writes_started: Literal[False] = False
    slot_id: Identifier | None = None
    reused_bytes: int = Field(default=0, ge=0, le=256 * 1024 * 1024)
    missing_files: int = Field(default=0, ge=0, le=256)


class TransferConfirmation(SessionControl):
    plan_id: Identifier
    plan_hash: Digest
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value: object) -> Literal[True]:
        if value is not True:
            raise ValueError("DATA_TRANSFER_CONFIRMATION_REQUIRED")
        return True


class TransferJob(Contract):
    transfer_id: Identifier
    plan_id: Identifier
    plan_hash: Digest
    project_id: Identifier
    connection_id: Identifier
    target_path: RemotePath
    status: Literal[
        "UPLOADING",
        "VERIFYING",
        "CANCELLING",
        "CLEANUP_PENDING",
        "COMPLETED",
        "CANCELLED",
        "FAILED",
    ]
    file_count: int = Field(ge=1, le=256)
    total_bytes: int = Field(ge=0, le=256 * 1024 * 1024)
    reused_bytes: int = Field(default=0, ge=0, le=256 * 1024 * 1024)
    sent_bytes: int = Field(default=0, ge=0, le=256 * 1024 * 1024)
    verified_bytes: int = Field(default=0, ge=0, le=256 * 1024 * 1024)
    completed_files: int = Field(default=0, ge=0, le=256)
    error_code: TransferError | None = None
    data_ready: Literal[False] = False


class TransferHistory(Contract):
    transfer_id: Identifier
    project_id: Identifier
    target_id: Identifier
    target_revision: int = Field(ge=1)
    target_path: RemotePath
    file_count: int = Field(ge=1, le=256)
    total_bytes: int = Field(ge=0, le=256 * 1024 * 1024)
    last_completed: bool
    inspection_required: Literal[True] = True
