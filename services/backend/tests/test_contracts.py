import copy
import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from easyai.compiler.decode import DecodeError, decode
from easyai.domain.catalog import HANDLER_IDS, SOURCE_ROOT, definitions
from easyai.domain.contracts import EpochMetrics, ProjectDocument
from easyai.domain.symbols import registry
from easyai.services.project_service import ProjectService, read_project

FIXTURES = SOURCE_ROOT / "packages/contracts/fixtures"


def example() -> dict:
    return json.loads((FIXTURES / "mnist.json").read_text())


def problems(value: dict) -> list[str]:
    roots, issues = decode(ProjectDocument.model_validate(value))
    _, refs = registry(roots)
    return [issue.code for issue in issues + refs]


def data_blocks(value: dict) -> list[dict]:
    return value["workspaces"]["data"]["blocks"]["blocks"]


def test_real_fixtures_and_catalog() -> None:
    catalog = definitions()
    assert len(catalog) == 21 and set(catalog) == HANDLER_IDS
    assert not problems(example())
    all_blocks = json.loads((FIXTURES / "all-blocks.json").read_text())["blocks"]["blocks"]
    assert {b["type"] for b in all_blocks} == set(catalog)
    assert next(b for b in all_blocks if b["type"] == "model.dropout")["disabledReasons"]
    assert not decode(ProjectDocument.model_validate_json((FIXTURES / "blank.json").read_bytes()))[
        0
    ]


def test_rename_delete_unregister_undo() -> None:
    value = example()
    block = data_blocks(value)[0]
    block["fields"]["NAME"] = "renamed_transform"
    assert not problems(value)
    original = data_blocks(value).pop(0)
    assert "REF_NOT_FOUND" in problems(value)
    data_blocks(value).insert(0, original)
    assert not problems(value)
    block["extraState"]["easyai"]["registered"] = False
    assert "REF_NOT_REGISTERED" in problems(value)


def test_names_roles_and_missing_reference() -> None:
    value = example()
    data_blocks(value)[1]["fields"]["NAME"] = "preprocess"
    assert "NAME_DUPLICATED" in problems(value)
    value = example()
    duplicate = copy.deepcopy(data_blocks(value)[1])
    duplicate["id"] = "second-train-dataset"
    duplicate["fields"]["NAME"] = "another_train_data"
    data_blocks(value).append(duplicate)
    assert "ROLE_DUPLICATED" in problems(value)
    value = example()
    train = value["workspaces"]["training"]["blocks"]["blocks"][0]
    train["fields"]["TRAIN_LOADER_REF"] = "test-loader"
    assert "ROLE_MISMATCH" in problems(value)
    value = example()
    data_blocks(value)[1]["fields"]["TRANSFORM_REF"] = "missing"
    assert "REF_NOT_FOUND" in problems(value)


@pytest.mark.parametrize("name", ["torch", "class", "123bad", "中文", "nn"])
def test_reserved_names(name: str) -> None:
    value = example()
    data_blocks(value)[0]["fields"]["NAME"] = name
    assert "NAME_INVALID" in problems(value)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "12"])
def test_illegal_numeric_fields(value: object) -> None:
    project = example()
    project["workspaces"]["training"]["blocks"]["blocks"][0]["fields"]["EPOCHS"] = value
    if isinstance(value, float) and not math.isfinite(value):
        with pytest.raises(ValidationError, match="Non-finite"):
            ProjectDocument.model_validate(project)
        valid = ProjectDocument.model_validate(example())
        valid.workspaces.training.blocks.blocks[0]["fields"]["EPOCHS"] = value
        assert "FIELD_INVALID" in [issue.code for issue in decode(valid)[1]]
    else:
        assert "FIELD_INVALID" in problems(project)


