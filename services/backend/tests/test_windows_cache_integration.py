"""Actual default selector/native NTFS integration; no external SSH/training."""

import os
import socket

import pytest

from easyai.security import remote_cache
from easyai.security.windows_store import WindowsDirectory

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Requires native Windows x64 NTFS")


@pytest.fixture(autouse=True)
def native_default_selector(monkeypatch):
    assert remote_cache.WINDOWS_NATIVE_CACHE_VERIFIED is True
    assert remote_cache.windows_cache_enabled()

    def no_network(*args, **kwargs):
        pytest.fail("Native integration must never connect to an external endpoint")

    monkeypatch.setattr(socket, "create_connection", no_network)


def test_actual_selector_bounded_names_and_source_stream(tmp_path):
    from easyai.domain.data_transfer import TransferBudget
    from easyai.services.data_transfer_source import TransferSource

    source = tmp_path / "source"
    source.mkdir()
    (source / "one.bin").write_bytes(b"one")
    (source / "two.bin").write_bytes(b"two")
    directory = remote_cache.local_directory(source)
    try:
        assert isinstance(directory, WindowsDirectory)
        assert remote_cache.limited_names(directory, 2) == ["one.bin", "two.bin"]
        with pytest.raises(ValueError, match="DATA_TRANSFER_SOURCE_LIMIT"):
            remote_cache.limited_names(directory, 1)
    finally:
        directory.close()
    inventory = TransferSource.inventory(source, TransferBudget(), lambda: None)
    assert len(inventory.files) == 2
    with inventory.open(inventory.files[0], lambda: None) as stream:
        assert stream.read() in (b"one", b"two")


def test_actual_selector_default_runservice_journal_and_recovery(owned):
    from easyai.services.run_service import RunService
    from test_run_service import prepare

    project, service, doc, phash, data = owned
    assert isinstance(service._store, WindowsDirectory)
    try:
        run = prepare((project, service, doc, phash, data))
        assert service._journals[run.run_id]._directory is service._log_directories[run.run_id]
        with pytest.raises(ValueError, match="RUN_STORE_HELD"):
            RunService(service.root)
        assert service.cancel(run.run_id).status == "CANCELLED"
    finally:
        service.close()
    reopened = RunService(service.root)
    try:
        assert isinstance(reopened._store, WindowsDirectory)
        assert reopened.get(run.run_id).status == "CANCELLED"
        assert reopened.events(run.run_id, 0)[-1].payload["status"] == "CANCELLED"
    finally:
        reopened.close()


def test_actual_selector_remote_unknown_start_recovery(tmp_path):
    from test_ssh_run_coordinator import Owner, Transport, auth_for, identity
    from easyai.runners.ssh import RemoteProtocolError, RemoteUnavailable, SshRunCoordinator

    owner = Owner(identity())
    current = [auth_for(owner.identity)]
    coordinator = SshRunCoordinator(tmp_path, owner.identity)
    assert isinstance(coordinator._store, WindowsDirectory)

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
    restored = SshRunCoordinator(tmp_path, owner.identity)
    try:
        current[0] = auth_for(owner.identity)
        restored.attach(current[0], Transport(owner), lambda: current[0])
        assert restored.start().execution_state == "RUNNING"
        assert owner.start_calls == owner.stage_calls == 1
    finally:
        restored.close()
