"""Local controlled-install planning and lifecycle contracts; no commands or paths in requests."""

from typing import Annotated, Literal, Self
from pydantic import Field, model_validator, field_validator
from easyai.domain.contracts import Contract
from easyai.domain.environment import Identifier

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
PackageId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")]


class PackageCard(Contract):
    package_id: PackageId
    import_name: str
    group: Literal["ml", "dl", "cv", "nlp"]
    purpose: str
    dependency_note: str
    installed_status: Literal["unknown"] = "unknown"
    installed_version: str | None = None
    target_version: str | None


class PackageCatalog(Contract):
    catalog_version: Literal[1] = 1
    packages: list[PackageCard]
    profiles: list[Literal["teacher-existing", "easyai-cpu"]]
    execution_enabled: bool = False


class NewEnvironmentSpec(Contract):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")


class InstallPlanRequest(Contract):
    target_id: Literal["local"]
    profile_id: Literal["teacher-existing", "easyai-cpu"]
    package_ids: list[PackageId] = Field(min_length=1, max_length=17)
    owned_environment_id: Identifier | None = None
    new_environment_spec: NewEnvironmentSpec | None = None

    @model_validator(mode="after")
    def one_target(self) -> Self:
        if (self.owned_environment_id is None) == (self.new_environment_spec is None):
            raise ValueError("INSTALL_TARGET_AMBIGUOUS")
        if len(self.package_ids) != len(set(self.package_ids)):
            raise ValueError("INSTALL_PACKAGE_DUPLICATED")
        return self


class PackageChange(Contract):
    package_id: PackageId
    previous_version: str | None
    target_version: str | None
    action: Literal["add", "keep", "unresolved"]
    requested: bool


class InstallPlan(Contract):
    plan_id: Identifier
    plan_hash: Digest
    target_id: Literal["local"] = "local"
    profile_id: Literal["easyai-cpu"] = "easyai-cpu"
    environment_id: Identifier
    environment_name: str
    new_environment: bool
    baseline_fingerprint: Digest
    constraints_hash: Digest
    package_changes: list[PackageChange]
    requires_network: bool = True
    download_bytes: int | None = Field(ge=0)
    installed_bytes: int | None = Field(ge=0)
    size_status: Literal["locked-wheel-estimate", "unresolved"]
    platform: str
    blockers: list[str]
    execution_enabled: bool = False
    runtime_fingerprint: Digest | None = None
    bootstrap_bytes: int | None = Field(default=None, ge=0)
    disk_budget_bytes: int | None = Field(default=None, ge=1)
    execution_seconds: int | None = Field(default=None, ge=1, le=3600)


class InstallConfirmation(Contract):
    plan_id: Identifier
    plan_hash: Digest
    confirmed: Literal[True]
    network_acknowledged: Literal[True]

    @field_validator("confirmed", "network_acknowledged", mode="before")
    @classmethod
    def explicit_confirmation(cls, value: object) -> Literal[True]:
        if value is not True:
            raise ValueError("INSTALL_CONFIRMATION_REQUIRED")
        return True


class InstallInspection(Contract):
    """Trusted fixed-probe adapter output, never accepted from HTTP/IPC."""

    nonce: Identifier
    prefix: str
    python_version: str = Field(max_length=128)
    versions: dict[str, str]
    imports: dict[str, bool]
    tensor_ok: bool


class InstallJob(Contract):
    job_id: Identifier
    plan_id: Identifier
    plan_hash: Digest
    environment_id: Identifier
    state: Literal[
        "AWAITING_EXECUTION",
        "INSTALLING",
        "VERIFYING",
        "SUCCEEDED",
        "FAILED",
        "CANCEL_REQUESTED",
        "CANCELLED",
    ]
    status_code: str
    logs: list[str] = Field(max_length=128)
    needs_reprobe: bool = True
    changes_possible: bool = False
    verified: bool = False
    execution_enabled: bool = False
