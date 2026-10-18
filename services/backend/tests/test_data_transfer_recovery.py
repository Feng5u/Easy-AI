"""Owned local directories and SFTP-API fixture only; no real network/user data."""

import json
from pathlib import Path
import threading
from uuid import uuid4

import pytest
from test_data_transfers import (
    prepared as shared_source_fixture,
    plan_for,
    confirm_for,
    finish,
    DataSftp,
    Session,
)
from easyai.domain.connections import SessionControl
from easyai.services.data_transfers import DataTransfers
from easyai.services.data_transfer_transport import DataUploadTransport

prepared = shared_source_fixture


def fresh(prepared, service):
    _, source, endpoint, auth, _, request, guard, _ = prepared
    scope = auth.scope.model_copy(update={"connection_id": str(uuid4())})
    next_auth = auth.model_copy(update={"scope": scope})
    transport = DataUploadTransport(
        scope, Session(scope), threading.RLock(), guard, lambda channel: DataSftp(endpoint)
    )
    next_request = request.model_copy(
        update={"connection_id": scope.connection_id, "data_selection_id": str(uuid4())}
    )
    return service, source, endpoint, next_auth, transport, next_request, guard, prepared[-1]


@pytest.fixture
def interrupted(prepared, tmp_path):
    state = tmp_path / "private-app"
    state.mkdir(mode=0o700)
    service = DataTransfers(threading.RLock(), state)
    data = (service, *prepared[1:])
    endpoint = prepared[2]
    plan = plan_for(data)
    fired = []

    def cancel(action, path):
        if (
            action == "write"
            and path.name.startswith(".part-")
            and path.parent == Path(plan.target_path)
            and not fired
        ):
            fired.append(True)
            service.cancel(
                plan.plan_id,
                SessionControl(project_id=plan.project_id, connection_id=plan.connection_id),
            )

    endpoint.callback = cancel
    result = finish(service, service.confirm(confirm_for(plan)))
    assert fired and result.status == "CANCELLED", result
    endpoint.callback = lambda *args: None
    service.close()
    service.wait_idle()
    calls = len(endpoint.calls)
    restored = DataTransfers(threading.RLock(), state)
    assert len(endpoint.calls) == calls  # Loading ledger cannot open a remote channel.
    try:
        yield restored, fresh(prepared, restored), plan, state
    finally:
        restored.close()
        restored.wait_idle()


def test_restart_reauthorizes_source_inspects_readonly_and_sends_missing_only(interrupted):
    service, data, original, state = interrupted
    _, source, endpoint, auth, transport, request, guard, _ = data
    files = list(Path(original.target_path).glob(".part-*"))
    assert len(files) == 1
    partial = files[0].read_bytes()
    existing = Path(original.target_path) / "images/synthetic.bin"
    stamp = existing.stat().st_mtime_ns
    history = service.history(request.project_id)
    assert len(history) == 1 and history[0].inspection_required and not history[0].last_completed
    raw = (state / "data-transfers" / (original.plan_id + ".json")).read_text()
    assert str(source) not in raw and original.connection_id not in raw and "password" not in raw
    before = len(endpoint.calls)
    plan = service.prepare_recovery(original.plan_id, request, source, auth, transport, guard)
    assert plan.slot_id == original.plan_id and plan.plan_id != original.plan_id
    assert plan.missing_files == 1 and plan.reused_bytes == existing.stat().st_size
    assert all(
        action not in {"write", "mkdir", "before_rename"} for action, _ in endpoint.calls[before:]
    )
    result = finish(service, service.confirm(confirm_for(plan)))
    assert result.status == "COMPLETED", result
    assert result.sent_bytes == (source / "labels.bin").stat().st_size
    assert result.reused_bytes + result.sent_bytes == result.verified_bytes == result.total_bytes
    assert existing.stat().st_mtime_ns == stamp and files[0].read_bytes() == partial
    assert result.target_path == original.target_path and not result.data_ready
    assert service.history(request.project_id)[0].last_completed
    assert (
        json.loads((Path(result.target_path) / ".easyai-complete.json").read_bytes())["transferId"]
        == original.plan_id
    )


