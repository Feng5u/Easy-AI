"""HTTP -> real SSH adapter/coordinator/portable owner, offline synthetic endpoint.

Only the test-owned stdlib child executes locally. Probe metadata is synthetic;
this proves composition, not SSH compatibility, torch training or gate A/B.
"""

import hashlib
import json
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import threading
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.domain.remote_run import RemoteRunIdentity, identity_digest
from easyai.services.connection_manager import ConnectionManager
from easyai.services.local_workspace import LocalWorkspace
from easyai.services.owner_transport import UID_CODE
from test_connection_manager import Client, FakeTimer, Session, SYNTHETIC_PASSWORD, grant
from test_environment_service import synthetic_report
from test_environment_transport import Channel
from test_owner_transport import Sftp
from test_portable_owner import CHILD
from test_remote_artifacts import png

PYTHON = str(Path(sys.base_prefix) / "bin/python3.11")


class EndpointChannel(Channel):
    def __init__(self, session):
        super().__init__(out=b"")
        self.session = session
        self.eof_received, self.code = False, None
        self.probe = False

    def invoke_subsystem(self, name):
        assert name == "sftp"

    def exec_command(self, command):
        self.session.channel_calls += 1
        argv = shlex.split(command)
        assert argv[:3] == ["/usr/bin/timeout", "--signal=TERM", "--kill-after=2s"]
        argv = argv[4:]
        if argv[0] == "/usr/bin/env":
            assert argv[1] == "PYTHONDONTWRITEBYTECODE=1"
            assert argv[2] == "CONDA_NO_PLUGINS=true"
            argv = argv[3:]
        assert argv[:3] == [PYTHON, "-I", "-B"]
        if argv[3] == "-c" and argv[4] != UID_CODE:
            assert "download=False" in argv[4]
            self.probe = True
            return
        if argv[3] == "-c":
            assert argv[4] == UID_CODE and len(argv) == 6
        else:
            assert argv[4] in {"--start", "--inspect", "--cancel"}
            root = Path(argv[6])
            assert root.parent == self.session.client.run_base
            assert argv[3] == str(root / "code/supervisor.py")
            identity = RemoteRunIdentity.model_validate_json(
                (root / "remote-identity.json").read_bytes()
            )
            assert argv[5:] == [
                "--run-dir",
                str(root),
                "--expected-identity",
                identity_digest(identity),
            ]
            self.session.client.commands.append(argv[4])
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=4)
        self.out, self.err = bytearray(result.stdout), bytearray(result.stderr)
        self.code, self.eof_received = result.returncode, True
        if len(argv) > 4 and argv[4] == "--start" and self.session.client.lose_start_ack:
            raise RuntimeError("synthetic consumed start, lost ACK")

    def shutdown_write(self):
        if self.probe:
            value = synthetic_report(json.loads(self.stdin), PYTHON, sys.base_prefix)
            self.out = bytearray(json.dumps(value).encode())
            self.code, self.eof_received = 0, True

    def exit_status_ready(self):
        return self.code is not None


class EndpointSession(Session):
    def __init__(self, client, endpoint):
        super().__init__(endpoint, client.identity.fingerprint, client.mutex)
        self.client = client
        self.io_lock = threading.Lock()
        self.read_sizes = []
        self.renames = 0
        self.hook = lambda *args: None

    def open_probe_channel(self, timeout):
        self.validate_probe_session()
        return EndpointChannel(self)

    @property
    def closed_quiescent(self):
        return self.closed and not self.io_lock.locked()


class EndpointClient(Client):
    def __init__(self, root, mutex, run_base):
        super().__init__(root, mutex)
        self.run_base = run_base
        self.commands = []
        self.lose_start_ack = False

    def connect_verified(self, endpoint, cancel):
        value = EndpointSession(self, endpoint)
        self.sessions.append(value)
        return value


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("No network"))
    # Replace only this test's compiler output with the explicitly nontraining child.
    # IR, saved revision/hash, bundle sealing and all production adapters remain real.
    import easyai.compiler.pipeline as pipeline

    original = pipeline.compile_project

    def nontraining(document):
        compiled = original(document)
        producer = compiled.program.training.before[0].id
        artifact = f"""
import hashlib
raw = {png()!r}
(root / "outputs").mkdir(exist_ok=True)
(root / "outputs/synthetic.png").write_bytes(raw)
emit_event("artifact_created", {producer!r}, {{
    "artifactId": "synthetic-image", "runId": config["runId"], "kind": "figure",
    "relativePath": "outputs/synthetic.png", "mimeType": "image/png",
    "sizeBytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    "producerBlockId": {producer!r}, "contributorBlockIds": [{producer!r}],
    "phase": "before", "syncState": "pending",
}})
"""
        child = CHILD
        child = child.replace(
            'emit_event("runtime_started", None, {})',
            'emit_event("runtime_started", None, {})' + artifact,
        )
        compiled.result.code = child
        compiled.result.code_hash = hashlib.sha256(child.encode()).hexdigest()
        return compiled

    monkeypatch.setattr(pipeline, "compile_project", nontraining)
    workspace = LocalWorkspace(tmp_path / "app")
    run_base = tmp_path / "remote-owned"
    run_base.mkdir(mode=0o700)
    endpoint = EndpointClient(tmp_path / "keys", workspace._mutex, run_base)
    workspace._ssh_client = endpoint
    folder = tmp_path / "project"
    folder.mkdir()
    session = workspace.create(
        workspace.select("project", folder).selection_id, "offline", "mnist-cnn"
    )
    project = session.project
    workspace._connections = ConnectionManager(
        endpoint,
        workspace.identity(),
        workspace._mutex,
        workspace._identity_project,
        timer_factory=FakeTimer,
        sftp_factory=lambda channel: Sftp(channel.session),
        verify_target=workspace.verify_connection_target,
    )
    api = TestClient(create_app("offline-token", workspace=workspace))
    api.headers.update({"Authorization": "Bearer offline-token"})
    try:
        yield workspace, endpoint, api, project
    finally:
        for root in run_base.iterdir():
            if root.is_dir() and (root / "code").is_dir():
                (root / "fixture-finish").touch()
        workspace.close()


