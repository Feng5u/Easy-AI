"""Real owned POSIX persistence and bounded faults; no SSH/training processes."""

import os
import stat
from types import SimpleNamespace

import pytest

from easyai.security.remote_cache import local_directory
from easyai.services.run_service import RunService
from test_run_service import prepare


class Monitor:
    def __init__(self):
        self.directories = []
        self.locks = []
        self.events = []
        self.failure = None

    def __call__(self, path):
        return Directory(self, local_directory(path))

    def assert_closed(self):
        assert self.directories and all(item.closed for item in self.directories)
        assert all(item.raw.fd is None for item in self.locks)


class Directory:
    def __init__(self, monitor, raw):
        self.monitor, self.raw, self.path = monitor, raw, raw.path
        self.closed = False
        monitor.directories.append(self)

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def child(self, name, *, create=False):
        return Directory(self.monitor, self.raw.child(name, create=create))

    def new_child(self, name):
        return Directory(self.monitor, self.raw.new_child(name))

    def owner_lock(self, name):
        result = Lock(self.monitor, self.path, name, self.raw.owner_lock(name))
        self.monitor.locks.append(result)
        return result

    def open_file(self, name, access="read"):
        self.monitor.events.append(("open", self.path, name, access))
        if self.monitor.failure == (self.path, "journal_open") and name == "events.jsonl":
            raise OSError("test journal open failure")
        return self.raw.open_file(name, access)

    def sync_file(self, fd):
        self.monitor.events.append(("sync_file", self.path))
        if self.monitor.failure == (self.path, "file_flush"):
            raise OSError("test file flush failure")
        self.raw.sync_file(fd)

    def publish(self, source, target, *, replace=False):
        self.monitor.events.append(("publish", self.path, target))
        if self.monitor.failure == (self.path, "publish"):
            raise OSError("test publication failure")
        self.raw.publish(source, target, replace=replace)

    def close(self):
        self.raw.close()
        if not self.closed:
            self.monitor.events.append(("directory_close", self.path))
        self.closed = True


class Lock:
    def __init__(self, monitor, path, name, raw):
        self.monitor, self.path, self.name, self.raw = monitor, path, name, raw

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def close(self):
        self.raw.close()
        self.monitor.events.append(("lock_close", self.path, self.name))


@pytest.fixture
def protected(owned):
    if os.name != "posix":
        pytest.skip("Actual POSIX handle faults, not Windows acceptance")
    project, previous, doc, phash, data = owned
    previous.close()
    monitor = Monitor()
    service = RunService(previous.root, storage=monitor)
    values = (project, service, doc, phash, data)
    try:
        yield values, monitor
    finally:
        service.close()
        monitor.assert_closed()


@pytest.mark.parametrize("action", ["get", "persist", "journal", "core"])
def test_root_replacement_rejects_reads_publication_and_core_before_io(protected, action):
    values, _ = protected
    service = values[1]
    run = prepare(values)
    before = (service.root / "catalog.json").read_bytes()
    held = service.root.with_name("held-root")
    service.root.rename(held)
    service.root.mkdir()
    operations = {
        "get": lambda: service.get(run.run_id),
        "persist": service._persist,
        "journal": lambda: service._journal(run.run_id),
        "core": lambda: service.remote.core(run.run_id),
    }
    with pytest.raises(ValueError, match="REPLACED"):
        operations[action]()
    assert list(service.root.iterdir()) == []
    assert (held / "catalog.json").read_bytes() == before


def test_held_logs_replacement_cannot_receive_old_journal_writes(protected):
    values, _ = protected
    service = values[1]
    run = prepare(values)
    logs = service.root / run.run_id / "logs"
    logs.rename(logs.with_name("held-logs"))
    logs.mkdir()
    with pytest.raises(ValueError, match="REPLACED"):
        service.events(run.run_id, 0)
    assert list(logs.iterdir()) == []


