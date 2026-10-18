"""Controlled contract fixtures, not installed Python environments or real dependency probes."""

from concurrent.futures import ThreadPoolExecutor
import json
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from easyai.api import create_app
from easyai.domain.install import InstallConfirmation, InstallInspection, InstallPlanRequest
from easyai.services.install_service import InstallService, PROFILE_ROOT
from easyai.services.local_workspace import LocalWorkspace


def request(**kwargs):
    return InstallPlanRequest(
        target_id="local",
        profile_id="easyai-cpu",
        package_ids=["torch"],
        new_environment_spec={"name": "classroom"},
        **kwargs,
    )


def confirmation(plan):
    return InstallConfirmation(
        plan_id=plan.plan_id, plan_hash=plan.plan_hash, confirmed=True, network_acknowledged=True
    )


@pytest.fixture
def service(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No subprocess or network is permitted in this fixture")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    app = tmp_path / "app"
    app.mkdir()
    value = InstallService(app)
    yield value
    value.close()
    # Fixtures prohibit all subprocesses: any retained unknown-stop lease belongs
    # to these controlled test adapters and is safe to retire at fixture cleanup.
    for lease in value._leases.values():
        lease.close()
    value._leases.clear()


def test_catalog_has_explicit_imports_and_no_app_environment_inventory(service):
    catalog = service.catalog()
    assert len(catalog.packages) == 17
    by_id = {item.package_id: item for item in catalog.packages}
    assert {item.group for item in catalog.packages} == {"ml", "dl", "cv", "nlp"}
    assert by_id["scikit-learn"].import_name == "sklearn"
    assert by_id["pillow"].import_name == "PIL"
    assert by_id["opencv-python"].import_name == "cv2"
    assert by_id["torch"].target_version == "2.10.0+cpu"
    assert all(
        item.installed_version is None and item.installed_status == "unknown"
        for item in catalog.packages
    )
    assert not catalog.execution_enabled


def test_plan_is_offline_full_pinned_closure_and_real_metadata_estimate_without_writes(service):
    before = list(service.app_root.iterdir())
    plan = service.plan(request())
    wheels = json.loads((PROFILE_ROOT / "easyai-cpu-sources.json").read_bytes())["packages"]
    assert {item.package_id: item.target_version for item in plan.package_changes} == {
        item["name"]: item["version"] for item in wheels
    }
    assert plan.download_bytes == sum(item["downloadBytes"] for item in wheels)
    assert plan.installed_bytes == sum(item["unpackedBytes"] for item in wheels)
    assert len(plan.plan_hash) == len(plan.baseline_fingerprint) == 64
    assert plan.requires_network and not plan.execution_enabled and plan.new_environment
    assert list(service.app_root.iterdir()) == before
    # A caller cannot mutate the stored plan into an unpinned package request.
    original_hash = plan.plan_hash
    plan.package_changes[0].target_version = "999"
    assert (
        service.confirm(
            InstallConfirmation(
                plan_id=plan.plan_id,
                plan_hash=original_hash,
                confirmed=True,
                network_acknowledged=True,
            )
        ).state
        == "AWAITING_EXECUTION"
    )


def test_group_and_single_selection_share_same_planner_unresolved_is_not_guessed(service):
    ids = [item.package_id for item in service.catalog().packages]
    raw = request().model_dump()
    raw["package_ids"] = ids
    plan = service.plan(InstallPlanRequest(**raw))
    assert "INSTALL_DEPENDENCIES_UNRESOLVED" in plan.blockers
    assert plan.size_status == "unresolved" and plan.download_bytes is plan.installed_bytes is None
    with pytest.raises(ValueError, match="INSTALL_PLAN_BLOCKED"):
        service.confirm(confirmation(plan))


@pytest.mark.parametrize(
    "mutation",
    [
        {"package_ids": ["torch;rm"]},
        {"package_ids": ["torch", "torch"]},
        {"new_environment_spec": {"name": "../teacher"}},
        {"owned_environment_id": str(uuid4())},
        {"target_id": "ssh"},
        {"command": "pip install private"},
    ],
)
def test_request_rejects_paths_commands_duplicate_packages_and_ambiguous_targets(mutation):
    raw = request().model_dump()
    raw.update(mutation)
    with pytest.raises(ValidationError):
        InstallPlanRequest(**raw)


def test_teacher_unknown_packages_and_unregistered_owned_environment_are_refused(service):
    raw = request().model_dump()
    raw["profile_id"] = "teacher-existing"
    with pytest.raises(ValueError, match="INSTALL_TEACHER_READ_ONLY"):
        service.plan(InstallPlanRequest(**raw))
    raw["profile_id"], raw["package_ids"] = "easyai-cpu", ["untrusted-package"]
    with pytest.raises(ValueError, match="INSTALL_PACKAGE_FORBIDDEN"):
        service.plan(InstallPlanRequest(**raw))
    raw.update(package_ids=["torch"], new_environment_spec=None, owned_environment_id=str(uuid4()))
    with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_FORBIDDEN"):
        service.plan(InstallPlanRequest(**raw))
    assert not service.root.exists()


def test_explicit_confirmation_is_idempotent_and_cancellation_never_claims_health(service):
    plan = service.plan(request())
    for field in ("confirmed", "network_acknowledged"):
        raw = confirmation(plan).model_dump()
        raw[field] = False
        with pytest.raises(ValidationError):
            InstallConfirmation(**raw)
    job = service.confirm(confirmation(plan))
    assert service.confirm(confirmation(plan)).job_id == job.job_id
    assert job.state == "AWAITING_EXECUTION" and not job.changes_possible and not job.verified
    assert job.status_code == "INSTALL_EXECUTION_NOT_ENABLED"
    ended = service.cancel(job.job_id)
    assert ended.state == "CANCELLED" and ended.needs_reprobe and not ended.verified
    assert service.confirm(confirmation(plan)).job_id == job.job_id
    assert not service.root.exists()


def test_existing_destination_expired_or_wrong_hash_plan_cannot_be_confirmed(service):
    plan = service.plan(request())
    bad = confirmation(plan).model_copy(update={"plan_hash": "f" * 64})
    with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
        service.confirm(bad)
    service.root.mkdir()
    (service.root / plan.environment_id).mkdir()
    with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
        service.confirm(confirmation(plan))
    other = service.plan(request())
    service._clock = lambda: 10**12
    with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
        service.confirm(confirmation(other))


def test_http_auth_strict_confirmation_and_cancel_never_install(tmp_path):
    workspace = LocalWorkspace(tmp_path / "app")
    try:
        client = TestClient(create_app("install-test", workspace=workspace))
        route = "/api/v1/environments/install-plan"
        assert client.post(route, json=request().model_dump(by_alias=True)).status_code == 401
        client.headers.update({"Authorization": "Bearer install-test"})
        assert client.get("/api/v1/catalog/packages").status_code == 200
        invalid = client.post(
            route, json={**request().model_dump(by_alias=True), "command": "private-secret"}
        )
        assert invalid.status_code == 422 and "private-secret" not in invalid.text
        planned = client.post(route, json=request().model_dump(by_alias=True))
        assert planned.status_code == 200
        body = {
            "planId": planned.json()["planId"],
            "planHash": planned.json()["planHash"],
            "confirmed": True,
            "networkAcknowledged": True,
        }
        assert (
            client.post("/api/v1/install-jobs", json={**body, "planHash": "0" * 64}).status_code
            == 412
        )
        job = client.post("/api/v1/install-jobs", json=body)
        assert job.status_code == 202 and job.json()["state"] == "AWAITING_EXECUTION"
        jid = job.json()["jobId"]
        assert client.get(f"/api/v1/install-jobs/{jid}").json() == job.json()
        assert client.post(f"/api/v1/install-jobs/{jid}/cancel").json()["state"] == "CANCELLED"
        assert not (workspace.root / "training-environments").exists()
    finally:
        workspace.close()


@pytest.fixture
def owned_install(service):
    environment_id = str(uuid4())
    prefix = service.root / environment_id
    prefix.mkdir(parents=True)
    (prefix / ".easyai-owned.json").write_text(
        json.dumps({"ownedByEasyAI": True, "environmentId": environment_id})
    )
    inventory = prefix / "fixture-inventory.json"
    inventory.write_text(json.dumps({"versions": {}, "imports": {}, "tensor_ok": False}))

    def inspect(path, nonce):
        value = json.loads(inventory.read_bytes())
        return InstallInspection(nonce=nonce, prefix=str(path), python_version="3.11.17", **value)

    service._inspector = inspect
    raw = request().model_dump()
    raw.update(new_environment_spec=None, owned_environment_id=environment_id)
    plan = service.plan(InstallPlanRequest(**raw))
    job = service.confirm(confirmation(plan))
    return service, plan, job, prefix, inventory


class ControlledExecutor:
    """Only test fixture inventory is changed; no pip/conda/Python execution."""

    def install(self, prefix, plan, cancel, progress):
        progress()
        (prefix / "fixture-inventory.json").write_text(
            json.dumps(
                {
                    "versions": {
                        item.package_id: item.target_version for item in plan.package_changes
                    },
                    "imports": {name: True for name in ("torch", "torchvision", "matplotlib")},
                    "tensor_ok": True,
                }
            )
        )
        return "completed"


def test_owned_contract_success_requires_fresh_post_install_probe_not_exit_code(owned_install):
    service, plan, job, prefix, _ = owned_install
    result = service.execute(job.job_id, ControlledExecutor())
    assert result.state == "SUCCEEDED" and result.verified and not result.needs_reprobe
    assert result.logs[-2:] == ["INSTALL_REPROBE_STARTED", "INSTALL_VERIFIED"]
    assert prefix.parent == service.root
    assert service.get(job.job_id) == result
    # This proves the trusted-adapter contract only, not actual import/tensor health.


def test_drift_after_confirmation_prevents_executor_and_foreign_marker_is_refused(owned_install):
    service, plan, job, prefix, inventory = owned_install
    value = json.loads(inventory.read_bytes())
    value["versions"] = {"torch": "different"}
    inventory.write_text(json.dumps(value))

    class Never:
        def install(self, *args):
            pytest.fail("Stale plan must never invoke installer")

    with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
        service.execute(job.job_id, Never())
    (prefix / ".easyai-owned.json").write_text(
        json.dumps({"ownedByEasyAI": False, "environmentId": plan.environment_id})
    )
    with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_FORBIDDEN"):
        service.execute(job.job_id, Never())


def test_reprobe_failure_does_not_claim_success_or_rollback(owned_install):
    service, _, job, _, inventory = owned_install

    class BadProbe(ControlledExecutor):
        def install(self, *args):
            super().install(*args)
            value = json.loads(inventory.read_bytes())
            value["imports"]["torchvision"] = False
            inventory.write_text(json.dumps(value))
            return "completed"

    result = service.execute(job.job_id, BadProbe())
    assert (
        result.state == "FAILED"
        and result.changes_possible
        and result.needs_reprobe
        and not result.verified
    )
    assert json.loads(inventory.read_bytes())["versions"]  # No claimed rollback.


def test_unknown_stop_retains_environment_reservation_and_never_says_cancelled(owned_install):
    service, plan, job, _, _ = owned_install

    class Unknown:
        def install(self, *args):
            return "unknown"

    result = service.execute(job.job_id, Unknown())
    assert result.state == "CANCEL_REQUESTED" and result.status_code == "INSTALL_STOP_UNCONFIRMED"
    raw = request().model_dump()
    raw.update(new_environment_spec=None, owned_environment_id=plan.environment_id)
    second = service.plan(InstallPlanRequest(**raw))
    with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_CONFLICT"):
        service.confirm(confirmation(second))
    assert service.cancel(job.job_id).state == "CANCEL_REQUESTED"


def test_running_cancel_is_only_terminal_after_adapter_confirms_quiescence(owned_install):
    service, _, job, _, _ = owned_install
    entered, release = threading.Event(), threading.Event()

    class Blocking:
        def install(self, prefix, plan, cancel, progress):
            entered.set()
            assert release.wait(2)
            assert cancel.is_set()
            return "cancelled"

    with ThreadPoolExecutor() as pool:
        pending = pool.submit(service.execute, job.job_id, Blocking())
        assert entered.wait(2)
        assert service.cancel(job.job_id).state == "CANCEL_REQUESTED"
        release.set()
        result = pending.result(3)
    assert result.state == "CANCELLED" and result.needs_reprobe and not result.verified


def test_changed_profile_constraints_force_fresh_confirmation(service, monkeypatch):
    plan = service.plan(request())
    monkeypatch.setattr(service, "_profile_hash", lambda: "a" * 64)
    with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
        service.confirm(confirmation(plan))


def test_kernel_environment_lease_excludes_an_independent_service_while_stop_unknown(owned_install):
    service, plan, job, _, _ = owned_install

    class Unknown:
        def install(self, *args):
            return "unknown"

    other = InstallService(service.app_root, inspector=service._inspector)
    try:
        assert service.execute(job.job_id, Unknown()).state == "CANCEL_REQUESTED"
        raw = request().model_dump()
        raw.update(new_environment_spec=None, owned_environment_id=plan.environment_id)
        second = other.plan(InstallPlanRequest(**raw))
        next_job = other.confirm(confirmation(second))
        with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_CONFLICT"):
            other.execute(next_job.job_id, Unknown())
    finally:
        other.close()
        # Fixture knows no process was launched. Release its intentionally retained
        # unknown-stop lease after assertions, not as a production recovery path.
        for lease in service._leases.values():
            lease.close()
        service._leases.clear()


def test_reprobe_wrong_nonce_and_log_flood_cannot_publish_healthy(owned_install):
    service, _, job, _, _ = owned_install
    original = service._inspector

    class WrongNonce(ControlledExecutor):
        def install(self, prefix, plan, cancel, progress):
            for _ in range(300):
                progress()
            result = super().install(prefix, plan, cancel, progress)

            def inspect(path, nonce):
                assert original is not None
                return original(path, nonce).model_copy(update={"nonce": str(uuid4())})

            service._inspector = inspect
            return result

    result = service.execute(job.job_id, WrongNonce())
    assert result.state == "FAILED" and result.needs_reprobe and not result.verified
    assert len(result.logs) <= 128


@pytest.mark.parametrize("field", ["confirmed", "network_acknowledged"])
def test_integer_one_is_not_explicit_boolean_confirmation(field):
    raw = {
        "plan_id": str(uuid4()),
        "plan_hash": "a" * 64,
        "confirmed": True,
        "network_acknowledged": True,
    }
    raw[field] = 1
    with pytest.raises(ValidationError):
        InstallConfirmation(**raw)
