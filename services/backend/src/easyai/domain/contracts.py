from typing import Any, Literal
import math
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        alias_generator=to_camel,
        populate_by_name=True,
        allow_inf_nan=False,
    )


class Origin(Contract):
    block_id: str = Field(min_length=1, max_length=256)
    workspace: Literal["data", "model", "training"]


class Diagnostic(Contract):
    code: str
    severity: Literal["error", "warning", "info"] = "error"
    message: str
    origin: Origin | None = None
    field: str | None = None
    suggestion: str | None = None
    details: dict[str, Any] | None = None


class SourceSpan(Contract):
    file: Literal["train.py"] = "train.py"
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    origin: Origin
    kind: Literal["semantic", "scaffold"]

    @field_validator("end_line")
    @classmethod
    def valid_end(cls, value: int, info: Any) -> int:
        if value < info.data.get("start_line", 1):
            raise ValueError("endLine precedes startLine")
        return value


class Settings(Contract):
    data_directory: Literal["data"] = "data"
    seed: int = Field(default=42, ge=0, le=4294967295)
    execution_mode: Literal["full", "quick"] = "full"


class UI(Contract):
    active_tab: Literal["data", "model", "training"] = "data"
    code_visible: bool = False


class BlocklyBlocks(Contract):
    language_version: Literal[0] = 0
    blocks: list[dict[str, Any]] = Field(default_factory=list)


class Workspace(Contract):
    blocks: BlocklyBlocks


class Workspaces(Contract):
    data: Workspace
    model: Workspace
    training: Workspace


class ProjectDocument(Contract):
    schema_version: Literal[1] = 1
    app_version: Literal["0.0.0"] = "0.0.0"
    block_library_version: Literal["0.0.0"] = "0.0.0"
    project_id: str
    name: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=1)
    workspaces: Workspaces
    settings: Settings = Field(default_factory=Settings)
    ui: UI = Field(default_factory=UI)

    @model_validator(mode="after")
    def finite_snapshot(self) -> "ProjectDocument":
        def walk(value: Any) -> None:
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Non-finite JSON number")
            if isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(self.workspaces.model_dump())
        return self

    @field_validator("project_id")
    @classmethod
    def valid_uuid(cls, value: str) -> str:
        UUID(value)
        return value


class BlockIR(Contract):
    type_id: str
    origin: Origin
    fields: dict[str, Any]
    inputs: dict[str, list["BlockIR"]]


class SymbolEntry(Contract):
    id: str
    kind: Literal["transform", "dataset", "dataloader", "model_class"]
    name: str
    role: Literal["train", "test"] | None = None
    workspace: Literal["data", "model"]
    registered: bool


class CompileResult(Contract):
    revision: int = Field(ge=1)
    program_hash: str
    compiler_version: str = "0.0.0"
    diagnostics: list[Diagnostic]
    runnable: bool
    code: str | None = None
    code_hash: str | None = None
    source_map: list[SourceSpan] | None = None


class EpochMetrics(Contract):
    # Metrics deliberately use snake_case, unlike API envelopes.
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    epoch: int = Field(ge=1)
    train_loss: float = Field(ge=0)
    test_accuracy: float = Field(ge=0, le=1)
    train_samples: int = Field(gt=0)
    test_samples: int = Field(gt=0)
    elapsed_seconds: float = Field(ge=0)


class Event(Contract):
    protocol_version: Literal[1] = 1
    run_id: str
    seq: int = Field(ge=1)
    source: Literal["runtime", "application"]
    source_seq: int | None = Field(default=None, ge=1)
    timestamp: str
    type: Literal[
        "runtime_started",
        "device_selected",
        "progress",
        "epoch_completed",
        "artifact_created",
        "runtime_error",
        "pipeline_cancelled",
        "pipeline_completed",
        "process_exited",
        "status_changed",
    ]
    block_id: str | None = None
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_event(self) -> "Event":
        if self.source == "runtime" and self.source_seq is None:
            raise ValueError("Runtime events require sourceSeq")
        if self.type == "epoch_completed":
            EpochMetrics.model_validate(self.payload)
        return self


class ArtifactRecord(Contract):
    artifact_id: str
    run_id: str
    kind: Literal["figure", "model", "log", "metrics"]
    relative_path: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_block_id: str
    contributor_block_ids: list[str]
    phase: Literal["before", "epoch_end", "after"] | None = None
    epoch: int | None = Field(default=None, ge=1)
    sync_state: Literal["pending", "syncing", "ready", "error"]


class QuickLimits(Contract):
    epochs: Literal[1] = 1
    train_samples: Literal[1024] = 1024
    test_samples: Literal[256] = 256


class RunConfig(Contract):
    config_version: Literal[1] = 1
    run_id: str
    project_id: str
    project_revision: int = Field(ge=1)
    program_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_id: str
    runner: Literal["local", "ssh"]
    data_root: str
    run_root: str
    python_executable: str
    environment_prefix: str | None = None
    execution_mode: Literal["full", "quick"]
    seed: int = Field(ge=0, le=4294967295)
    num_workers: int = Field(ge=0, le=16)
    pin_memory_policy: Literal["cuda_only"] = "cuda_only"
    quick_limits: QuickLimits | None = None


class Run(Contract):
    run_id: str
    project_id: str
    status: Literal[
        "CREATED",
        "PRECHECKING",
        "STAGING",
        "STARTING",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLING",
        "CANCELLED",
        "INTERRUPTED",
    ]
    connection_state: Literal["connected", "disconnected", "reconnecting"]
    sync_state: Literal["pending", "syncing", "complete", "error"]
    config: RunConfig


class CompileRequest(Contract):
    project: ProjectDocument
    request_id: int = Field(ge=1)


class CompileResponse(CompileResult):
    request_id: int = Field(ge=1)
