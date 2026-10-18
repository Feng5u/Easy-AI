"""Compiler checks never import torch or execute generated teaching code."""

import ast
import copy
import importlib.util
import json
import subprocess
import sys

import pytest

from easyai.compiler.emit import emit_program
from easyai.compiler.pipeline import prepare
from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import Origin, ProjectDocument
from easyai.domain.program import (
    AxisSpec,
    DataSourceSpec,
    FigureSpec,
    PanelSpec,
    SaveSpec,
    SequentialSpec,
    TitleSpec,
)


def program():
    document = ProjectDocument.model_validate(
        json.loads((SOURCE_ROOT / "packages/contracts/fixtures/mnist.json").read_bytes())
    )
    result, diagnostics = prepare(document)
    assert not diagnostics and result is not None
    return result


def origin(value):
    return Origin(block_id=value, workspace="training")


def figure(phase, source="train_loss", chart="line"):
    return FigureSpec(
        id=phase + "/unsafe?[]",
        origin=origin(phase),
        layout=[1, 1],
        size="medium",
        panels=[
            PanelSpec(
                origin=origin(phase + "-panel"),
                chart_type=chart,
                count=10,
                rows=2,
                cols=5,
                sources=[
                    DataSourceSpec(
                        origin=origin(phase + "-source"),
                        source=source,
                        x_source="epoch" if chart != "image_grid" else "none",
                    )
                ],
                title=TitleSpec(
                    origin=origin(phase + "-title"),
                    text="'\n__import__('os').system('never')",
                    color="blue",
                ),
                axis=AxisSpec(origin=origin(phase + "-axis"), show_ticks=False),
                legend=origin(phase + "-legend"),
            )
        ],
        save=SaveSpec(origin=origin(phase + "-save"), relative_path="outputs/中文 plot.png"),
    )


def test_expanded_training_is_syntax_valid_and_deterministic():
    value = program()
    code, spans = emit_program(value)
    ast.parse(code)
    assert emit_program(value) == (code, spans)
    assert f"class {value.model.name}(nn.Module):" in code
    assert "download=False" in code
    for token in (
        "loss.backward()",
        "optimizer.step()",
        "model.eval()",
        "torch.no_grad()",
        "float(loss.item()) * int(x.size(0))",
        "correct / test_samples",
        "torch.save(model.state_dict(), model_path)",
        "if __name__ == '__main__':",
    ):
        assert token in code
    for layer in value.model.layers:
        selected = [span for span in spans if span.origin == layer.origin]
        assert selected and all(
            1 <= span.start_line <= span.end_line <= len(code.splitlines()) for span in selected
        )
        if layer.kind != "model.flatten":
            assert len(selected) >= 2
    assert "import easyai" not in code


def test_three_phases_figures_safe_literals_explicit_axes_and_close():
    value = program()
    value.training.before = [figure("before", "train_samples", "image_grid")]
    value.training.body = [figure("body", "test_accuracy", "scatter")]
    value.training.after = [figure("after", "predictions", "image_grid")]
    code, spans = emit_program(value)
    ast.parse(code)
    assert code.count("plt.close(fig)") == 3
    assert code.count("format='png'") == 3
    assert "plt.show" not in code
    assert "PercentFormatter(xmax=1)" in code
    assert ".clamp(0, 1)" in code and "len(sample_dataset)" in code
    assert "outcome = 'correct'" in code
    assert "'epoch_end', epoch" in code and "'before', None" in code and "'after', None" in code
    assert {span.origin.block_id for span in spans} >= {"before-source", "body-title", "after-save"}
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"exec", "eval", "__import__"}
        for node in ast.walk(ast.parse(code))
    )


def test_sequential_children_have_actual_constructor_and_forward_spans():
    value = program()
    first = value.model.layers[:3]
    value.model.layers = [
        SequentialSpec(origin=Origin(block_id="seq", workspace="model"), layers=first)
    ] + value.model.layers[3:]
    code, spans = emit_program(value)
    ast.parse(code)
    assert "nn.Sequential(" in code
    for index, child in enumerate(first):
        mapped = [code.splitlines()[s.start_line - 1] for s in spans if s.origin == child.origin]
        assert any(f"self.layer_0[{index}](x)" in line for line in mapped)
        assert len(mapped) == 2


def test_quick_adam_and_untrusted_import():
    value = program()
    value.execution_mode = "quick"
    value.training.optimizer = "Adam"
    code, _ = emit_program(value)
    assert "default_execution_mode='quick'" in code
    assert "range(1, 1 + 1)" in code and "range(min(1024" in code and "range(min(256" in code
    assert "torch.optim.Adam" in code and "momentum=" not in code
    value.imports.append("os.system")
    with pytest.raises(ValueError, match="whitelist"):
        emit_program(value)


