"""Synthetic paths and constructor traps only; no torch or .pt deserialization."""

import ast
import importlib
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

import pytest

from easyai.runtime import dataset_inputs as inputs
from easyai.services.local_workspace import preflight_data
from test_run_service import prepare


class Stub:
    insert_legacy = False

    def __init__(self, **options):
        self.root = options["root"]
        if self.insert_legacy:
            path = Path(self.processed_folder)
            path.mkdir(parents=True, exist_ok=True)
            (path / "training.pt").write_bytes(b"never deserialize")
        if self._check_legacy_exist():
            pytest.fail("Legacy selection must never occur")
        self.options = options

    def _check_legacy_exist(self):
        return True

    def _load_legacy_data(self):
        pytest.fail("Never read legacy data")


class MNIST(Stub):
    pass


class FashionMNIST(Stub):
    pass


@pytest.mark.parametrize("name", ["MNIST", "FashionMNIST"])
def test_legal_model_name_cannot_shadow_dataset_constructor(tmp_path, monkeypatch, name):
    from easyai.compiler.pipeline import compile_project
    from test_compilation import project

    value = project("mnist")
    value.workspaces.model.blocks.blocks[0]["fields"]["NAME"] = "construct_dataset"
    for block in value.workspaces.data.blocks.blocks:
        if block["type"] == "data.dataset_builtin":
            block["fields"]["DATASET_NAME"] = name
    result = compile_project(value).result
    assert result.runnable
    tree = ast.parse(result.code)
    model = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    assert model.name == "construct_dataset"
    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "dataset_inputs"
    )
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and any(
            isinstance(arg, ast.Attribute)
            and isinstance(arg.value, ast.Name)
            and arg.value.id == "datasets"
            for arg in node.value.args
        )
    ]
    assert len(assignments) == 2
    namespace = {
        "nn": SimpleNamespace(Module=object),
        "datasets": SimpleNamespace(**{name: globals()[name]}),
        "context": SimpleNamespace(data_root=tmp_path),
    }
    for assignment in assignments:
        transform = next(
            item.value for item in assignment.value.keywords if item.arg == "transform"
        )
        assert isinstance(transform, ast.Name)
        namespace[transform.id] = "stub-transform"
    monkeypatch.setitem(sys.modules, "dataset_inputs", inputs)
    # Execute only the actual import, class definition and two constructor lines.
    # No generated main(), model instantiation, torch, tensors or data contents.
    selected = ast.Module(body=[helper, model, *assignments], type_ignores=[])
    exec(compile(selected, "<constructor-scope>", "exec"), namespace)
    for assignment, train in zip(assignments, (True, False), strict=True):
        target = assignment.targets[0]
        assert isinstance(target, ast.Name)
        selected_data = namespace[target.id]
        assert isinstance(selected_data, globals()[name])
        assert selected_data.options == dict(
            root=str(tmp_path), train=train, transform="stub-transform", download=False
        )


def raw_data(root, name):
    raw = root / name / "raw"
    raw.mkdir(parents=True)
    for split in ("train", "t10k"):
        (raw / f"{split}-images-idx3-ubyte").write_bytes(
            struct.pack(">IIII", 2051, 1, 28, 28) + bytes(784)
        )
        (raw / f"{split}-labels-idx1-ubyte").write_bytes(struct.pack(">II", 2049, 1) + b"\x00")


@pytest.mark.parametrize("name", ["MNIST", "FashionMNIST"])
@pytest.mark.parametrize("file", ["training.pt", "test.pt"])
def test_raw_preflight_rejects_any_legacy_file_without_touching_it(tmp_path, name, file):
    raw_data(tmp_path, name)
    preflight_data(tmp_path, {name})
    processed = tmp_path / name / "processed"
    processed.mkdir()
    (processed / file).write_bytes(b"untrusted harmless placeholder")
    with pytest.raises(ValueError, match="DATASET_LEGACY_CACHE_FORBIDDEN"):
        preflight_data(tmp_path, {name})
    with pytest.raises(ValueError, match="DATASET_LEGACY_CACHE_FORBIDDEN"):
        inputs.construct_dataset(globals()[name], root=str(tmp_path), train=True, transform=None)
    assert (processed / file).read_bytes() == b"untrusted harmless placeholder"


@pytest.mark.parametrize("name", ["MNIST", "FashionMNIST"])
@pytest.mark.parametrize("target", ["processed", "training.pt", "test.pt"])
def test_processed_symlinks_and_dangling_files_fail_closed(tmp_path, name, target):
    raw_data(tmp_path, name)
    processed = tmp_path / name / "processed"
    if target == "processed":
        path = processed
    else:
        processed.mkdir()
        path = processed / target
    try:
        path.symlink_to(tmp_path / "absent", target_is_directory=target == "processed")
    except OSError as error:
        pytest.skip(f"Host cannot create a symlink: {error.errno}")
    with pytest.raises(ValueError, match="DATA_PATH_FORBIDDEN|DATASET_LEGACY_CACHE_FORBIDDEN"):
        preflight_data(tmp_path, {name})
    assert path.is_symlink()


