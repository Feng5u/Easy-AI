"""Pure compiler API, frozen examples and standalone bundle acceptance."""

import ast
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.compiler.bundle import export_bundle
from easyai.compiler.pipeline import compile_project
from easyai.compiler.source_map import locate_line
from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import Origin, ProjectDocument, SourceSpan

GOLDEN = Path(__file__).parent / "fixtures/golden"


def project(name="mnist-figures"):
    return ProjectDocument.model_validate_json(
        (SOURCE_ROOT / f"packages/contracts/fixtures/{name}.json").read_bytes()
    )


def test_real_blockly_example_matches_frozen_code_ir_and_map():
    compiled = compile_project(project())
    assert compiled.result.runnable and compiled.program is not None
    assert compiled.result.code.encode("utf-8") == (GOLDEN / "mnist.py.txt").read_bytes()
    assert compiled.program.model_dump(mode="json", by_alias=True) == json.loads(
        (GOLDEN / "mnist-program.json").read_text()
    )
    assert [
        span.model_dump(mode="json", by_alias=True) for span in compiled.result.source_map
    ] == json.loads((GOLDEN / "mnist-source-map.json").read_text())
    example = ProjectDocument.model_validate_json(
        (SOURCE_ROOT / "examples/mnist-cnn/project.easyai.json").read_bytes()
    )
    assert compile_project(example) == compiled


def test_ui_changes_leave_code_map_and_hash_unchanged():
    value = project()
    first = compile_project(value).result
    value.revision += 1
    for workspace in (value.workspaces.data, value.workspaces.model, value.workspaces.training):
        for block in workspace.blocks.blocks:
            block.update(x=999, y=-500)
    second = compile_project(value).result
    assert first.code == second.code and first.source_map == second.source_map
    assert first.program_hash == second.program_hash and first.code_hash == second.code_hash
    assert first.revision != second.revision


def test_epoch_and_conv_edits_change_actual_code_without_model_rewrite():
    value = project("mnist")
    initial = compile_project(value).result
    value.workspaces.training.blocks.blocks[0]["fields"]["EPOCHS"] = 3
    changed = compile_project(value).result
    assert changed.runnable and changed.program_hash != initial.program_hash

    def model_ast(code):
        return ast.dump(
            next(node for node in ast.parse(code).body if isinstance(node, ast.ClassDef))
        )

    assert model_ast(initial.code) == model_ast(changed.code)
    assert "range(1, 3 + 1)" in changed.code
    # Padding and kernel change together preserves shape, exposing real parameters.
    conv = value.workspaces.model.blocks.blocks[0]["inputs"]["body"]["block"]
    conv["fields"].update(KERNEL_SIZE=5, PADDING=2)
    edited = compile_project(value).result
    assert edited.runnable and "nn.Conv2d(1, 16, 5, padding=2)" in edited.code
    assert model_ast(initial.code) != model_ast(edited.code)


def test_compile_api_is_authenticated_and_preserves_request_identity():
    client = TestClient(create_app("test-token"))
    value = project()
    path = f"/api/v1/projects/{value.project_id}/compile"
    body = {"project": value.model_dump(by_alias=True), "requestId": 7}
    assert client.post(path, json=body).status_code == 401
    headers = {"Authorization": "Bearer test-token"}
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["requestId"] == 7 and response.json()["runnable"]
    assert (
        client.post("/api/v1/projects/wrong/compile", json=body, headers=headers).status_code == 422
    )
    body["requestId"] = -1
    assert client.post(path, json=body, headers=headers).status_code == 422
    blank = project("blank")
    response = client.post(
        f"/api/v1/projects/{blank.project_id}/compile",
        json={"project": blank.model_dump(by_alias=True), "requestId": 8},
        headers=headers,
    )
    assert response.status_code == 200 and not response.json()["runnable"]
    assert response.json()["code"] is None


def test_line_mapping_prefers_narrowest_semantic_then_container():
    root = Origin(block_id="root", workspace="model")
    child = Origin(block_id="child", workspace="model")
    spans = [
        SourceSpan(start_line=1, end_line=10, origin=root, kind="scaffold"),
        SourceSpan(start_line=3, end_line=7, origin=root, kind="semantic"),
        SourceSpan(start_line=4, end_line=4, origin=child, kind="semantic"),
    ]
    assert locate_line(spans, 4).origin == child
    assert locate_line(spans, 5).origin == root
    assert locate_line(spans, 1).kind == "scaffold"
    assert locate_line(spans, 11) is None