def runtime_module():
    spec = importlib.util.spec_from_file_location(
        "exported_runtime", SOURCE_ROOT / "runtime/easyai_runtime.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context(tmp_path, application=False):
    module = runtime_module()
    data = tmp_path / "数据 root"
    data.mkdir()
    output = tmp_path / "结果 output"
    if application:
        output.mkdir()
    return module, module.RunContext(data, output, 42, "quick", 0, application)


def test_runtime_atomic_artifacts_paths_and_no_overwrite(tmp_path):
    _, ctx = context(tmp_path)
    with ctx.atomic_target("outputs/中文.png") as target:
        target.write_bytes(b"real-file")
    record = ctx.artifact("outputs/中文.png", "figure", "figure", ["source"])
    assert record["sizeBytes"] == 9 and len(record["sha256"]) == 64
    assert json.loads((ctx.output_root / "artifacts.json").read_text())[0] == record
    for unsafe in ("../x", "/tmp/x", "outputs/../../x", "C:/x", "outputs\\x"):
        with pytest.raises(ValueError):
            with ctx.atomic_target(unsafe):
                pytest.fail("unsafe yield")
    with pytest.raises(FileExistsError):
        with ctx.atomic_target("outputs/中文.png"):
            pytest.fail("overwrite yield")
    (ctx.output_root / "outputs/link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        with ctx.atomic_target("outputs/link/outside"):
            pytest.fail("symlink yield")
    with pytest.raises(RuntimeError):
        with ctx.atomic_target("outputs/partial.png") as target:
            target.write_bytes(b"partial")
            raise RuntimeError("interrupted")
    assert not (ctx.output_root / "outputs/partial.png").exists()


def test_runtime_real_metrics_csv_and_application_single_writer(tmp_path):
    _, ctx = context(tmp_path)
    metrics = dict(
        epoch=1,
        train_loss=0.25,
        test_accuracy=0.973,
        train_samples=3,
        test_samples=2,
        elapsed_seconds=0.1,
    )
    ctx.emit("epoch_completed", "training", metrics)
    assert ".973" in (ctx.output_root / "metrics/epochs.csv").read_text()
    with pytest.raises(ValueError):
        ctx.emit("epoch_completed", "training", metrics)
    metrics = copy.copy(metrics)
    metrics.update(epoch=2, train_loss=float("nan"))
    with pytest.raises(ValueError):
        ctx.emit("epoch_completed", "training", metrics)
    separate = tmp_path / "other"
    separate.mkdir()
    _, managed = context(separate, True)
    managed.emit("runtime_started", "training", {})
    assert list(managed.output_root.iterdir()) == []


def test_runtime_figure_paths_and_cancel_match_run_id(tmp_path):
    module, ctx = context(tmp_path)
    first = ctx.figure_path("../../raw-id", "epoch_end", 1, "outputs/loss.png")
    second = ctx.figure_path("other", "epoch_end", 1, "outputs/loss.png")
    assert first != second and ".." not in first and "__epoch-0001.png" in first
    request = ctx.output_root / "cancel.request.json"
    request.write_text(json.dumps({"runId": "other"}))
    ctx.check_cancelled()
    request.write_text(json.dumps({"runId": ctx.run_id}))
    with pytest.raises(module.PipelineCancelled):
        ctx.check_cancelled()


def test_entry_structured_name_error_and_nonzero_exit(tmp_path):
    for name in ("entry.py", "easyai_runtime.py"):
        (tmp_path / name).write_bytes((SOURCE_ROOT / "runtime" / name).read_bytes())
    (tmp_path / "train.py").write_text("missing_variable\n")
    result = subprocess.run(
        [sys.executable, str(tmp_path / "entry.py")], capture_output=True, text=True, check=False
    )
    assert result.returncode == 1 and "Traceback" in result.stderr
    payload = json.loads(result.stdout.removeprefix("@@EASYAI_EVENT@@"))
    assert payload["type"] == "runtime_error"
    assert payload["payload"]["variableName"] == "missing_variable"
    assert payload["payload"]["line"] == 1


def test_runtime_standalone_existing_directory_is_not_overwritten(tmp_path):
    module, ctx = context(tmp_path)
    sentinel = ctx.output_root / "sentinel"
    sentinel.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        module.RunContext(ctx.data_root, ctx.output_root, 42, "full", 0)
    assert sentinel.read_bytes() == b"keep"


def test_runtime_cli_config_mutual_exclusion_and_mode_check(tmp_path, monkeypatch):
    module, ctx = context(tmp_path)
    config = tmp_path / "run-config.json"
    config.write_text(json.dumps({"configVersion": 1, "executionMode": "full"}))
    monkeypatch.setattr(sys, "argv", ["train.py", "--config", str(config), "--seed", "1"])
    with pytest.raises(SystemExit):
        module.RunContext.from_cli()
    monkeypatch.setattr(sys, "argv", ["train.py", "--config", str(config)])
    with pytest.raises(ValueError, match="execution mode"):
        module.RunContext.from_cli(default_execution_mode="quick")


def test_runtime_failure_persisted_before_close_without_duplicate_entry(tmp_path):
    _, ctx = context(tmp_path)
    failure = NameError("name 'missing' is not defined", name="missing")
    ctx.report_failure(failure, "training")
    ctx.close()
    records = (ctx.output_root / "logs/events.jsonl").read_text().splitlines()
    assert len(records) == 1
    assert json.loads(records[0])["payload"]["variableName"] == "missing"
    assert failure._easyai_event_reported