@pytest.mark.parametrize("base", [MNIST, FashionMNIST])
def test_official_adapter_inheritance_preserves_folders_arguments_and_spawn_type(
    tmp_path, base, monkeypatch
):
    result = inputs.construct_dataset(base, root=str(tmp_path), train=False, transform="fixture")
    assert isinstance(result, base)
    assert result.raw_folder == str(tmp_path / base.__name__ / "raw")
    assert result.processed_folder == str(tmp_path / base.__name__ / "processed")
    assert result.options == dict(
        root=str(tmp_path), train=False, transform="fixture", download=False
    )
    with pytest.raises(ValueError, match="DATASET_LEGACY_CACHE_FORBIDDEN"):
        result._load_legacy_data()
    cls = type(result)
    assert cls.__module__ == inputs.__name__ and "<locals>" not in cls.__qualname__
    delattr(inputs, cls.__name__)
    original = importlib.import_module
    monkeypatch.setattr(
        inputs.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(datasets=SimpleNamespace(**{base.__name__: base}))
            if name == "torchvision"
            else original(name)
        ),
    )
    rebuilt = getattr(inputs, cls.__name__)
    assert rebuilt.__name__ == cls.__name__ and rebuilt.__bases__ == (base,)


@pytest.mark.parametrize("base", [MNIST, FashionMNIST])
def test_cache_added_inside_constructor_cannot_switch_to_legacy(tmp_path, base, monkeypatch):
    monkeypatch.setattr(base, "insert_legacy", True)
    with pytest.raises(ValueError, match="DATASET_LEGACY_CACHE_FORBIDDEN"):
        inputs.construct_dataset(base, root=str(tmp_path), train=True, transform=None)


@pytest.mark.parametrize("name", ["MNIST", "FashionMNIST"])
def test_formal_start_rechecks_cache_added_after_preflight_and_does_not_spawn(
    owned, monkeypatch, name
):
    if name == "FashionMNIST":
        from easyai.compiler.pipeline import compile_project

        value = owned[2].model_copy(deep=True)
        for block in value.workspaces.data.blocks.blocks:
            if block["type"] == "data.dataset_builtin":
                block["fields"]["DATASET_NAME"] = name
        value = owned[0].save(value, value.revision)
        owned = (owned[0], owned[1], value, compile_project(value).result.program_hash, owned[4])
    run = prepare(owned)
    data = Path(run.config.data_root)
    processed = data / name / "processed"
    processed.mkdir(parents=True)
    (processed / "training.pt").write_bytes(b"not loaded")
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("No process allowed"))
    with pytest.raises(ValueError, match="DATASET_LEGACY_CACHE_FORBIDDEN"):
        owned[1].start(run.run_id)
    assert owned[1].get(run.run_id).status == "CREATED"


def test_old_direct_constructor_is_not_executable_or_exportable_but_code_is_preserved(tmp_path):
    from easyai.compiler.bundle import export_bundle
    from easyai.compiler.pipeline import compile_project
    from test_compilation import project

    compiled = compile_project(project())
    code = compiled.result.code.replace(
        "_easyai_construct_dataset(datasets.MNIST, ", "datasets.MNIST("
    )
    compiled.result.code = code
    with pytest.raises(ValueError, match="DATASET_INPUT_GUARD_REQUIRED"):
        export_bundle(compiled, tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists() and compiled.result.code == code


def test_old_created_snapshot_cannot_start_or_be_rewritten(owned, monkeypatch):
    import hashlib
    from easyai.compiler import bundle
    from easyai.compiler.pipeline import compile_project
    from easyai.services import run_service

    compiled = compile_project(owned[2])
    old = compiled.result.code.replace(
        "_easyai_construct_dataset(datasets.MNIST, ", "datasets.MNIST("
    )
    compiled.result.code = old
    compiled.result.code_hash = hashlib.sha256(old.encode()).hexdigest()
    # Build a prior-version fixture with internally consistent immutable hashes.
    # Restore every production gate before asking the current service to start it.
    with monkeypatch.context() as setup:
        setup.setattr(run_service, "compile_project", lambda project: compiled)
        setup.setattr(bundle, "require_guarded_code", lambda code: None)
        run = prepare(owned)
    path = Path(run.config.run_root) / "code/train.py"
    before = path.read_bytes()
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("No process allowed"))
    with pytest.raises(ValueError, match="DATASET_INPUT_GUARD_REQUIRED"):
        owned[1].start(run.run_id)
    assert path.read_bytes() == before and owned[1].get(run.run_id).status == "CREATED"
