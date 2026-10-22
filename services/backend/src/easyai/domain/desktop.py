"""Main-authorized local workflow DTOs; compiler contracts remain authoritative."""

from typing import Literal
from pydantic import Field
from easyai.domain.contracts import Contract, ProjectDocument, SourceSpan


class SelectionResult(Contract):
    selection_id: str
    kind: Literal["project", "python", "data"]
    label: str


class ProjectSession(Contract):
    project: ProjectDocument | None
    read_only: bool
    reason: str | None = None
    raw_text: str | None = None
    label: str | None = None


class RunStartRequest(Contract):
    expected_revision: int = Field(ge=1)
    expected_program_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    python_selection_id: str
    data_selection_id: str


class BundleExportResult(Contract):
    exported: Literal[True] = True
    project_id: str
    project_revision: int = Field(ge=1)
    program_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    directory_name: str = Field(pattern=r"^easyai-code-[0-9a-f-]{36}$")


class RunLogs(Contract):
    stdout: str
    stderr: str
    stdout_after: int = Field(ge=0)
    stderr_after: int = Field(ge=0)
    done: bool


class SnapshotObject(Contract):
    block_id: str = Field(min_length=1, max_length=256)
    kind: Literal["transform", "dataset", "dataloader", "model_class"]
    role: Literal["train", "test"] | None
    workspace: Literal["data", "model"]
    registered: bool


class RunSource(Contract):
    project_revision: int = Field(ge=1)
    program_hash: str
    code_hash: str
    code: str
    source_map: list[SourceSpan]
    snapshot: ProjectDocument
    objects: list[SnapshotObject] = Field(default_factory=list)
    reference_check: Literal["passed", "failed", "unavailable"] = "unavailable"


class LocalPreflightRequest(Contract):
    project_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    expected_revision: int = Field(ge=1)
    python_selection_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    data_selection_id: str = Field(pattern=r"^[0-9a-f-]{36}$")


class LocalPreflightCheck(Contract):
    ok: bool
    code: str


class LocalPythonVersions(Contract):
    python: str
    prefix: str
    torch: str
    torchvision: str
    matplotlib: str


class LocalPreflightResult(LocalPreflightRequest):
    environment: LocalPreflightCheck
    data: LocalPreflightCheck
    versions: LocalPythonVersions | None = None
    dataset_names: list[str]


class DiagnosticReport(Contract):
    report_version: Literal[1] = 1
    scope: Literal["local_safe_summary"] = "local_safe_summary"
    code: Literal["RUNTIME_NAME_ERROR", "RUNTIME_EXCEPTION"]
    run_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    event_seq: int = Field(ge=1)
    code_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    project_revision: int = Field(ge=1)
    precision: Literal["semantic", "scaffold", "none"]
    name_state: Literal["registered", "unregistered", "not_matched", "ambiguous", "unavailable"]
    reference_check: Literal["passed", "failed", "unavailable"]
    objects_total: int | None = Field(default=None, ge=0, le=500)
    registered_total: int | None = Field(default=None, ge=0, le=500)
