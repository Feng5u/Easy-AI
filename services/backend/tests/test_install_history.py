"""Read-only synthetic ledger recovery. Never trains, installs, probes or starts workers."""

import hashlib
from pathlib import Path
import threading
from uuid import uuid4

import pytest
from easyai.security.project_lock import ProjectLock
from easyai.services.install_service import InstallService
from test_install_service import request, confirmation


def snapshot(root: Path):
    return {
        str(p.relative_to(root)): (
            p.stat().st_ino,
            p.stat().st_size,
            hashlib.sha256(p.read_bytes()).hexdigest(),
        )
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("History never executes"))
    monkeypatch.setattr(
        "socket.create_connection", lambda *a, **k: pytest.fail("History never connects")
    )


def saved(service, state):
    plan = service.plan(request())
    job = service.confirm(confirmation(plan))
    current = service._jobs[job.job_id]
    current.state = state
    current.status_code = (
        "INSTALL_VERIFIED"
        if state == "SUCCEEDED"
        else "INSTALL_REPROBE_FAILED"
        if state == "FAILED"
        else current.status_code
    )
    current.verified = state == "SUCCEEDED"
    current.needs_reprobe = state != "SUCCEEDED"
    current.changes_possible = state != "AWAITING_EXECUTION"
    service._record(current)
    return current


def test_restart_history_finds_success_failure_expired_and_unknown_without_ids_or_writes(tmp_path):
    first = InstallService(tmp_path)
    jobs = {
        state: saved(first, state)
        for state in ["SUCCEEDED", "FAILED", "AWAITING_EXECUTION", "INSTALLING"]
    }
    # Simulate process loss without graceful cancellation rewriting the fixture.
    # There are no execution owners in this synthetic producer.
    assert not first._workers and not first._leases and not first._executing
    for journal in first._journals.values():
        journal.close()
    first._journals.clear()
    first._closed = True
    before = snapshot(tmp_path)
    second = InstallService(tmp_path)
    try:
        history = second.history()
        assert history.limit == 64 and len(history.entries) == 4
        assert all(e.origin == "recovered" and not e.worker_alive for e in history.entries)
        by_id = {e.job_id: e for e in history.entries}
        pending = by_id[jobs["AWAITING_EXECUTION"].job_id]
        assert pending.recorded_state == "AWAITING_EXECUTION" and pending.state == "CANCELLED"
        assert pending.status_code == "INSTALL_RESTART_CONFIRMATION_EXPIRED"
        unknown = by_id[jobs["INSTALLING"].job_id]
        assert unknown.observation == "stop-unconfirmed" and unknown.state == "CANCEL_REQUESTED"
        active = dict(second._active)
        for state, job in jobs.items():
            report = second.report(job.job_id)
            assert report.recorded.state == state and not report.current_environment_verified
            assert report.recorded.verified == (state == "SUCCEEDED")
        second.history()
        second.report(jobs["INSTALLING"].job_id)
        assert second._active == active and not second._workers and not second._leases
        assert snapshot(tmp_path) == before
        assert second.cancel(jobs["INSTALLING"].job_id).state == "CANCEL_REQUESTED"
        assert snapshot(tmp_path) == before
    finally:
        second.close()


def test_refresh_does_not_adopt_foreign_live_records_or_release_unknown_lease(tmp_path):
    reader = InstallService(tmp_path)
    writer = InstallService(tmp_path)
    job = saved(writer, "INSTALLING")
    held = ProjectLock(tmp_path / "synthetic-environment.lock")
    writer._leases[job.job_id] = held
    entered, release = threading.Event(), threading.Event()
    worker = threading.Thread(target=lambda: (entered.set(), release.wait(5)))
    writer._workers[job.job_id] = worker
    worker.start()
    assert entered.wait(1)
    try:
        state = writer._jobs[job.job_id].model_copy(deep=True)
        before = snapshot(tmp_path)
        assert writer.history().entries[0].observation == "managed-worker-alive"
        assert writer.history().entries[0].worker_alive
        foreign = reader.history().entries[0]
        assert (
            foreign.origin == "external"
            and foreign.observation == "stop-unconfirmed"
            and not foreign.worker_alive
        )
        assert reader.report(job.job_id).observed.state == "CANCEL_REQUESTED"
        assert job.job_id not in reader._jobs and not reader._active
        worker.join(0.01)
        held.verify()
        assert writer._jobs[job.job_id] == state and snapshot(tmp_path) == before
    finally:
        release.set()
        worker.join(1)
        assert not worker.is_alive()
        writer._leases.pop(job.job_id).close()
        writer._jobs[job.job_id].state = "FAILED"
        writer._record(writer._jobs[job.job_id])
        writer.close()
        reader.close()


