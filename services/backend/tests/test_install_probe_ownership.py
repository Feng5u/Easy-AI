"""Deterministic probe cleanup barriers; no interpreter, conda, pip or network."""

from contextlib import contextmanager
import threading

import pytest
from easyai.services import install_process
from easyai.services.install_process import ManagedInstallCommand, ManagedInstallInspector
from easyai.runtime.supervisor import ManagedSupervisor
from test_install_process import owned as owned_fixture
from test_install_service import ControlledExecutor
from test_owned_creation import pending as pending_fixture, Bootstrap, InstallFixture

owned = owned_fixture
pending = pending_fixture


@pytest.mark.parametrize("phase", ["bootstrap", "final", "baseline"])
def test_probe_cleanup_pending_retains_its_lease_and_journal(request, phase, monkeypatch, tmp_path):
    if phase == "bootstrap":
        service, plan, job = request.getfixturevalue("pending")
    else:
        service, plan, job, prefix, _, _ = request.getfixturevalue("owned")
    entered, release = threading.Event(), threading.Event()
    owners = []

    class ProbeOwner:
        def __init__(self, *args, **kwargs):
            self.physical = threading.Thread(target=lambda: (entered.set(), release.wait(8)))
            self.closed = False
            owners.append(self)

        @property
        def quiescent(self):
            return self.closed and not self.physical.is_alive()

        def start(self):
            self.physical.start()
            assert entered.wait(1)

        def wait(self, timeout):
            return 0  # Leader exit alone cannot prove its pipe/cleanup owner quiet.

        @contextmanager
        def snapshot(self):
            yield "COMPLETED", True, 0

        def events(self):
            return []

        def close(self):
            if not release.is_set():
                raise RuntimeError("synthetic probe owner cleanup pending")
            self.physical.join(1)
            self.closed = True

    monkeypatch.setattr(install_process, "ManagedSupervisor", ProbeOwner)
    monkeypatch.setattr(
        "subprocess.Popen", lambda *args, **kwargs: pytest.fail("Never execute a real probe")
    )
    root = tmp_path / "probe-commands"
    root.mkdir()
    inspector = ManagedInstallInspector(ManagedInstallCommand(root))

    def prepare(prefix):
        (prefix / "bin").mkdir(exist_ok=True)
        (prefix / "bin/python").write_text("nonexecutable fixture, never run")
        service._inspector = inspector

    class BootstrapProbe(Bootstrap):
        def create(self, prefix, *args):
            result = super().create(prefix, *args)
            prepare(prefix)
            return result

    class FinalProbe(ControlledExecutor):
        def install(self, prefix, *args):
            result = super().install(prefix, *args)
            prepare(prefix)
            return result

    try:
        if phase == "baseline":
            prepare(prefix)
        result = service.execute(
            job.job_id,
            InstallFixture() if phase == "bootstrap" else FinalProbe(),
            provisioner=BootstrapProbe() if phase == "bootstrap" else None,
        )
        assert entered.is_set() and len(owners) == 1 and owners[0].physical.is_alive()
        assert (
            result.state == "CANCEL_REQUESTED" and result.status_code == "INSTALL_STOP_UNCONFIRMED"
        )
        assert not result.verified and result.needs_reprobe
        assert job.job_id in service._leases and service._journals
        lease = service._leases[job.job_id]
        lease.verify()
        with pytest.raises(ValueError, match="INSTALL_STOP_UNCONFIRMED"):
            service.close()
        assert not service._closed and service._journals and lease.fd is not None
    finally:
        release.set()
        for owner in owners:
            owner.close()
            assert owner.quiescent
        # Test-only retirement: every owner above is a joined stdlib fixture,
        # not evidence permitting production to discard an unknown probe.
        if hasattr(service, "_probes"):
            service._probes.clear()


def test_unknown_probe_blocks_only_its_prefix(owned, tmp_path):
    service, _, _, prefix, _, _ = owned
    from easyai.services.install_service import ProbeReceipt

    entered, release = threading.Event(), threading.Event()
    owners = []

    def inspector(path, nonce):
        worker = threading.Thread(target=lambda: (entered.set(), release.wait(8)))
        owners.append(worker)
        worker.start()
        assert entered.wait(1)
        raise RuntimeError("synthetic unknown cleanup")

    service._inspector = inspector
    first, rejected, independent = ProbeReceipt(), ProbeReceipt(), ProbeReceipt()
    try:
        with pytest.raises(RuntimeError, match="unknown cleanup"):
            service._probe(prefix, "first", first)
        with pytest.raises(ValueError, match="INSTALL_STOP_UNCONFIRMED"):
            service._probe(prefix, "same", rejected)
        assert len(owners) == 1 and rejected.quiescent
        with pytest.raises(RuntimeError, match="unknown cleanup"):
            service._probe(tmp_path / "another-prefix", "other", independent)
        assert len(owners) == 2 and len(service._probes) == 2
        assert not first.cancel.is_set() and not independent.cancel.is_set()
        # Per-job cancellation remains scoped to its own receipt token.
        first.cancel.set()
        assert not independent.cancel.is_set()
        with pytest.raises(ValueError, match="INSTALL_STOP_UNCONFIRMED"):
            service.close()
        assert independent.cancel.is_set() and service._journals
    finally:
        release.set()
        for worker in owners:
            worker.join(1)
            assert not worker.is_alive()
        service._probes.clear()


def test_managed_close_requires_physical_reader_exit(tmp_path, monkeypatch):
    root = tmp_path / "owner"
    root.mkdir()
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("Never start a process"))
    supervisor = ManagedSupervisor(root, "reader-fixture", ["never-executed"], tmp_path)
    release = threading.Event()
    reader = threading.Thread(target=lambda: release.wait(8))
    reader.start()
    supervisor._threads = [reader]
    supervisor._done.set()  # Logical completion cannot replace physical cleanup.
    try:
        with pytest.raises(RuntimeError, match="cleanup is still pending"):
            supervisor.close()
        assert not supervisor.quiescent and not supervisor._closed
    finally:
        release.set()
        reader.join(1)
        assert not reader.is_alive()
        supervisor.close()
    assert supervisor.quiescent