def test_decoder_next_and_disabled_from_real_serialization() -> None:
    value = example()
    roots, _ = decode(ProjectDocument.model_validate(value))
    assert [b.type_id for b in roots[0].inputs["steps"]] == ["data.to_tensor", "data.normalize"]
    disabled = json.loads((FIXTURES / "all-blocks.json").read_text())["blocks"]["blocks"]
    dropout = next(b for b in disabled if b["type"] == "model.dropout")
    value["workspaces"]["model"]["blocks"]["blocks"][0]["inputs"]["body"]["block"] = dropout
    roots, _ = decode(ProjectDocument.model_validate(value))
    assert roots[-2].inputs["body"] == []


def test_epoch_metrics_units_and_strictness() -> None:
    fields = dict(
        epoch=1,
        train_loss=0.1,
        test_accuracy=0.973,
        train_samples=8,
        test_samples=4,
        elapsed_seconds=0.3,
    )
    metrics = EpochMetrics(**fields)
    assert metrics.model_dump()["test_accuracy"] == 0.973
    for change in [
        {"test_accuracy": 97.3},
        {"train_loss": float("nan")},
        {"epoch": True},
        {"testAccuracy": 0.9},
    ]:
        with pytest.raises(ValidationError):
            EpochMetrics(**(fields | change))


def test_unknown_field_rejected() -> None:
    value = example()
    value["credential"] = "not-allowed"
    with pytest.raises(ValidationError):
        ProjectDocument.model_validate(value)
    value = example()
    data_blocks(value)[1]["fields"]["DOWNLOAD"] = True
    with pytest.raises(DecodeError, match="FIELD_UNKNOWN"):
        problems(value)


@pytest.mark.parametrize("change", [{"schemaVersion": 2}, {"blockLibraryVersion": "1.0.0"}])
def test_future_version_preserves_bytes(tmp_path: Path, change: dict) -> None:
    path = tmp_path / "project.easyai.json"
    payload = json.dumps(example() | change).encode()
    path.write_bytes(payload)
    opened = read_project(path)
    assert opened.read_only and opened.raw == payload
    service = ProjectService(tmp_path)
    try:
        with pytest.raises(ValueError, match="PROJECT_READ_ONLY"):
            service.save(ProjectDocument.model_validate(example()), 1)
        assert path.read_bytes() == payload
    finally:
        service.close()


def test_unknown_block_preserved(tmp_path: Path) -> None:
    value = example()
    data_blocks(value)[0]["type"] = "future.transform"
    path = tmp_path / "project.easyai.json"
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    assert read_project(path).read_only and read_project(path).raw == raw


def test_atomic_save_revision_lock_and_interruption(tmp_path: Path) -> None:
    path = tmp_path / "project.easyai.json"
    raw = (FIXTURES / "mnist.json").read_bytes()
    path.write_bytes(raw)
    first, second = ProjectService(tmp_path), ProjectService(tmp_path)
    doc = ProjectDocument.model_validate_json(raw)
    try:
        with pytest.raises(ValueError, match="PROJECT_READ_ONLY"):
            second.save(doc, 1)
        with patch(
            "easyai.services.project_service.os.replace",
            side_effect=OSError("simulated disk failure"),
        ):
            with pytest.raises(OSError):
                first.save(doc, 1)
        assert path.read_bytes() == raw
        saved = first.save(doc, 1)
        assert saved.revision == 2
        assert (tmp_path / ".easyai/backup/project.easyai.json.bak").read_bytes() == raw
        with pytest.raises(ValueError, match="PROJECT_REVISION_CONFLICT"):
            first.save(doc, 1)
    finally:
        second.close()
        first.close()


def test_symlink_metadata_rejected(tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    other.mkdir()
    (tmp_path / ".easyai").symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match="PROJECT_PATH_FORBIDDEN"):
        ProjectService(tmp_path)


def test_real_shadow_fixture() -> None:
    value = example()
    value["workspaces"]["model"] = json.loads((FIXTURES / "shadow.json").read_text())
    roots, _ = decode(ProjectDocument.model_validate(value))
    model = next(root for root in roots if root.type_id == "model.define")
    assert model.inputs["body"][0].origin.block_id == "shadow-layer"


