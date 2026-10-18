import json
import sys
from pathlib import Path

from pydantic import BaseModel

from easyai.domain import contracts, desktop
from easyai.domain.program import ProgramIR
from easyai.domain.ssh import SshEndpoint, HostKeyObservation, HostKeyConfirmation

MODELS: list[type[BaseModel]] = [
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
    desktop.SelectionResult,
    desktop.ProjectSession,
    desktop.RunStartRequest,
    desktop.RunLogs,
    desktop.RunSource,
    SshEndpoint,
    HostKeyObservation,
    HostKeyConfirmation,
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
