"""Compile/plan bounds only; never launch a training process or SSH."""

import pytest

from easyai.compiler.artifact_budget import validate_artifact_budget
from easyai.compiler.bundle import export_bundle
from easyai.compiler.pipeline import compile_project
from test_compilation import project
from test_run_service import prepare


def test_formal_ten_epoch_example_fits_actual_artifact_count_and_receipt_budget():
    compiled = compile_project(project())
    assert compiled.result.runnable
    program = compiled.program
    count, receipt = validate_artifact_budget(program)
    assert (
        count
        == len(program.training.before)
        + 10 * len(program.training.body)
        + len(program.training.after)
        + 1
    )
    assert receipt < 65536


def test_three_hundred_epochs_with_one_figure_are_rejected_before_emission():
    value = project()
    value.workspaces.training.blocks.blocks[0]["fields"]["EPOCHS"] = 300
    compiled = compile_project(value)
    assert not compiled.result.runnable and compiled.result.code is None
    assert any(d.code == "ARTIFACT_PLAN_COUNT_EXCEEDED" for d in compiled.result.diagnostics)
    quick = value.model_copy(deep=True)
    quick.settings.execution_mode = "quick"
    assert compile_project(quick).result.runnable


def test_receipt_bytes_are_bounded_independently_of_record_count(tmp_path):
    compiled = compile_project(project())
    program = compiled.program
    program.training.before = []
    program.training.after = []
    program.training.body = program.training.body[:1]
    program.training.epochs = 200  # Under 256 records, over the 64 KiB receipt budget.
    with pytest.raises(ValueError, match="ARTIFACT_PLAN_RECEIPT_EXCEEDED"):
        validate_artifact_budget(program)
    with pytest.raises(ValueError, match="ARTIFACT_PLAN_RECEIPT_EXCEEDED"):
        export_bundle(compiled, tmp_path / "not-exported")
    assert not (tmp_path / "not-exported").exists()


def test_formal_start_rechecks_saved_plan_without_spawning(owned, monkeypatch):
    from easyai.compiler import artifact_budget

    run = prepare(owned)
    monkeypatch.setattr(artifact_budget, "MAX_ARTIFACTS", 1)
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("No execution"))
    with pytest.raises(ValueError, match="ARTIFACT_PLAN_COUNT_EXCEEDED"):
        owned[1].start(run.run_id)
    assert owned[1].get(run.run_id).status == "CREATED"


def test_unicode_configuration_ids_cannot_overflow_ascii_cache_index():
    compiled = compile_project(project())
    program = compiled.program
    program.training.before = []
    program.training.after = []
    program.training.body = program.training.body[:1]
    program.training.epochs = 30
    figure = program.training.body[0]
    figure.origin.block_id = "😀" * 200
    for panel in figure.panels:
        panel.origin.block_id = "中文😀" * 60
    with pytest.raises(ValueError, match="ARTIFACT_PLAN_RECEIPT_EXCEEDED"):
        validate_artifact_budget(program)
