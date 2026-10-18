"""Offline identity protocol: synthetic PUBLIC bytes, no private keys or SSH sockets."""

import base64
import os
import socket
import struct
import threading

from fastapi.testclient import TestClient
import paramiko
import pytest

from easyai.api import create_app
from easyai.domain.ssh import SshEndpoint, SshFailure
from easyai.security.host_keys import HostKeyStore, PublicIdentity
from easyai.services.local_workspace import LocalWorkspace
from easyai.services.ssh_client import SshClient


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Offline suite must never dial a network socket")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def key(seed=0):
    # SSH public wire format only. No keypair/private material is generated.
    name = b"ssh-ed25519"
    raw = (
        struct.pack(">I", len(name))
        + name
        + struct.pack(">I", 32)
        + bytes((seed + i) % 256 for i in range(32))
    )
    return paramiko.Ed25519Key(data=raw)


def pin(store, endpoint, public):
    observed = store.observe(endpoint, PublicIdentity.from_key(public))
    assert observed.trust_state == "unknown"
    return store.confirm(observed.challenge_id, observed.fingerprint)


class SocketFixture:
    def __init__(self):
        self.closed = False
        self.timeout = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def close(self):
        self.closed = True


class TransportFixture:
    def __init__(self, public, hang=False):
        self.public = public
        self.hang = hang
        self.active = True
        self.closed = False
        self.authenticated = False
        self.auth_calls = []
        self.handshake_timeout = 0
        self.banner_timeout = 0
        self.auth_timeout = 0
        self.error = None

    def start_client(self, event):
        if not self.hang:
            event.set()

    def get_remote_server_key(self):
        return self.public

    def is_active(self):
        return self.active

    def is_authenticated(self):
        return self.authenticated

    def auth_password(self, username, password, event, fallback):
        self.auth_calls.append(("password", username, fallback))
        if self.error:
            raise RuntimeError(self.error + password)
        self.authenticated = True
        event.set()

    def auth_publickey(self, username, key, event):
        self.auth_calls.append(("publickey", username))
        self.authenticated = True
        event.set()

    def close(self):
        self.closed = True
        self.active = False


def client(store, public=None, hang=False):
    connection = SocketFixture()
    transport = TransportFixture(public or key(), hang)
    return (
        SshClient(
            store, dial=lambda endpoint, timeout: connection, transport=lambda sock: transport
        ),
        connection,
        transport,
    )


def test_unknown_probe_requires_explicit_exact_confirmation_then_pins_and_never_authenticates(
    tmp_path,
):
    store = HostKeyStore(tmp_path / "app-owned")
    endpoint = SshEndpoint(host="School.Example.", port=2222)
    ssh, connection, transport = client(store)
    observation = ssh.probe(endpoint)
    assert observation.endpoint.host == "school.example"
    assert observation.fingerprint == key().fingerprint
    assert observation.trust_state == "unknown" and observation.challenge_id
    assert connection.closed and transport.closed and transport.auth_calls == []
    assert not store.path.exists()
    with pytest.raises(ValueError, match="MISMATCH"):
        store.confirm(observation.challenge_id, "SHA256:" + "A" * 43)
    assert not store.path.exists()
    assert store.confirm(observation.challenge_id, observation.fingerprint).trust_state == "trusted"
    raw = store.path.read_text()
    assert raw.startswith("[school.example]:2222 ssh-ed25519 ")
    if os.name == "posix":
        assert store.path.stat().st_mode & 0o777 == 0o600
    reopened = HostKeyStore(store.root)
    assert reopened.observe(endpoint, PublicIdentity.from_key(key())).trust_state == "trusted"
    changed = reopened.observe(endpoint, PublicIdentity.from_key(key(1)))
    assert changed.trust_state == "changed" and changed.challenge_id is None
    assert changed.previous_fingerprint == observation.fingerprint
    assert store.path.read_text() == raw
    assert (
        reopened.observe(
            SshEndpoint(host=endpoint.host, port=22), PublicIdentity.from_key(key())
        ).trust_state
        == "unknown"
    )


def test_untrusted_or_changed_connection_cannot_reach_authentication(tmp_path):
    store = HostKeyStore(tmp_path / "state")
    endpoint = SshEndpoint(host="offline.invalid")
    for public, expected in [(key(), "CONFIRMATION_REQUIRED"), (key(1), "CHANGED")]:
        if public == key(1):
            pin(store, endpoint, key())
        ssh, connection, transport = client(store, public)
        with pytest.raises(ValueError, match=expected):
            ssh.connect_verified(endpoint)
        assert connection.closed and transport.closed
        assert transport.auth_calls == []


