"""Native NTFS readiness gates. Skipped on Linux; never enables production support.

Only pytest-owned files and bounded stdlib child processes; no SSH or training.
An unsupported ACL/volume/flush is a failed readiness gate, not a skipped success.
"""

import os
import subprocess
import sys

import pytest

from easyai.security.windows_store import WindowsDirectory
from easyai.services.event_journal import EventJournal

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Requires native Windows x64 NTFS")


@pytest.fixture
def directory(tmp_path):
    result = WindowsDirectory(tmp_path)
    try:
        yield result
    finally:
        result.close()


def write(directory, name, raw):
    with os.fdopen(directory.open_file(name, "exclusive"), "wb") as output:
        assert not os.get_inheritable(output.fileno())
        output.write(raw)
        output.flush()
        directory.sync_file(output.fileno())


def test_native_identity_crt_ownership_and_namespace_publication(directory):
    write(directory, "源.bin", b"native NTFS receipt")
    descriptor = directory.open_file("源.bin")
    try:
        assert not os.get_inheritable(descriptor)
        directory.verify_file("源.bin", descriptor)
        before = directory.api.info(directory.api.from_fd(descriptor)).identity
        assert os.read(descriptor, 99) == b"native NTFS receipt"
    finally:
        os.close(descriptor)
    directory.publish("源.bin", "published.bin")
    with pytest.raises(FileExistsError):
        directory.publish("源.bin", "published.bin")
    descriptor = directory.open_file("published.bin")
    try:
        assert directory.api.info(directory.api.from_fd(descriptor)).identity == before
    finally:
        os.close(descriptor)
    write(directory, "replacement.bin", b"replacement")
    directory.publish("replacement.bin", "published.bin", replace=True)
    with os.fdopen(directory.open_file("published.bin"), "rb") as source:
        assert source.read() == b"replacement"
    assert "published.bin" in directory.names()
    directory.remove("published.bin")
    with pytest.raises(FileNotFoundError):
        directory.open_file("published.bin")
    directory.sync()  # Actual directory FlushFileBuffers must succeed, no fallback.


def test_native_protected_journal_recovery_and_permanent_owner_lock(directory):
    path = directory.path / "application.jsonl"
    journal = EventJournal(path, "native-run", "application", directory=directory)
    try:
        assert journal.append("status_changed", None, {"status": "CREATED"}).seq == 1
        with pytest.raises(ValueError, match="JOURNAL_WRITER_HELD"):
            EventJournal(path, "native-run", "application", directory=directory)
    finally:
        journal.close()
    reopened = EventJournal(path, "native-run", "application", directory=directory)
    try:
        assert reopened.after(0)[0].payload == {"status": "CREATED"}
        assert reopened.append("status_changed", None, {"status": "CANCELLED"}).seq == 2
    finally:
        reopened.close()
    assert path.with_name(path.name + ".writer.lock").is_file()


def test_native_legacy_owner_lock_is_never_recovered_by_pid_or_unlink(directory):
    write(directory, ".owner.lock", b"")
    lock = directory.owner_lock(".owner.lock")
    assert lock.fd is None and lock.reason == "PROJECT_LOCK_LEGACY_UNVERIFIED"
    lock.close()
    assert (directory.path / ".owner.lock").read_bytes() == b""


