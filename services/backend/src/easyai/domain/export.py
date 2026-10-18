import json
import sys
from pathlib import Path

from pydantic import BaseModel

from easyai.domain import contracts, desktop, environment, connections
from easyai.domain.program import ProgramIR
from easyai.domain.remote_run import RemoteRunIdentity, RemoteRunObservation, RemoteRunCheckpoint
from easyai.domain.remote_run import ArtifactManifest
from easyai.domain.remote_execution import (
    RemoteBinding,
    RemoteBindingRequest,
    RemoteRunStartRequest,
)
from easyai.domain.ssh import (
    SshEndpoint,
    HostKeyObservation,
    HostKeyConfirmation,
    IdentityRequest,
    IdentityProbeRequest,
    IdentityConfirmRequest,
    IdentityResult,
)

MODELS: list[type[BaseModel]] = [
    ArtifactManifest,
    RemoteBinding,
    RemoteBindingRequest,
    RemoteRunStartRequest,
    RemoteRunIdentity,
    RemoteRunObservation,
    RemoteRunCheckpoint,
    connections.ConnectionProfileInput,
    connections.ConnectionProfile,
    connections.ConnectionProfileUpdate,
    connections.ConnectionTargetReference,
    connections.AuthenticationRequest,
    connections.AuthenticatedConnection,
    connections.SessionControl,
    environment.EnvironmentScope,
    environment.EnvironmentRequest,
    environment.EnvironmentDiscoveryRequest,
    environment.EnvironmentProbeRequest,
    environment.DatasetProbe,
    environment.EnvironmentDescriptor,
    environment.EnvironmentCatalog,
    environment.EnvironmentProbeReport,
    environment.EnvironmentProbeResult,
    contracts.ProjectDocument,
    contracts.Origin,
    contracts.BlockIR,
    ProgramIR,
    contracts.Diagnostic,
    contracts.SourceSpan,
    contracts.SymbolEntry,
    contracts.CompileResult,
    contracts.CompileRequest,
    contracts.CompileResponse,
    contracts.Event,
    contracts.EpochMetrics,
    contracts.ArtifactRecord,
    contracts.RunConfig,
    contracts.Run,
    desktop.LocalPreflightRequest,
    desktop.LocalPreflightResult,
    desktop.SelectionResult,
    desktop.ProjectSession,
    desktop.RunStartRequest,
    desktop.RunLogs,
    desktop.RunSource,
    desktop.DiagnosticReport,
    SshEndpoint,
    HostKeyObservation,
    HostKeyConfirmation,
    IdentityRequest,
    IdentityProbeRequest,
    IdentityConfirmRequest,
    IdentityResult,
]


def main() -> None:
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    for model in MODELS:
        schema = model.model_json_schema(by_alias=True)
        (target / f"{model.__name__}.json").write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
