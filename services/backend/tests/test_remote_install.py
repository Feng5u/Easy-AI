"""Controlled remote protocol integration; no SSH, dependency install or imports."""

import ast
from datetime import datetime, timedelta, timezone
import json
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from easyai.domain.connections import SessionControl
from easyai.domain.install import InstallPlanRequest, InstallConfirmation, InstallTargetIdentity
from easyai.services.install_registry import InstallRegistry, remote_target_unsettled
from easyai.services.remote_install import RemoteConfiguration, RemoteConfigurations
from easyai.services.install_service import digest


class SyntheticRemote:
    """Stateful protocol fixture. Every receipt is synthetic, never runtime evidence."""

    def __init__(self, identity):
        self.identity = identity
        self.calls = []
        self.envs = {}
        self.claims = {}
        self.phases = {}
        self.source_revision = 1
        self.lose_next_reserve = False
        self.lose_next_run = False
        self.probe_failure = False
        self.free_bytes = 10**10

    def call(self, request):
        self.calls.append(request)
        action, env = request["action"], request["environmentId"]
        prefix = self.identity.root + "/training-environments/" + env
        common = dict(
            nonce=request["nonce"],
            root=self.identity.root,
            prefix=prefix,
            jobId=request.get("jobId"),
            planHash=request.get("planHash"),
        )
        record = self.envs.get(env)
        if action == "snapshot":
            return dict(
                common,
                platform="linux-x86_64-cp311",
                pythonVersion="3.11.17",
                owned=bool(record and record["owned"]),
                ready=bool(record and record["ready"]),
                prefixIdentity=[1, 2] if record else None,
                versions=record["versions"] if record else {},
                fingerprint=digest([env, record, self.source_revision]),
                sourceFingerprint=digest(
                    [self.source_revision, request["configuration"], request["wheels"]]
                ),
                bootstrapBytes=20,
                sourceBytes=30,
                freeBytes=self.free_bytes,
            )
        if action == "reserve":
            previous = self.claims.get(env)
            if previous and previous["jobId"] != request["jobId"] and not previous["closed"]:
                raise ValueError("INSTALL_ENVIRONMENT_CONFLICT")
            self.claims[env] = dict(
                jobId=request["jobId"], planHash=request["planHash"], closed=False
            )
            if self.lose_next_reserve:
                self.lose_next_reserve = False
                raise ValueError("SYNTHETIC_RESERVE_ACK_LOST")
        elif action == "allocate":
            assert env not in self.envs
            self.envs[env] = dict(owned=False, ready=False, versions={})
        elif action == "mark-owned":
            record["owned"] = True
        elif action == "mark-ready":
            record["ready"] = True
        elif action == "release":
            assert all(p["quiescent"] for p in self.phases.values())
            self.claims[env]["closed"] = True
        elif action == "run":
            phase = request["phase"]
            assert phase not in self.phases
            source = request["argv"][-1]
            if "requirements.lock" in request["files"]:
                assert "--no-index" in source and "--require-hashes" in source
                record["versions"] = {w["name"]: w["version"] for w in request["wheels"]}
                events = []
            elif "report={" in source:
                tree = ast.parse(source)
                assignment = next(
                    n
                    for n in ast.walk(tree)
                    if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "report" for t in n.targets)
                )
                nonce = ast.literal_eval(assignment.value.values[0])
                loops = [n for n in tree.body if isinstance(n, ast.For)]
                imports = ast.literal_eval(loops[1].iter)
                events = [
                    dict(
                        type="progress",
                        payload=dict(
                            nonce=nonce,
                            prefix=prefix,
                            pythonVersion="3.11.17",
                            versions=record["versions"].copy(),
                            imports={n: not self.probe_failure for n in imports},
                            tensorOk=not self.probe_failure,
                        ),
                    )
                ]
            else:
                assert "import conda" in source and "explicit.txt" in request["files"]
                events = []
            self.phases[phase] = dict(
                common, phase=phase, outcome="completed", quiescent=True, events=events
            )
            if self.lose_next_run:
                self.lose_next_run = False
                self.phases[phase].update(outcome="unknown", quiescent=False)
                raise ValueError("SYNTHETIC_ACK_LOST")
            return self.phases[phase]
        elif action in {"inspect", "cancel"}:
            phase = request.get("phase") or next(reversed(self.phases), None)
            if phase is None:
                return dict(common, outcome="not_dispatched", quiescent=True, events=[])
            result = self.phases[phase].copy()
            result["nonce"] = request["nonce"]
            return result
        return dict(common, ack=True, prefixIdentity=[1, 2])


@pytest.fixture(autouse=True)
def no_external_execution(monkeypatch):
    monkeypatch.setattr(
        "subprocess.Popen", lambda *a, **k: pytest.fail("No remote tools or installs")
    )
    monkeypatch.setattr("socket.create_connection", lambda *a, **k: pytest.fail("No real SSH"))