@pytest.mark.parametrize(
    "mutation", ["source", "target_file", "unknown", "unknown_part", "link", "pin", "marker"]
)
def test_recovery_rejects_conflicts_before_any_write_and_preserves_unknown(interrupted, mutation):
    service, data, original, _ = interrupted
    _, source, endpoint, auth, transport, request, guard, _ = data
    root = Path(original.target_path)
    preserve = None
    if mutation == "source":
        (source / "labels.bin").write_bytes(b"changed")
    elif mutation == "target_file":
        (root / "images/synthetic.bin").write_bytes(b"conflict")
    elif mutation in {"unknown", "unknown_part"}:
        preserve = root / (
            "teacher-file" if mutation == "unknown" else ".part-" + str(uuid4()) + "-0"
        )
        preserve.write_bytes(b"unknown-preserve")
    elif mutation == "link":
        (root / "images/synthetic.bin").unlink()
        (root / "images/synthetic.bin").symlink_to(source / "labels.bin")
    elif mutation == "marker":
        (root / ".easyai-transfer.json").write_text("{}")
    else:
        auth = auth.model_copy(
            update={
                "scope": auth.scope.model_copy(update={"host_fingerprint": "SHA256:" + "B" * 43})
            }
        )
    before = len(endpoint.calls)
    with pytest.raises(ValueError):
        service.prepare_recovery(original.plan_id, request, source, auth, transport, guard)
    assert all(
        action not in {"write", "mkdir", "before_rename"} for action, _ in endpoint.calls[before:]
    )
    if preserve:
        assert preserve.read_bytes() == b"unknown-preserve"


def test_completed_marker_without_all_files_is_not_completion(interrupted):
    service, data, original, _ = interrupted
    _, source, endpoint, auth, transport, request, guard, _ = data
    record = service.ledger.records[original.plan_id]
    (Path(original.target_path) / ".easyai-complete.json").write_bytes(record.intent.completion())
    before = len(endpoint.calls)
    with pytest.raises(ValueError):
        service.prepare_recovery(original.plan_id, request, source, auth, transport, guard)
    assert not any(action == "write" for action, _ in endpoint.calls[before:])


def test_store_lock_and_tampered_intent_fail_closed(interrupted):
    service, data, original, state = interrupted
    _, source, endpoint, auth, transport, request, guard, _ = data
    with pytest.raises(ValueError):
        DataTransfers(threading.RLock(), state)
    path = state / "data-transfers" / (original.plan_id + ".json")
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        service.prepare_recovery(original.plan_id, request, source, auth, transport, guard)


def test_close_keeps_ledger_until_inflight_planning_is_quiet(prepared, tmp_path):
    from easyai.services.data_transfer_errors import TransferFailure

    state = tmp_path / "planning-state"
    state.mkdir(mode=0o700)
    service = DataTransfers(threading.RLock(), state)
    _, source, _, auth, transport, request, guard, _ = prepared
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    failures = []

    def blocked_inspect(cancel):
        with transport.connection(cancel, 10):
            entered.set()
            assert release.wait(8)
        return str(prepared[2].home), 0

    transport.inspect = blocked_inspect

    def planning():
        try:
            service.prepare(request, source, auth, transport, guard)
        except Exception as error:
            failures.append(error)
        finally:
            done.set()

    thread = threading.Thread(target=planning)
    thread.start()
    assert entered.wait(2)
    service.close()
    try:
        with pytest.raises(TransferFailure, match="DATA_TRANSFER_CLEANUP_PENDING"):
            service.wait_idle()
        assert not done.is_set() and transport.session.io_lock.locked()
        with pytest.raises(TransferFailure, match="DATA_TRANSFER_BUSY"):
            DataTransfers(threading.RLock(), state)
    finally:
        release.set()
        thread.join(3)
        service.wait_idle()
    assert done.is_set() and failures and not service.plans
    replacement = DataTransfers(threading.RLock(), state)
    replacement.close()
    replacement.wait_idle()


def test_failed_intent_persistence_cannot_write_remote(prepared, tmp_path, monkeypatch):
    from easyai.services.data_transfer_errors import TransferFailure

    state = tmp_path / "failed-state"
    state.mkdir(mode=0o700)
    service = DataTransfers(threading.RLock(), state)
    data = (service, *prepared[1:])
    plan = plan_for(data)
    before = len(prepared[2].calls)

    def fail(record):
        raise TransferFailure("DATA_TRANSFER_PERSISTENCE_FAILED")

    monkeypatch.setattr(service.ledger, "put", fail)
    try:
        result = finish(service, service.confirm(confirm_for(plan)))
        assert result.status == "FAILED"
        assert result.error_code == "DATA_TRANSFER_PERSISTENCE_FAILED"
        assert not list(prepared[2].home.iterdir())
        assert all(
            action not in {"write", "mkdir", "before_rename"}
            for action, _ in prepared[2].calls[before:]
        )
    finally:
        service.close()
        service.wait_idle()


def test_recovery_source_change_after_inspection_refuses_before_write(interrupted):
    service, data, original, _ = interrupted
    _, source, endpoint, auth, transport, request, guard, _ = data
    plan = service.prepare_recovery(original.plan_id, request, source, auth, transport, guard)
    before = len(endpoint.calls)
    (source / "labels.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="DATA_TRANSFER_SOURCE_CHANGED"):
        service.confirm(confirm_for(plan))
    assert len(endpoint.calls) == before
    assert not service.jobs
