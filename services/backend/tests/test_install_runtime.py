"""Controlled protocol fixtures only: no conda/pip/installation or genuine tensor PASS."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import socket
import sys
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.domain.install import InstallConfirmation, InstallInspection, InstallPlanRequest
from easyai.services import install_runtime as runtime_module
from easyai.services.install_runtime import Capability, InstallRuntime, protected, tree
from easyai.services.install_service import InstallService
from easyai.services.install_process import (
    HEADER,
    ManagedInstallCommand,
    ManagedInstallInspector,
    _event,
)
from easyai.services.local_workspace import LocalWorkspace
from easyai.services.owned_creation import OwnedCreation, require_ready
from test_owned_creation import Bootstrap, InstallFixture


def request():
    return InstallPlanRequest(
        target_id="local",
        profile_id="easyai-cpu",
        package_ids=["torch"],
        new_environment_spec={"name": "controlled"},
    )


def confirmation(plan):
    return InstallConfirmation(
        plan_id=plan.plan_id, plan_hash=plan.plan_hash, confirmed=True, network_acknowledged=True
    )


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: pytest.fail("No network in installation protocol tests"),
    )


@pytest.fixture
def configured(tmp_path, monkeypatch):
    app = tmp_path / "app"
    app.mkdir(mode=0o700)
    sources = tmp_path / "sources"
    sources.mkdir(mode=0o700)
    launcher = sources / "nonexecuted-launcher"
    launcher.write_bytes(b"fixture only: never execute")
    launcher.chmod(0o700)
    modules = sources / "approved-modules"
    (modules / "conda").mkdir(parents=True)
    (modules / "conda/__init__.py").write_text("__version__='25.9.1'\n")

    def artifact(path):
        return {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    archives = []
    for name in ("python-3.11.17-fixture.conda", "pip-fixture.conda"):
        path = sources / name
        path.write_bytes(b"synthetic manifest fixture; not an install archive")
        archives.append(artifact(path))
    wheels = sources / "wheels"
    wheels.mkdir()
    wheel = wheels / "torch-fixture.whl"
    wheel.write_bytes(b"not a wheel; never install")
    profiles = sources / "profile"
    profiles.mkdir()
    (profiles / "easyai-cpu-sources.json").write_text(
        json.dumps(
            {
                "packages": [
                    {
                        "name": "torch",
                        "version": "fixture",
                        "filename": wheel.name,
                        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                        "downloadBytes": wheel.stat().st_size,
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(
        runtime_module, "PROFILE_ROOT", profiles
    )  # Synthetic source inventory, not production lock replacement.
    config = {
        "schemaVersion": 1,
        "condaVersion": "25.9.1",
        "launcher": artifact(launcher),
        "moduleRoot": str(modules),
        "moduleTreeSha256": tree(modules),
        "bootstrap": archives,
        "wheelhouse": str(wheels),
        "diskBudgetBytes": 100000,
        "seconds": 30,
        "executionAuthorized": True,
        "authorizationExpires": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }
    path = app / "install-runtime.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    return app, sources, config


def test_missing_runtime_injects_real_inspector_but_does_not_enable_or_spawn(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda *args, **kwargs: pytest.fail("Unconfigured planning cannot spawn"),
    )
    workspace = LocalWorkspace(tmp_path / "app")
    try:
        service = workspace.installs()
        assert isinstance(service._inspector, ManagedInstallInspector)
        plan = service.plan(request())
        assert not plan.execution_enabled and plan.runtime_fingerprint is None
        job = service.confirm(confirmation(plan))
        assert job.state == "AWAITING_EXECUTION" and not service._workers
    finally:
        workspace.close()


def test_fixed_conda_contract_is_captured_not_executed_and_rejects_unknown_prefix(
    configured, monkeypatch
):
    app, _, _ = configured
    runtime = InstallRuntime(app)
    service = InstallService(app, runtime=runtime, inspector=runtime.inspector)
    plan = service.plan(request())
    assert plan.execution_enabled and not plan.requires_network and plan.download_bytes == 0
    creation = OwnedCreation(app, plan.environment_id, str(uuid4()), plan.plan_hash)
    lease = creation.reserve()
    prefix = creation.allocate()
    calls = []

    def capture(argv, cwd, cancel, progress, *, environment):
        assert argv[1:5] == ["-I", "-S", "-B", "-c"]
        compile(argv[5], "<fixed-conda-contract>", "exec")  # Never exec the launcher or conda.
        assert "'--offline'" in argv[5] and "'--no-default-packages'" in argv[5]
        assert "'--no-plugins'" in argv[5] and "'--copy'" in argv[5]
        assert "--force" not in argv[5] and "--clone" not in argv[5]
        assert "CONDA_PREFIX" not in environment and "PYTHONPATH" not in environment
        assert environment["CONDA_OFFLINE"] == "true"
        work = next(runtime.commands.root.glob("bootstrap-*"))
        lines = (work / "explicit.txt").read_text().splitlines()
        assert lines[0] == "@EXPLICIT" and all(
            s.startswith("file://") and "#" in s for s in lines[1:]
        )
        calls.append(True)
        progress()
        return "failed", []  # Captured command is never an install success.

    monkeypatch.setattr(runtime.commands, "run", capture)
    try:
        assert (
            runtime.provisioner.create(prefix, plan, threading.Event(), creation.verify) == "failed"
        )
        assert calls == [True] and not (prefix / ".easyai-owned.json").exists()
        (prefix / "unknown").write_bytes(b"preserve")
        with pytest.raises(ValueError, match="INSTALL_BOOTSTRAP_PREFIX_NOT_EMPTY"):
            runtime.provisioner.create(prefix, plan, threading.Event(), creation.verify)
        assert calls == [True] and (prefix / "unknown").read_bytes() == b"preserve"
    finally:
        lease.close()
        service.close()


def test_source_drift_after_plan_fails_before_unique_worker(configured):
    app, _, config = configured
    runtime = InstallRuntime(app)
    service = InstallService(app, runtime=runtime, inspector=runtime.inspector)
    plan = service.plan(request())
    Path(config["bootstrap"][0]["path"]).write_bytes(b"changed source")
    try:
        with pytest.raises(ValueError, match="INSTALL_SOURCE_CHANGED"):
            service.confirm(confirmation(plan))
        assert not service._workers and not service._jobs
    finally:
        service.close()


def test_unsafe_nonsticky_ancestor_rejected_before_hash_or_spawn(tmp_path):
    parent = tmp_path / "unsafe"
    parent.mkdir(mode=0o777)
    parent.chmod(0o777)
    leaf = parent / "source.py"
    leaf.write_bytes(b"harmless")
    leaf.chmod(0o600)
    with pytest.raises(ValueError, match="DIRECTORY_UNSAFE"):
        protected(leaf)


class ControlledRuntime:
    """Reuses earlier synthetic inventories, never represents actual imports/tensors."""

    def __init__(self, root, installer=None):
        self.root = root
        self.provisioner = Bootstrap()
        self.executor = installer or InstallFixture()
        self.inspector = lambda prefix, nonce: InstallInspection(
            nonce=nonce,
            prefix=str(prefix),
            python_version="3.11.17",
            **json.loads((prefix / "bootstrap.json").read_bytes()),
        )
        self.cancel_requested = threading.Event()

    def snapshot(self):
        return Capability("a" * 64, True, 1, 1000000)

    @contextmanager
    def job(self, cancel):
        yield

    def budget(self, prefix, limit):
        pass

    def request_cancel(self):
        self.cancel_requested.set()


def test_http_confirmation_replay_registers_one_worker_and_controlled_reprobe(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(runtime_module, "InstallRuntime", ControlledRuntime)
    monkeypatch.setattr(
        "subprocess.Popen", lambda *args, **kwargs: pytest.fail("Controlled adapter only")
    )
    workspace = LocalWorkspace(tmp_path / "app")
    client = TestClient(create_app("controlled-token", workspace=workspace))
    client.headers.update({"Authorization": "Bearer controlled-token"})
    try:
        response = client.post(
            "/api/v1/environments/install-plan", json=request().model_dump(by_alias=True)
        )
        assert response.status_code == 200
        plan = response.json()
        body = {
            "planId": plan["planId"],
            "planHash": plan["planHash"],
            "confirmed": True,
            "networkAcknowledged": True,
        }
        first = client.post("/api/v1/install-jobs", json=body)
        second = client.post("/api/v1/install-jobs", json=body)
        assert first.status_code == second.status_code == 202
        assert first.json()["jobId"] == second.json()["jobId"]
        service = workspace.installs()
        assert len(service._workers) == 1
        worker = next(iter(service._workers.values()))
        worker.join(2)
        job = service.get(first.json()["jobId"])
        assert job.state == "SUCCEEDED" and job.verified  # Synthetic inspector inventory only.
        require_ready(workspace.root, job.environment_id, service.root / job.environment_id)
    finally:
        workspace.close()


def test_close_timeout_keeps_journal_and_lease_until_same_worker_finishes(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    class Blocking:
        def install(self, prefix, plan, cancel, progress):
            entered.set()
            assert release.wait(6)
            assert cancel.is_set()
            return "cancelled"

    policy = ControlledRuntime(tmp_path / "app", Blocking())
    monkeypatch.setattr(runtime_module, "InstallRuntime", lambda root: policy)
    workspace = LocalWorkspace(tmp_path / "app")
    service = workspace.installs()
    job = service.confirm(confirmation(service.plan(request())))
    assert entered.wait(2)
    try:
        with pytest.raises(ValueError, match="INSTALL_STOP_UNCONFIRMED"):
            workspace.close()
        assert policy.cancel_requested.is_set() and service._leases and service._journals
        assert not service._closed
        with workspace._mutex:  # Close did not wait while holding the workspace lock.
            assert workspace._closing
    finally:
        release.set()
        service._workers[job.job_id].join(2)
        workspace.close()
    assert service._closed and not service._leases and not service._journals
    assert service._jobs[job.job_id].state == "CANCELLED"


def test_install_command_uses_whitelist_environment_with_real_stdlib_child(tmp_path, monkeypatch):
    root = tmp_path / "commands"
    root.mkdir()
    for name in ("CONDA_PREFIX", "PIP_TARGET", "PYTHONPATH", "EASYAI_POLLUTION"):
        monkeypatch.setenv(name, "synthetic-inherited-pollution")
    code = (
        HEADER
        + "assert not any(k in os.environ for k in ('CONDA_PREFIX','PIP_TARGET','PYTHONPATH','EASYAI_POLLUTION'))\n"
        + _event("pipeline_completed")
    )
    outcome, _ = ManagedInstallCommand(root).run(
        [sys.executable, "-I", "-B", "-c", code], root, threading.Event(), lambda: None
    )
    assert outcome == "completed"  # Only stdlib protocol, never a real installation.


def test_close_budget_includes_planning_mutex_and_prevents_late_plan(tmp_path):
    app = tmp_path / "app"
    app.mkdir(mode=0o700)
    env_id = str(uuid4())
    prefix = app / "training-environments" / env_id
    prefix.mkdir(parents=True)
    (prefix / ".easyai-owned.json").write_text(
        json.dumps({"ownedByEasyAI": True, "environmentId": env_id})
    )
    entered, release = threading.Event(), threading.Event()
    errors = []

    def blocking(path, nonce):
        entered.set()
        assert release.wait(6)
        return InstallInspection(
            nonce=nonce,
            prefix=str(path),
            python_version="3.11.17",
            versions={},
            imports={},
            tensor_ok=False,
        )

    service = InstallService(app, inspector=blocking)

    def planning():
        try:
            service.plan(
                InstallPlanRequest(
                    target_id="local",
                    profile_id="easyai-cpu",
                    package_ids=["torch"],
                    owned_environment_id=env_id,
                )
            )
        except Exception as error:
            errors.append(error)

    worker = threading.Thread(target=planning)
    worker.start()
    assert entered.wait(1)
    try:
        with pytest.raises(ValueError, match="INSTALL_STOP_UNCONFIRMED"):
            service.close()
        assert service._close_requested.is_set() and not service._closed
        assert worker.is_alive()  # Timeout is not a claim that planning is quiet.
    finally:
        release.set()
        worker.join(2)
        service.close()
    assert errors and str(errors[0]) == "INSTALL_SESSION_CLOSED"
    assert not service._plans


def test_close_during_runtime_hash_cannot_publish_enabled_late_plan(tmp_path):
    app = tmp_path / "app"
    app.mkdir(mode=0o700)
    entered, release = threading.Event(), threading.Event()
    errors = []

    class Slow(ControlledRuntime):
        calls = 0

        def snapshot(self):
            self.calls += 1
            if self.calls == 2:  # catalog first, execution source snapshot second.
                entered.set()
                assert release.wait(6)
            return super().snapshot()

    runtime = Slow(app)
    service = InstallService(app, inspector=runtime.inspector, runtime=runtime)

    def planning():
        try:
            service.plan(request())
        except Exception as error:
            errors.append(error)

    worker = threading.Thread(target=planning)
    worker.start()
    assert entered.wait(1)
    try:
        with pytest.raises(ValueError, match="INSTALL_STOP_UNCONFIRMED"):
            service.close()
        assert service._close_requested.is_set()
    finally:
        release.set()
        worker.join(2)
        service.close()
    assert errors and str(errors[0]) == "INSTALL_SESSION_CLOSED" and not service._plans
