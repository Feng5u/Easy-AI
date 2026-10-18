"""Export a complete source bundle into an explicitly authorized new directory."""

import ast
import hashlib
import json
from pathlib import Path

from easyai.compiler.pipeline import Compilation
from easyai.domain.catalog import RUNTIME_ROOT


def export_bundle(compilation: Compilation, destination: Path) -> dict[str, str]:
    result, program = compilation.result, compilation.program
    if not result.runnable or result.code is None or result.source_map is None or program is None:
        raise ValueError("BUNDLE_NOT_RUNNABLE")
    # mkdir(exist_ok=False) is the single claim point. Never merge into or replace
    # a user directory, including a pre-existing empty directory or symlink.
    parent = destination.parent.resolve(strict=True)
    if destination.name in ("", ".", "..") or destination.is_symlink():
        raise ValueError("OUTPUT_PATH_FORBIDDEN")
    target = parent / destination.name
    files: dict[str, str] = {
        "code/train.py": result.code,
        "code/source-map.json": json.dumps(
            [item.model_dump(by_alias=True) for item in result.source_map],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        "program.ir.json": program.model_dump_json(by_alias=True, indent=2) + "\n",
        "ENVIRONMENT.md": (
            "# Execution environment\n\nPython 3.11 and compatible torch/torchvision/matplotlib are required.\n"
            "Use a teacher-prepared environment. This export does not install packages or download data.\n"
            "No Easy-AI Python package is required; all auxiliary source is included in code/.\n"
            "Training dependency versions remain unverified until the separately authorized M3 environment check.\n"
        ),
        "README.md": (
            "# Easy-AI generated source bundle\n\nRun in your prepared training environment:\n\n"
            f'```sh\npython code/train.py --data-root "/absolute/path/to/data" '
            f'--output-dir "/absolute/path/to/new-output" --seed {program.seed}\n```\n\n'
            "The output directory must be new. Dataset download is disabled.\n"
            f"Compilation mode: {program.execution_mode}. Program hash: {result.program_hash}.\n"
            "Quick mode is a capped small-sample check and does not replace the formal example.\n"
        ),
    }
    for helper in ("easyai_runtime.py", "entry.py", "supervisor.py", "portable_journal.py"):
        files[f"code/{helper}"] = (RUNTIME_ROOT / helper).read_text(encoding="utf-8")
    managed = Path(__file__).parents[1] / "runtime/managed.py"
    if not managed.is_file():
        managed = RUNTIME_ROOT / "managed.py"
    files["code/managed.py"] = managed.read_text(encoding="utf-8")
    # Check every generated/exported Python file without importing or executing it.
    for path, text in files.items():
        if path.endswith(".py"):
            ast.parse(text, filename=path)
    hashes = {
        path: hashlib.sha256(text.encode("utf-8")).hexdigest()
        for path, text in sorted(files.items())
    }
    bundle_hash = hashlib.sha256(
        json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    files["bundle.json"] = (
        json.dumps(
            {
                "bundleHash": bundle_hash,
                "programHash": result.program_hash,
                "codeHash": result.code_hash,
                "files": hashes,
            },
            indent=2,
        )
        + "\n"
    )
    target.mkdir(exist_ok=False)
    for path, text in sorted(files.items()):
        output = target / path
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    return {
        "bundleHash": bundle_hash,
        "programHash": result.program_hash,
        "codeHash": result.code_hash or "",
    }
