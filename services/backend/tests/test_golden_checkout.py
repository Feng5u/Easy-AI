"""Canonical compiler snapshots must survive Windows Git checkout byte for byte."""

import hashlib
import shutil
import subprocess
from pathlib import Path

from easyai.compiler.pipeline import compile_project
from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import ProjectDocument


def test_autocrlf_checkout_preserves_compiler_golden_bytes(tmp_path: Path) -> None:
    repository = tmp_path / "git-input"
    repository.mkdir()
    relative = Path("services/backend/tests/fixtures/golden")
    shutil.copytree(SOURCE_ROOT / relative, repository / relative)
    shutil.copyfile(SOURCE_ROOT / ".gitattributes", repository / ".gitattributes")
    for arguments in (
        ["init", "--quiet"],
        ["config", "core.autocrlf", "true"],
        ["config", "core.safecrlf", "false"],
        ["add", "."],
    ):
        subprocess.run(["git", *arguments], cwd=repository, check=True, capture_output=True)
    checkout = tmp_path / "checkout"
    subprocess.run(
        ["git", "checkout-index", "--all", f"--prefix={checkout.as_posix()}/"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    project = ProjectDocument.model_validate_json(
        (SOURCE_ROOT / "packages/contracts/fixtures/mnist-figures.json").read_bytes()
    )
    compiled = compile_project(project)
    assert compiled.result.runnable
    code = compiled.result.code.encode("utf-8")
    actual = (checkout / relative / "mnist.py.txt").read_bytes()
    assert actual == code
    assert hashlib.sha256(actual).hexdigest() == compiled.result.code_hash
    for source in (SOURCE_ROOT / relative).iterdir():
        assert (checkout / relative / source.name).read_bytes() == source.read_bytes()
    # A CRLF version is different protocol content, even with identical lines.
    changed = code.replace(b"\n", b"\r\n")
    assert hashlib.sha256(changed).hexdigest() != compiled.result.code_hash
