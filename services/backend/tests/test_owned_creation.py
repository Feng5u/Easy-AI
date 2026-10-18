"""Synthetic owned directories and stdlib subprocesses, never conda/venv/pip creation."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
import sys
import threading
from uuid import uuid4

import pytest

from easyai.domain.install import InstallConfirmation, InstallInspection, InstallPlanRequest
from easyai.services.install_process import HEADER, ManagedInstallCommand, _event
from easyai.services.install_service import InstallService
from easyai.services.owned_creation import OwnedCreation, require_ready

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="Creation filesystem executor is POSIX only"
)


@pytest.fixture
def pending(tmp_path):
    app = tmp_path / "app"
    app.mkdir()

    def inspector(prefix, nonce):
        value = json.loads((prefix / "bootstrap.json").read_bytes())
        return InstallInspection(nonce=nonce, prefix=str(prefix), python_version="3.11.17", **value)

    service = InstallService(app, inspector=inspector)
    plan = service.plan(
        InstallPlanRequest(
            target_id="local",
            profile_id="easyai-cpu",
            package_ids=["torch"],
            new_environment_spec={"name": "new_owned"},
        )
    )
    job = service.confirm(
        InstallConfirmation(
            plan_id=plan.plan_id,
            plan_hash=plan.plan_hash,
            confirmed=True,
            network_acknowledged=True,
        )
    )
    yield service, plan, job
    service.close()
    for lease in service._leases.values():
        lease.close()  # Fixtures know no unknown live process exists.


class Bootstrap:
    def create(self, prefix, plan, cancel, progress):
        assert prefix.is_dir() and not list(prefix.iterdir())
        (prefix / "bootstrap.json").write_text(
            json.dumps({"versions": {}, "imports": {}, "tensor_ok": False})
        )
        return "completed"


class InstallFixture:
    def install(self, prefix, plan, cancel, progress):
        assert json.loads((prefix / ".easyai-owned.json").read_bytes()) == {
            "ownedByEasyAI": True,
            "environmentId": plan.environment_id,
        }
        # This is synthetic inventory, not an installed Python or genuine tensor result.
        (prefix / "bootstrap.json").write_text(
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


class Never:
    def install(self, *args):
        pytest.fail("Installer must not run past a failed provisioning gate")


def test_new_creation_remains_gated_without_explicit_internal_adapter(pending):
    service, plan, job = pending
    with pytest.raises(ValueError, match="INSTALL_PROVISIONER_NOT_ENABLED"):
        service.execute(job.job_id, Never())
    assert not (service.root / plan.environment_id).exists()
    assert not (service.app_root / "environment-creations").exists()


def test_synthetic_creation_promotes_only_after_bootstrap_install_and_final_probe(pending):
    service, plan, job = pending
    result = service.execute(job.job_id, InstallFixture(), provisioner=Bootstrap())
    assert result.state == "SUCCEEDED" and result.verified
    prefix = service.root / plan.environment_id
    require_ready(service.app_root, plan.environment_id, prefix)
    assert service._owned(plan.environment_id) == prefix
    service.close()
    other = InstallService(service.app_root, inspector=service._inspector)
    try:
        assert other.get(job.job_id).state == "SUCCEEDED"
        assert other._owned(plan.environment_id) == prefix
    finally:
        other.close()


@pytest.mark.skipif(os.name != "posix", reason="Existing owned process-group adapter is POSIX only")
def test_real_stdlib_child_populates_synthetic_prefix_through_existing_manager(pending, tmp_path):
    service, _, job = pending
    commands = ManagedInstallCommand(tmp_path, seconds=3)

    class ChildBootstrap:
        def create(self, prefix, plan, cancel, progress):
            source = (
                HEADER
                + "from pathlib import Path\nPath('bootstrap.json').write_text("
                + repr(json.dumps({"versions": {}, "imports": {}, "tensor_ok": False}))
                + ")\n"
                + _event("pipeline_completed")
            )
            outcome, _ = commands.run(
                [sys.executable, "-I", "-B", "-c", source], prefix, cancel, progress
            )
            return outcome

    result = service.execute(job.job_id, InstallFixture(), provisioner=ChildBootstrap())
    assert result.state == "SUCCEEDED" and result.verified
    assert (commands.last_root / "logs/runtime-events.jsonl").is_file()


@pytest.mark.parametrize("outcome", ["failed", "cancelled", "unknown"])
def test_partial_creation_preserved_unowned_and_never_usable(pending, outcome):
    service, plan, job = pending

    class Partial:
        def create(self, prefix, plan, cancel, progress):
            (prefix / "partial-user-visible.txt").write_text("keep this partial evidence")
            return outcome

    result = service.execute(job.job_id, Never(), provisioner=Partial())
    prefix = service.root / plan.environment_id
    assert (prefix / "partial-user-visible.txt").read_text() == "keep this partial evidence"
    assert not (prefix / ".easyai-owned.json").exists()
    assert not (
        service.app_root / "environment-creations" / plan.environment_id / "ready.json"
    ).exists()
    assert not result.verified and result.needs_reprobe
    assert (
        result.state
        == {"failed": "FAILED", "cancelled": "CANCELLED", "unknown": "CANCEL_REQUESTED"}[outcome]
    )
    assert (job.job_id in service._leases) == (outcome == "unknown")
    with pytest.raises(ValueError):
        service._owned(plan.environment_id)


def test_preexisting_unknown_prefix_and_old_reservation_are_never_adopted(pending):
    service, plan, job = pending
    prefix = service.root / plan.environment_id
    prefix.mkdir(parents=True)
    original = prefix / "unknown.txt"
    original.write_text("do not touch")
    with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
        service.execute(job.job_id, Never(), provisioner=Bootstrap())
    assert original.read_text() == "do not touch"
    assert list(prefix.iterdir()) == [original]


def test_unknown_reservation_blocks_retry_even_when_prefix_absent(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    env_id, job_id = str(uuid4()), str(uuid4())
    first = OwnedCreation(app, env_id, job_id, "a" * 64)
    lease = first.reserve()
    lease.close()
    second = OwnedCreation(app, env_id, str(uuid4()), "b" * 64)
    with pytest.raises(FileExistsError):
        second.reserve()
    assert json.loads((first.claim / "claim.json").read_bytes())["jobId"] == job_id
    assert not first.prefix.exists()


def test_replaced_directory_or_bootstrap_marker_is_preserved_and_refused(pending):
    service, plan, job = pending

    class Replacement:
        def create(self, prefix, plan, cancel, progress):
            prefix.rename(prefix.with_name(prefix.name + "-original"))
            prefix.mkdir()
            (prefix / "unknown.txt").write_text("replacement")
            return "completed"

    result = service.execute(job.job_id, Never(), provisioner=Replacement())
    prefix = service.root / plan.environment_id
    assert result.state == "FAILED" and not result.verified
    assert (prefix / "unknown.txt").read_text() == "replacement"
    assert prefix.with_name(prefix.name + "-original").is_dir()
    assert not (prefix / ".easyai-owned.json").exists()


def test_failed_bootstrap_identity_does_not_publish_owned_marker(pending):
    service, plan, job = pending
    original = service._inspector
    service._inspector = lambda path, nonce: original(path, nonce).model_copy(
        update={"prefix": "/synthetic-wrong-prefix"}
    )
    result = service.execute(job.job_id, Never(), provisioner=Bootstrap())
    assert result.state == "FAILED" and not result.verified
    assert not (service.root / plan.environment_id / ".easyai-owned.json").exists()


def test_cancel_during_bootstrap_probe_preserves_partial_and_does_not_install(pending):
    service, plan, job = pending
    entered, release = threading.Event(), threading.Event()
    original = service._inspector

    def inspect(path, nonce):
        entered.set()
        assert release.wait(3)
        return original(path, nonce)

    service._inspector = inspect
    with ThreadPoolExecutor() as pool:
        future = pool.submit(service.execute, job.job_id, Never(), provisioner=Bootstrap())
        assert entered.wait(3)
        assert service.cancel(job.job_id).state == "CANCEL_REQUESTED"
        release.set()
        result = future.result(3)
    assert result.state == "CANCELLED" and not result.verified
    assert (service.root / plan.environment_id / "bootstrap.json").is_file()
    assert not (service.root / plan.environment_id / ".easyai-owned.json").exists()


def test_failed_install_after_bootstrap_is_not_ready_or_reusable(pending):
    service, plan, job = pending

    class Fail:
        def install(self, *args):
            return "failed"

    result = service.execute(job.job_id, Fail(), provisioner=Bootstrap())
    prefix = service.root / plan.environment_id
    assert result.state == "FAILED" and (prefix / ".easyai-owned.json").is_file()
    with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_INCOMPLETE"):
        service._owned(plan.environment_id)
    assert (prefix / "bootstrap.json").is_file()


def test_symlinked_controlled_root_cannot_write_outside_app(pending, tmp_path):
    service, _, job = pending
    outside = tmp_path / "outside"
    outside.mkdir()
    (service.app_root / "environment-creations").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        service.execute(job.job_id, Never(), provisioner=Bootstrap())
    assert not list(outside.iterdir())


def test_creation_changed_profile_or_expired_plan_before_install_preserves_prefix(pending):
    service, plan, job = pending
    original = service._inspector

    def changed(path, nonce):
        report = original(path, nonce)
        service._profile_hash = lambda: "f" * 64
        return report

    service._inspector = changed
    result = service.execute(job.job_id, Never(), provisioner=Bootstrap())
    assert result.state == "FAILED" and result.status_code == "INSTALL_PLAN_STALE"
    assert (service.root / plan.environment_id / "bootstrap.json").exists()
    assert not (service.root / plan.environment_id / ".easyai-owned.json").exists()


def test_ready_file_alone_cannot_promote_unknown_or_failed_persisted_job(pending):
    service, plan, job = pending
    result = service.execute(job.job_id, InstallFixture(), provisioner=Bootstrap())
    assert result.verified
    result.state, result.verified = "FAILED", False
    service._record(result)
    with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_INCOMPLETE"):
        require_ready(service.app_root, plan.environment_id, service.root / plan.environment_id)


@pytest.mark.parametrize("lose_origin", [False, True])
def test_missing_claim_cannot_turn_partial_new_environment_into_legacy(pending, lose_origin):
    service, plan, job = pending

    class Failed:
        def install(self, *args):
            return "failed"

    assert service.execute(job.job_id, Failed(), provisioner=Bootstrap()).state == "FAILED"
    prefix = service.root / plan.environment_id
    claim = service.app_root / "environment-creations" / plan.environment_id
    claim.rename(claim.with_name(claim.name + "-preserved"))
    if lose_origin:
        (prefix / ".easyai-origin.json").rename(prefix / "origin-preserved.json")
    with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_INCOMPLETE"):
        service._owned(plan.environment_id)
    assert (prefix / "bootstrap.json").is_file()


def test_cancel_during_final_probe_never_publishes_creation_ready(pending):
    service, plan, job = pending
    entered, release = threading.Event(), threading.Event()
    original = service._inspector
    count = [0]

    def inspect(path, nonce):
        count[0] += 1
        if count[0] == 2:
            entered.set()
            assert release.wait(3)
        return original(path, nonce)

    service._inspector = inspect
    with ThreadPoolExecutor() as pool:
        future = pool.submit(service.execute, job.job_id, InstallFixture(), provisioner=Bootstrap())
        assert entered.wait(3)
        assert service.cancel(job.job_id).state == "CANCEL_REQUESTED"
        release.set()
        result = future.result(3)
    assert result.state == "CANCELLED" and not result.verified
    assert not (
        service.app_root / "environment-creations" / plan.environment_id / "ready.json"
    ).exists()
    with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_INCOMPLETE"):
        service._owned(plan.environment_id)


def test_foreign_marker_created_by_adapter_is_not_overwritten_or_adopted(pending):
    service, plan, job = pending

    class Marker(Bootstrap):
        def create(self, prefix, plan, cancel, progress):
            super().create(prefix, plan, cancel, progress)
            (prefix / ".easyai-owned.json").write_text("foreign content")
            return "completed"

    result = service.execute(job.job_id, Never(), provisioner=Marker())
    assert result.state == "FAILED"
    assert (
        service.root / plan.environment_id / ".easyai-owned.json"
    ).read_text() == "foreign content"


def test_real_child_cancel_keeps_synthetic_half_directory_and_confirms_exit(pending, tmp_path):
    service, plan, job = pending
    commands = ManagedInstallCommand(tmp_path, seconds=3)
    entered = threading.Event()
    exits = []

    class SlowChild:
        def create(self, prefix, plan, cancel, progress):
            source = (
                HEADER
                + "from pathlib import Path\nimport time\nPath('partial.txt').write_text('keep')\ntime.sleep(30)\n"
            )

            def tick():
                progress()
                if (prefix / "partial.txt").exists():
                    entered.set()

            outcome, events = commands.run(
                [sys.executable, "-I", "-B", "-c", source], prefix, cancel, tick
            )
            exits.extend(event for event in events if event.type == "process_exited")
            return outcome

    with ThreadPoolExecutor() as pool:
        future = pool.submit(service.execute, job.job_id, Never(), provisioner=SlowChild())
        assert entered.wait(3)
        assert service.cancel(job.job_id).state == "CANCEL_REQUESTED"
        result = future.result(5)
    assert result.state == "CANCELLED" and not result.verified and exits
    assert exits[-1].payload["exitCode"] != 0
    prefix = service.root / plan.environment_id
    assert (prefix / "partial.txt").read_text() == "keep"
    assert not (prefix / ".easyai-owned.json").exists()
    assert job.job_id not in service._leases
