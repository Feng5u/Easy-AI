"""Real stdlib child processes and synthetic owned dirs; never installs dependencies."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import threading
from uuid import uuid4

import pytest

from easyai.domain.install import InstallConfirmation, InstallInspection, InstallPlanRequest
from easyai.services.install_process import (
    HEADER,
    LOG_LIMIT,
    ManagedInstallCommand,
    ManagedInstallInspector,
    OfflineWheelInstaller,
    _event,
)
from easyai.services.install_service import InstallService


@pytest.fixture
def owned(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    env_id = str(uuid4())
    prefix = root / "training-environments" / env_id
    prefix.mkdir(parents=True)
    (prefix / ".easyai-owned.json").write_text(
        json.dumps({"ownedByEasyAI": True, "environmentId": env_id})
    )
    inventory = prefix / "fixture.json"
    inventory.write_text(json.dumps({"versions": {}, "imports": {}, "tensor_ok": False}))

    def inspect(path, nonce):
        return InstallInspection(
            nonce=nonce,
            prefix=str(path),
            python_version="3.11.17",
            **json.loads(inventory.read_bytes()),
        )

    service = InstallService(root, inspector=inspect)
    request = InstallPlanRequest(
        target_id="local",
        profile_id="easyai-cpu",
        package_ids=["torch"],
        owned_environment_id=env_id,
    )
    plan = service.plan(request)
    job = service.confirm(
        InstallConfirmation(
            plan_id=plan.plan_id,
            plan_hash=plan.plan_hash,
            confirmed=True,
            network_acknowledged=True,
        )
    )
    yield service, plan, job, prefix, inventory, request
    service.close()
    for lease in service._leases.values():
        lease.close()  # Test knows its controlled child is stopped, unlike production recovery.


def test_final_ttl_after_slow_inspector_prevents_executor(owned):
    service, plan, job, _, _, _ = owned
    now = [0.0]
    service._clock = lambda: now[0]
    service._plans[plan.plan_id].deadline = 10.0
    original = service._inspector

    def slow(path, nonce):
        report = original(path, nonce)
        now[0] = 11.0
        return report

    service._inspector = slow

    class Never:
        def install(self, *args):
            pytest.fail("Expired plan must not start a child")

    with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
        service.execute(job.job_id, Never())
    assert job.job_id not in service._leases
    assert service.get(job.job_id).state == "AWAITING_EXECUTION"


def test_cancel_during_reprobe_never_publishes_verified(owned):
    service, plan, job, _, inventory, _ = owned
    entered, release = threading.Event(), threading.Event()
    original = service._inspector

    class Fixture:
        def install(self, *args):
            inventory.write_text(
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

            def blocked(path, nonce):
                entered.set()
                assert release.wait(3)
                return original(path, nonce)

            service._inspector = blocked
            return "completed"

    with ThreadPoolExecutor() as pool:
        future = pool.submit(service.execute, job.job_id, Fixture())
        assert entered.wait(3)
        assert service.cancel(job.job_id).state == "CANCEL_REQUESTED"
        release.set()
        result = future.result(3)
    assert result.state == "CANCELLED" and not result.verified and result.needs_reprobe


@pytest.mark.skipif(sys.platform == "win32", reason="Owned process-group adapter is POSIX only")
def test_real_managed_child_then_reprobe_and_durable_restart(owned, tmp_path):
    service, plan, job, prefix, inventory, _ = owned
    commands = ManagedInstallCommand(tmp_path, seconds=3)
    content = {
        "versions": {item.package_id: item.target_version for item in plan.package_changes},
        "imports": {name: True for name in ("torch", "torchvision", "matplotlib")},
        "tensor_ok": True,
    }

    class Child:
        def install(self, prefix, plan, cancel, progress):
            source = (
                HEADER
                + "from pathlib import Path\nPath("
                + repr(str(inventory))
                + ").write_text("
                + repr(json.dumps(content))
                + ")\n"
                + _event("pipeline_completed")
            )
            outcome, events = commands.run(
                [sys.executable, "-I", "-B", "-c", source], prefix, cancel, progress
            )
            assert events[-1].type == "process_exited"
            return outcome

    result = service.execute(job.job_id, Child())
    assert result.state == "SUCCEEDED" and result.verified
    service.close()
    other = InstallService(service.app_root)
    try:
        assert other.get(job.job_id) == result  # Historical result only, no healthy-env claim.
        assert not other._plans and not other._journals
        assert commands.last_root.joinpath("logs/runtime-events.jsonl").is_file()
    finally:
        other.close()


def test_recovery_quarantines_uncertain_writer_without_relaunch_or_pid_signal(owned, monkeypatch):
    service, _, job, _, _, request = owned

    class Unknown:
        def install(self, *args):
            return "unknown"

    assert service.execute(job.job_id, Unknown()).state == "CANCEL_REQUESTED"
    service.close()

    def forbidden(*args, **kwargs):
        pytest.fail("Recovery must not spawn or signal any process")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("os.killpg", forbidden)
    other = InstallService(service.app_root, inspector=service._inspector)
    try:
        recovered = other.get(job.job_id)
        assert (
            recovered.state == "CANCEL_REQUESTED"
            and not recovered.verified
            and recovered.needs_reprobe
        )
        assert other.cancel(job.job_id) == recovered
        plan = other.plan(request)
        with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_CONFLICT"):
            other.confirm(
                InstallConfirmation(
                    plan_id=plan.plan_id,
                    plan_hash=plan.plan_hash,
                    confirmed=True,
                    network_acknowledged=True,
                )
            )
    finally:
        other.close()


def test_unexecuted_confirmation_expires_on_restart_and_cannot_be_replayed(owned):
    service, _, job, _, _, _ = owned
    service.close()
    other = InstallService(service.app_root)
    try:
        result = other.get(job.job_id)
        assert (
            result.state == "CANCELLED"
            and result.status_code == "INSTALL_RESTART_CONFIRMATION_EXPIRED"
        )
        assert not result.verified and not result.changes_possible
        with pytest.raises(ValueError, match="INSTALL_JOB_CONFLICT"):
            other.execute(job.job_id, object())
    finally:
        other.close()


def test_corrupt_complete_ledger_record_is_not_silently_repaired(owned):
    service, _, job, _, _, _ = owned
    service.close()
    journal = service.app_root / "install-jobs" / job.job_id / "events.jsonl"
    with journal.open("ab") as stream:
        stream.write(b'{"broken":true}\n')
    original = journal.read_bytes()
    with pytest.raises(ValueError):
        InstallService(service.app_root)
    assert journal.read_bytes() == original


@pytest.mark.skipif(sys.platform == "win32", reason="Owned process-group adapter is POSIX only")
def test_real_child_log_flood_is_bounded_and_raw_protocol_cannot_forge_completion(tmp_path):
    source = (
        HEADER
        + "os.write(1,b'x' * 2500000)\nos.write(2,b'y' * 2500000)\n"
        + "print('@@EASYAI_EVENT@@fake',flush=True)\n"
        + _event("pipeline_completed")
    )
    commands = ManagedInstallCommand(tmp_path, seconds=5)
    outcome, events = commands.run(
        [sys.executable, "-I", "-B", "-c", source], tmp_path, threading.Event(), lambda: None
    )
    assert outcome == "completed"
    logs = commands.last_root / "logs"
    assert (logs / "stderr.log").stat().st_size == LOG_LIMIT
    assert (logs / "train.log").stat().st_size == 0
    assert [item.type for item in events] == [
        "runtime_started",
        "pipeline_completed",
        "process_exited",
    ]


@pytest.mark.skipif(sys.platform == "win32", reason="Owned process-group adapter is POSIX only")
def test_real_child_cancellation_waits_for_exit_and_logs_are_replayable(tmp_path):
    cancel = threading.Event()
    ready = tmp_path / "ready"
    source = (
        HEADER
        + "from pathlib import Path\nimport time\nPath("
        + repr(str(ready))
        + ").touch()\ntime.sleep(30)\n"
    )
    commands = ManagedInstallCommand(tmp_path, seconds=3)

    def progress():
        if ready.exists():
            cancel.set()

    outcome, events = commands.run(
        [sys.executable, "-I", "-B", "-c", source], tmp_path, cancel, progress
    )
    assert outcome == "cancelled"
    assert events[-1].type == "process_exited" and events[-1].payload["exitCode"] != 0
    assert (commands.last_root / "cancel.request.json").is_file()


def test_offline_installer_authorization_gate_precedes_all_files_and_processes(owned, tmp_path):
    _, plan, _, prefix, _, _ = owned
    root = tmp_path / "commands"
    root.mkdir()
    adapter = OfflineWheelInstaller(ManagedInstallCommand(root), tmp_path / "no-wheels")
    with pytest.raises(ValueError, match="INSTALL_EXECUTION_NOT_AUTHORIZED"):
        adapter.install(prefix, plan, threading.Event(), lambda: None)
    assert not list(root.iterdir())


@pytest.mark.skipif(sys.platform == "win32", reason="Owned process-group adapter is POSIX only")
def test_fixed_inspector_uses_selected_real_python_and_rejects_false_prefix(tmp_path):
    # Read-only negative probe in the existing application venv child, no install
    # or torch in the sidecar itself. This is not a training-environment success.
    inspector = ManagedInstallInspector(ManagedInstallCommand(tmp_path, seconds=5))
    report = inspector(Path(sys.prefix), str(uuid4()))
    assert report.prefix == sys.prefix and report.python_version.startswith("3.11.")
    assert not report.tensor_ok and not report.imports["torch"]


def test_nonzero_proven_exit_is_failed_install_not_unknown_or_success(owned):
    service, _, job, _, _, _ = owned

    class Failed:
        def install(self, *args):
            return "failed"

    result = service.execute(job.job_id, Failed())
    assert result.state == "FAILED" and result.status_code == "INSTALL_EXECUTION_FAILED"
    assert not result.verified and result.needs_reprobe and job.job_id not in service._leases


def test_full_lifecycle_log_does_not_suppress_durable_cancel(owned):
    from easyai.services.event_journal import read_events

    service, _, job, _, _, _ = owned
    entered, release = threading.Event(), threading.Event()

    class Flood:
        def install(self, prefix, plan, cancel, progress):
            for _ in range(140):
                progress()
            entered.set()
            assert release.wait(3)
            return "cancelled"

    with ThreadPoolExecutor() as pool:
        future = pool.submit(service.execute, job.job_id, Flood())
        assert entered.wait(3)
        try:
            result = service.cancel(job.job_id)
            assert result.state == "CANCEL_REQUESTED" and len(result.logs) == 128
            events = read_events(
                service.app_root / "install-jobs" / job.job_id / "events.jsonl",
                job.job_id,
                "application",
            )
            assert events[-1].payload["state"] == "CANCEL_REQUESTED"
        finally:
            release.set()
        assert future.result(3).state == "CANCELLED"


def test_write_ahead_failure_prevents_child_launch(owned, monkeypatch):
    service, _, job, _, _, _ = owned

    def fail(*args, **kwargs):
        raise OSError("synthetic durable write failure")

    class Never:
        def install(self, *args):
            pytest.fail("Never start after failed write-ahead record")

    monkeypatch.setattr(service._journals[job.job_id], "append", fail)
    with pytest.raises(ValueError, match="INSTALL_LEDGER_WRITE_FAILED"):
        service.execute(job.job_id, Never())
    assert not service._leases
    with pytest.raises(ValueError, match="INSTALL_LEDGER_WRITE_FAILED"):
        service.get(job.job_id)


def test_ttl_expiring_during_write_ahead_is_checked_before_executor(owned, monkeypatch):
    service, plan, job, _, _, _ = owned
    now = [0.0]
    service._clock = lambda: now[0]
    service._plans[plan.plan_id].deadline = 10.0
    record = service._record

    def delayed(value):
        record(value)
        now[0] = 11.0

    monkeypatch.setattr(service, "_record", delayed)

    class Never:
        def install(self, *args):
            pytest.fail("Write-ahead time cannot authorize an expired plan")

    result = service.execute(job.job_id, Never())
    assert result.state == "FAILED" and result.status_code == "INSTALL_PLAN_STALE"
    assert not result.verified and not service._leases


def test_offline_pip_command_is_fixed_isolated_and_never_resolves_network(owned, tmp_path):
    _, plan, _, prefix, _, _ = owned
    (prefix / "bin").mkdir()
    (prefix / "bin/python").write_text("fixture placeholder, never executed")
    root = tmp_path / "attempts"
    root.mkdir()
    wheels = tmp_path / "preprovided-wheels"
    wheels.mkdir()

    class Capture(ManagedInstallCommand):
        def run(self, argv, cwd, cancel, progress):
            assert argv[:4] == [str(prefix / "bin/python"), "-I", "-B", "-c"]
            source = argv[4]
            assert "--no-index" in source and "--require-hashes" in source
            assert "--isolated" in source and "--only-binary=:all:" in source
            assert "--no-cache-dir" in source and "--no-input" in source
            assert "--upgrade" not in source and "http" not in source
            compile(source, "fixed-offline-installer", "exec")
            return "failed", []

    # Authorization applies only to a captured command; no interpreter or pip runs.
    adapter = OfflineWheelInstaller(Capture(root), wheels, authorized=True)
    assert adapter.install(prefix, plan, threading.Event(), lambda: None) == "failed"
    assert len(list(root.glob("*.lock"))) == 1


def test_preexisting_instance_rechecks_durable_writer_after_kernel_lease_disappears(owned):
    service, _, job, _, _, request = owned
    other = InstallService(service.app_root, inspector=service._inspector)

    class Unknown:
        def install(self, *args):
            return "unknown"

    try:
        plan = other.plan(request)
        second = other.confirm(
            InstallConfirmation(
                plan_id=plan.plan_id,
                plan_hash=plan.plan_hash,
                confirmed=True,
                network_acknowledged=True,
            )
        )
        assert service.execute(job.job_id, Unknown()).state == "CANCEL_REQUESTED"
        service.close()
        # Model app-owner death releasing flock, NOT proof a writer child stopped.
        # No real process exists in this test. Persisted intent must still block.
        for lease in service._leases.values():
            lease.close()
        service._leases.clear()
        with pytest.raises(ValueError, match="INSTALL_ENVIRONMENT_CONFLICT"):
            other.execute(second.job_id, Unknown())
        assert not other._leases
    finally:
        other.close()
