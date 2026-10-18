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


@pytest.mark.parametrize("unsafe_umask", [0o000, 0o002])
def test_private_trust_creation_ignores_unsafe_umask_without_changing_existing_modes(
    tmp_path, unsafe_umask
):
    before = tmp_path.stat().st_mode
    previous = os.umask(unsafe_umask)
    try:
        store = HostKeyStore(tmp_path / "new-parent" / "private-trust")
        pin(store, SshEndpoint(host="offline.invalid"), key())
    finally:
        os.umask(previous)
    assert store.root.stat().st_mode & 0o777 == 0o700
    assert store.root.parent.stat().st_mode & 0o777 == 0o700
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert tmp_path.stat().st_mode == before


@pytest.mark.parametrize("mode", [0o777, 0o770, 0o702])
def test_existing_writable_trust_directory_is_rejected_without_chmod(tmp_path, mode):
    root = tmp_path / "unsafe"
    root.mkdir(mode=mode)
    root.chmod(mode)  # Only a task-owned synthetic fixture.
    with pytest.raises(ValueError, match="SSH_TRUST_PERMISSIONS_UNSAFE"):
        HostKeyStore(root)
    assert root.stat().st_mode & 0o777 == mode
    assert list(root.iterdir()) == []


def test_unsafe_ancestor_and_regular_file_replacement_are_not_trusted(tmp_path):
    parent = tmp_path / "shared"
    parent.mkdir()
    parent.chmod(0o777)
    with pytest.raises(ValueError, match="SSH_TRUST_PERMISSIONS_UNSAFE"):
        HostKeyStore(parent / "not-created")
    assert list(parent.iterdir()) == []
    store = HostKeyStore(tmp_path / "private")
    endpoint = SshEndpoint(host="offline.invalid")
    pin(store, endpoint, key())
    other = PublicIdentity.from_key(key(2))
    replacement = store.root / "replacement"
    replacement.write_text(
        f"offline.invalid {other.algorithm} {base64.b64encode(other.raw).decode()}\n"
    )
    replacement.chmod(0o666)
    replacement.replace(store.path)
    with pytest.raises(ValueError, match="SSH_TRUST_PERMISSIONS_UNSAFE"):
        store.observe(endpoint, other)
    assert store.path.stat().st_mode & 0o777 == 0o666


@pytest.mark.parametrize("which", ["directory", "file"])
def test_wrong_owner_metadata_is_rejected_without_chown(tmp_path, monkeypatch, which):
    store = HostKeyStore(tmp_path / "private")
    endpoint = SshEndpoint(host="offline.invalid")
    pin(store, endpoint, key())
    inode = (store.root if which == "directory" else store.path).stat().st_ino
    original = os.fstat

    def wrong_owner(fd):
        info = original(fd)
        if info.st_ino == inode:
            fields = list(info)
            fields[4] = store._uid + 12345
            return os.stat_result(fields)
        return info

    # Metadata boundary simulation only: never chown a real directory/file.
    monkeypatch.setattr(os, "fstat", wrong_owner)
    with pytest.raises(ValueError, match="SSH_TRUST_PERMISSIONS_UNSAFE"):
        store.observe(endpoint, PublicIdentity.from_key(key()))


def test_permissions_changed_while_reading_pinned_fd_are_rechecked(tmp_path, monkeypatch):
    store = HostKeyStore(tmp_path / "private")
    endpoint = SshEndpoint(host="offline.invalid")
    pin(store, endpoint, key())
    original = os.fstat
    inode = store.path.stat().st_ino
    reads = [0]

    def change_after_initial_check(fd):
        info = original(fd)
        if info.st_ino == inode:
            reads[0] += 1
            if reads[0] == 2:
                store.path.chmod(0o666)
                info = original(fd)
        return info

    monkeypatch.setattr(os, "fstat", change_after_initial_check)
    with pytest.raises(ValueError, match="SSH_TRUST_PERMISSIONS_UNSAFE"):
        store.observe(endpoint, PublicIdentity.from_key(key()))


