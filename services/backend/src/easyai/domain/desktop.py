"""Main-authorized local workflow DTOs; compiler contracts remain authoritative."""

from typing import Literal
from pydantic import Field
from easyai.domain.contracts import Contract, ProjectDocument, SourceSpan


class SelectionResult(Contract):
    selection_id: str
    kind: Literal["project", "python", "data"]
    label: str


class ProjectSession(Contract):
    project: ProjectDocument
    read_only: bool
    reason: str | None = None


class RunStartRequest(Contract):
    expected_revision: int = Field(ge=1)
    expected_program_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    python_selection_id: str
    data_selection_id: str


class RunLogs(Contract):
    stdout: str
    stderr: str
    stdout_after: int = Field(ge=0)
    stderr_after: int = Field(ge=0)
    done: bool


class RunSource(Contract):
    project_revision: int = Field(ge=1)
    program_hash: str
    code_hash: str
    code: str
    source_map: list[SourceSpan]
    snapshot: ProjectDocument
