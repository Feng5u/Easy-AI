"""Windows cache acceptance cannot silently enable host-key trust."""

from types import SimpleNamespace

import pytest

from easyai.security import host_keys


def test_unverified_windows_trust_refuses_before_native_store_or_network(tmp_path, monkeypatch):
    monkeypatch.setattr(host_keys, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(host_keys, "WINDOWS_NATIVE_TRUST_VERIFIED", False)
    with pytest.raises(ValueError, match="SSH_TRUST_PLATFORM_UNVERIFIED"):
        host_keys.HostKeyStore(tmp_path / "must-not-create-trust")
    assert not (tmp_path / "must-not-create-trust").exists()


def test_unverified_windows_trust_blocks_lazy_client_before_dial(tmp_path, monkeypatch):
    from easyai.domain.ssh import SshEndpoint
    from easyai.services.ssh_client import SshClient

    monkeypatch.setattr(host_keys, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(host_keys, "WINDOWS_NATIVE_TRUST_VERIFIED", False)

    def forbidden(*args, **kwargs):
        pytest.fail("Unverified trust must not dial")

    client = SshClient(lambda: host_keys.HostKeyStore(tmp_path / "trust"), dial=forbidden)
    with pytest.raises(ValueError, match="SSH_TRUST_PLATFORM_UNVERIFIED"):
        client.probe(SshEndpoint(host="synthetic.invalid"))
    assert not (tmp_path / "trust").exists()
