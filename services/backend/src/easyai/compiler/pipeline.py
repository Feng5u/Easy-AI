"""Pure compile service: no training imports, execution, subprocess, or network."""

import ast
import hashlib
import json
from dataclasses import dataclass

from easyai.compiler.decode import DecodeError, decode
from easyai.compiler.lower import lower_program
from easyai.domain.contracts import CompileResult, Diagnostic, ProjectDocument
from easyai.domain.program import ProgramIR
from easyai.domain.symbols import registry
from easyai.services.project_service import validate_project_bytes


@dataclass
class Compilation:
    result: CompileResult
    program: ProgramIR | None


def program_hash(program: ProgramIR) -> str:
    canonical = json.dumps(
        program.model_dump(by_alias=True),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prepare(project: ProjectDocument) -> tuple[ProgramIR | None, list[Diagnostic]]:
    try:
        # Revalidate the exact snapshot so direct callers cannot bypass save/open limits.
        validated = validate_project_bytes(project.model_dump_json(by_alias=True).encode("utf-8"))
        roots, diagnostics = decode(validated)
        symbols, references = registry(roots)
        diagnostics.extend(references)
        if any(item.severity == "error" for item in diagnostics):
            return None, diagnostics
        program, semantic = lower_program(validated, roots, symbols)
        diagnostics.extend(semantic)
        return program, diagnostics
    except (ValueError, RecursionError, DecodeError) as error:
        return None, [
            Diagnostic(
                code="PROJECT_INVALID",
                message="工程结构、版本或资源限制不受支持。",
                details={"reason": str(error)[:256]},
            )
        ]


def compile_project(project: ProjectDocument) -> Compilation:
    from easyai.compiler.emit import emit_program

    program, diagnostics = prepare(project)
    if program is None:
        # No UI coordinates or rejected raw project content become an executable cache key.
        return Compilation(
            CompileResult(
                revision=project.revision, program_hash="", diagnostics=diagnostics, runnable=False
            ),
            None,
        )
    code, source_map = emit_program(program)
    try:
        ast.parse(code, filename="train.py")
    except SyntaxError as error:
        diagnostics.append(
            Diagnostic(
                code="COMPILER_SYNTAX_ERROR",
                message="生成代码存在语法错误，不能运行。",
                details={"line": error.lineno or 0},
            )
        )
        return Compilation(
            CompileResult(
                revision=project.revision,
                program_hash=program_hash(program),
                diagnostics=diagnostics,
                runnable=False,
            ),
            program,
        )
    return Compilation(
        CompileResult(
            revision=project.revision,
            program_hash=program_hash(program),
            compiler_version=program.compiler_version,
            diagnostics=diagnostics,
            runnable=True,
            code=code,
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            source_map=source_map,
        ),
        program,
    )
