"""Explicit owned temporary roots shared by local protocol tests."""

import pytest
from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import ProjectDocument
from easyai.compiler.pipeline import compile_project
from easyai.services.project_service import ProjectService
from easyai.services.run_service import RunService


@pytest.fixture
def owned(tmp_path):
    project_root = tmp_path / "工程 root"
    project_root.mkdir()
    raw = (SOURCE_ROOT / "packages/contracts/fixtures/mnist-figures.json").read_bytes()
    (project_root / "project.easyai.json").write_bytes(raw)
    project = ProjectService(project_root)
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    service = RunService(runs_root)
    data = tmp_path / "数据 root"
    data.mkdir()
    doc = ProjectDocument.model_validate_json(raw)
    phash = compile_project(doc).result.program_hash
    try:
        yield project, service, doc, phash, data
    finally:
        service.close()
        project.close()
