"""Private synthetic manifests only; no launcher, conda, probe or package execution."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest
from easyai.domain.install import InstallSourceRequest, InstallSourceConfirmation
from easyai.services import install_source_selection as source_module
from easyai.services.install_runtime import InstallRuntime
from easyai.services.install_service import InstallService
from easyai.security.project_lock import ProjectLock
from test_install_runtime import configured as configured_fixture, request, confirmation
from test_install_process import owned as owned_fixture

configured = configured_fixture
owned = owned_fixture


@pytest.fixture
def selection(configured, monkeypatch):
    app, sources, config = configured
    source = sources / "operator.json"
    source.write_text(json.dumps(config))
    source.chmod(0o600)
    monkeypatch.setattr(source_module, "PROFILE_ROOT", sources / "profile")
    runtime = InstallRuntime(app)
    service = InstallService(app, runtime=runtime, inspector=runtime.inspector)
    monkeypatch.setattr(
        "subprocess.Popen", lambda *a, **k: pytest.fail("Never execute source files")
    )
    yield service, runtime, source, config
    service.close()


def preview(service, path):
    return service.preview_sources(
        InstallSourceRequest(manifest_path=str(path), package_ids=["torch"])
    )


def confirm(service, value):
    return service.confirm_sources(
        InstallSourceConfirmation(
            preview_id=value.preview_id, preview_hash=value.preview_hash, confirmed=True
        )
    )


def test_preview_is_readonly_confirm_preserves_budget_but_never_imports_authority(selection):
    service, runtime, source, config = selection
    before = runtime.configuration_path.read_bytes(), runtime.configuration_path.stat().st_ino
    old_plan = service.plan(request())
    value = preview(service, source)
    assert (
        runtime.configuration_path.read_bytes(),
        runtime.configuration_path.stat().st_ino,
    ) == before
    assert value.declared_execution_authorized and not value.execution_enabled
    assert value.manifest_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert (
        value.disk_budget_bytes == config["diskBudgetBytes"]
        and value.execution_seconds == config["seconds"]
    )
    assert len(value.wheels) == 1 and value.installed_bytes is None
    result = confirm(service, value)
    after = runtime.configuration_path.read_bytes()
    saved = json.loads(after)
    assert saved["executionAuthorized"] is False and not result.execution_enabled
    assert (
        saved["diskBudgetBytes"] == config["diskBudgetBytes"]
        and saved["seconds"] == config["seconds"]
    )
    assert datetime.fromisoformat(
        saved["authorizationExpires"].replace("Z", "+00:00")
    ) == datetime.fromisoformat(config["authorizationExpires"])
    assert runtime.configuration_path.stat().st_mode & 0o077 == 0
    assert source.read_bytes() != after  # Original source authorization is not rewritten.
    registered = runtime.configuration_path.stat().st_ino
    assert (
        confirm(service, value) == result and runtime.configuration_path.stat().st_ino == registered
    )
    with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
        service.confirm(confirmation(old_plan))
    fresh = service.plan(request())
    assert not fresh.execution_enabled and fresh.runtime_fingerprint == result.runtime_fingerprint
    assert service.confirm(confirmation(fresh)).state == "AWAITING_EXECUTION"
    service.cancel(next(iter(service._jobs)))


@pytest.mark.parametrize(
    "change",
    [
        "source-replaced",
        "source-permission",
        "source-expired",
        "destination-replaced",
        "wheel-changed",
        "budget-changed",
        "receipt-expired",
    ],
)
def test_preview_changes_refuse_without_replacing_current_configuration(selection, change):
    service, runtime, source, config = selection
    value = preview(service, source)
    if change == "source-replaced":
        replacement = source.with_name("replacement.json")
        replacement.write_bytes(source.read_bytes())
        replacement.chmod(0o600)
        replacement.replace(source)
    elif change == "source-permission":
        source.chmod(0o644)
    elif change == "source-expired":
        config["authorizationExpires"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
        source.write_text(json.dumps(config))
    elif change == "destination-replaced":
        replacement = runtime.root / "replacement.json"
        replacement.write_bytes(runtime.configuration_path.read_bytes())
        replacement.chmod(0o600)
        replacement.replace(runtime.configuration_path)
    elif change == "wheel-changed":
        (Path(config["wheelhouse"]) / "torch-fixture.whl").write_bytes(b"changed")
    elif change == "budget-changed":
        config["diskBudgetBytes"] += 1
        source.write_text(json.dumps(config))
    else:
        service._sources.deadline = 0
    before = runtime.configuration_path.read_bytes(), runtime.configuration_path.stat().st_ino
    with pytest.raises(ValueError):
        confirm(service, value)
    assert (
        runtime.configuration_path.read_bytes(),
        runtime.configuration_path.stat().st_ino,
    ) == before


def test_private_permissions_missing_hash_and_unknown_fields_are_not_trust(selection):
    service, runtime, source, config = selection
    before = runtime.configuration_path.read_bytes()
    source.chmod(0o644)
    with pytest.raises(ValueError):
        preview(service, source)
    source.chmod(0o600)
    config["launcher"]["sha256"] = "f" * 64
    source.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        preview(service, source)
    assert runtime.configuration_path.read_bytes() == before
    with pytest.raises(ValueError):
        InstallSourceRequest(
            manifest_path=str(source), package_ids=["torch"], executionAuthorized=True
        )


def test_fresh_persisted_writer_and_shared_commit_lock_block_cross_instance_changes(selection):
    service, runtime, source, _ = selection
    value = preview(service, source)
    other = InstallService(
        runtime.root
    )  # No runtime: register intent without scheduling any worker.
    try:
        plan = other.plan(request())
        job = other.confirm(confirmation(plan))
        job = other._jobs[job.job_id]
        job.state = "INSTALLING"
        other._record(job)  # Synthetic durable writer started after first service opened.
        before = runtime.configuration_path.read_bytes()
        with pytest.raises(ValueError, match="INSTALL_SOURCE_BUSY"):
            confirm(service, value)
        assert runtime.configuration_path.read_bytes() == before
        job.state = "FAILED"
        other._record(job)
        lock = ProjectLock(runtime.root / ".install-source.lock")
        try:
            lock.verify()
            with pytest.raises(ValueError):
                confirm(service, value)
            assert runtime.configuration_path.read_bytes() == before
        finally:
            lock.close()
        assert confirm(service, value).execution_enabled is False
    finally:
        other.cancel(job.job_id)
        other.close()


def test_installer_cannot_publish_writer_intent_during_source_commit(owned):
    service, _, job, _, _, _ = owned
    lock = ProjectLock(service.app_root / ".install-source.lock")

    class Never:
        def install(self, *args):
            pytest.fail("Never dispatch while configuration commit owns the gate")

    try:
        lock.verify()
        with pytest.raises(ValueError, match="INSTALL_SOURCE_BUSY"):
            service.execute(job.job_id, Never())
        assert service.get(job.job_id).state == "AWAITING_EXECUTION"
        assert job.job_id not in service._leases
    finally:
        lock.close()


def test_authenticated_http_preview_confirmation_and_renderer_authority_rejection(
    selection, monkeypatch
):
    from fastapi.testclient import TestClient
    from easyai.api import create_app
    from easyai.services.local_workspace import LocalWorkspace

    service, runtime, source, _ = selection
    workspace = LocalWorkspace(runtime.root)
    monkeypatch.setattr(workspace, "installs", lambda: service)
    client = TestClient(create_app("source-token", workspace=workspace))
    body = {"manifestPath": str(source), "packageIds": ["torch"]}
    endpoint = "/api/v1/environments/install-source/"
    before = runtime.configuration_path.read_bytes()
    assert client.post(endpoint + "preview", json=body).status_code == 401
    client.headers.update({"Authorization": "Bearer source-token"})
    assert (
        client.post(endpoint + "preview", json={**body, "executionAuthorized": True}).status_code
        == 422
    )
    response = client.post(endpoint + "preview", json=body)
    assert response.status_code == 200
    value = response.json()
    assert value["executionEnabled"] is False and runtime.configuration_path.read_bytes() == before
    confirmation = {
        "previewId": value["previewId"],
        "previewHash": value["previewHash"],
        "confirmed": True,
    }
    assert (
        client.post(endpoint + "confirm", json={**confirmation, "confirmed": 1}).status_code == 422
    )
    result = client.post(endpoint + "confirm", json=confirmation)
    assert result.status_code == 200 and result.json()["executionEnabled"] is False
    workspace.close()


def test_expiry_after_slow_revalidation_and_close_before_commit_keep_configuration(
    selection, monkeypatch
):
    service, runtime, source, _ = selection
    value = preview(service, source)
    original = runtime.inspect_source

    def expired(*args):
        result = original(*args)
        service._sources.deadline = 0
        return result

    monkeypatch.setattr(runtime, "inspect_source", expired)
    before = runtime.configuration_path.read_bytes()
    with pytest.raises(ValueError):
        confirm(service, value)
    assert runtime.configuration_path.read_bytes() == before
    monkeypatch.setattr(runtime, "inspect_source", original)
    value = preview(service, source)

    def closing(*args):
        result = original(*args)
        service._close_requested.set()
        return result

    monkeypatch.setattr(runtime, "inspect_source", closing)
    with pytest.raises(ValueError, match="INSTALL_SESSION_CLOSED"):
        confirm(service, value)
    assert runtime.configuration_path.read_bytes() == before
