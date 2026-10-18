"""Read-only Linux environment discovery/probe contracts; no install or shell fields."""

from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, AfterValidator, model_validator

from easyai.domain.contracts import Contract
from easyai.domain.ssh import SshEndpoint


def remote_path(value: str) -> str:
    if (
        not value.startswith("/")
        or value == "/"
        or len(value) > 1024
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or "\\" in value
        or ".." in value.split("/")
    ):
        raise ValueError("ENVIRONMENT_PATH_INVALID")
    return value


RemotePath = Annotated[
    str,
    Field(min_length=2, max_length=1024, pattern=r"^/[^\\\x00-\x1f\x7f]*$"),
    AfterValidator(remote_path),
]
Identifier = Annotated[
    str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
]
Fingerprint = Annotated[str, Field(pattern=r"^SHA256:[A-Za-z0-9+/]{43}$")]


class EnvironmentScope(Contract):
    model_config = ConfigDict(frozen=True)
    project_id: Identifier
    connection_id: Identifier
    endpoint: SshEndpoint
    host_fingerprint: Fingerprint


class EnvironmentRequest(Contract):
    model_config = ConfigDict(frozen=True)
    project_id: Identifier
    connection_id: Identifier
    request_id: Identifier


class EnvironmentDiscoveryRequest(EnvironmentRequest):
    conda_path: RemotePath | None = None
    python_path: RemotePath | None = None

    @model_validator(mode="after")
    def one_launcher(self) -> Self:
        if self.conda_path is not None and self.python_path is not None:
            raise ValueError("ENVIRONMENT_SELECTION_AMBIGUOUS")
        return self


class DatasetProbe(Contract):
    model_config = ConfigDict(frozen=True)
    name: Literal["MNIST", "FashionMNIST", "CIFAR10"]
    data_root: RemotePath


class EnvironmentProbeRequest(EnvironmentRequest):
    environment_id: Identifier
    device: Literal["cpu", "cuda", "mps"] = "cpu"
    dataset: DatasetProbe | None = None


class EnvironmentDescriptor(Contract):
    model_config = ConfigDict(frozen=True)
    environment_id: Identifier
    kind: Literal["conda", "python"]
    location: RemotePath
    read_only: Literal[True] = True


class EnvironmentCatalog(EnvironmentRequest):
    scope: EnvironmentScope
    environments: list[EnvironmentDescriptor] = Field(max_length=64)
    conda_executable: RemotePath | None = None
    conda_version: str | None = Field(default=None, max_length=128)
    note: Literal["unprobed", "conda_not_found"] = "unprobed"


class PackageCheck(Contract):
    version: str | None = Field(max_length=128)
    imported: bool
    error: Literal["missing", "import_failed"] | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.imported != (self.error is None):
            raise ValueError("ENVIRONMENT_REPORT_INCONSISTENT")
        return self


class ImportChecks(Contract):
    torch: PackageCheck
    torchvision: PackageCheck
    matplotlib: PackageCheck


class PythonCheck(Contract):
    executable: RemotePath
    prefix: RemotePath
    version: list[Annotated[int, Field(ge=0, le=1000)]] = Field(min_length=3, max_length=3)


class DeviceCheck(Contract):
    cuda_available: bool | None
    mps_available: bool | None


class TensorCheck(Contract):
    attempted: bool
    ok: bool
    device: Literal["cpu", "cuda", "mps"]
    error: Literal["dependency_missing", "device_unavailable", "execution_failed"] | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.ok and not self.attempted or self.ok != (self.error is None):
            raise ValueError("ENVIRONMENT_REPORT_INCONSISTENT")
        return self


class DatasetCheck(Contract):
    name: Literal["MNIST", "FashionMNIST", "CIFAR10"]
    data_root: RemotePath
    ok: bool
    sample_shape: list[Annotated[int, Field(ge=1, le=4096)]] | None = Field(max_length=4)
    sample_dtype: str | None = Field(max_length=64)
    label: int | None = Field(ge=0, le=9)
    error: Literal["dependency_missing", "unavailable", "unsafe_format_blocked"] | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        complete = (
            self.sample_shape is not None
            and self.sample_dtype is not None
            and self.label is not None
        )
        if self.ok != (self.error is None) or self.ok != complete:
            raise ValueError("ENVIRONMENT_REPORT_INCONSISTENT")
        if not self.ok and any(
            value is not None for value in (self.sample_shape, self.sample_dtype, self.label)
        ):
            raise ValueError("ENVIRONMENT_REPORT_INCONSISTENT")
        expected = [3, 32, 32] if self.name == "CIFAR10" else [1, 28, 28]
        if self.ok and self.sample_shape != expected:
            raise ValueError("ENVIRONMENT_DATASET_SHAPE_INVALID")
        return self


class EnvironmentProbeReport(Contract):
    schema_version: Literal[1]
    nonce: Identifier
    platform: Literal["linux"]
    python: PythonCheck
    imports: ImportChecks
    devices: DeviceCheck
    tensor: TensorCheck
    dataset: DatasetCheck | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if not self.imports.torch.imported and (
            self.tensor.attempted
            or self.devices.cuda_available is not None
            or self.devices.mps_available is not None
        ):
            raise ValueError("ENVIRONMENT_REPORT_INCONSISTENT")
        if self.tensor.ok and (
            self.tensor.device == "cuda"
            and self.devices.cuda_available is not True
            or self.tensor.device == "mps"
            and self.devices.mps_available is not True
        ):
            raise ValueError("ENVIRONMENT_REPORT_INCONSISTENT")
        if (
            self.dataset is not None
            and self.dataset.ok
            and not (self.imports.torch.imported and self.imports.torchvision.imported)
        ):
            raise ValueError("ENVIRONMENT_REPORT_INCONSISTENT")
        return self


class ProbeIssue(Contract):
    code: Literal[
        "PYTHON_UNSUPPORTED",
        "TORCH_IMPORT_FAILED",
        "TORCHVISION_IMPORT_FAILED",
        "MATPLOTLIB_IMPORT_FAILED",
        "TENSOR_CHECK_FAILED",
        "DATASET_CHECK_FAILED",
    ]
    suggestion: str = Field(max_length=256)


class EnvironmentProbeResult(EnvironmentRequest):
    scope: EnvironmentScope
    environment_id: Identifier
    report: EnvironmentProbeReport
    environment_ready: bool
    data_ready: bool | None
    issues: list[ProbeIssue] = Field(max_length=6)