def authorize(workspace, api, project):
    req = grant(workspace.identity(), project.project_id)
    profiles = api.get("/api/v1/connections").json()
    if not profiles:
        response = api.post(
            "/api/v1/connections",
            json={
                "alias": "offline",
                "endpoint": {"host": "synthetic.invalid", "port": 22},
                "username": req.username,
            },
        )
        assert response.status_code == 201, response.text
        profile = response.json()
    else:
        profile = profiles[0]
    req = req.model_copy(
        update={"target_id": profile["targetId"], "target_revision": profile["revision"]}
    )
    response = api.post(
        "/api/v1/connections/auth/password",
        json={
            "request": req.model_dump(by_alias=True),
            "password": SYNTHETIC_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return {
        "projectId": project.project_id,
        "connectionId": response.json()["scope"]["connectionId"],
    }


def binding(h):
    workspace, endpoint, api, project = h
    control = authorize(workspace, api, project)
    discovery = api.post(
        "/api/v1/environments/discover",
        json={
            **control,
            "requestId": str(uuid4()),
            "pythonPath": PYTHON,
        },
    )
    assert discovery.status_code == 200, discovery.text
    probe_id = str(uuid4())
    probe = api.post(
        "/api/v1/environments/probe",
        json={
            **control,
            "requestId": probe_id,
            "environmentId": discovery.json()["environments"][0]["environmentId"],
            "device": "cpu",
            "dataset": {"name": "MNIST", "dataRoot": "/synthetic-data"},
        },
    )
    assert probe.status_code == 200, probe.text
    from easyai.compiler.pipeline import compile_project

    program_hash = compile_project(project).result.program_hash
    body = {
        **control,
        "requestId": str(uuid4()),
        "probeRequestId": probe_id,
        "expectedRevision": project.revision,
        "expectedProgramHash": program_hash,
        "runBase": str(endpoint.run_base),
    }
    bound = api.post(f"/api/v1/projects/{project.project_id}/run-bindings", json=body)
    assert bound.status_code == 200, bound.text
    request = {
        "runner": "ssh",
        "bindingId": bound.json()["bindingId"],
        "expectedRevision": project.revision,
        "expectedProgramHash": program_hash,
    }
    return control, body, request


def wait_for(read, predicate, timeout=8):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        value = read()
        if predicate(value):
            return value
        time.sleep(0.03)
    raise AssertionError(repr(value))


def test_public_start_real_owner_cached_reads_idempotency_and_incomplete_success(harness):
    workspace, endpoint, api, project = harness
    control, body, request = binding(harness)
    route = f"/api/v1/projects/{project.project_id}/runs"
    for field in ("command", "bundle", "runRoot", "pythonExecutable", "password"):
        rejected = api.post(
            route, json={**request, field: "DO_NOT_ECHO"}, headers={"Idempotency-Key": "bad"}
        )
        assert rejected.status_code == 422 and "DO_NOT_ECHO" not in rejected.text
    started = api.post(route, json=request, headers={"Idempotency-Key": "one"})
    assert started.status_code == 202, started.text
    run_id = started.json()["runId"]
    base = f"/api/v1/runs/{run_id}"
    run = wait_for(lambda: api.get(base).json(), lambda r: r["status"] == "RUNNING")
    assert run["config"]["device"] == "cpu" and run["config"]["dataRoot"] == "/synthetic-data"
    assert len((endpoint.run_base / run_id / "fixture-starts").read_text().splitlines()) == 1
    retry = api.post(route, json=request, headers={"Idempotency-Key": "one"})
    assert retry.status_code == 202 and retry.json()["runId"] == run_id
    conflict = api.post(route, json=request, headers={"Idempotency-Key": "two"})
    assert conflict.status_code == 409, conflict.text
    (endpoint.run_base / run_id / "fixture-finish").touch()
    run = wait_for(lambda: api.get(base).json(), lambda r: r["syncState"] == "error")
    assert run["status"] == "COMPLETED" and not run["remote"]["artifactsVerified"]
    assert endpoint.commands.count("--start") == 1
    # No owner remains; all HTTP views and journal reads are cached and scoped.
    calls = sum(s.channel_calls for s in endpoint.sessions)
    assert "标准库" in api.get(base + "/logs").json()["stdout"]
    assert api.get(base + "/source").status_code == 200
    artifacts = api.get(base + "/artifacts").json()
    assert len(artifacts) == 1 and artifacts[0]["syncState"] == "ready"
    content = base + "/artifacts/synthetic-image/content"
    assert api.get(content).content == png()
    cache = workspace.runs._directory(run_id) / "cache/artifacts/artifact-index.json"
    original_index = cache.read_bytes()
    index = json.loads(original_index)
    index["artifacts"][0]["phase"] = "after"
    cache.write_text(json.dumps(index))
    assert api.get(content).status_code == 422
    cache.write_bytes(original_index)
    assert api.get(base + "/events").status_code == 200
    assert sum(s.channel_calls for s in endpoint.sessions) == calls
    workspace.connections().close(
        __import__(
            "easyai.domain.connections", fromlist=["SessionControl"]
        ).SessionControl.model_validate(control)
    )
    workspace.connections().wait_idle()
    assert (
        api.post(route, json=request, headers={"Idempotency-Key": "one"}).json()["runId"] == run_id
    )
    assert endpoint.commands.count("--start") == 1
    assert api.get("/api/v1/local/activity").json()["activeRunIds"] == []


def test_binding_requires_current_evidence_and_scoped_reads(harness):
    workspace, endpoint, api, project = harness
    control, body, request = binding(harness)
    route = f"/api/v1/projects/{project.project_id}/runs"
    invalid = api.post(
        route,
        json={**request, "expectedProgramHash": "0" * 64},
        headers={"Idempotency-Key": "changed"},
    )
    assert invalid.status_code == 422 and not endpoint.commands
    workspace._remote_bindings[request["bindingId"]] = (
        *workspace._remote_bindings[request["bindingId"]][:3],
        0.0,
        workspace._remote_bindings[request["bindingId"]][4],
    )
    expired = api.post(route, json=request, headers={"Idempotency-Key": "expired"})
    assert expired.status_code == 422 and not endpoint.commands
    assert api.get(f"/api/v1/runs/{uuid4()}").status_code == 404


def test_restart_is_inspect_only_fresh_auth_and_cancel_waits_actual_owner(harness):
    workspace, endpoint, api, project = harness
    _, _, request = binding(harness)
    route = f"/api/v1/projects/{project.project_id}/runs"
    started = api.post(route, json=request, headers={"Idempotency-Key": "restart"})
    assert started.status_code == 202
    run_id = started.json()["runId"]
    base = f"/api/v1/runs/{run_id}"
    wait_for(lambda: api.get(base).json(), lambda r: r["status"] == "RUNNING")
    workspace.close()
    reopened = LocalWorkspace(workspace.root)
    try:
        reopened.open(reopened.select("project", endpoint.run_base.parent / "project").selection_id)
        second_endpoint = EndpointClient(endpoint.store.root, reopened._mutex, endpoint.run_base)
        reopened._ssh_client = second_endpoint
        reopened._connections = ConnectionManager(
            second_endpoint,
            reopened.identity(),
            reopened._mutex,
            reopened._identity_project,
            timer_factory=FakeTimer,
            sftp_factory=lambda channel: Sftp(channel.session),
            verify_target=reopened.verify_connection_target,
        )
        second = TestClient(create_app("offline-token", workspace=reopened))
        second.headers.update({"Authorization": "Bearer offline-token"})
        recovered = second.get(base).json()
        assert recovered["status"] == "RUNNING" and recovered["connectionState"] == "disconnected"
        assert not second_endpoint.sessions and not second_endpoint.commands
        retry = second.post(route, json=request, headers={"Idempotency-Key": "restart"})
        assert retry.json()["runId"] == run_id and not second_endpoint.sessions
        cancelled = second.post(base + "/cancel")
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "CANCELLING"
        assert cancelled.json()["remote"]["cancelState"] == "pending"
        control = authorize(reopened, second, project)
        resumed = second.post(base + "/resume", json=control)
        assert resumed.status_code == 202, resumed.text
        result = wait_for(lambda: second.get(base).json(), lambda r: r["syncState"] == "complete")
        assert result["status"] == "CANCELLED" and result["remote"]["cancelState"] == "resolved"
        assert "--start" not in second_endpoint.commands
        assert endpoint.commands.count("--start") == 1
        assert len((endpoint.run_base / run_id / "fixture-starts").read_text().splitlines()) == 1
        # Opening another project immediately removes all historical run read access.
        folder = endpoint.run_base.parent / "other"
        folder.mkdir()
        reopened.create(reopened.select("project", folder).selection_id, "other", "blank")
        for suffix in ("", "/events", "/source", "/logs", "/artifacts"):
            assert second.get(base + suffix).status_code == 404
    finally:
        reopened.close()


def test_cancel_before_start_is_durable_and_releases_project(harness):
    workspace, endpoint, api, project = harness
    _, _, request = binding(harness)
    # Stop before begin by using the exact same production prepare authority.
    from easyai.domain.remote_execution import RemoteRunStartRequest
    from easyai.domain.connections import SessionControl

    stored = workspace._remote_bindings[request["bindingId"]]
    bound, _, _, _, evidence = stored
    auth = workspace.connections().current(
        SessionControl(project_id=project.project_id, connection_id=bound.connection_id)
    )
    run = workspace.runs.remote.prepare(
        workspace._projects[project.project_id],
        RemoteRunStartRequest.model_validate(request),
        "before",
        bound,
        auth,
        evidence,
    )
    cancelled = api.post(f"/api/v1/runs/{run.run_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["syncState"] == "complete"
    core = workspace.runs.remote.core(run.run_id)
    assert core.checkpoint().cancelled_before_start
    assert core.checkpoint().start_outcome == "not_attempted"
    assert not endpoint.commands
    next_run = api.post(
        f"/api/v1/projects/{project.project_id}/runs",
        json=request,
        headers={"Idempotency-Key": "after"},
    )
    assert next_run.status_code == 202, next_run.text
    next_id = next_run.json()["runId"]
    wait_for(lambda: api.get(f"/api/v1/runs/{next_id}").json(), lambda r: r["status"] == "RUNNING")
    (endpoint.run_base / next_id / "fixture-finish").touch()
    wait_for(lambda: api.get(f"/api/v1/runs/{next_id}").json(), lambda r: r["syncState"] == "error")


def test_consumed_start_lost_ack_explicit_fresh_resume_never_restarts(harness):
    workspace, endpoint, api, project = harness
    _, _, request = binding(harness)
    endpoint.lose_start_ack = True
    route = f"/api/v1/projects/{project.project_id}/runs"
    started = api.post(route, json=request, headers={"Idempotency-Key": "unknown"})
    assert started.status_code == 202
    run_id = started.json()["runId"]
    base = f"/api/v1/runs/{run_id}"
    unknown = wait_for(
        lambda: api.get(base).json(),
        lambda r: r["remote"]
        and r["remote"]["startOutcome"] == "unknown"
        and r["connectionState"] == "disconnected",
    )
    assert unknown["status"] == "STARTING"
    control = authorize(workspace, api, project)
    resumed = api.post(base + "/resume", json=control)
    assert resumed.status_code == 202, resumed.text
    wait_for(lambda: api.get(base).json(), lambda r: r["status"] == "RUNNING")
    (endpoint.run_base / run_id / "fixture-finish").touch()
    wait_for(lambda: api.get(base).json(), lambda r: r["syncState"] == "error")
    assert endpoint.commands.count("--start") == 1
    assert len((endpoint.run_base / run_id / "fixture-starts").read_text().splitlines()) == 1


def test_shared_protected_journal_provider_reopens_unknown_without_start(harness):
    from easyai.domain.connections import SessionControl
    from easyai.domain.remote_execution import RemoteRunStartRequest
    from easyai.runners.ssh import RemoteProtocolError, RemoteUnavailable
    from easyai.services.run_service import RunService
    from test_ssh_run_coordinator import Owner, Transport, auth_for

    workspace, endpoint, _, project = harness
    _, _, request = binding(harness)
    bound, _, _, _, evidence = workspace._remote_bindings[request["bindingId"]]
    auth = workspace.connections().current(
        SessionControl(project_id=project.project_id, connection_id=bound.connection_id)
    )
    run = workspace.runs.remote.prepare(
        workspace._projects[project.project_id],
        RemoteRunStartRequest.model_validate(request),
        "protected-unknown",
        bound,
        auth,
        evidence,
    )
    service = workspace.runs
    core = service.remote.core(run.run_id)
    journal = service._journal(run.run_id)
    assert core._journal is journal and not core._owns_journal
    assert journal._directory is service._log_directories[run.run_id]
    assert service._store is not None and core._store.path.is_relative_to(service.root)
    owner = Owner(core.identity)  # Synthetic owner, no remote or local execution.
    current = [auth_for(owner.identity)]
    core.attach(current[0], Transport(owner), lambda: current[0])

    def lost_ack():
        raise RemoteUnavailable("synthetic consumed start, lost ACK")

    owner.start_hook = lost_ack
    with pytest.raises(RemoteProtocolError, match="STATE_UNKNOWN"):
        core.start()
    service.remote._publish(run.run_id, core.checkpoint())
    assert service.get(run.run_id).remote.start_outcome == "unknown"
    workspace.close()
    assert journal._fd is None and not endpoint.commands
    restored = RunService(service.root)
    try:
        recovered = restored.get(run.run_id)
        assert recovered.remote.start_outcome == "unknown"
        assert recovered.connection_state == "disconnected"
        assert owner.start_calls == owner.stage_calls == 1 and owner.inspect_calls == 0
        recovered_core = restored.remote.core(run.run_id)
        assert recovered_core._journal is restored._journal(run.run_id)
        current[0] = auth_for(owner.identity)
        recovered_core.attach(current[0], Transport(owner), lambda: current[0])
        assert recovered_core.start().execution_state == "RUNNING"  # inspect only
        assert owner.start_calls == owner.stage_calls == 1 and owner.inspect_calls > 0
    finally:
        restored.close()


@pytest.mark.parametrize("replacement", ["root_symlink", "run_directory"])
def test_remote_prepare_root_swap_cannot_redirect_bundle_output(
    harness, tmp_path, monkeypatch, replacement
):
    import easyai.services.run_service as bundle
    from easyai.domain.connections import SessionControl
    from easyai.domain.remote_execution import RemoteRunStartRequest

    workspace, endpoint, _, project = harness
    _, _, request = binding(harness)
    bound, _, _, _, evidence = workspace._remote_bindings[request["bindingId"]]
    auth = workspace.connections().current(
        SessionControl(project_id=project.project_id, connection_id=bound.connection_id)
    )
    root = workspace.runs.root
    outside = tmp_path / "outside-run"
    outside.mkdir()
    original = bundle.export_bundle
    replacement_path = []

    def redirected(*args, **kwargs):
        if replacement == "root_symlink":
            root.rename(root.with_name("held-runs"))
            root.symlink_to(outside, target_is_directory=True)
            return original(*args, **kwargs)
        result = original(*args, **kwargs)
        path = kwargs["directory"].path
        path.rename(path.with_name("held-run"))
        path.mkdir(mode=0o700)
        replacement_path.append(path)
        return result

    monkeypatch.setattr(bundle, "export_bundle", redirected)
    with pytest.raises((ValueError, OSError)):
        workspace.runs.remote.prepare(
            workspace._projects[project.project_id],
            RemoteRunStartRequest.model_validate(request),
            "root-swap",
            bound,
            auth,
            evidence,
        )
    assert list(outside.iterdir()) == []
    assert all(list(path.iterdir()) == [] for path in replacement_path)
    assert not workspace.runs._ledger.entries and not endpoint.commands


def test_initialization_failure_after_core_root_swap_releases_all_quiescent_resources(
    harness, monkeypatch
):
    from easyai.domain.connections import SessionControl
    from easyai.domain.remote_execution import RemoteRunStartRequest
    from easyai.services.remote_runs import RemoteRuns
    from easyai.services.run_service import RunService
    from test_run_storage import Monitor

    workspace, endpoint, _, project = harness
    _, _, request = binding(harness)
    bound, _, _, _, evidence = workspace._remote_bindings[request["bindingId"]]
    auth = workspace.connections().current(
        SessionControl(project_id=project.project_id, connection_id=bound.connection_id)
    )
    run = workspace.runs.remote.prepare(
        workspace._projects[project.project_id],
        RemoteRunStartRequest.model_validate(request),
        "init-root-swap",
        bound,
        auth,
        evidence,
    )
    root = workspace.runs.root
    workspace.close()
    captured = []

    def fail_after_core(remote):
        core = remote.core(run.run_id)
        captured.append((core, remote.runs._journal(run.run_id)))
        root.rename(root.with_name("held-runs"))
        root.mkdir()
        raise OSError("test original recovery error")

    monkeypatch.setattr(RemoteRuns, "recover", fail_after_core)
    monitor = Monitor()
    with pytest.raises(OSError, match="original recovery error"):
        RunService(root, storage=monitor)
    monitor.assert_closed()
    assert captured[0][0]._closed and captured[0][1]._fd is None
    assert list(root.iterdir()) == [] and not endpoint.commands


def test_ssh_cancel_scope_commits_after_core_lock_and_rejects_project_switch(harness, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from easyai.domain.connections import SessionControl
    from easyai.domain.remote_execution import RemoteRunStartRequest

    workspace, endpoint, api, project = harness
    _, _, request = binding(harness)
    bound, _, _, _, evidence = workspace._remote_bindings[request["bindingId"]]
    auth = workspace.connections().current(
        SessionControl(project_id=project.project_id, connection_id=bound.connection_id)
    )
    run = workspace.runs.remote.prepare(
        workspace._projects[project.project_id],
        RemoteRunStartRequest.model_validate(request),
        "scope-before",
        bound,
        auth,
        evidence,
    )
    core = workspace.runs.remote.core(run.run_id)
    entered, release = threading.Event(), threading.Event()
    original = workspace.run_commit_scope

    @contextmanager
    def paused(scope):
        # The request has acquired the real coordinator lock, but has not taken WS.
        assert core._mutex._is_owned() and not workspace._mutex._is_owned()
        entered.set()
        assert release.wait(2)
        with original(scope):
            yield

    monkeypatch.setattr(workspace, "run_commit_scope", paused)
    with ThreadPoolExecutor() as pool:
        response = pool.submit(api.post, f"/api/v1/runs/{run.run_id}/cancel")
        assert entered.wait(2)
        folder = endpoint.run_base.parent / "other-scope"
        folder.mkdir()
        workspace.create(workspace.select("project", folder).selection_id, "B", "blank")
        release.set()
        result = response.result(3)
    assert result.status_code == 404, result.text
    assert core.checkpoint().cancel_state == "none" and not core.checkpoint().cancelled_before_start
    assert workspace.runs.get(run.run_id).status == "CREATED"
    assert not endpoint.commands


def test_unverified_cache_platform_refuses_binding_and_prepare_without_staging(
    harness, monkeypatch
):
    from types import SimpleNamespace
    import easyai.security.remote_cache as storage

    workspace, endpoint, api, project = harness
    _, body, request = binding(harness)
    entries = set(workspace.runs.root.iterdir())
    bindings = set(workspace._remote_bindings)
    calls = sum(session.channel_calls for session in endpoint.sessions)
    # Capability-provider injection only, not Windows filesystem emulation.
    with monkeypatch.context() as capability:
        capability.setattr(storage, "os", SimpleNamespace(name="nt"))
        refused = api.post(f"/api/v1/projects/{project.project_id}/run-bindings", json=body)
        assert (
            refused.status_code == 422
            and refused.json()["error"]["code"] == "REMOTE_CACHE_PLATFORM_UNVERIFIED"
        )
        refused = api.post(
            f"/api/v1/projects/{project.project_id}/runs",
            json=request,
            headers={"Idempotency-Key": "unsupported"},
        )
        assert (
            refused.status_code == 422
            and refused.json()["error"]["code"] == "REMOTE_CACHE_PLATFORM_UNVERIFIED"
        )
    assert not workspace.runs._ledger.entries
    assert set(workspace.runs.root.iterdir()) == entries
    assert set(workspace._remote_bindings) == bindings
    assert sum(session.channel_calls for session in endpoint.sessions) == calls
    assert not endpoint.commands and list(endpoint.run_base.iterdir()) == []


def test_saved_profile_stable_binding_active_identity_guard_and_frozen_run(harness, monkeypatch):
    workspace, _, api, project = harness
    _, body, request = binding(harness)
    first = workspace._remote_bindings[request["bindingId"]][0]
    again = api.post(
        f"/api/v1/projects/{project.project_id}/run-bindings",
        json={**body, "requestId": str(uuid4())},
    )
    assert again.status_code == 200, again.text
    profile = api.get("/api/v1/connections").json()[0]
    assert first.target_id == again.json()["targetId"] == profile["targetId"]
    # Prepare a real immutable run but do not stage/start any remote process.
    monkeypatch.setattr(
        workspace.runs.remote, "begin", lambda run_id, *args, **kwargs: workspace.runs.get(run_id)
    )
    started = api.post(
        f"/api/v1/projects/{project.project_id}/runs",
        json=request,
        headers={"Idempotency-Key": "profile-freeze-test"},
    )
    assert started.status_code == 202, started.text
    run_id = started.json()["runId"]
    config = workspace.runs.get(run_id).config.model_dump_json()
    identity = workspace.runs._ledger.entries[run_id].remote_identity.model_dump_json()
    before = workspace.profiles.path.read_bytes()
    changed = {
        "alias": "renamed",
        "endpoint": {"host": "other.invalid", "port": 22},
        "username": profile["username"],
        "expectedRevision": 1,
    }
    response = api.patch(f"/api/v1/connections/{first.target_id}", json=changed)
    assert response.status_code == 409 and workspace.profiles.path.read_bytes() == before
    changed["endpoint"] = profile["endpoint"]
    response = api.patch(f"/api/v1/connections/{first.target_id}", json=changed)
    assert response.status_code == 200 and response.json()["revision"] == 2
    assert workspace.runs.get(run_id).config.model_dump_json() == config
    assert workspace.runs._ledger.entries[run_id].remote_identity.model_dump_json() == identity


@pytest.mark.parametrize("failure", ["publish_then_error", "external_change"])
def test_changed_profile_cannot_start_old_binding(harness, monkeypatch, failure):
    from easyai.domain.connections import ConnectionProfileUpdate, SessionControl
    from easyai.domain.remote_execution import RemoteRunStartRequest
    from easyai.domain.ssh import SshFailure
    from easyai.services.project_service import ProjectService

    workspace, _, api, project = harness
    control, _, request = binding(harness)
    profile = workspace.list_connection_profiles()[0]
    update = ConnectionProfileUpdate(
        alias="changed",
        endpoint={"host": "other.invalid", "port": 22},
        username=profile.username,
        expected_revision=1,
    )
    if failure == "publish_then_error":
        original = ProjectService.atomic_write

        def fail_after_publish(path, payload):
            original(path, payload)
            if path == workspace.profiles.path:
                raise OSError("synthetic directory fsync failed after replace")

        monkeypatch.setattr(ProjectService, "atomic_write", staticmethod(fail_after_publish))
        with pytest.raises(OSError, match="synthetic directory fsync"):
            workspace.update_connection_profile(profile.target_id, update)
        assert not workspace._remote_bindings
        assert workspace.connections().current(SessionControl.model_validate(control)) is None
    else:
        # Even out-of-band catalog changes cannot revive a cached authority.
        workspace.profiles.update(profile.target_id, update, lambda _: None)
    assert workspace.list_connection_profiles()[0].endpoint.host == "other.invalid"
    with pytest.raises(
        (ValueError, SshFailure),
        match="REMOTE_BINDING_EXPIRED|SSH_SESSION_INVALID|SSH_TARGET_REFERENCE_STALE",
    ):
        workspace.start(
            project.project_id, RemoteRunStartRequest.model_validate(request), "must-not-prepare"
        )
    assert not workspace.runs._ledger.entries


def test_updating_profile_a_does_not_retire_unrelated_b_lease(harness):
    workspace, _, api, project = harness
    from easyai.domain.connections import SessionControl

    first = api.post(
        "/api/v1/connections",
        json={
            "alias": "A",
            "endpoint": {"host": "synthetic.invalid", "port": 22},
            "username": "synthetic-user",
        },
    ).json()
    second = api.post(
        "/api/v1/connections",
        json={
            "alias": "B",
            "endpoint": {"host": "synthetic.invalid", "port": 22},
            "username": "synthetic-user",
        },
    ).json()
    req = grant(workspace.identity(), project.project_id).model_copy(
        update={
            "target_id": second["targetId"],
            "target_revision": 1,
            "username": second["username"],
        }
    )
    response = api.post(
        "/api/v1/connections/auth/password",
        json={"request": req.model_dump(by_alias=True), "password": SYNTHETIC_PASSWORD},
    )
    assert response.status_code == 200, response.text
    auth = response.json()
    changed = api.patch(
        f"/api/v1/connections/{first['targetId']}",
        json={
            "alias": "new A",
            "endpoint": {"host": "other.invalid", "port": 22},
            "username": "synthetic-user",
            "expectedRevision": 1,
        },
    )
    assert changed.status_code == 200, changed.text
    current = workspace.connections().current(
        SessionControl(project_id=project.project_id, connection_id=auth["scope"]["connectionId"])
    )
    assert current is not None and current.target_id == second["targetId"]


def test_running_png_sync_pause_resume_keeps_training_owner_and_rejects_retired_scope(
    harness, monkeypatch
):
    workspace, endpoint, api, project = harness
    _, _, request = binding(harness)
    entered, release = threading.Event(), threading.Event()
    retired, resume_return = threading.Event(), threading.Event()
    paused_once = []
    from easyai.services.remote_runs import RemoteRuns

    original_progress = RemoteRuns._sync_progress

    def hold_paused(self, run_id, owner, **kwargs):
        original_progress(self, run_id, owner, **kwargs)
        if (
            kwargs.get("state") == "paused"
            and threading.current_thread().name.startswith("easyai-run-")
            and not retired.is_set()
        ):
            retired.set()
            assert resume_return.wait(4)

    monkeypatch.setattr(RemoteRuns, "_sync_progress", hold_paused)

    def block(action, path):
        if action == "read" and path.name == "synthetic.png" and not paused_once:
            entered.set()
            assert release.wait(4)
            paused_once.append(True)

    endpoint.sessions[-1].hook = block
    response = api.post(
        f"/api/v1/projects/{project.project_id}/runs",
        json=request,
        headers={"Idempotency-Key": "live-sync"},
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["runId"]
    base = f"/api/v1/runs/{run_id}"
    try:
        assert entered.wait(5)
        paused = api.post(base + "/artifacts/sync/pause")
        assert paused.status_code == 200, paused.text
        assert paused.json()["artifactSync"]["state"] == "cleanup_pending"
        assert api.get(base).json()["status"] == "RUNNING"
        assert "--cancel" not in endpoint.commands
        assert api.get(base + "/artifacts").json()[0]["syncState"] == "pending"
    finally:
        release.set()
    run = wait_for(
        lambda: api.get(base).json(),
        lambda value: value.get("artifactSync", {}).get("state") == "paused",
    )
    assert run["status"] == "RUNNING" and run["syncState"] == "pending"
    assert retired.wait(2)
    try:
        resumed = api.post(base + "/artifacts/sync/resume")
        assert resumed.status_code == 200, resumed.text
    finally:
        resume_return.set()
    try:
        files = wait_for(
            lambda: api.get(base + "/artifacts").json(),
            lambda values: values and values[0]["syncState"] == "ready",
        )
    except AssertionError:
        owner = workspace.runs.remote._workers[run_id]
        raise AssertionError(
            (
                api.get(base).json(),
                owner.thread.is_alive(),
                owner.paused,
                endpoint.sessions[-1].closed,
                endpoint.commands,
            )
        ) from None
    current = api.get(base).json()
    assert current["status"] == "RUNNING" and not current["remote"]["artifactsVerified"]
    assert current["artifactSync"]["verifiedBytes"] == len(png())
    assert current["artifactSync"]["receivedBytes"] == len(png())
    image = api.get(base + "/artifacts/" + files[0]["artifactId"] + "/content")
    assert image.status_code == 200 and image.content == png()
    assert endpoint.commands.count("--start") == 1 and "--cancel" not in endpoint.commands
    # Real coordinator snapshot validated receipt against committed raw event bytes.
    core = workspace.runs.remote.core(run_id)
    checkpoint = core.checkpoint()
    assert checkpoint.last_observation.artifact_receipt is not None
    (endpoint.run_base / run_id / "fixture-finish").touch()
    final = wait_for(lambda: api.get(base).json(), lambda value: value["syncState"] == "error")
    assert final["status"] == "COMPLETED" and not final["remote"]["artifactsVerified"]
    # Missing final model/figures cannot turn the structural PNG into training success.
    other = endpoint.run_base.parent / "other-project"
    other.mkdir()
    workspace.create(workspace.select("project", other).selection_id, "other", "mnist-cnn")
    assert api.post(base + "/artifacts/sync/pause").status_code == 404


@pytest.mark.parametrize("fault", ["receipt_read", "cache_commit"])
def test_restart_cancel_sync_fault_records_only_fixed_diagnostic_and_can_reconnect(
    harness, monkeypatch, fault
):
    from easyai.security.remote_cache import _PosixDirectory

    workspace, endpoint, api, project = harness
    _, _, request = binding(harness)
    route = f"/api/v1/projects/{project.project_id}/runs"
    started = api.post(route, json=request, headers={"Idempotency-Key": "restart-diagnostic"})
    assert started.status_code == 202
    run_id = started.json()["runId"]
    base = f"/api/v1/runs/{run_id}"
    wait_for(lambda: api.get(base).json(), lambda r: r["status"] == "RUNNING")
    workspace.close()
    reopened = LocalWorkspace(workspace.root)
    armed = [True]
    secret = "REMOTE_ARTIFACT_FAILED SECRET_SENTINEL /private/server/path"
    original_open, original_publish = Sftp.open, _PosixDirectory.publish

    def fail_read(self, path, mode, **kwargs):
        if armed[0] and fault == "receipt_read" and Path(path).name.startswith("remote-artifacts-"):
            raise OSError(secret)
        return original_open(self, path, mode, **kwargs)

    def fail_commit(self, source, target, **kwargs):
        if armed[0] and fault == "cache_commit" and target == "artifact-index.json":
            raise OSError(secret)
        return original_publish(self, source, target, **kwargs)

    monkeypatch.setattr(Sftp, "open", fail_read)
    monkeypatch.setattr(_PosixDirectory, "publish", fail_commit)
    try:
        reopened.open(reopened.select("project", endpoint.run_base.parent / "project").selection_id)
        second_endpoint = EndpointClient(endpoint.store.root, reopened._mutex, endpoint.run_base)
        reopened._ssh_client = second_endpoint
        reopened._connections = ConnectionManager(
            second_endpoint,
            reopened.identity(),
            reopened._mutex,
            reopened._identity_project,
            timer_factory=FakeTimer,
            sftp_factory=lambda channel: Sftp(channel.session),
            verify_target=reopened.verify_connection_target,
        )
        second = TestClient(create_app("offline-token", workspace=reopened))
        second.headers.update({"Authorization": "Bearer offline-token"})
        assert second.post(base + "/cancel").json()["remote"]["cancelState"] == "pending"
        control = authorize(reopened, second, project)
        assert second.post(base + "/resume", json=control).status_code == 202
        failed = wait_for(lambda: second.get(base).json(), lambda r: r["syncState"] == "error")
        assert failed["status"] == "CANCELLING" and failed["connectionState"] == "disconnected"
        assert failed["remote"]["executionState"] == "RUNNING"
        assert failed["remote"]["cancelState"] == "acknowledged"
        assert failed["artifactSync"]["failure"] == {"stage": fault, "code": "SYNC_IO_FAILED"}
        events = reopened.runs.events(run_id, 0)
        failures = [event for event in events if event.type == "artifact_sync_failed"]
        assert failures[-1].payload == {
            "failure": {"stage": fault, "code": "SYNC_IO_FAILED"},
            "cleanupFailure": None,
        }
        assert all(
            "SECRET_SENTINEL" not in event.model_dump_json()
            and "/private/server/path" not in event.model_dump_json()
            for event in events
        )
        assert "SECRET_SENTINEL" not in json.dumps(failed)
        assert "--start" not in second_endpoint.commands
        reopened.runs.remote._workers[run_id].thread.join(2)
        armed[0] = False
        fresh = authorize(reopened, second, project)
        assert second.post(base + "/resume", json=fresh).status_code == 202
        final = wait_for(lambda: second.get(base).json(), lambda r: r["syncState"] == "complete")
        assert final["status"] == "CANCELLED" and final["artifactSync"]["failure"] is None
        assert endpoint.commands.count("--start") == 1 and "--start" not in second_endpoint.commands
        # Retain the earlier fixed failure event even after an explicit successful retry.
        assert any(
            event.type == "artifact_sync_failed" for event in reopened.runs.events(run_id, 0)
        )
    finally:
        armed[0] = False
        reopened.close()


def test_acceptance_resume_waits_exact_old_worker_without_restarting(harness, monkeypatch):
    from easyai.domain.connections import SessionControl
    from easyai.domain.remote_execution import RemoteRunStartRequest
    from test_ssh_acceptance_entry import entry

    workspace, endpoint, api, project = harness
    control, _, request = binding(harness)
    started = workspace.start(
        project.project_id,
        RemoteRunStartRequest.model_validate(request),
        "acceptance-worker-barrier",
    )
    wait_for(lambda: workspace.runs.get(started.run_id), lambda r: r.status == "RUNNING")
    old = workspace.runs.remote._workers[started.run_id].thread
    core = workspace.runs.remote.core(started.run_id)
    entered, release = threading.Event(), threading.Event()
    disconnect = core.disconnect
    authentications = []

    def blocked_disconnect():
        if threading.current_thread() is old:
            entered.set()
            assert release.wait(5)
        disconnect()

    monkeypatch.setattr(core, "disconnect", blocked_disconnect)
    original_wait = workspace.connections().wait_idle

    def closed_connection():
        original_wait()
        assert entered.wait(2)

    monkeypatch.setattr(workspace.connections(), "wait_idle", closed_connection)

    def fresh():
        authentications.append(True)
        return SessionControl.model_validate(authorize(workspace, api, project))

    # Release only through the new bounded wait seam. Old code attempts resume
    # while the worker is deterministically alive and raises REMOTE_RUN_BUSY.
    wait_owner = getattr(workspace.runs.remote, "wait_worker_exit", None)
    if wait_owner is not None:

        def release_then_wait(run_id, seconds):
            assert run_id == started.run_id and old.is_alive()
            with pytest.raises(ValueError, match="REMOTE_RUN_BUSY"):
                wait_owner(run_id, 0.01)
            assert old.is_alive() and workspace.runs.remote._workers[run_id].thread is old
            assert endpoint.commands.count("--start") == 1
            release.set()
            return wait_owner(run_id, seconds)

        monkeypatch.setattr(workspace.runs.remote, "wait_worker_exit", release_then_wait)
    try:
        restored = entry.resume_after_disconnect(
            workspace, started.run_id, SessionControl.model_validate(control), fresh, lambda: None
        )
        assert restored.connection_id != control["connectionId"]
        assert authentications == [True]
        assert endpoint.commands.count("--start") == 1
    finally:
        release.set()
