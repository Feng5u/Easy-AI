"""Portable editing/persistence gates; no training, installations or data downloads."""

import os
import sys
from pathlib import Path

import pytest

from easyai.compiler.pipeline import compile_project
from easyai.services.local_workspace import LocalWorkspace


def create(store, root, template="mnist-cnn"):
    root.mkdir()
    return store.create(store.select("project", root).selection_id, "课堂工程", template)


def test_saved_three_pages_and_ui_restore_without_machine_bindings(tmp_path):
    state = tmp_path / "state"
    store = LocalWorkspace(state)
    try:
        session = create(store, tmp_path / "project")
        assert session.project is not None
        changed = session.project.model_copy(deep=True)
        changed.ui.active_tab = "model"
        changed.ui.code_visible = True
        changed.workspaces.model.blocks.blocks[0]["x"] = 450
        saved = store.save(changed.project_id, changed, 1)
        assert saved.project is not None
        python_selection = store.select("python", Path(sys.executable)).selection_id
    finally:
        store.close()
    reopened = LocalWorkspace(state)
    try:
        current = reopened.current()
        assert current is not None and current.project == saved.project
        assert not current.read_only
        with pytest.raises(KeyError):
            reopened._selection(python_selection, "python")
    finally:
        reopened.close()


def test_unknown_project_is_readonly_byte_exact_without_metadata_and_can_export(tmp_path):
    root = tmp_path / "future"
    root.mkdir()
    raw = b'{"schemaVersion":999,"unknown":{"keep":"\\u4fdd\\u7559"}}\n'
    source = root / "project.easyai.json"
    source.write_bytes(raw)
    store = LocalWorkspace(tmp_path / "state")
    try:
        session = store.open(store.select("project", root).selection_id)
        assert session.read_only and session.project is None and session.raw_text == raw.decode()
        assert not (root / ".easyai").exists()
        destination = tmp_path / "portable.json"
        store.export_current(destination)
        assert destination.read_bytes() == raw == source.read_bytes()
        with pytest.raises(ValueError, match="EXISTS"):
            store.export_current(destination)
        assert destination.read_bytes() == raw
    finally:
        store.close()


def test_blank_and_compatible_import_preserve_ids_data_and_original_files(tmp_path):
    store = LocalWorkspace(tmp_path / "state")
    try:
        blank = create(store, tmp_path / "blank", "blank")
        assert blank.project is not None
        assert all(
            not ws.blocks.blocks
            for ws in (
                blank.project.workspaces.data,
                blank.project.workspaces.model,
                blank.project.workspaces.training,
            )
        )
        original = create(store, tmp_path / "source")
        assert original.project is not None
        raw = (tmp_path / "source/project.easyai.json").read_bytes()
        target = tmp_path / "target"
        (target / "data").mkdir(parents=True)
        (target / "data/keep").write_bytes(b"prepared data")
        imported = store.import_project(tmp_path / "source/project.easyai.json", target)
        assert imported.project is not None
        assert imported.project.project_id != original.project.project_id
        assert imported.project.workspaces == original.project.workspaces
        assert imported.project.revision == 1
        assert (target / "data/keep").read_bytes() == b"prepared data"
        assert (tmp_path / "source/project.easyai.json").read_bytes() == raw
        with pytest.raises(ValueError, match="ALREADY_EXISTS"):
            store.import_project(tmp_path / "source/project.easyai.json", target)
        draft = imported.project.model_copy(update={"name": "unsaved but exported"})
        store.export_current(tmp_path / "draft.json", draft)
        assert b"unsaved but exported" in (tmp_path / "draft.json").read_bytes()
        assert b"unsaved but exported" not in (target / "project.easyai.json").read_bytes()
    finally:
        store.close()


def test_unknown_import_and_fifo_source_never_rewrite_user_content(tmp_path):
    source = tmp_path / "unknown.json"
    raw = b'{"future":true,"schemaVersion":999}'
    source.write_bytes(raw)
    target = tmp_path / "target"
    target.mkdir()
    store = LocalWorkspace(tmp_path / "state")
    try:
        imported = store.import_project(source, target)
        assert imported.read_only and imported.project is None
        assert (target / "project.easyai.json").read_bytes() == source.read_bytes() == raw
        if os.name == "posix":
            fifo = tmp_path / "fifo.json"
            os.mkfifo(fifo)
            other = tmp_path / "other"
            other.mkdir()
            with pytest.raises(ValueError, match="FILE_NOT_REGULAR"):
                store.import_project(fifo, other)
            assert list(other.iterdir()) == []
    finally:
        store.close()


def test_oversized_readonly_prefix_is_never_exported_as_the_original(tmp_path):
    root = tmp_path / "oversized"
    root.mkdir()
    source = root / "project.easyai.json"
    raw = b'{"schemaVersion":999,"future":"' + b"x" * (6 * 1024 * 1024) + b'"}'
    source.write_bytes(raw)
    store = LocalWorkspace(tmp_path / "state")
    try:
        session = store.open(store.select("project", root).selection_id)
        assert session.project is None and session.reason == "PROJECT_SIZE_LIMIT"
        destination = tmp_path / "must-not-be-truncated.json"
        with pytest.raises(ValueError, match="PROJECT_SIZE_LIMIT"):
            store.export_current(destination)
        assert not destination.exists()
        assert source.read_bytes() == raw
    finally:
        store.close()


def test_history_pages_replay_durable_run_ids_without_launching_training(tmp_path):
    state = tmp_path / "state"
    store = LocalWorkspace(state)
    try:
        session = create(store, tmp_path / "project")
        assert session.project is not None
        project = session.project
        service = store._projects[project.project_id]
        ids = []
        for index in range(3):
            run = store.runs.prepare(
                service,
                1,
                compile_project(project).result.program_hash,
                f"history-{index}",
                Path(sys.executable),
                tmp_path,
            )
            ids.append(run.run_id)
            store.runs.cancel(run.run_id)
        assert [run.run_id for run in store.history(project.project_id, 0, 2)] == ids[::-1][:2]
        assert [run.run_id for run in store.history(project.project_id, 2, 2)] == ids[:1]
        with pytest.raises(ValueError):
            store.history(project.project_id, 0, 51)
    finally:
        store.close()
    reopened = LocalWorkspace(state)
    try:
        assert [run.run_id for run in reopened.history(project.project_id)] == ids[::-1]
        assert all(run.status == "CANCELLED" for run in reopened.history(project.project_id))
    finally:
        reopened.close()