def test_bundle_complete_deterministic_and_refuses_existing_targets(tmp_path):
    compiled = compile_project(project())
    first, second = tmp_path / "first", tmp_path / "second"
    assert export_bundle(compiled, first) == export_bundle(compiled, second)
    manifest = json.loads((first / "bundle.json").read_text())
    assert set(manifest["files"]) == {
        "code/train.py",
        "code/source-map.json",
        "code/entry.py",
        "code/easyai_runtime.py",
        "code/supervisor.py",
        "code/portable_journal.py",
        "code/managed.py",
        "code/dataset_inputs.py",
        "program.ir.json",
        "ENVIRONMENT.md",
        "README.md",
    }
    for name, digest in manifest["files"].items():
        content = (first / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
        assert content == (second / name).read_bytes()
        if name.endswith(".py"):
            tree = ast.parse(content)
            assert not any(
                isinstance(node, ast.ImportFrom) and (node.module or "").startswith("easyai.")
                for node in ast.walk(tree)
            )
    expected = hashlib.sha256(
        json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert expected == manifest["bundleHash"]
    with pytest.raises(FileExistsError):
        export_bundle(compiled, first)
    link = tmp_path / "link"
    link.symlink_to(first, target_is_directory=True)
    with pytest.raises(ValueError, match="OUTPUT_PATH_FORBIDDEN"):
        export_bundle(compiled, link)
    with pytest.raises(ValueError, match="BUNDLE_NOT_RUNNABLE"):
        export_bundle(compile_project(project("blank")), tmp_path / "empty")
    assert not (tmp_path / "empty").exists()


@pytest.mark.parametrize("name", ["started", "str", "super", "train_loss", "fig", "error"])
def test_model_name_collisions_are_located_errors(name):
    value = project()
    value.workspaces.model.blocks.blocks[0]["fields"]["NAME"] = name
    result = compile_project(value).result
    assert not result.runnable
    assert any(item.code == "NAME_INVALID" and item.field == "NAME" for item in result.diagnostics)


def test_model_scope_reserved_names_cover_all_generated_bindings():
    from easyai.domain.symbols import RESERVED

    for fixture in ("mnist-figures", "mnist-sequential"):
        tree = ast.parse(compile_project(project(fixture)).result.code)
        bindings = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        }
        assert {name for name in bindings if not name.startswith("_")} <= RESERVED


def test_logical_path_is_canonical_and_line_uses_axes_plot(tmp_path):
    from easyai.security.paths import artifact_relative_path
    from test_emission import context

    _, runtime = context(tmp_path)
    assert artifact_relative_path("plots/loss.png") == "outputs/plots/loss.png"
    assert runtime.figure_path("f", "before", logical="plots/loss.png").startswith("outputs/plots/")
    assert runtime.figure_path("f", "before", logical="plots/loss.png") == runtime.figure_path(
        "f", "before", logical=artifact_relative_path("plots/loss.png")
    )
    code = compile_project(project()).result.code
    assert "ax.plot(epoch_history" in code and "ax.line(" not in code


def test_logical_path_length_limit_applies_after_canonicalization(tmp_path):
    from easyai.security.paths import artifact_relative_path
    from test_emission import context

    _, runtime = context(tmp_path)
    allowed = "folder/" * 5 + "x" * 209 + ".png"  # 248 raw / 256 canonical
    assert len(allowed) == 248
    canonical = artifact_relative_path(allowed)
    assert len(canonical) == 256
    assert runtime.figure_path("f", "before", logical=allowed) == runtime.figure_path(
        "f", "before", logical=canonical
    )
    for rejected in ("folder/" + "x" * 238 + ".png", "x" * 252 + ".png"):
        with pytest.raises(ValueError, match="OUTPUT_PATH_FORBIDDEN"):
            artifact_relative_path(rejected)
        with pytest.raises(ValueError, match="Invalid logical figure path"):
            runtime.figure_path("f", "before", logical=rejected)


@pytest.mark.parametrize("fixture", ["mnist-figures", "mnist-sequential"])
def test_all_active_semantic_blocks_have_actual_source_spans(fixture):
    from easyai.compiler.decode import decode

    value = project(fixture)
    roots, diagnostics = decode(value)
    assert not diagnostics
    expected = set()

    def visit(node):
        expected.add(node.origin.block_id)
        for children in node.inputs.values():
            for child in children:
                visit(child)

    for node in roots:
        visit(node)
    result = compile_project(value).result
    assert result.runnable
    actual = {span.origin.block_id for span in result.source_map if span.kind == "semantic"}
    assert expected <= actual, expected - actual


@pytest.mark.parametrize("stem", ["x" * 220, "中" * 73 + "a"])
def test_final_figure_component_boundary_really_writes_files(tmp_path, stem):
    from easyai.security.paths import artifact_relative_path
    from test_emission import context

    _, runtime = context(tmp_path)
    logical = artifact_relative_path("folder/" + stem + ".png")
    for phase, epoch in (("before", None), ("epoch_end", 10000)):
        physical = runtime.figure_path("f", phase, epoch, logical)
        with runtime.atomic_target(physical) as output:
            output.write_bytes(b"actual-boundary-file")
        assert (runtime.output_root / physical).read_bytes() == b"actual-boundary-file"
        assert len(Path(physical).name.encode("utf-8")) <= 255
    assert len(Path(physical).name.encode("utf-8")) == 255


@pytest.mark.parametrize(
    "logical",
    ["folder/" + "x" * 237 + ".png", "x" * 221 + ".png", "中" * 74 + ".png", "中" * 86 + "/a.png"],
)
def test_final_utf8_figure_budget_rejects_before_filesystem_write(tmp_path, logical):
    from easyai.security.paths import artifact_relative_path
    from test_emission import context

    _, runtime = context(tmp_path)
    with pytest.raises(ValueError):
        artifact_relative_path(logical)
    with pytest.raises(ValueError):
        runtime.figure_path("f", "epoch_end", 10000, logical)
    assert not (runtime.output_root / "outputs").exists()


@pytest.mark.parametrize("show", [True, False])
def test_axis_explicit_toggle_has_its_own_effectful_semantic_lines(show):
    from test_lowering import nodes

    value = project().model_dump(by_alias=True)
    for node in nodes(value):
        if node["type"] == "viz.axis":
            node["fields"]["SHOW_TICKS"] = show
    result = compile_project(ProjectDocument.model_validate(value)).result
    assert result.runnable
    lines = result.code.splitlines()
    for axis_id in ("before-0-axis", "body-0-axis", "body-1-axis", "after-0-axis"):
        selected = [
            lines[span.start_line - 1]
            for span in result.source_map
            if span.origin.block_id == axis_id and span.kind == "semantic"
        ]
        assert selected
        assert any(
            "tick_params(" in text if show else "set_xticks([])" in text for text in selected
        )


def test_bundle_can_export_managed_core_from_frozen_resource_layout(tmp_path, monkeypatch):
    import shutil
    import easyai.compiler.bundle as bundle

    resources = tmp_path / "resources"
    resources.mkdir()
    for name in ("entry.py", "easyai_runtime.py", "supervisor.py", "portable_journal.py"):
        shutil.copyfile(SOURCE_ROOT / "runtime" / name, resources / name)
    expected = (SOURCE_ROOT / "services/backend/src/easyai/runtime/managed.py").read_bytes()
    (resources / "managed.py").write_bytes(expected)
    (resources / "dataset_inputs.py").write_bytes(
        (SOURCE_ROOT / "services/backend/src/easyai/runtime/dataset_inputs.py").read_bytes()
    )
    monkeypatch.setattr(bundle, "__file__", str(tmp_path / "frozen/easyai/compiler/bundle.py"))
    monkeypatch.setattr(bundle, "RUNTIME_ROOT", resources)
    bundle.export_bundle(compile_project(project()), tmp_path / "exported")
    assert (tmp_path / "exported/code/managed.py").read_bytes() == expected


def test_explicit_cpu_never_silently_selects_available_accelerator():
    from types import SimpleNamespace

    tree = ast.parse(compile_project(project()).result.code)
    selection = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and ast.unparse(node.test) == "context.device != 'auto'"
    )

    def unexpected():
        pytest.fail("Explicit CPU must not auto-probe/select an accelerator")

    scope = {
        "context": SimpleNamespace(device="cpu"),
        "torch": SimpleNamespace(
            device=lambda name: SimpleNamespace(type=name),
            cuda=SimpleNamespace(is_available=unexpected),
            backends=SimpleNamespace(mps=SimpleNamespace(is_available=unexpected)),
        ),
    }
    exec(compile(ast.Module(body=[selection], type_ignores=[]), "device-fixture", "exec"), scope)
    assert scope["device"].type == "cpu"
    scope["context"].device = "cuda"
    scope["torch"].cuda.is_available = lambda: False
    with pytest.raises(RuntimeError, match="Configured CUDA"):
        exec(
            compile(ast.Module(body=[selection], type_ignores=[]), "device-fixture", "exec"), scope
        )