def test_unknown_blocks_in_disabled_subtree_are_preserved(tmp_path: Path) -> None:
    value = example()
    top = data_blocks(value)[0]
    top["disabledReasons"] = ["MANUALLY_DISABLED"]
    top["inputs"]["steps"]["block"]["type"] = "future.block"
    path = tmp_path / "project.easyai.json"
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    assert read_project(path).read_only and read_project(path).raw == raw


def test_structure_and_disabled_blocks_count_limits() -> None:
    value = example()
    data_blocks(value)[0]["template"] = "malicious.py"
    with pytest.raises(DecodeError, match="BLOCK_STRUCTURE_INVALID"):
        problems(value)
    value = example()
    node = data_blocks(value)[1]
    for index in range(501):
        clone = copy.deepcopy(node)
        clone["id"] = f"disabled-{index}"
        clone["disabledReasons"] = ["MANUALLY_DISABLED"]
        data_blocks(value).append(clone)
    with pytest.raises(DecodeError, match="BLOCK_COUNT_LIMIT"):
        problems(value)


def test_manifest_schema_and_handler_targets() -> None:
    from jsonschema import Draft202012Validator
    from easyai.domain.catalog import load_catalog

    schema = json.loads((SOURCE_ROOT / "packages/block-library/schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    catalog = load_catalog()
    validator.validate(catalog)
    assert {item["backendHandler"] for item in catalog["blocks"]} == HANDLER_IDS
    assert all(item["helpKey"] == f"blocks.{item['id']}" for item in catalog["blocks"])
    changed = copy.deepcopy(catalog)
    changed["blocks"][0]["execute"] = "arbitrary.py"
    assert list(validator.iter_errors(changed))


def test_huge_integer_is_diagnostic_not_crash() -> None:
    value = example()
    value["workspaces"]["training"]["blocks"]["blocks"][0]["fields"]["EPOCHS"] = 10**400
    assert "FIELD_INVALID" in problems(value)


def test_concurrent_save_accepts_one_revision(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    path = tmp_path / "project.easyai.json"
    path.write_bytes((FIXTURES / "mnist.json").read_bytes())
    doc = ProjectDocument.model_validate(example())
    service = ProjectService(tmp_path)
    barrier = Barrier(2)

    def save(name: str) -> str:
        barrier.wait()
        try:
            service.save(doc.model_copy(update={"name": name}), 1)
            return "saved"
        except ValueError as error:
            return str(error)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, ["first", "second"]))
        assert sorted(results) == ["PROJECT_REVISION_CONFLICT", "saved"]
        assert read_project(path).document.revision == 2
    finally:
        service.close()


def test_close_waits_for_inflight_save(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event

    path = tmp_path / "project.easyai.json"
    path.write_bytes((FIXTURES / "mnist.json").read_bytes())
    doc = ProjectDocument.model_validate(example())
    service = ProjectService(tmp_path)
    entered, release = Event(), Event()
    original_read = read_project

    def paused_read(target: Path):
        result = original_read(target)
        entered.set()
        assert release.wait(3)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        with patch("easyai.services.project_service.read_project", side_effect=paused_read):
            saving = pool.submit(service.save, doc, 1)
            assert entered.wait(3)
            closing = pool.submit(service.close)
            try:
                with pytest.raises(TimeoutError):
                    closing.result(timeout=0.1)
            finally:
                release.set()
            saved = saving.result(timeout=3)
            closing.result(timeout=3)
    second = ProjectService(tmp_path)
    try:
        assert second.owned
        assert second.save(saved.model_copy(update={"name": "new-owner"}), 2).revision == 3
        with pytest.raises(ValueError, match="PROJECT_READ_ONLY"):
            service.save(saved.model_copy(update={"name": "old-owner"}), 2)
        assert read_project(path).document.name == "new-owner"
    finally:
        second.close()