def test_authentication_rechecks_identity_and_trust_and_closes_on_failures(tmp_path):
    endpoint = SshEndpoint(host="offline.invalid")
    store = HostKeyStore(tmp_path / "state")
    pin(store, endpoint, key())
    ssh, connection, transport = client(store)
    session = ssh.connect_verified(endpoint)
    transport.public = key(2)
    with pytest.raises(SshFailure, match="SSH_HOST_KEY_CHANGED"):
        session.authenticate_password("student", "unit-only-not-a-real-credential")
    assert transport.auth_calls == [] and connection.closed and transport.closed

    ssh, connection, transport = client(store)
    with ssh.connect_verified(endpoint) as session:
        session.authenticate_password("student", "unit-only-not-a-real-credential")
        assert transport.auth_calls == [("password", "student", False)]
        assert transport.authenticated
    assert transport.closed and connection.closed

    ssh, connection, transport = client(store)
    session = ssh.connect_verified(endpoint)
    transport.error = "SDK leaked: "
    with pytest.raises(SshFailure) as raised:
        session.authenticate_password("student", "DO_NOT_LEAK_TEST_MARKER")
    assert str(raised.value) == "SSH_AUTH_FAILED" and raised.value.__suppress_context__
    assert "DO_NOT_LEAK" not in repr(raised.value)
    assert transport.closed and connection.closed


def test_cancel_and_handshake_failure_release_owned_resources_without_auth(tmp_path):
    store = HostKeyStore(tmp_path / "state")
    endpoint = SshEndpoint(host="offline.invalid")
    cancel = threading.Event()
    ssh, connection, transport = client(store, hang=True)
    original = transport.start_client

    def start(event):
        original(event)
        cancel.set()

    transport.start_client = start
    with pytest.raises(SshFailure, match="SSH_CANCELLED"):
        ssh.probe(endpoint, cancel)
    assert transport.closed and connection.closed and transport.auth_calls == []
    ssh, connection, transport = client(store)

    def failure(event):
        raise RuntimeError("untrusted server text")

    transport.start_client = failure
    with pytest.raises(SshFailure) as raised:
        ssh.probe(endpoint)
    assert str(raised.value) == "SSH_CONNECTION_FAILED"
    assert transport.closed and connection.closed


def test_expiry_caps_racing_confirmation_and_strict_known_hosts(tmp_path):
    now = [1.0]
    store = HostKeyStore(tmp_path / "state", clock=lambda: now[0])
    endpoint = SshEndpoint(host="offline.invalid")
    observed = store.observe(endpoint, PublicIdentity.from_key(key()))
    now[0] = 602
    with pytest.raises(ValueError, match="EXPIRED"):
        store.confirm(observed.challenge_id, observed.fingerprint)
    first = store.observe(endpoint, PublicIdentity.from_key(key()))
    other = HostKeyStore(store.root)
    pin(other, endpoint, key(2))
    with pytest.raises(ValueError, match="CHANGED"):
        store.confirm(first.challenge_id, first.fingerprint)
    raw = store.path.read_bytes()
    now[0] += 601
    for index in range(32):
        store.observe(SshEndpoint(host=f"h{index}.invalid"), PublicIdentity.from_key(key()))
    with pytest.raises(ValueError, match="LIMIT"):
        store.observe(SshEndpoint(host="overflow.invalid"), PublicIdentity.from_key(key()))
    assert store.path.read_bytes() == raw
    store.path.write_text("@revoked school ssh-ed25519 bad\n")
    with pytest.raises(ValueError, match="STORE_INVALID"):
        store.observe(endpoint, PublicIdentity.from_key(key()))


def test_host_store_nonregular_and_symlink_inputs_fail_closed_without_hanging(tmp_path):
    store = HostKeyStore(tmp_path / "state")
    endpoint = SshEndpoint(host="offline.invalid")
    if os.name == "posix":
        os.mkfifo(store.path)
        with pytest.raises(ValueError, match="FILE_NOT_REGULAR"):
            store.observe(endpoint, PublicIdentity.from_key(key()))
        store.path.unlink()
    target = tmp_path / "private-existing"
    target.write_bytes(b"preserve")
    store.path.symlink_to(target)
    with pytest.raises(OSError):
        store.observe(endpoint, PublicIdentity.from_key(key()))
    assert target.read_bytes() == b"preserve"


@pytest.mark.parametrize(
    "host",
    ["host; command", "host/name", "user@host", "[::1]", "127.1", "a\n", "x%eth0", "-bad.invalid"],
)
def test_invalid_hosts_are_rejected_before_any_transport(host):
    with pytest.raises(ValueError):
        SshEndpoint(host=host)


