import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import ProjectDocument
from easyai.services.project_service import ProjectService

FIXTURE = SOURCE_ROOT / "packages/contracts/fixtures/mnist.json"


@pytest.mark.parametrize("limit", ["size", "depth"])
def test_save_rejects_unreadable_payload_without_touching_files(tmp_path: Path, limit: str) -> None:
    path = tmp_path / "project.easyai.json"
    original = FIXTURE.read_bytes()
    path.write_bytes(original)
    value = json.loads(original)
    metadata: object = "leaf"
    if limit == "size":
        metadata = "x" * (5 * 1024 * 1024)
    else:
        for _ in range(65):
            metadata = [metadata]
    value["workspaces"]["data"]["blocks"]["blocks"][0]["data"] = metadata
    document = ProjectDocument.model_validate(value)
    service = ProjectService(tmp_path)
    backup = tmp_path / ".easyai/backup/project.easyai.json.bak"
    backup.parent.mkdir()
    backup.write_bytes(b"previous-backup")
    try:
        with pytest.raises(ValueError, match=f"PROJECT_{limit.upper()}_LIMIT"):
            service.save(document, 1)
        assert path.read_bytes() == original
        assert backup.read_bytes() == b"previous-backup"
    finally:
        service.close()


def test_os_releases_project_lock_after_process_crash(tmp_path: Path) -> None:
    (tmp_path / "project.easyai.json").write_bytes(FIXTURE.read_bytes())
    code = """
import sys
from pathlib import Path
from easyai.services.project_service import ProjectService
service = ProjectService(Path(sys.argv[1]))
print(service.owned, flush=True)
sys.stdin.buffer.read()
service.close()
"""
    child = subprocess.Popen(
        [sys.executable, "-u", "-c", code, str(tmp_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert child.stdout.readline().replace(b"\r\n", b"\n") == b"True\n"
        live_contender = ProjectService(tmp_path)
        try:
            assert not live_contender.owned
        finally:
            live_contender.close()
        child.kill()  # Abrupt crash: no close(), atexit, PID inspection or lock-file removal.
        child.wait(timeout=5)
        recovered = ProjectService(tmp_path)
        try:
            assert recovered.owned
            doc = ProjectDocument.model_validate_json(FIXTURE.read_bytes())
            assert recovered.save(doc, 1).revision == 2
        finally:
            recovered.close()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        child.stdin.close()
        child.stdout.close()
        child.stderr.close()


def test_lock_inode_survives_close_and_excludes_live_writers(tmp_path: Path) -> None:
    first = ProjectService(tmp_path)
    lock = tmp_path / ".easyai/project.lock"
    identity = (lock.stat().st_dev, lock.stat().st_ino)
    second = ProjectService(tmp_path)
    try:
        assert first.owned and not second.owned
        assert not os.get_inheritable(first._project_lock.fd)
        assert second.lock_reason == "PROJECT_LOCK_HELD"
        first.close()
        assert lock.exists() and (lock.stat().st_dev, lock.stat().st_ino) == identity
        reopened = ProjectService(tmp_path)
        try:
            assert reopened.owned
            assert (lock.stat().st_dev, lock.stat().st_ino) == identity
        finally:
            reopened.close()
    finally:
        first.close()
        second.close()


def test_unverifiable_legacy_lock_remains_read_only_and_unchanged(tmp_path: Path) -> None:
    meta = tmp_path / ".easyai"
    meta.mkdir()
    lock = meta / "project.lock"
    lock.write_bytes(b"")
    identity = lock.stat().st_ino
    service = ProjectService(tmp_path)
    try:
        assert not service.owned
        assert service.lock_reason == "PROJECT_LOCK_LEGACY_UNVERIFIED"
    finally:
        service.close()
    assert lock.read_bytes() == b"" and lock.stat().st_ino == identity


def test_lock_replacement_invalidates_old_owner_without_deleting_new_lock(tmp_path: Path) -> None:
    from easyai.security.project_lock import MAGIC

    path = tmp_path / "project.easyai.json"
    original = FIXTURE.read_bytes()
    path.write_bytes(original)
    service = ProjectService(tmp_path)
    lock = tmp_path / ".easyai/project.lock"
    replacement = tmp_path / ".easyai/replacement"
    replacement.write_bytes(MAGIC)
    # Either the OS refuses replacement, or the old owner must refuse all writes.
    try:
        replacement.replace(lock)
    except PermissionError:
        try:
            assert service.save(ProjectDocument.model_validate_json(original), 1).revision == 2
        finally:
            service.close()
        assert lock.read_bytes() == MAGIC
        return
    new_inode = lock.stat().st_ino
    try:
        with pytest.raises(ValueError, match="PROJECT_LOCK_REPLACED"):
            service.save(ProjectDocument.model_validate_json(original), 1)
        assert path.read_bytes() == original
    finally:
        service.close()
    assert lock.exists() and lock.stat().st_ino == new_inode


def relu_chain_project(length: int) -> ProjectDocument:
    import copy

    value = json.loads(FIXTURE.read_bytes())
    model = value["workspaces"]["model"]["blocks"]["blocks"][0]
    template = model["inputs"]["body"]["block"]["next"]["block"]
    assert template["type"] == "model.relu"
    head = None
    for index in reversed(range(length)):
        node = copy.deepcopy(template)
        node.pop("next", None)
        node["id"] = f"boundary-relu-{index}"
        if head is not None:
            node["next"] = {"block": head}
        head = node
    model["inputs"]["body"]["block"] = head
    return ProjectDocument.model_validate(value)


@pytest.mark.parametrize("length,accepted", [(27, True), (28, False)])
def test_next_chain_json_depth_save_reopen_boundary(
    tmp_path: Path, length: int, accepted: bool
) -> None:
    from easyai.services.project_service import read_project, validate_project_bytes

    path = tmp_path / "project.easyai.json"
    original = FIXTURE.read_bytes()
    path.write_bytes(original)
    document = relu_chain_project(length)
    service = ProjectService(tmp_path)
    backup = tmp_path / ".easyai/backup/project.easyai.json.bak"
    backup.parent.mkdir()
    backup.write_bytes(b"previous-backup")
    payload = (document.model_dump_json(by_alias=True, indent=2) + "\n").encode()
    try:
        if accepted:
            validate_project_bytes(payload)
            saved = service.save(document, 1)
            opened = read_project(path)
            assert not opened.read_only
            assert opened.document == saved
            assert backup.read_bytes() == original
        else:
            with pytest.raises(ValueError, match="PROJECT_DEPTH_LIMIT"):
                validate_project_bytes(payload)
            with pytest.raises(ValueError, match="PROJECT_DEPTH_LIMIT"):
                service.save(document, 1)
            assert path.read_bytes() == original
            assert backup.read_bytes() == b"previous-backup"
    finally:
        service.close()
