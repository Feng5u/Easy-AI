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
