"""Ephemeral synthetic keypairs only; no user keys, credentials, SSH or filesystem key store."""

from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import threading
import base64
import struct

from fastapi.testclient import TestClient
import paramiko
import pytest

from easyai.api import create_app
from easyai.domain.connections import PrivateKeyAuthenticationInput
from easyai.domain.ssh import IdentityRequest, SshFailure
from easyai.services.private_keys import load_private_key
from test_connection_manager import (
    setup as connection_setup,
    no_network as no_network,
    grant,
    control,
)


@pytest.fixture
def key_setup(tmp_path):
    yield from connection_setup.__wrapped__(tmp_path)


@pytest.fixture(scope="module")
def material():
    key = paramiko.RSAKey.generate(2048)
    plain, encrypted = StringIO(), StringIO()
    phrase = "synthetic-test-only-passphrase"
    key.write_private_key(plain)
    key.write_private_key(encrypted, password=phrase)
    yield key, plain.getvalue(), encrypted.getvalue(), phrase
    plain.close()
    encrypted.close()


def key_session(client, expected, hook=None):
    def prepare(session):
        def authenticate(username, key, cancel=None, timeout=None):
            assert not session.mutex._is_owned()
            assert username == "synthetic-user" and key.can_sign()
            assert key.asbytes() == expected.asbytes()
            assert timeout is not None and timeout > 0
            if hook:
                hook(cancel)
            session.auth_calls += 1
            session.authenticated = True

        session.authenticate_public_key = authenticate

    client.session_hook = prepare


def test_plain_and_encrypted_parsers_are_memory_only_and_errors_hide_material(material):
    original, plain, encrypted, phrase = material
    for text, password in ((plain, ""), (encrypted, phrase)):
        parsed = load_private_key(text, password)
        assert parsed.can_sign() and parsed.asbytes() == original.asbytes()
    for text, password in (
        (encrypted, "wrong"),
        ("invalid-secret-body", phrase),
        (plain + "\0", phrase),
    ):
        with pytest.raises(SshFailure) as failure:
            load_private_key(text, password)
        assert text not in str(failure.value) and phrase not in str(failure.value)
    with pytest.raises(SshFailure, match="SSH_KEY_PASSPHRASE_REQUIRED"):
        load_private_key(encrypted, "")


def test_key_authentication_reuses_trust_grant_fixed_lease_and_does_not_persist_secrets(
    key_setup, material, tmp_path, caplog
):
    manager, identities, client, clock, _, _ = key_setup
    original, _, encrypted, phrase = material
    key_session(client, original)
    request = grant(identities)
    info = manager.authenticate_private_key(request, encrypted, phrase)
    assert info.method == "private_key" and info.authenticated and info.expires_in_seconds == 300
    assert manager.current(control(info)).method == "private_key"
    assert client.sessions[-1].auth_calls == 1
    assert encrypted not in repr(manager._auth) and phrase not in repr(manager._auth)
    assert phrase not in caplog.text and encrypted not in caplog.text
    for path in tmp_path.rglob("*"):
        if path.is_file():
            content = path.read_bytes()
            assert encrypted.encode() not in content and phrase.encode() not in content
    clock[0] += 301
    assert manager.current(control(info)) is None


def test_changed_host_receives_no_key_and_cancelled_parse_cannot_authenticate(
    key_setup, material, monkeypatch
):
    manager, identities, client, _, _, _ = key_setup
    original, plain, _, _ = material
    key_session(client, original)
    request = grant(identities)
    entered, release = threading.Event(), threading.Event()
    real = load_private_key

    def blocked(text, phrase):
        entered.set()
        assert release.wait(3)
        return real(text, phrase)

    monkeypatch.setattr("easyai.services.connection_manager.load_private_key", blocked)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(manager.authenticate_private_key, request, plain)
        assert entered.wait(3)
        manager.cancel_auth(
            IdentityRequest(project_id=request.project_id, request_id=request.request_id)
        )
        release.set()
        with pytest.raises(SshFailure, match="SSH_AUTH_CANCELLED"):
            future.result(3)
    assert client.sessions[-1].auth_calls == 0
    manager.wait_idle()
    monkeypatch.setattr("easyai.services.connection_manager.load_private_key", real)
    request = grant(identities)
    client.session_hook = lambda session: setattr(session, "host_fingerprint", "SHA256:" + "B" * 43)
    with pytest.raises(SshFailure, match="SSH_HOST_KEY_CHANGED"):
        manager.authenticate_private_key(request, plain)
    assert client.sessions[-1].auth_calls == 0


