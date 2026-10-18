"""Synthetic in-process SFTP only. No sockets, SSH server, user data or training."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import threading
import time
from uuid import uuid4

import pytest
from easyai.domain.connections import AuthenticatedConnection, SessionControl
from easyai.domain.data_transfer import TransferBudget, TransferPlanRequest, TransferConfirmation
from easyai.domain.environment import EnvironmentScope
from easyai.domain.ssh import SshEndpoint
from easyai.services.data_transfers import DataTransfers
from easyai.services.data_transfer_source import TransferSource
from easyai.services.data_transfer_transport import DataUploadTransport
from test_owner_transport import Sftp


class Channel:
    def __init__(self):
        self.closed, self.eof_received = False, False
        self.out = bytearray()

    def settimeout(self, seconds):
        assert 0 < seconds <= 1

    def invoke_subsystem(self, name):
        assert name == "sftp"

    def exec_command(self, command):
        argv = shlex.split(command)
        assert argv[:-2] == [
            "/usr/bin/timeout",
            "--signal=TERM",
            "--kill-after=2s",
            "3s",
            "/usr/bin/env",
            "PYTHONDONTWRITEBYTECODE=1",
            "CONDA_NO_PLUGINS=true",
        ]
        assert argv[-2:] in [["/usr/bin/id", "-u"], ["/usr/bin/uname", "-s"]]
        self.out.extend(
            b"Linux\n" if argv[-2] == "/usr/bin/uname" else str(os.getuid()).encode() + b"\n"
        )

    def shutdown_write(self):
        self.eof_received = True

    def recv_ready(self):
        return bool(self.out)

    def recv(self, size):
        value = bytes(self.out[:size])
        del self.out[:size]
        return value

    def recv_stderr_ready(self):
        return False

    def recv_stderr(self, size):
        return b""

    def exit_status_ready(self):
        return True

    def recv_exit_status(self):
        return 0

    def close(self):
        self.closed = True


class Session:
    def __init__(self, scope):
        self.endpoint, self.host_fingerprint = scope.endpoint, scope.host_fingerprint
        self.io_lock = threading.Lock()
        self.closed = False

    def validate_probe_session(self):
        if self.closed:
            raise ValueError("SSH_SESSION_INVALID")

    def open_probe_channel(self, timeout):
        self.validate_probe_session()
        return Channel()

    def close(self):
        self.closed = True


class Endpoint:
    def __init__(self, home):
        self.home, self.renames = home, 0
        self.read_sizes = []
        self.calls = []
        self.callback = lambda action, path: None

    def hook(self, action, path):
        self.calls.append((action, path))
        self.callback(action, path)


class DataSftp(Sftp):
    def normalize(self, path):
        assert path == "."
        return str(self.endpoint.home)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("Synthetic SFTP suite cannot dial sockets")

    monkeypatch.setattr(socket, "create_connection", no_network)
    source = tmp_path / "selected-data"
    source.mkdir()
    (source / "images").mkdir()
    (source / "images/synthetic.bin").write_bytes(b"synthetic-data-only" * 7000)
    (source / "labels.bin").write_bytes(bytes(range(10)))
    home = tmp_path / "remote-home"
    home.mkdir(mode=0o700)
    mutex = threading.RLock()
    scope = EnvironmentScope(
        project_id=str(uuid4()),
        connection_id=str(uuid4()),
        endpoint=SshEndpoint(host="synthetic.invalid", port=22),
        host_fingerprint="SHA256:" + "A" * 43,
    )
    auth = AuthenticatedConnection(
        project_id=scope.project_id,
        request_id=str(uuid4()),
        identity_request_id=str(uuid4()),
        scope=scope,
        username="synthetic",
        target_id=str(uuid4()),
        target_revision=1,
        expires_in_seconds=300,
    )
    endpoint = Endpoint(home)
    session = Session(scope)
    active = [True]

    def guard():
        if not active[0]:
            raise ValueError("DATA_TRANSFER_AUTH_STALE")

    transport = DataUploadTransport(
        scope, session, mutex, guard, lambda channel: DataSftp(endpoint)
    )
    service = DataTransfers(mutex)
    request = TransferPlanRequest(
        project_id=scope.project_id,
        connection_id=scope.connection_id,
        expected_revision=1,
        data_selection_id=str(uuid4()),
        budget=TransferBudget(),
    )
    yield service, source, endpoint, auth, transport, request, guard, active
    service.close()
    for job in service.jobs.values():
        if job.thread:
            job.thread.join(2)


def plan_for(prepared):
    service, source, endpoint, auth, transport, request, guard, _ = prepared
    return service.prepare(request, source, auth, transport, guard)


def confirm_for(plan):
    return TransferConfirmation(
        project_id=plan.project_id,
        connection_id=plan.connection_id,
        plan_id=plan.plan_id,
        plan_hash=plan.plan_hash,
        confirmed=True,
    )


def finish(service, value, timeout=3):
    service.jobs[value.transfer_id].thread.join(timeout)
    return service.get(
        value.transfer_id,
        SessionControl(project_id=value.project_id, connection_id=value.connection_id),
    )


def test_explicit_plan_confirm_upload_and_remote_completion_hashes(prepared):
    service, source, endpoint, _, _, _, _, _ = prepared
    plan = plan_for(prepared)
    assert plan.file_count == 2 and not plan.writes_started
    assert not any(action in {"mkdir", "write"} for action, _ in endpoint.calls)
    confirmation = confirm_for(plan)
    with pytest.raises(ValueError):
        service.confirm(confirmation.model_copy(update={"plan_hash": "0" * 64}))
    assert not list(endpoint.home.iterdir())
    job = service.confirm(confirmation)
    result = finish(service, job)
    assert result.status == "COMPLETED", result
    assert result.sent_bytes == result.verified_bytes == result.total_bytes
    assert result.completed_files == 2 and not result.data_ready
    manifest = json.loads((Path(plan.target_path) / ".easyai-complete.json").read_text())
    for record in manifest["files"]:
        raw = (Path(plan.target_path) / record["path"]).read_bytes()
        assert raw == (source / record["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["sha256"]
    assert not list(Path(plan.target_path).rglob(".part-*"))
    calls = len(endpoint.calls)
    assert service.confirm(confirmation).transfer_id == job.transfer_id
    assert len(endpoint.calls) == calls


@pytest.mark.parametrize("failure", ["link", "fifo", "budget", "private", "changed", "stale"])
def test_source_or_authority_failure_never_writes_remote(prepared, failure):
    service, source, endpoint, auth, transport, request, guard, active = prepared
    if failure == "link":
        (source / "link").symlink_to(source / "labels.bin")
    elif failure == "fifo":
        os.mkfifo(source / "fifo")
    elif failure == "private":
        (source / "id_ed25519").write_text("synthetic-rejected-name")
    elif failure == "budget":
        request.budget.max_bytes = 1
    if failure in {"changed", "stale"}:
        plan = plan_for(prepared)
        if failure == "changed":
            (source / "labels.bin").write_bytes(b"changed")
        else:
            active[0] = False
        with pytest.raises(ValueError):
            service.confirm(confirm_for(plan))
    else:
        with pytest.raises(ValueError):
            service.prepare(request, source, auth, transport, guard)
    assert not any(action in {"mkdir", "write"} for action, _ in endpoint.calls)


def test_existing_unknown_managed_directory_is_not_adopted_or_overwritten(prepared):
    service, _, endpoint, _, _, request, _, _ = prepared
    parent = endpoint.home / ".easyai/projects" / request.project_id / "data"
    parent.mkdir(parents=True, mode=0o700)
    sentinel = parent / "teacher-existing"
    sentinel.write_text("preserve")
    plan = plan_for(prepared)
    result = finish(service, service.confirm(confirm_for(plan)))
    assert result.status == "FAILED"
    assert sentinel.read_text() == "preserve"
    assert not Path(plan.target_path).exists()


def test_cancel_before_confirmation_is_a_tombstone_and_late_confirm_never_uploads(prepared):
    service, _, endpoint, _, _, _, _, _ = prepared
    plan = plan_for(prepared)
    scope = SessionControl(project_id=plan.project_id, connection_id=plan.connection_id)
    canceled = service.cancel(plan.plan_id, scope)
    assert canceled.status == "CANCELLED" and canceled.sent_bytes == 0
    replay = service.confirm(confirm_for(plan))
    assert replay.status == "CANCELLED" and service.jobs[plan.plan_id].thread is None
    assert not any(action in {"mkdir", "write"} for action, _ in endpoint.calls)


def test_cancel_retains_owned_partial_and_never_reports_completed(prepared):
    service, _, endpoint, _, _, _, _, _ = prepared
    entered, release = threading.Event(), threading.Event()

    def blocked(action, path):
        if action == "write" and path.name.startswith(".part-"):
            entered.set()
            assert release.wait(3)

    endpoint.callback = blocked
    plan = plan_for(prepared)
    job = service.confirm(confirm_for(plan))
    try:
        assert entered.wait(2)
        scope = SessionControl(project_id=job.project_id, connection_id=job.connection_id)
        assert service.cancel(job.transfer_id, scope).status == "CANCELLING"
        service.jobs[job.transfer_id].deadline = time.monotonic() - 3
        assert service.get(job.transfer_id, scope).status == "CLEANUP_PENDING"
        assert not (Path(plan.target_path) / ".easyai-complete.json").exists()
    finally:
        release.set()
    assert finish(service, job).status == "CANCELLED"
    assert Path(plan.target_path).is_dir()
    assert not (Path(plan.target_path) / ".easyai-complete.json").exists()


def test_readback_corruption_cannot_publish_complete(prepared):
    service, _, endpoint, _, _, _, _, _ = prepared
    changed = [False]

    def corrupt(action, path):
        if action == "read" and path.name.startswith(".part-") and not changed[0]:
            changed[0] = True
            path.write_bytes(b"corrupt")

    endpoint.callback = corrupt
    plan = plan_for(prepared)
    assert finish(service, service.confirm(confirm_for(plan))).status == "FAILED"
    assert not (Path(plan.target_path) / ".easyai-complete.json").exists()


@pytest.mark.parametrize("confirmed", [1, 0, "true", False, None])
def test_confirmation_requires_actual_boolean_true(prepared, confirmed):
    plan = plan_for(prepared)
    with pytest.raises(ValueError, match="DATA_TRANSFER_CONFIRMATION_REQUIRED|Input should be"):
        TransferConfirmation.model_validate(
            {**confirm_for(plan).model_dump(), "confirmed": confirmed}
        )
    assert not any(action in {"mkdir", "write"} for action, _ in prepared[2].calls)


def test_external_exception_with_valid_prefix_cannot_echo_secrets(prepared):
    service, _, endpoint, _, _, _, _, _ = prepared
    plan = plan_for(prepared)

    def fail(action, path):
        if action == "mkdir":
            raise RuntimeError("DATA_TRANSFER_PASSWORD_SECRET")

    endpoint.callback = fail
    result = finish(service, service.confirm(confirm_for(plan)))
    assert result.status == "FAILED" and result.error_code == "DATA_TRANSFER_FAILED"
    assert "PASSWORD_SECRET" not in result.model_dump_json()


def test_unconfirmed_sdk_cleanup_retains_gate_and_blocks_another_job(prepared):
    service, _, endpoint, _, transport, _, _, _ = prepared
    plan = plan_for(prepared)

    def broken_close():
        raise OSError("synthetic unknown socket close")

    transport.session.close = broken_close

    def fail(action, path):
        if action == "sftp_close":
            raise OSError("synthetic SFTP close failure")

    endpoint.callback = fail
    result = finish(service, service.confirm(confirm_for(plan)))
    assert result.status == "CLEANUP_PENDING"
    assert transport.cleanup_pending and transport.session.io_lock.locked()
    with pytest.raises(ValueError, match="DATA_TRANSFER_BUSY"):
        plan_for(prepared)


def test_terminal_result_is_preserved_while_worker_thread_retires(prepared, monkeypatch):
    service = prepared[0]
    entered, release = threading.Event(), threading.Event()
    original = threading.Thread

    def thread(*args, **kwargs):
        if kwargs.get("name") == "easyai-data-upload":
            target = kwargs["target"]

            def held():
                target()
                entered.set()
                assert release.wait(3)

            kwargs["target"] = held
        return original(*args, **kwargs)

    monkeypatch.setattr("easyai.services.data_transfers.threading.Thread", thread)
    plan = plan_for(prepared)
    value = service.confirm(confirm_for(plan))
    scope = SessionControl(project_id=value.project_id, connection_id=value.connection_id)
    try:
        assert entered.wait(2)
        service.jobs[value.transfer_id].deadline = time.monotonic() - 3
        assert service.get(value.transfer_id, scope).status == "COMPLETED"
        assert service.cancel(value.transfer_id, scope).status == "COMPLETED"
        service.invalidate()
        assert service.get(value.transfer_id, scope).status == "COMPLETED"
    finally:
        release.set()
    assert finish(service, value).status == "COMPLETED"


def test_interrupt_close_failure_is_sanitized_and_keeps_cleanup_pending(prepared, monkeypatch):
    service, _, endpoint, _, transport, _, _, _ = prepared
    plan = plan_for(prepared)
    entered, release, attempted = threading.Event(), threading.Event(), threading.Event()
    uncaught = []
    monkeypatch.setattr(threading, "excepthook", lambda args: uncaught.append(args))

    class BadClose(Channel):
        def close(self):
            attempted.set()
            raise RuntimeError("DATA_TRANSFER_PASSWORD_SECRET")

    transport.session.open_probe_channel = lambda timeout: BadClose()

    def broken_socket():
        raise OSError("synthetic unconfirmed socket")

    transport.session.close = broken_socket

    def block(action, path):
        if action == "write" and path.name.startswith(".part-"):
            entered.set()
            assert release.wait(3)

    endpoint.callback = block
    job = service.confirm(confirm_for(plan))
    try:
        assert entered.wait(2)
        service.cancel(
            job.transfer_id,
            SessionControl(project_id=job.project_id, connection_id=job.connection_id),
        )
        assert attempted.wait(2)
    finally:
        release.set()
    result = finish(service, job)
    assert result.status == "CLEANUP_PENDING" and transport.session.io_lock.locked()
    assert not uncaught and "PASSWORD_SECRET" not in result.model_dump_json()


def test_directory_enumeration_is_bounded_before_materializing_names(prepared):
    source = prepared[1]
    for index in range(514):
        (source / f"empty-{index}").touch()
    with pytest.raises(ValueError, match="DATA_TRANSFER_SOURCE_LIMIT"):
        TransferSource.inventory(source, TransferBudget(), lambda: None)


def test_authenticated_http_routes_keep_paths_and_authority_out_of_renderer_input(
    prepared, tmp_path
):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from easyai.api import create_app
    from easyai.services.local_workspace import LocalWorkspace

    _, source, _, auth, transport, request, _, _ = prepared
    workspace = LocalWorkspace(tmp_path / "http-state")
    project_root = tmp_path / "http-project"
    project_root.mkdir()
    try:
        project = workspace.create(
            workspace.select("project", project_root).selection_id, "synthetic transfer"
        ).project
        scope = auth.scope.model_copy(update={"project_id": project.project_id})
        auth = auth.model_copy(update={"project_id": project.project_id, "scope": scope})
        transport.scope = scope
        workspace._connections = SimpleNamespace(
            data_transport=lambda value: (auth, transport), invalidate=lambda: None
        )
        selection = workspace.select("data", source)
        body = request.model_copy(
            update={"project_id": project.project_id, "data_selection_id": selection.selection_id}
        ).model_dump(mode="json", by_alias=True)
        client = TestClient(create_app("synthetic-transfer-token", workspace=workspace))
        headers = {"Authorization": "Bearer synthetic-transfer-token"}
        assert client.post("/api/v1/data-transfers/plan", json=body).status_code == 401
        invalid = client.post(
            "/api/v1/data-transfers/plan",
            json={**body, "remotePath": "/teacher/untouched"},
            headers=headers,
        )
        assert invalid.status_code == 422 and "/teacher/untouched" not in invalid.text
        response = client.post("/api/v1/data-transfers/plan", json=body, headers=headers)
        assert response.status_code == 200, response.text
        plan = response.json()
        confirm = {
            "projectId": project.project_id,
            "connectionId": auth.scope.connection_id,
            "planId": plan["planId"],
            "planHash": plan["planHash"],
            "confirmed": 1,
        }
        assert (
            client.post("/api/v1/data-transfers", json=confirm, headers=headers).status_code == 422
        )
        confirm["confirmed"] = True
        response = client.post("/api/v1/data-transfers", json=confirm, headers=headers)
        assert response.status_code == 200, response.text
        service = workspace.transfers()
        service.jobs[plan["planId"]].thread.join(3)
        path = f"/api/v1/data-transfers/{plan['planId']}?project_id={project.project_id}&connection_id={auth.scope.connection_id}"
        response = client.get(path, headers=headers)
        assert response.status_code == 200 and response.json()["status"] == "COMPLETED", (
            response.text
        )
        assert not workspace.runs._ledger.entries
    finally:
        workspace._connections = None
        workspace.close()
