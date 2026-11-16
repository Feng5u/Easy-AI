"""Compile actual Blockly fixtures without training or importing torch."""

import ast
import copy
import json

import pytest

from easyai.compiler.pipeline import compile_project
from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import ProjectDocument


def fixture(name="mnist-direct-plots"):
    return json.loads((SOURCE_ROOT / f"packages/contracts/fixtures/{name}.json").read_bytes())


def loop(document):
    return document["workspaces"]["training"]["blocks"]["blocks"][0]


def compile_document(document):
    return compile_project(ProjectDocument.model_validate(document))


def test_direct_charts_own_figures_for_all_phases_and_map_real_block_ids():
    compiled = compile_document(fixture())
    assert compiled.result.runnable, compiled.result.diagnostics
    training = compiled.program.training
    assert [len(training.before), len(training.body), len(training.after)] == [1, 1, 1]
    assert [f.layout for f in [training.before[0], training.body[0], training.after[0]]] == [
        [1, 1],
        [1, 2],
        [1, 1],
    ]
    assert [f.size for f in [training.before[0], training.body[0], training.after[0]]] == [
        "medium",
        "medium",
        "large",
    ]
    assert [p.origin.block_id for p in training.body[0].panels] == ["body-0-panel", "body-1-panel"]
    assert training.body[0].id == "auto:training:body"
    assert all(f.save is None for f in training.before + training.body + training.after)
    ast.parse(compiled.result.code)
    assert compiled.result.code.count("plt.close(fig)") == 3
    assert compiled.result.code.count("format='png'") == 3
    assert "'epoch_end', epoch" in compiled.result.code
    assert "plt.show" not in compiled.result.code
    assert {span.origin.block_id for span in compiled.result.source_map} >= {
        "before-0-panel",
        "body-0-panel",
        "body-1-source",
        "after-0-panel",
    }


def test_manual_layout_and_size_are_authoritative_and_small_layout_is_rejected():
    document = fixture()
    loop(document)["fields"].update(BODY_LAYOUT="2,2", BODY_SIZE="small")
    compiled = compile_document(document)
    assert compiled.result.runnable
    assert compiled.program.training.body[0].layout == [2, 2]
    assert compiled.program.training.body[0].size == "small"
    loop(document)["fields"]["BODY_LAYOUT"] = "1,1"
    rejected = compile_document(document)
    assert not rejected.result.runnable
    assert any(d.code == "FIGURE_LAYOUT_INVALID" for d in rejected.result.diagnostics)


def test_disabled_and_reordered_direct_charts_keep_identity_and_automatic_capacity():
    document = fixture()
    first = loop(document)["inputs"]["body"]["block"]
    second = first.pop("next")["block"]
    second["next"] = {"block": first}
    loop(document)["inputs"]["body"]["block"] = second
    compiled = compile_document(document)
    assert compiled.result.runnable
    assert [p.origin.block_id for p in compiled.program.training.body[0].panels] == [
        "body-1-panel",
        "body-0-panel",
    ]
    second["disabledReasons"] = ["MANUALLY_DISABLED"]
    compiled = compile_document(document)
    assert compiled.result.runnable
    assert compiled.program.training.body[0].layout == [1, 1]
    assert compiled.program.training.body[0].panels[0].origin.block_id == "body-0-panel"
    first["disabledReasons"] = ["MANUALLY_DISABLED"]
    compiled = compile_document(document)
    assert compiled.result.runnable and compiled.program.training.body == []


@pytest.mark.parametrize("error", ["missing", "phase", "layout"])
def test_direct_chart_validation_is_not_bypassed(error):
    document = fixture()
    panel = loop(document)["inputs"]["before"]["block"]
    if error == "missing":
        del panel["inputs"]["data"]
        code = "VIZ_SOURCE_MISSING"
    elif error == "phase":
        panel["inputs"]["data"]["block"]["fields"]["SOURCE"] = "predictions"
        code = "VIZ_PHASE_INVALID"
    else:
        panel["fields"].update(COUNT=10, ROWS=1, COLS=5)
        code = "FIGURE_LAYOUT_INVALID"
    compiled = compile_document(document)
    assert not compiled.result.runnable
    assert any(d.code == code for d in compiled.result.diagnostics)


def test_legacy_figures_and_paths_remain_separate_when_mixed_with_direct_charts():
    document = fixture()
    legacy = loop(fixture("mnist-figures"))["inputs"]["body"]["block"]
    # Use a different phase's legacy nodes to keep the real serialized IDs unique.
    direct = loop(document)["inputs"].pop("after")["block"]
    legacy["next"] = {"block": direct}
    loop(document)["inputs"]["body"]["block"] = legacy
    compiled = compile_document(document)
    assert compiled.result.runnable, compiled.result.diagnostics
    old, automatic = compiled.program.training.body
    assert old.id == "body-figure" and old.layout == [1, 2]
    assert old.save.relative_path == "outputs/preview.png"
    assert automatic.id == "auto:training:body" and automatic.layout == [1, 1]
    assert automatic.panels[0].origin.block_id == "after-0-panel"
    assert automatic.save is None


def test_old_projects_default_settings_do_not_change_generated_code():
    document = fixture("mnist-figures")
    old = compile_document(document)
    for phase in ["BEFORE", "BODY", "AFTER"]:
        loop(document)["fields"][f"{phase}_LAYOUT"] = "auto"
        loop(document)["fields"][f"{phase}_SIZE"] = "auto"
    new = compile_document(document)
    assert old.result.runnable and new.result.runnable
    assert old.result.code == new.result.code
    assert old.result.source_map == new.result.source_map
    assert old.result.program_hash == new.result.program_hash


def test_automatic_rows_expand_and_more_than_ten_charts_is_rejected():
    document = fixture()
    original = loop(document)["inputs"]["body"]["block"]
    original.pop("next")
    tail = original
    for index in range(1, 11):
        panel = copy.deepcopy(original)
        panel.pop("next", None)
        panel["id"] = f"extra-panel-{index}"
        panel["inputs"].pop("style")
        panel["inputs"]["data"]["block"]["id"] = f"extra-source-{index}"
        tail["next"] = {"block": panel}
        tail = panel
        compiled = compile_document(document)
        if index < 10:
            assert compiled.result.runnable, compiled.result.diagnostics
            assert compiled.program.training.body[0].layout == [(index + 2) // 2, 2]
        else:
            assert not compiled.result.runnable
            assert any(d.code == "FIGURE_LAYOUT_INVALID" for d in compiled.result.diagnostics)