def test_authenticated_probe_api_accepts_no_credentials_and_confirmation_is_bound_to_probe(
    tmp_path,
):
    workspace = LocalWorkspace(tmp_path / "state")
    store = HostKeyStore(tmp_path / "host-state")
    ssh, connection, transport = client(store)
    workspace._ssh_client = ssh
    api = TestClient(create_app("offline-test-token", workspace=workspace))
    headers = {"Authorization": "Bearer offline-test-token"}
    try:
        assert (
            api.post("/api/v1/connections/probe", json={"host": "offline.invalid"}).status_code
            == 401
        )
        rejected = api.post(
            "/api/v1/connections/probe",
            json={"host": "offline.invalid", "password": "DO_NOT_ECHO_TEST_MARKER"},
            headers=headers,
        )
        assert rejected.status_code == 422
        assert "DO_NOT_ECHO" not in rejected.text and "password" not in rejected.text
        response = api.post(
            "/api/v1/connections/probe", json={"host": "offline.invalid"}, headers=headers
        )
        assert response.status_code == 200 and response.json()["trustState"] == "unknown"
        observation = response.json()
        confirmed = api.post(
            "/api/v1/connections/trust-host-key",
            json={
                "challengeId": observation["challengeId"],
                "fingerprint": observation["fingerprint"],
            },
            headers=headers,
        )
        assert confirmed.status_code == 200 and confirmed.json()["trustState"] == "trusted"
        assert transport.auth_calls == [] and connection.closed and transport.closed
    finally:
        workspace.close()


def test_public_identity_rejects_wrong_type_trailing_bytes_and_noncanonical_keys():
    public = key()
    for algorithm, raw in [
        ("ssh-dss", public.asbytes()),
        ("ssh-ed25519", public.asbytes() + b"tail"),
        ("ssh-ed25519", b"x" * 17000),
    ]:
        with pytest.raises(ValueError, match="SSH_HOST_KEY_INVALID"):
            PublicIdentity.parse(algorithm, raw)
    assert (
        base64.b64decode(base64.b64encode(public.asbytes())) == PublicIdentity.from_key(public).raw
    )


def test_replaced_trust_root_cannot_redirect_reads_or_confirmation(tmp_path):
    root = tmp_path / "state"
    store = HostKeyStore(root)
    endpoint = SshEndpoint(host="offline.invalid")
    observation = store.observe(endpoint, PublicIdentity.from_key(key()))
    outside = tmp_path / "outside"
    outside.mkdir()
    root.rename(tmp_path / "original")
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="SSH_TRUST_PATH_INVALID"):
        store.confirm(observation.challenge_id, observation.fingerprint)
    with pytest.raises(ValueError, match="SSH_TRUST_PATH_INVALID"):
        store.observe(endpoint, PublicIdentity.from_key(key()))
    assert list(outside.iterdir()) == []
    assert list((tmp_path / "original").iterdir()) == []


def test_root_replaced_during_publication_keeps_all_writes_anchored(tmp_path, monkeypatch):
    root = tmp_path / "state"
    store = HostKeyStore(root)
    observation = store.observe(SshEndpoint(host="offline.invalid"), PublicIdentity.from_key(key()))
    outside = tmp_path / "outside"
    outside.mkdir()
    original = store._verify_publication

    def redirect():
        root.rename(tmp_path / "original")
        root.symlink_to(outside, target_is_directory=True)
        original()

    monkeypatch.setattr(store, "_verify_publication", redirect)
    with pytest.raises(ValueError, match="SSH_TRUST_PATH_INVALID"):
        store.confirm(observation.challenge_id, observation.fingerprint)
    assert list(outside.iterdir()) == []
    assert list((tmp_path / "original").iterdir()) == []


def test_handshake_and_auth_timeouts_close_resources_without_sdk_text(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import easyai.services.ssh_client as module

    clock = [0]

    def monotonic():
        clock[0] += 10
        return clock[0]

    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=monotonic))
    store = HostKeyStore(tmp_path / "state")
    endpoint = SshEndpoint(host="offline.invalid")
    ssh, connection, transport = client(store, hang=True)
    with pytest.raises(SshFailure, match="SSH_TIMEOUT"):
        ssh.probe(endpoint)
    assert connection.closed and transport.closed and transport.auth_calls == []
    pin(store, endpoint, key())
    ssh, connection, transport = client(store)
    session = ssh.connect_verified(endpoint)
    # Use the real asynchronous path, with an offline never-completing operation.
    transport.auth_password = lambda *args, **kwargs: None
    with pytest.raises(SshFailure, match="SSH_TIMEOUT"):
        session.authenticate_password("student", "unit-only-not-a-real-credential")
    assert connection.closed and transport.closed


def test_explicit_key_auth_gate_accepts_only_caller_supplied_object(tmp_path):
    store = HostKeyStore(tmp_path / "state")
    endpoint = SshEndpoint(host="offline.invalid")
    pin(store, endpoint, key())
    ssh, connection, transport = client(store)
    with ssh.connect_verified(endpoint) as session:
        # A sentinel consumed only by the fixture; no real private key exists here.
        session.authenticate_public_key("student", object())
        assert transport.auth_calls == [("publickey", "student")]
    assert connection.closed and transport.closed