def identity_service(tmp_path):
    from easyai.services.ssh_identity import SshIdentityService

    current = ["11111111-1111-4111-8111-111111111111"]

    def verify(project):
        if current[0] != project:
            raise ValueError("SSH_IDENTITY_PROJECT_CHANGED")

    store = HostKeyStore(tmp_path / "identity")
    ssh, connection, transport = client(store)
    service = SshIdentityService(ssh, threading.RLock(), verify)
    return service, store, ssh, connection, transport, current


def identity_request(host="offline.invalid", request_id=None, project_id=None):
    from uuid import uuid4
    from easyai.domain.ssh import IdentityProbeRequest

    return IdentityProbeRequest(
        project_id=project_id or "11111111-1111-4111-8111-111111111111",
        request_id=request_id or str(uuid4()),
        endpoint=SshEndpoint(host=host),
    )


def identity_confirm(result):
    from easyai.domain.ssh import IdentityConfirmRequest, HostKeyConfirmation

    return IdentityConfirmRequest(
        project_id=result.project_id,
        request_id=result.request_id,
        confirmation=HostKeyConfirmation(
            challenge_id=result.observation.challenge_id,
            fingerprint=result.observation.fingerprint,
        ),
    )


def test_scoped_identity_confirmation_matches_exact_request_project_and_target(tmp_path):
    service, store, ssh, connection, transport, current = identity_service(tmp_path)
    request = identity_request()
    result = service.probe(request)
    confirmation = identity_confirm(result)
    # Pydantic copy creates fixtures only; production DTO validation remains strict.
    for stale in [
        confirmation.model_copy(update={"request_id": "22222222-2222-4222-8222-222222222222"}),
        confirmation.model_copy(update={"project_id": "22222222-2222-4222-8222-222222222222"}),
    ]:
        with pytest.raises(ValueError, match="SSH_IDENTITY_"):
            service.confirm(stale)
    assert not store.path.exists()
    assert service.confirm(confirmation).observation.trust_state == "trusted"
    assert store.path.exists() and transport.auth_calls == [] and connection.closed
    with pytest.raises(ValueError, match="STALE"):
        service.confirm(confirmation)
    with pytest.raises(ValueError, match="RETIRED"):
        service.probe(request)


def test_cancel_before_registration_after_result_and_project_change_reject_confirmation(tmp_path):
    service, store, ssh, connection, transport, current = identity_service(tmp_path)
    request = identity_request()
    service.cancel(request)
    with pytest.raises(ValueError, match="RETIRED"):
        service.probe(request)
    assert not connection.closed  # No transport opened at all.
    result = service.probe(identity_request())
    confirmation = identity_confirm(result)
    service.cancel(result)
    with pytest.raises(ValueError, match="STALE"):
        service.confirm(confirmation)
    assert not store.path.exists() and len(store._pending) == 0
    result = service.probe(identity_request())
    current[0] = "22222222-2222-4222-8222-222222222222"
    service.invalidate()
    with pytest.raises(ValueError, match="PROJECT_CHANGED"):
        service.confirm(identity_confirm(result))
    assert not store.path.exists() and len(store._pending) == 0