@pytest.mark.parametrize("window", ["bundle_entry", "bundle_claim", "snapshot"])
def test_prepare_root_replacement_never_redirects_initial_output(
    protected, tmp_path, monkeypatch, window
):
    import easyai.services.run_service as module

    values, _ = protected
    service = values[1]
    outside = tmp_path / "outside"
    outside.mkdir()

    def replace_root():
        service.root.rename(service.root.with_name("held-root"))
        service.root.symlink_to(outside, target_is_directory=True)

    if window == "bundle_entry":
        original = module.export_bundle

        def replace_before_export(*args, **kwargs):
            replace_root()
            return original(*args, **kwargs)

        monkeypatch.setattr(module, "export_bundle", replace_before_export)
    elif window == "bundle_claim":
        original = service._store.new_child

        def replace_after_claim(name):
            result = original(name)
            replace_root()
            return result

        monkeypatch.setattr(service._store, "new_child", replace_after_claim)
    else:
        original = service._write_run_file

        def replace_before_snapshot(*args, **kwargs):
            replace_root()
            return original(*args, **kwargs)

        monkeypatch.setattr(service, "_write_run_file", replace_before_snapshot)
    with pytest.raises((ValueError, OSError)):
        prepare(values)
    assert list(outside.iterdir()) == []
    assert not service._ledger.entries and not service._supervisors


def test_exclusive_run_identity_is_held_across_bundle_and_snapshot(protected, monkeypatch):
    import easyai.services.run_service as module

    values, _ = protected
    service = values[1]
    original = module.export_bundle
    replaced = []

    def replace_after_export(*args, **kwargs):
        result = original(*args, **kwargs)
        directory = kwargs["directory"]
        assert directory is service._run_directories[directory.path.name]
        directory.path.rename(directory.path.with_name("held-run"))
        directory.path.mkdir(mode=0o700)
        replaced.append(directory.path)
        return result

    monkeypatch.setattr(module, "export_bundle", replace_after_export)
    with pytest.raises(ValueError, match="REPLACED"):
        prepare(values)
    assert replaced and all(list(path.iterdir()) == [] for path in replaced)
    assert not service._ledger.entries and not service._supervisors


@pytest.mark.parametrize("failure", ["file_flush", "publish", "directory_flush"])
def test_uncertain_catalog_poisoned_until_reopen_never_restarts(protected, failure, monkeypatch):
    values, monitor = protected
    service = values[1]
    run = prepare(values)
    catalog = service.root / "catalog.json"
    before = catalog.read_bytes()
    service._ledger.entries[run.run_id].run.status = "STARTING"
    if failure == "directory_flush":
        # Fail the real directory fsync after os.replace, not a pre-call stub.
        real_fsync = os.fsync

        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("test directory flush failure")
            real_fsync(fd)

        monkeypatch.setattr(os, "fsync", fail_directory)
    else:
        monitor.failure = (service.root, failure)
    with pytest.raises(OSError, match="test"):
        service._persist()
    after = catalog.read_bytes()
    assert (after == before) == (failure != "directory_flush")
    for action in (
        service._persist,
        lambda: service.get(run.run_id),
        lambda: service.remote.core(run.run_id),
    ):
        with pytest.raises(ValueError, match="WRITE_UNCERTAIN"):
            action()
    assert not list(service.root.glob(".record-*"))
    service.close()
    monitor.assert_closed()
    monitor.failure = None
    monkeypatch.undo()
    if failure == "directory_flush":
        from easyai.runtime.supervisor import ManagedSupervisor

        monkeypatch.setattr(ManagedSupervisor, "start", lambda *_: pytest.fail("Must never start"))
        restored = RunService(service.root)
        try:
            assert restored.get(run.run_id).status == "STARTING"
            with pytest.raises(ValueError, match="PROCESS_IDENTITY_UNKNOWN"):
                restored.start(run.run_id)
        finally:
            restored.close()