def test_current_unknown_view_is_conservative_and_tail_is_not_repaired(tmp_path):
    service = InstallService(tmp_path)
    job = saved(service, "INSTALLING")
    path = tmp_path / "install-jobs" / job.job_id / "events.jsonl"
    with path.open("ab") as stream:
        stream.write(b'{"incomplete"')
    before = snapshot(tmp_path)
    report = service.report(job.job_id)
    assert report.recorded.state == "INSTALLING" and report.observed.state == "CANCEL_REQUESTED"
    assert service._jobs[job.job_id].state == "INSTALLING"
    assert snapshot(tmp_path) == before
    service.close()


def test_history_limits_identity_and_mutation_are_fail_closed(tmp_path):
    service = InstallService(tmp_path)
    job = saved(service, "FAILED")
    value = service.history()
    value.entries.clear()
    report = service.report(job.job_id)
    report.recorded.logs.clear()
    assert len(service.history().entries) == 1 and service.report(job.job_id).recorded.logs
    path = tmp_path / "install-jobs" / job.job_id / "events.jsonl"
    with path.open("ab") as stream:
        stream.write(b"x" * (4 * 1024 * 1024 + 1))
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match="JOURNAL_READ_LIMIT"):
        service.history()
    assert snapshot(tmp_path) == before
    service.close()
    extra = tmp_path / "empty"
    extra.mkdir()
    bounded = InstallService(extra)
    for _ in range(65):
        (extra / "install-jobs" / str(uuid4())).mkdir(parents=True)
    with pytest.raises(ValueError, match="INSTALL_JOB_LIMIT"):
        bounded.history()
    bounded.close()


def test_authenticated_history_report_can_be_found_after_restart(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from easyai.api import create_app
    from easyai.services.local_workspace import LocalWorkspace

    service = InstallService(tmp_path)
    job = saved(service, "FAILED")
    service.close()
    workspace = LocalWorkspace(tmp_path)
    client = TestClient(create_app("history-token", workspace=workspace))
    assert client.get("/api/v1/install-jobs").status_code == 401
    client.headers.update({"Authorization": "Bearer history-token"})
    value = client.get("/api/v1/install-jobs")
    assert value.status_code == 200
    entry = value.json()["entries"][0]
    assert entry["jobId"] == job.job_id
    result = client.get(f"/api/v1/install-jobs/{entry['jobId']}/report")
    assert result.status_code == 200 and result.json()["recorded"]["state"] == "FAILED"
    assert result.json()["currentEnvironmentVerified"] is False
    assert client.get(f"/api/v1/install-jobs/{uuid4()}/report").status_code == 404
    workspace.close()


def test_history_and_startup_stop_directory_enumeration_at_65(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    service = InstallService(tmp_path)
    root = tmp_path / "install-jobs"
    root.mkdir(exist_ok=True)
    consumed = []

    @contextmanager
    def many_entries(path):
        assert Path(path) == root

        def entries():
            for _ in range(2000):
                consumed.append(1)
                yield SimpleNamespace(path=str(root / str(uuid4())))

        yield entries()

    with monkeypatch.context() as scoped:
        scoped.setattr("easyai.services.install_service.os.scandir", many_entries)
        with pytest.raises(ValueError, match="INSTALL_JOB_LIMIT"):
            service.history()
        assert len(consumed) == 65
        consumed.clear()
        with pytest.raises(ValueError, match="INSTALL_JOB_LIMIT"):
            InstallService(tmp_path)
        assert len(consumed) == 65
    service.close()