def test_cancelled_late_probe_is_drained_without_reuse_or_parallel_dial(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    service, store, ssh, connection, transport, current = identity_service(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = ssh.probe

    def blocked(endpoint, cancel):
        entered.set()
        assert release.wait(2)
        # Simulate a late result even though cancellation arrived already.
        return original(endpoint, None)

    ssh.probe = blocked
    request = identity_request()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(service.probe, request)
        assert entered.wait(2)
        try:
            service.cancel(request)
            with pytest.raises(ValueError, match="BUSY"):
                service.probe(identity_request(host="other.invalid"))
        finally:
            release.set()
        with pytest.raises(ValueError, match="CANCELLED"):
            future.result(timeout=2)
    assert len(store._pending) == 0 and not store.path.exists()
    assert connection.closed and transport.closed and transport.auth_calls == []


def test_new_target_invalidates_old_challenge_and_request_retention_is_bounded(tmp_path):
    service, store, ssh, connection, transport, current = identity_service(tmp_path)
    result = service.probe(identity_request())
    confirmation = identity_confirm(result)
    second = service.probe(identity_request(host="other.invalid"))
    assert second.observation.endpoint.host == "other.invalid"
    with pytest.raises(ValueError, match="STALE"):
        service.confirm(confirmation)
    assert confirmation.confirmation.challenge_id not in store._pending
    for index in range(62):
        service.cancel(identity_request())
    with pytest.raises(ValueError, match="REQUEST_LIMIT"):
        service.probe(identity_request())
    assert len(service._retired) == 64 and not store.path.exists()


def test_normal_api_rejects_cross_project_then_confirms_and_invalidates_on_switch(tmp_path):
    workspace = LocalWorkspace(tmp_path / "app")
    store = HostKeyStore(tmp_path / "identity")
    ssh, connection, transport = client(store)
    workspace._ssh_client = ssh
    selected = tmp_path / "project"
    selected.mkdir()
    selection = workspace.select("project", selected)
    session = workspace.create(selection.selection_id, "offline", "blank")
    project_id = session.project.project_id
    api = TestClient(create_app("offline-test-token", workspace=workspace))
    headers = {"Authorization": "Bearer offline-test-token"}
    request = identity_request(project_id=project_id)
    base = "/api/v1/connections/identity/"
    try:
        assert api.post(base + "probe", json=request.model_dump(by_alias=True)).status_code == 401
        wrong = request.model_copy(update={"project_id": "22222222-2222-4222-8222-222222222222"})
        assert (
            api.post(
                base + "probe", json=wrong.model_dump(by_alias=True), headers=headers
            ).status_code
            == 422
        )
        response = api.post(base + "probe", json=request.model_dump(by_alias=True), headers=headers)
        assert response.status_code == 200, response.text
        from easyai.domain.ssh import IdentityResult

        result = IdentityResult.model_validate(response.json())
        confirmation = identity_confirm(result)
        cancelled = api.post(
            base + "cancel",
            json={"projectId": project_id, "requestId": request.request_id},
            headers=headers,
        )
        assert cancelled.status_code == 200
        rejected = api.post(
            base + "confirm", json=confirmation.model_dump(by_alias=True), headers=headers
        )
        assert rejected.status_code == 422 and not store.path.exists()
        request = identity_request(project_id=project_id)
        result = IdentityResult.model_validate(
            api.post(base + "probe", json=request.model_dump(by_alias=True), headers=headers).json()
        )
        accepted = api.post(
            base + "confirm",
            json=identity_confirm(result).model_dump(by_alias=True),
            headers=headers,
        )
        assert (
            accepted.status_code == 200
            and accepted.json()["observation"]["trustState"] == "trusted"
        )
        assert transport.auth_calls == []
        new_dir = tmp_path / "next-project"
        new_dir.mkdir()
        workspace.create(workspace.select("project", new_dir).selection_id, "next", "blank")
        assert (
            api.post(
                base + "confirm", json=confirmation.model_dump(by_alias=True), headers=headers
            ).status_code
            == 422
        )
    finally:
        workspace.close()


def test_mismatched_probe_target_is_rejected_before_persisting_any_trust(tmp_path):
    service, store, ssh, connection, transport, current = identity_service(tmp_path)
    original = ssh.probe

    def different_target(endpoint, cancel):
        return original(SshEndpoint(host="different.invalid", port=2222), cancel)

    ssh.probe = different_target
    with pytest.raises(ValueError, match="RESPONSE_INVALID"):
        service.probe(identity_request())
    assert not store.path.exists() and len(store._pending) == 0
    assert transport.auth_calls == [] and connection.closed