def test_journal_initialization_failure_releases_its_lock_and_log_handle(protected):
    values, monitor = protected
    service = values[1]
    # prepare creates immutable inputs, then fails before any execution intent.
    original_child = service._store.new_child

    def fail_logs(name):
        result = original_child(name)
        original = result.child

        def child(part, *, create=False):
            nested = original(part, create=create)
            if part == "logs":
                monitor.failure = (nested.path, "journal_open")
            return nested

        result.child = child
        return result

    service._store.new_child = fail_logs
    with pytest.raises(OSError, match="journal open"):
        prepare(values)
    assert not service._journals and not service._log_directories
    logs = [item for item in monitor.directories if item.path.name == "logs"]
    assert logs and all(item.closed for item in logs)
    journal_locks = [item for item in monitor.locks if item.name.endswith("writer.lock")]
    assert journal_locks and all(item.raw.fd is None for item in journal_locks)


def test_borrowed_journal_and_owner_locks_close_before_directories(protected):
    values, monitor = protected
    service = values[1]
    run = prepare(values)
    logs = service.root / run.run_id / "logs"
    assert service._journals[run.run_id]._directory is service._log_directories[run.run_id]
    monitor.events.clear()
    service.close()
    monitor.assert_closed()
    events = monitor.events
    log_close = events.index(("directory_close", logs))
    assert events.index(("lock_close", logs, "events.jsonl.writer.lock")) < log_close
    assert events.index(("lock_close", service.root, ".runs.lock")) < log_close
    assert log_close < events.index(("directory_close", logs.parent))
    assert events.index(("directory_close", logs.parent)) < events.index(
        ("directory_close", service.root)
    )
    # Permanent inode remains, and a new owner replays without launching anything.
    inode = (service.root / ".runs.lock").stat().st_ino
    restored = RunService(service.root)
    try:
        assert restored.get(run.run_id).status == "CREATED"
        assert (service.root / ".runs.lock").stat().st_ino == inode
    finally:
        restored.close()


@pytest.mark.parametrize("bad_catalog", ["invalid_json", "symlink", "fifo"])
def test_catalog_initialization_failure_closes_all_ownership(tmp_path, bad_catalog):
    if os.name != "posix":
        pytest.skip("POSIX namespace faults")
    root = tmp_path / "runs"
    root.mkdir()
    catalog = root / "catalog.json"
    if bad_catalog == "invalid_json":
        catalog.write_bytes(b"{invalid")
    elif bad_catalog == "symlink":
        outside = tmp_path / "untouched"
        outside.write_bytes(b"{}")
        catalog.symlink_to(outside)
    else:
        os.mkfifo(catalog)
    monitor = Monitor()
    with pytest.raises((ValueError, OSError)):
        RunService(root, storage=monitor)
    monitor.assert_closed()
    if bad_catalog == "symlink":
        assert outside.read_bytes() == b"{}"
    catalog.unlink()
    restored = RunService(root)
    restored.close()


def test_second_owner_failure_does_not_close_first_owner(protected):
    values, _ = protected
    service = values[1]
    other = Monitor()
    with pytest.raises(ValueError, match="RUN_STORE_HELD"):
        RunService(service.root, storage=other)
    other.assert_closed()
    service._verify()


def test_recovery_initialization_failure_closes_journal_before_borrowed_handles(
    protected, monkeypatch
):
    from easyai.services.remote_runs import RemoteRuns

    values, _ = protected
    service = values[1]
    run = prepare(values)
    service.close()

    def fail_after_journal(remote):
        remote.runs._journal(run.run_id)
        raise OSError("test initialization failure")

    other = Monitor()
    with monkeypatch.context() as fault:
        fault.setattr(RemoteRuns, "recover", fail_after_journal)
        with pytest.raises(OSError, match="initialization failure"):
            RunService(service.root, storage=other)
    other.assert_closed()
    restored = RunService(service.root)
    restored.close()


def test_unverified_host_does_not_gate_local_startup_but_cannot_create_remote_core(
    tmp_path, monkeypatch
):
    import easyai.services.run_service as module

    # Capability selection only, not Windows API emulation or acceptance.
    monkeypatch.setattr(module, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(module, "local_directory", lambda *_: pytest.fail("Must not select POSIX"))
    service = RunService(tmp_path)
    try:
        assert service._store is None and not service._ledger.entries
        with pytest.raises(ValueError, match="PLATFORM_UNVERIFIED"):
            service.remote.core("00000000-0000-4000-8000-000000000000")
    finally:
        service.close()
