"""Synthetic public keys and fake handshake; actual native NTFS trust transactions."""

import os
import socket

import pytest

from easyai.domain.ssh import SshEndpoint
from easyai.security import host_keys
from easyai.security.host_keys import HostKeyStore, PublicIdentity
from easyai.security.windows_store import WindowsDirectory
from easyai.services.ssh_client import SshClient
from test_ssh_identity import SocketFixture, TransportFixture, key

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Requires native Windows x64 NTFS")


@pytest.fixture(autouse=True)
def native_trust_default(monkeypatch):
    # Actual default path: no platform/storage/TOFU/gate injection.
    assert host_keys.WINDOWS_NATIVE_TRUST_VERIFIED is True

    def forbidden(*args, **kwargs):
        pytest.fail("Synthetic handshake must never dial an external endpoint")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def test_native_tofu_explicit_confirmation_reopen_and_changed_key_block(tmp_path):
    store = HostKeyStore(tmp_path / "trust")
    endpoint = SshEndpoint(host="synthetic.invalid", port=2222)
    first, changed = PublicIdentity.from_key(key()), PublicIdentity.from_key(key(1))
    pending = store.observe(endpoint, first)
    assert pending.trust_state == "unknown" and not store.path.exists()
    with pytest.raises(ValueError, match="SSH_HOST_KEY_CONFIRMATION_REQUIRED"):
        store.require_trusted(endpoint, first)
    with pytest.raises(ValueError, match="SSH_CONFIRMATION_MISMATCH"):
        store.confirm(pending.challenge_id, changed.fingerprint)
    assert not store.path.exists()
    assert store.confirm(pending.challenge_id, first.fingerprint).trust_state == "trusted"
    raw = store.path.read_bytes()
    reopened = HostKeyStore(store.root)
    assert reopened.observe(endpoint, first).trust_state == "trusted"
    observed = reopened.observe(endpoint, changed)
    assert observed.trust_state == "changed" and observed.challenge_id is None
    with pytest.raises(ValueError, match="SSH_HOST_KEY_CHANGED"):
        reopened.require_trusted(endpoint, changed)
    assert store.path.read_bytes() == raw
    assert (store.root / ".known-hosts.lock").is_file()


def test_native_trust_competing_confirmation_never_replaces_key(tmp_path):
    endpoint = SshEndpoint(host="synthetic.invalid")
    first, second = HostKeyStore(tmp_path / "trust"), HostKeyStore(tmp_path / "trust")
    one = first.observe(endpoint, PublicIdentity.from_key(key()))
    two = second.observe(endpoint, PublicIdentity.from_key(key(1)))
    first.confirm(one.challenge_id, one.fingerprint)
    raw = first.path.read_bytes()
    with pytest.raises(ValueError, match="SSH_HOST_KEY_CHANGED"):
        second.confirm(two.challenge_id, two.fingerprint)
    assert first.path.read_bytes() == raw


def test_native_trust_writer_lock_releases_and_persists_inode(tmp_path):
    store = HostKeyStore(tmp_path / "trust")
    endpoint = SshEndpoint(host="synthetic.invalid")
    observed = store.observe(endpoint, PublicIdentity.from_key(key()))
    directory = WindowsDirectory(store.root)
    held = directory.writer_lock(".known-hosts.lock")
    try:
        with pytest.raises(ValueError, match="SSH_TRUST_STORE_BUSY"):
            store.confirm(observed.challenge_id, observed.fingerprint)
        assert not store.path.exists()
    finally:
        held.close()
        directory.close()
    store.confirm(observed.challenge_id, observed.fingerprint)
    assert (store.root / ".known-hosts.lock").is_file()


@pytest.mark.parametrize("failure", ["sync", "publish"])
def test_native_trust_failure_keeps_old_store_and_cleans_temporary(tmp_path, monkeypatch, failure):
    store = HostKeyStore(tmp_path / "trust")
    endpoint = SshEndpoint(host="synthetic.invalid")
    first = store.observe(endpoint, PublicIdentity.from_key(key()))
    store.confirm(first.challenge_id, first.fingerprint)
    raw = store.path.read_bytes()
    pending = store.observe(SshEndpoint(host="second.invalid"), PublicIdentity.from_key(key(1)))

    def fail(*args, **kwargs):
        raise OSError("injected native publication failure")

    with monkeypatch.context() as patch:
        patch.setattr(WindowsDirectory, "sync_file" if failure == "sync" else "publish", fail)
        with pytest.raises(OSError):
            store.confirm(pending.challenge_id, pending.fingerprint)
    assert store.path.read_bytes() == raw
    assert list(store.root.glob(".known-hosts-*.tmp")) == []
    assert store.confirm(pending.challenge_id, pending.fingerprint).trust_state == "trusted"


def test_native_trust_root_replacement_is_rejected_before_read_or_write(tmp_path):
    store = HostKeyStore(tmp_path / "trust")
    endpoint = SshEndpoint(host="synthetic.invalid")
    pending = store.observe(endpoint, PublicIdentity.from_key(key()))
    store.root.rename(tmp_path / "old")
    store.root.mkdir()
    for operation in (
        lambda: store.observe(endpoint, PublicIdentity.from_key(key())),
        lambda: store.confirm(pending.challenge_id, pending.fingerprint),
    ):
        with pytest.raises(ValueError, match="SSH_TRUST_PATH_INVALID"):
            operation()
    assert not store.path.exists()


def test_native_trust_nonregular_known_hosts_is_rejected(tmp_path):
    store = HostKeyStore(tmp_path / "trust")
    store.path.mkdir()
    with pytest.raises((ValueError, OSError)):
        store.observe(SshEndpoint(host="synthetic.invalid"), PublicIdentity.from_key(key()))
    assert store.path.is_dir()


def test_native_trust_real_policy_with_local_synthetic_handshake(tmp_path):
    store = HostKeyStore(tmp_path / "trust")
    endpoint = SshEndpoint(host="synthetic.invalid")
    transports = []

    def transport(connection):
        value = TransportFixture(key())
        transports.append(value)
        return value

    client = SshClient(store, dial=lambda *_: SocketFixture(), transport=transport)
    with pytest.raises(ValueError, match="SSH_HOST_KEY_CONFIRMATION_REQUIRED"):
        client.connect_verified(endpoint)
    assert not transports[-1].auth_calls
    pending = client.probe(endpoint)
    store.confirm(pending.challenge_id, pending.fingerprint)
    session = client.connect_verified(endpoint)
    session.close()
    assert not transports[-1].auth_calls  # Trust acceptance never fabricates authentication.
    changed = SshClient(
        store, dial=lambda *_: SocketFixture(), transport=lambda _: TransportFixture(key(1))
    )
    with pytest.raises(ValueError, match="SSH_HOST_KEY_CHANGED"):
        changed.connect_verified(endpoint)