@pytest.fixture
def remote(tmp_path):
    identity = InstallTargetIdentity(
        project_id=str(uuid4()),
        target_id=str(uuid4()),
        target_revision=1,
        endpoint={"host": "synthetic.invalid", "port": 22},
        host_fingerprint="SHA256:" + "A" * 43,
        username="synthetic",
        root="/synthetic/owned",
    )
    config = RemoteConfiguration(
        schema_version=1,
        conda_version="25.9.1",
        identity=identity,
        launcher={"path": "/synthetic/python", "sha256": "a" * 64, "bytes": 10},
        module_root="/synthetic/modules",
        module_tree_sha256="b" * 64,
        bootstrap=[
            {"path": "/synthetic/python-3.11.17-fixture.conda", "sha256": "c" * 64, "bytes": 10},
            {"path": "/synthetic/pip-fixture.conda", "sha256": "d" * 64, "bytes": 10},
        ],
        wheelhouse="/synthetic/wheels",
        disk_budget_bytes=10**9,
        seconds=1,
        execution_authorized=True,
        authorization_expires=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    policy = tmp_path / "remote-install-runtime.json"
    policy.write_text(RemoteConfigurations(targets=[config]).model_dump_json(by_alias=True))
    policy.chmod(0o600)
    rpc = SyntheticRemote(identity)

    def transport(scope, pinned, launcher):
        if scope.project_id != identity.project_id or pinned != identity:
            raise ValueError("SSH_SESSION_INVALID")
        return rpc

    registry = InstallRegistry(tmp_path, lambda: SimpleNamespace(install_transport=transport))
    scope = SessionControl(project_id=identity.project_id, connection_id=str(uuid4()))
    yield registry, rpc, identity, scope, policy
    # Uncertain fixtures explicitly prove quiet before releasing their synthetic
    # lease. Never use close() as that proof.
    for service in registry._remotes.values():
        for lease in service._leases.values():
            lease.reserved = False
            lease.local.close()
        service._leases.clear()
    registry.close()


def planned(remote):
    service, rpc, identity, scope, _ = remote
    return service.plan(
        InstallPlanRequest(
            target_id=identity.target_id,
            remote_session=scope,
            profile_id="easyai-cpu",
            package_ids=["pytorch-lightning"],
            new_environment_spec={"name": "remote"},
        )
    )


def confirmed(service, plan):
    return service.confirm(
        InstallConfirmation(
            plan_id=plan.plan_id,
            plan_hash=plan.plan_hash,
            confirmed=True,
            network_acknowledged=True,
        )
    )


def wait(service, job):
    child = service._job_service(job.job_id)
    child._workers[job.job_id].join(3)
    assert not child._workers[job.job_id].is_alive()
    return service.get(job.job_id)


def test_remote_complete_existing_lifecycle_and_unique_confirmation(remote):
    service, rpc, identity, _, _ = remote
    plan = planned(remote)
    assert plan.target_identity == identity and plan.remote_free_bytes == 10**10
    assert plan.execution_enabled and plan.download_bytes == 0 and len(plan.package_changes) == 35
    job = confirmed(service, plan)
    result = wait(service, job)
    assert result.state == "SUCCEEDED" and result.verified and not result.needs_reprobe
    assert confirmed(service, plan).job_id == job.job_id
    assert len([r for r in rpc.calls if r["action"] == "run"]) == 4
    assert rpc.claims[plan.environment_id]["closed"]
    assert service.history().entries[0].target_id == identity.target_id
    assert service.report(job.job_id).current_environment_verified is False
    before = len(rpc.calls)
    assert service.reconcile(job.job_id, remote[3], False) == result
    assert service.reconcile(job.job_id, remote[3], True) == result
    assert len(rpc.calls) == before  # No remote operation or terminal downgrade.


def test_remote_default_off_and_stale_sources_or_policy_never_start(remote):
    service, rpc, _, _, policy = remote
    data = json.loads(policy.read_text())
    data["targets"][0]["executionAuthorized"] = False
    policy.write_text(json.dumps(data))
    plan = planned(remote)
    assert not plan.execution_enabled
    job = confirmed(service, plan)
    assert job.state == "AWAITING_EXECUTION" and not any(r["action"] == "run" for r in rpc.calls)
    service.cancel(job.job_id)
    next_plan = planned(remote)
    rpc.source_revision += 1
    with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
        confirmed(service, next_plan)
    assert not any(r["action"] == "reserve" for r in rpc.calls)


def test_remote_lost_ack_keeps_lease_reconcile_never_replays_or_claims_success(remote):
    service, rpc, _, scope, _ = remote
    plan = planned(remote)
    rpc.lose_next_run = True
    job = wait(service, confirmed(service, plan))
    assert job.state == "CANCEL_REQUESTED" and not job.verified
    child = service._job_service(job.job_id)
    assert job.job_id in child._leases
    remote[4].unlink()  # Revoked/removed policy cannot prevent bounded owner recovery.
    assert service.reconcile(job.job_id, scope, False).state == "CANCEL_REQUESTED"
    count = len([r for r in rpc.calls if r["action"] == "run"])
    phase = next(iter(rpc.phases))
    rpc.phases[phase].update(outcome="cancelled", quiescent=True)
    result = service.reconcile(job.job_id, scope, True)
    assert result.state == "CANCELLED" and result.needs_reprobe and not result.verified
    assert len([r for r in rpc.calls if r["action"] == "run"]) == count
    assert not child._leases


def test_remote_final_import_failure_never_verified(remote):
    service, rpc, *_ = remote
    rpc.probe_failure = True
    result = wait(service, confirmed(service, planned(remote)))
    assert result.state == "FAILED" and not result.verified and result.needs_reprobe
    assert rpc.claims[result.environment_id]["closed"]


def test_remote_missing_configuration_and_teacher_never_execute(tmp_path):
    service = InstallRegistry(tmp_path, lambda: pytest.fail("No connection without configuration"))
    with pytest.raises(ValueError, match="INSTALL_REMOTE_NOT_CONFIGURED"):
        service.plan(
            InstallPlanRequest(
                target_id=str(uuid4()),
                remote_session={"projectId": str(uuid4()), "connectionId": str(uuid4())},
                profile_id="easyai-cpu",
                package_ids=["torch"],
                new_environment_spec={"name": "x"},
            )
        )
    service.close()


def test_reservation_ack_loss_is_durable_unknown_and_only_quiet_reconciles(remote):
    service, rpc, _, scope, policy = remote
    plan = planned(remote)
    rpc.lose_next_reserve = True
    result = wait(service, confirmed(service, plan))
    assert result.state == "CANCEL_REQUESTED" and not result.verified
    child = service._job_service(result.job_id)
    assert result.job_id in child._leases
    assert remote_target_unsettled(service.app_root, result.target_id)
    assert not any(r["action"] == "run" for r in rpc.calls)
    assert service.report(result.job_id).recorded.state == "CANCEL_REQUESTED"
    policy.unlink()
    recovered = service.reconcile(result.job_id, scope, True)
    assert recovered.state == "CANCELLED" and recovered.needs_reprobe
    assert not child._leases and rpc.claims[result.environment_id]["closed"]
    assert not remote_target_unsettled(service.app_root, result.target_id)


def test_registry_reconcile_reuses_session_cleanup_owner_after_delayed_sdk_close(remote):
    """Real Registry→ConnectionManager→transport lifecycle, synthetic SDK only."""
    from easyai.services.connection_manager import ConnectionManager
    from test_install_transport import Channel

    service, rpc, identity, scope, _ = remote
    plan = planned(remote)
    rpc.lose_next_run = True
    job = wait(service, confirmed(service, plan))
    assert job.state == "CANCEL_REQUESTED"
    phase = next(iter(rpc.phases))
    rpc.phases[phase].update(outcome="cancelled", quiescent=True)
    close_entered, release_close = threading.Event(), threading.Event()
    channels = []

    class ProtocolChannel(Channel):
        def __init__(self, delayed):
            super().__init__(True)
            self.delayed = delayed
            self.out = b""

        def shutdown_write(self):
            tree = ast.parse(self.sent.decode())
            assignment = next(
                n
                for n in tree.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_request" for t in n.targets)
            )
            request = ast.literal_eval(assignment.value)
            self.out = json.dumps(rpc.call(request)).encode()
            self.eof_received = True

        def close(self):
            if self.delayed:
                close_entered.set()
                assert release_close.wait(3)
            self.closed = True

    def channel(**kwargs):
        value = ProtocolChannel(not channels)
        channels.append(value)
        return value

    session = SimpleNamespace(
        io_lock=threading.Lock(), closed_quiescent=False, open_probe_channel=channel
    )
    auth = SimpleNamespace(
        target_id=identity.target_id,
        target_revision=identity.target_revision,
        username=identity.username,
    )
    lease = SimpleNamespace(
        scope=SimpleNamespace(
            endpoint=identity.endpoint, host_fingerprint=identity.host_fingerprint
        ),
        operation=SimpleNamespace(request=auth),
        session=session,
        install_transports={},
    )
    manager = ConnectionManager.__new__(ConnectionManager)
    manager._mutex = threading.RLock()
    manager._valid_lease = (
        lambda project, connection: lease
        if (project, connection) == (scope.project_id, scope.connection_id)
        else None
    )
    service._manager = lambda: manager
    _, first = service._target_service(identity.target_id, scope)
    first.bind(plan, job.job_id)
    transport = first.rpc.__self__
    try:
        with pytest.raises(ValueError, match="INSTALL_REMOTE_CLEANUP_UNCONFIRMED"):
            first.call("inspect")
        assert close_entered.is_set() and session.io_lock.locked()
        pending = transport._cleanup_owner
        release_close.set()
        assert pending[1].wait(1) and channels[0].closed
        result = service.reconcile(job.job_id, scope, True)
        assert result.state == "CANCELLED" and result.needs_reprobe and not result.verified
        current = service._job_service(job.job_id)._target
        assert current is not first and current.rpc.__self__ is transport
        assert len(channels) == 3 and not session.io_lock.locked()
    finally:
        release_close.set()
