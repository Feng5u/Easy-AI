import copy
import json

import pytest

from easyai.compiler.pipeline import prepare, program_hash
from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import ProjectDocument
from easyai.domain.program import Conv2dSpec, LinearSpec

FIXTURE = SOURCE_ROOT / "packages/contracts/fixtures/mnist.json"


def value() -> dict:
    return json.loads(FIXTURE.read_bytes())


def nodes(project: dict):
    def walk(node):
        yield node
        for connection in node.get("inputs", {}).values():
            for child in connection.values():
                yield from walk(child)
        if "next" in node:
            yield from walk(node["next"]["block"])

    for workspace in project["workspaces"].values():
        for root in workspace["blocks"]["blocks"]:
            yield from walk(root)


def test_typed_ir_and_mnist_shape_trace() -> None:
    program, diagnostics = prepare(ProjectDocument.model_validate(value()))
    assert not diagnostics and program is not None
    assert isinstance(program.model.layers[0], Conv2dSpec)
    assert isinstance(program.model.layers[-1], LinearSpec)
    assert [step.output_shape for step in program.shape_trace] == [
        [16, 28, 28],
        [16, 28, 28],
        [16, 14, 14],
        [32, 14, 14],
        [32, 14, 14],
        [32, 7, 7],
        [1568],
        [128],
        [128],
        [10],
    ]
    assert len(program.transforms) == 1 and len(program.datasets) == len(program.dataloaders) == 2
    assert len(program.imports) == len(set(program.imports))


def test_position_revision_root_order_do_not_change_semantics() -> None:
    first, _ = prepare(ProjectDocument.model_validate(value()))
    changed = value()
    changed["revision"] = 10
    changed["ui"]["activeTab"] = "model"
    changed["workspaces"]["data"]["blocks"]["blocks"].reverse()
    for node in nodes(changed):
        if "x" in node:
            node["x"], node["y"] = 500, -200
    second, _ = prepare(ProjectDocument.model_validate(changed))
    assert first == second and program_hash(first) == program_hash(second)


def test_linear_mismatch_is_located_without_repair() -> None:
    changed = value()
    block = next(n for n in nodes(changed) if n["type"] == "model.linear")
    block["fields"]["IN_FEATURES"] = 1500
    program, problems = prepare(ProjectDocument.model_validate(changed))
    assert program is None and problems[0].code == "SHAPE_MISMATCH"
    assert problems[0].origin.block_id == block["id"]
    assert block["fields"]["IN_FEATURES"] == 1500


def test_cifar_metadata_and_scalar_normalize_use_three_channels() -> None:
    changed = value()
    for node in nodes(changed):
        if node["type"] == "data.dataset_builtin":
            node["fields"]["DATASET_NAME"] = "CIFAR10"
    conv = next(n for n in nodes(changed) if n["type"] == "model.conv2d")
    conv["fields"]["IN_CHANNELS"] = 3
    linear = next(n for n in nodes(changed) if n["type"] == "model.linear")
    linear["fields"]["IN_FEATURES"] = 2048
    program, diagnostics = prepare(ProjectDocument.model_validate(changed))
    assert not diagnostics and program is not None
    assert program.datasets[0].channels == 3
    assert program.transforms[0].steps[1].mean == [0.1307] * 3
    assert program.shape_trace[6].output_shape == [2048]


@pytest.mark.parametrize("types", [["data.normalize", "data.to_tensor"], ["data.normalize"]])
def test_transform_order_is_semantic(types: list[str]) -> None:
    changed = value()
    compose = changed["workspaces"]["data"]["blocks"]["blocks"][0]
    tensor = copy.deepcopy(compose["inputs"]["steps"]["block"])
    normalize = tensor.pop("next")["block"]
    children = {"data.to_tensor": tensor, "data.normalize": normalize}
    chain = [children[t] for t in types]
    if len(chain) == 2:
        chain[0]["next"] = {"block": chain[1]}
    compose["inputs"]["steps"]["block"] = chain[0]
    program, diagnostics = prepare(ProjectDocument.model_validate(changed))
    assert program is None and diagnostics[0].code == "TRANSFORM_ORDER_INVALID"


def test_unused_unregistered_definitions_are_not_emitted() -> None:
    changed = value()
    draft = copy.deepcopy(changed["workspaces"]["model"]["blocks"]["blocks"][0])
    draft["id"] = "draft-model"
    draft["fields"]["NAME"] = "DraftModel"
    draft["extraState"]["easyai"]["registered"] = False
    for node in list(nodes({"workspaces": {"model": {"blocks": {"blocks": [draft]}}}})):
        if node is not draft:
            node["id"] = "draft-" + node["id"]
    changed["workspaces"]["model"]["blocks"]["blocks"].append(draft)
    program, diagnostics = prepare(ProjectDocument.model_validate(changed))
    assert program is not None and not diagnostics
    assert all(item.id != "draft-model" for item in program.symbols)


def test_real_blockly_sequential_and_dropout_are_typed() -> None:
    from easyai.domain.program import SequentialSpec, DropoutSpec

    fixture = SOURCE_ROOT / "packages/contracts/fixtures/mnist-sequential.json"
    program, diagnostics = prepare(ProjectDocument.model_validate_json(fixture.read_bytes()))
    assert not diagnostics and program is not None
    assert isinstance(program.model.layers[0], SequentialSpec)
    assert len(program.model.layers[0].layers) == 6
    assert any(isinstance(layer, DropoutSpec) for layer in program.model.layers)
    assert program.training.optimizer == "Adam"
    assert program.shape_trace[-1].output_shape == [10]


def test_figure_phase_and_paths_are_checked_before_emit() -> None:
    changed = json.loads(
        (SOURCE_ROOT / "packages/contracts/fixtures/mnist-figures.json").read_bytes()
    )
    source = next(n for n in nodes(changed) if n["id"] == "before-0-source")
    source["fields"]["SOURCE"] = "predictions"
    program, diagnostics = prepare(ProjectDocument.model_validate(changed))
    assert program is None and diagnostics[0].code == "VIZ_PHASE_INVALID"
    assert diagnostics[0].origin.block_id == source["id"]


@pytest.mark.parametrize(
    "path",
    [
        "../x.png",
        "/tmp/x.png",
        "C:\\temp\\x.png",
        "\\\\host\\share\\x.png",
        "nested/../../x.png",
        "image.svg",
        "file:///tmp/x.png",
    ],
)
def test_figure_save_rejects_cross_platform_escape(path: str) -> None:
    changed = json.loads(
        (SOURCE_ROOT / "packages/contracts/fixtures/mnist-figures.json").read_bytes()
    )
    save = next(n for n in nodes(changed) if n["id"] == "body-save")
    save["fields"]["PATH"] = path
    program, diagnostics = prepare(ProjectDocument.model_validate(changed))
    assert program is None and diagnostics[0].code == "OUTPUT_PATH_FORBIDDEN"
    assert diagnostics[0].origin.block_id == "body-save"
