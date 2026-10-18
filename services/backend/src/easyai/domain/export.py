import json
import sys
from pathlib import Path

from pydantic import BaseModel

from easyai.domain import contracts

MODELS: list[type[BaseModel]] = [
    contracts.ProjectDocument,
    contracts.Origin,
    contracts.BlockIR,
    contracts.ProgramIR,
    contracts.Diagnostic,
    contracts.SourceSpan,
    contracts.SymbolEntry,
    contracts.CompileResult,
    contracts.Event,
    contracts.EpochMetrics,
    contracts.ArtifactRecord,
    contracts.RunConfig,
    contracts.Run,
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
