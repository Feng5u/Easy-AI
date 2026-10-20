"""Project-scoped remote run requests reference backend-owned immutable bindings."""

from typing import Literal
from pydantic import Field
from easyai.domain.contracts import Contract
from easyai.domain.environment import EnvironmentRequest, Identifier, RemotePath


class RemoteBindingRequest(EnvironmentRequest):
    expected_revision: int = Field(ge=1)
    expected_program_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    probe_request_id: Identifier
    run_base: RemotePath


class RemoteBinding(Contract):
    binding_id: Identifier
    project_id: Identifier
    connection_id: Identifier
    target_id: Identifier
    environment_id: Identifier
    data_binding_id: Identifier
    project_revision: int = Field(ge=1)
    program_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    python_executable: RemotePath
    environment_prefix: RemotePath | None
    device: Literal["cpu", "cuda", "mps"]
    dataset_name: Literal["MNIST", "FashionMNIST", "CIFAR10"]
    data_root: RemotePath
    run_base: RemotePath
    expires_in_seconds: int = Field(ge=1, le=300)


class RemoteRunStartRequest(Contract):
    runner: Literal["ssh"]
    binding_id: Identifier
    expected_revision: int = Field(ge=1)
    expected_program_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