def test_private_key_input_is_excluded_redacted_and_forget_drops_references(key_setup, material):
    _, identities, _, _, _, _ = key_setup
    _, plain, _, phrase = material
    value = PrivateKeyAuthenticationInput(
        request=grant(identities), private_key=plain, passphrase=phrase
    )
    assert plain not in repr(value) and phrase not in repr(value)
    assert set(value.model_dump()) == {"request"}
    value.forget()
    assert value.private_key.get_secret_value() == value.passphrase.get_secret_value() == ""


def test_http_key_route_is_authenticated_bounded_and_never_echoes_secrets(key_setup, material):
    manager, identities, client, _, _, _ = key_setup
    original, _, encrypted, phrase = material
    key_session(client, original)
    request = grant(identities)

    class Local:
        runs = None

        def connections(self):
            return manager

    api = TestClient(create_app("synthetic-token", workspace=Local()))
    body = {
        "request": request.model_dump(by_alias=True),
        "privateKey": encrypted,
        "passphrase": phrase,
    }
    assert api.post("/api/v1/connections/auth/private-key", json=body).status_code == 401
    headers = {"Authorization": "Bearer synthetic-token"}
    for bad in (
        {**body, "privateKey": "x" * 65537},
        {**body, "passphrase": "x" * 1025},
        {**body, "privateKeyPath": "/never-read"},
        {**body, "request": {**body["request"], "unexpected": encrypted}},
    ):
        result = api.post("/api/v1/connections/auth/private-key", json=bad, headers=headers)
        assert (
            result.status_code == 422 and encrypted not in result.text and phrase not in result.text
        )
    response = api.post("/api/v1/connections/auth/private-key", json=body, headers=headers)
    assert response.status_code == 200 and response.json()["method"] == "private_key"
    assert encrypted not in response.text and phrase not in response.text


def test_openssh_high_cost_or_unknown_kdf_never_reaches_sdk(monkeypatch):
    def string(value):
        return struct.pack(">I", len(value)) + value

    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("Rejected KDF must not enter an SDK decoder")

    for kind in (paramiko.RSAKey, paramiko.ECDSAKey, paramiko.Ed25519Key):
        monkeypatch.setattr(kind, "from_private_key", forbidden)
    for rounds in (0, 65, 0xFFFFFFFF):
        options = string(b"synthetic-salt16") + struct.pack(">I", rounds)
        data = (
            b"openssh-key-v1\0"
            + string(b"aes256-ctr")
            + string(b"bcrypt")
            + string(options)
            + struct.pack(">I", 1)
            + string(string(b"ssh-ed25519") + string(bytes(32)))
            + string(bytes(64))
        )
        text = (
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
            + base64.b64encode(data).decode()
            + "\n-----END OPENSSH PRIVATE KEY-----\n"
        )
        with pytest.raises(SshFailure, match="SSH_PRIVATE_KEY_INVALID"):
            load_private_key(text, "synthetic")
    assert not calls


def test_real_encrypted_openssh_ed25519_roundtrip_with_bounded_cost():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.BestAvailableEncryption(b"synthetic-fixture"),
    )
    parsed = load_private_key(raw.decode(), "synthetic-fixture")
    assert parsed.can_sign() and parsed.get_name() == "ssh-ed25519"


def test_sdk_auth_handler_releases_actual_synthetic_private_key(material, tmp_path):
    from types import SimpleNamespace
    from easyai.services.ssh_client import VerifiedSshSession
    from easyai.security.host_keys import HostKeyStore, PublicIdentity
    from easyai.domain.ssh import SshEndpoint
    from test_ssh_identity import key, pin, TransportFixture, SocketFixture

    original, plain, _, _ = material
    public = key()
    endpoint = SshEndpoint(host="synthetic.invalid")
    store = HostKeyStore(tmp_path / "trust")
    pin(store, endpoint, public)
    transport = TransportFixture(public)
    transport.auth_timeout = 1
    transport.auth_handler = SimpleNamespace(private_key=None, password=None)

    def authenticate(username, private, event):
        assert private.asbytes() == original.asbytes()
        transport.auth_handler.private_key = private
        transport.authenticated = True
        event.set()

    transport.auth_publickey = authenticate
    session = VerifiedSshSession(
        endpoint, PublicIdentity.from_key(public), store, SocketFixture(), transport
    )
    try:
        session.authenticate_public_key("synthetic-user", load_private_key(plain, ""), timeout=1)
        assert transport.auth_handler.private_key is None
        session.validate_probe_session()
    finally:
        session.close()