def test_native_multiprocess_kernel_lock_and_abnormal_exit_release(directory):
    # Fixed test program; the only path argument is the pytest-owned directory.
    program = """
import sys
from pathlib import Path
from easyai.security.windows_store import WindowsDirectory
d = WindowsDirectory(Path(sys.argv[1]))
lock = d.owner_lock('.process.lock')
assert lock.fd is not None, lock.reason
print('LOCKED', flush=True)
sys.stdin.buffer.read(1)
lock.close()
d.close()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", program, str(directory.path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    try:
        # communicate is bounded even if native setup fails or hangs.
        from concurrent.futures import ThreadPoolExecutor

        pool = ThreadPoolExecutor(max_workers=1)
        assert child.stdout is not None
        line = pool.submit(child.stdout.readline)
        try:
            assert line.result(timeout=10).rstrip(b"\r\n") == b"LOCKED"
        finally:
            if not line.done():
                child.kill()
            pool.shutdown(wait=True)
        held = directory.owner_lock(".process.lock")
        assert held.fd is None and held.reason == "PROJECT_LOCK_HELD"
        held.close()
        child.kill()  # Kill only this test-owned stdlib lock holder.
        child.communicate(timeout=10)
        acquired = directory.owner_lock(".process.lock")
        try:
            assert acquired.fd is not None
            acquired.verify()
        finally:
            acquired.close()
        assert (directory.path / ".process.lock").is_file()
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)


def test_native_junction_component_is_rejected(tmp_path):
    target, junction = tmp_path / "target", tmp_path / "junction"
    target.mkdir()
    # Windows junctions do not require symlink privileges. Fixed cmd verb,
    # validated test-owned arguments; no user input, elevation, or ACL changes.
    assert all(
        not any(char in str(path) for char in '&|<>^%!?"\r\n') for path in (target, junction)
    )
    subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
        check=True,
        capture_output=True,
        timeout=10,
        shell=False,
    )
    try:
        with pytest.raises(ValueError, match="REPARSE"):
            WindowsDirectory(junction)
    finally:
        os.rmdir(junction)  # Remove the junction itself, never recurse into its target.
    assert target.is_dir()


def test_native_coordinator_unknown_start_never_restarts(tmp_path, monkeypatch):
    # Existing synthetic endpoint; the local store/journal are actual native NTFS.
    import socket
    from test_ssh_run_coordinator import Owner, Transport, auth_for, identity
    from easyai.runners.ssh import RemoteProtocolError, RemoteUnavailable, SshRunCoordinator

    def no_network(*args, **kwargs):
        pytest.fail("Native local storage test must not dial a remote endpoint")

    monkeypatch.setattr(socket, "create_connection", no_network)
    owner = Owner(identity())
    current = [auth_for(owner.identity)]
    coordinator = SshRunCoordinator(tmp_path, owner.identity, storage=WindowsDirectory)

    def lost_ack():
        raise RemoteUnavailable("synthetic lost ACK")

    owner.start_hook = lost_ack
    try:
        coordinator.attach(current[0], Transport(owner), lambda: current[0])
        with pytest.raises(RemoteProtocolError, match="STATE_UNKNOWN"):
            coordinator.start()
        assert coordinator.checkpoint().start_outcome == "unknown"
    finally:
        coordinator.close()
    restored = SshRunCoordinator(tmp_path, owner.identity, storage=WindowsDirectory)
    try:
        current[0] = auth_for(owner.identity)
        restored.attach(current[0], Transport(owner), lambda: current[0])
        recovered = restored.start()  # Recover through inspect, never another start.
        assert recovered.execution_state == "RUNNING"
        assert recovered.start_outcome == "acknowledged" and owner.inspect_calls > 0
        assert owner.start_calls == owner.stage_calls == 1
    finally:
        restored.close()


def test_native_runservice_catalog_and_shared_journal_lifecycle(owned):
    from easyai.services.run_service import RunService
    from test_run_service import prepare

    project, previous, doc, phash, data = owned
    previous.close()
    service = RunService(previous.root, storage=WindowsDirectory)
    try:
        run = prepare((project, service, doc, phash, data))
        assert service._journals[run.run_id]._directory is service._log_directories[run.run_id]
        with pytest.raises(ValueError, match="RUN_STORE_HELD"):
            RunService(previous.root, storage=WindowsDirectory)
        assert service.cancel(run.run_id).status == "CANCELLED"  # No process ever started.
    finally:
        service.close()
    reopened = RunService(previous.root, storage=WindowsDirectory)
    try:
        assert reopened.get(run.run_id).status == "CANCELLED"
        assert reopened.events(run.run_id, 0)[-1].payload["status"] == "CANCELLED"
    finally:
        reopened.close()
