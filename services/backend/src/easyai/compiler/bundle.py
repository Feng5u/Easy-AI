"""Export a complete source bundle into an explicitly authorized new directory."""

import ast
import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from easyai.compiler.pipeline import Compilation
from easyai.domain.catalog import RUNTIME_ROOT
from easyai.domain.contracts import ProjectDocument
from easyai.runtime.dataset_inputs import require_guarded_code

if TYPE_CHECKING:
    from easyai.security.remote_cache import LocalDirectory


def runtime_sources() -> dict[str, str]:
    """The single source of truth for packaged, portable execution helpers."""
    sources = {
        f"code/{helper}": (RUNTIME_ROOT / helper).read_text(encoding="utf-8")
        for helper in ("easyai_runtime.py", "entry.py", "supervisor.py", "portable_journal.py")
    }
    managed = Path(__file__).parents[1] / "runtime/managed.py"
    if not managed.is_file():
        managed = RUNTIME_ROOT / "managed.py"
    sources["code/managed.py"] = managed.read_text(encoding="utf-8")
    inputs = Path(__file__).parents[1] / "runtime/dataset_inputs.py"
    if not inputs.is_file():
        inputs = RUNTIME_ROOT / "dataset_inputs.py"
    sources["code/dataset_inputs.py"] = inputs.read_text(encoding="utf-8")
    return sources


def export_bundle(
    compilation: Compilation,
    destination: Path,
    *,
    directory: "LocalDirectory | None" = None,
    snapshot: ProjectDocument | None = None,
) -> dict[str, str]:
    result, program = compilation.result, compilation.program
    if not result.runnable or result.code is None or result.source_map is None or program is None:
        raise ValueError("BUNDLE_NOT_RUNNABLE")
    require_guarded_code(result.code)
    from easyai.compiler.artifact_budget import validate_artifact_budget

    validate_artifact_budget(program)
    # Standalone export exclusively claims the destination. Internal run export
    # borrows the owner's already exclusive claim; neither merges user output.
    if destination.name in ("", ".", "..") or destination.is_symlink():
        raise ValueError("OUTPUT_PATH_FORBIDDEN")
    if directory is not None and destination != directory.path:
        raise ValueError("OUTPUT_DIRECTORY_IDENTITY_INVALID")
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
    files.update(runtime_sources())
    if snapshot is not None:
        files["project.easyai.json"] = snapshot.model_dump_json(by_alias=True, indent=2) + "\n"
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
    if directory is None:
        target = destination.parent.resolve(strict=True) / destination.name
        target.mkdir(exist_ok=False)
        for path in sorted(files, key=lambda name: (name == "bundle.json", name)):
            text = files[path]
            output = target / path
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
    else:
        # Borrow the caller's exclusively claimed, continuously held run directory.
        directory.verify()
        code = None
        try:
            code = directory.new_child("code")
            for path, text in sorted(files.items()):
                if path == "bundle.json":
                    continue
                output_directory = code if path.startswith("code/") else directory
                name = path.removeprefix("code/")
                with os.fdopen(output_directory.open_file(name, "exclusive"), "wb") as stream:
                    raw = text.encode("utf-8")
                    if stream.write(raw) != len(raw):
                        raise OSError("BUNDLE_WRITE_INCOMPLETE")
                    stream.flush()
                    output_directory.sync_file(stream.fileno())
                    output_directory.verify_file(name, stream.fileno())
            code.sync()
            directory.sync()
            temporary = ".bundle-" + str(uuid4()) + ".tmp"
            with os.fdopen(directory.open_file(temporary, "exclusive"), "wb") as stream:
                raw = files["bundle.json"].encode("utf-8")
                if stream.write(raw) != len(raw):
                    raise OSError("BUNDLE_WRITE_INCOMPLETE")
                stream.flush()
                directory.sync_file(stream.fileno())
                directory.verify_file(temporary, stream.fileno())
            directory.publish(temporary, "bundle.json")
            directory.remove(temporary)
            directory.sync()
        finally:
            if code is not None:
                code.close()
    return {
        "bundleHash": bundle_hash,
        "programHash": result.program_hash,
        "codeHash": result.code_hash or "",
    }
