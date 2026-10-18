"""Authenticated lifecycle using synthetic PUBLIC keys and in-memory sessions only."""

from concurrent.futures import ThreadPoolExecutor
import json
import socket
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.domain.connections import (
    AuthenticationRequest,
    PasswordAuthenticationInput,
    SessionControl,
)
from easyai.domain.environment import EnvironmentDiscoveryRequest, EnvironmentProbeRequest
from easyai.domain.ssh import (
    SshEndpoint,
    IdentityRequest,
    IdentityProbeRequest,
    IdentityConfirmRequest,
    HostKeyConfirmation,
    SshFailure,
)
from easyai.security.host_keys import HostKeyStore, PublicIdentity
from easyai.services.connection_manager import ConnectionManager
from easyai.services.local_workspace import LocalWorkspace
from easyai.services.ssh_identity import SshIdentityService
from test_ssh_identity import key
from test_environment_transport import Channel
from test_environment_service import synthetic_report

PROJECT = "11111111-1111-4111-8111-111111111111"
SYNTHETIC_PASSWORD = "synthetic-memory-only"


class FakeTimer:
    def __init__(self, seconds, callback):
        self.seconds, self.callback, self.cancelled = seconds, callback, False

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True

    def fire_late(self):
        self.callback()


class ProbeChannel(Channel):
    def shutdown_write(self):
        super().shutdown_write()
        config = json.loads(self.stdin)
        self.out = bytearray(
            json.dumps(synthetic_report(config, executable="/synthetic/python")).encode()
        )


class Session:
    def __init__(self, endpoint, fingerprint, mutex):
        self.endpoint, self.host_fingerprint, self.mutex = endpoint, fingerprint, mutex
        self.authenticated = False
        self.closed = False
        self.auth_calls = 0
        self.channel_calls = 0
        self.auth_hook = None
        self.close_hook = None

    @property
    def closed_quiescent(self):
        return self.closed

    def authenticate_password(self, username, password, cancel=None, timeout=None):
        assert not self.mutex._is_owned()
        assert password == SYNTHETIC_PASSWORD and username == "synthetic-user"
        self.auth_calls += 1
        if self.auth_hook:
            self.auth_hook(cancel)
        self.authenticated = True

    def validate_probe_session(self):
        if not self.authenticated or self.closed:
            raise SshFailure("SSH_AUTHENTICATION_REQUIRED")

    def open_probe_channel(self, timeout):
        self.validate_probe_session()
        self.channel_calls += 1
        return ProbeChannel(out=b"")

    def close(self):
        assert not self.mutex._is_owned()
        if self.close_hook:
            self.close_hook()
        self.closed = True


class Client:
    def __init__(self, root, mutex):
        self.store = HostKeyStore(root)
        self.identity = PublicIdentity.from_key(key())
        self.mutex = mutex
        self.sessions = []
        self.connect_hook = None
        self.session_hook = None

    def probe(self, endpoint, cancel):
        return self.store.observe(endpoint, self.identity)

    def connect_verified(self, endpoint, cancel):
        assert not self.mutex._is_owned()
        if self.connect_hook:
            self.connect_hook(cancel)
        session = Session(endpoint, self.identity.fingerprint, self.mutex)
        if self.session_hook:
            self.session_hook(session)
        self.sessions.append(session)
        return session


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("Connection suite must never dial SSH")

    monkeypatch.setattr(socket, "create_connection", fail)


@pytest.fixture
def setup(tmp_path):
    mutex = threading.RLock()
    client = Client(tmp_path / "host-keys", mutex)
    clock = [10.0]
    current = [PROJECT]
    timers = []

    def verify(project):
        if current[0] != project:
            raise ValueError("SSH_IDENTITY_PROJECT_CHANGED")

    identities = SshIdentityService(client, mutex, verify, lambda: clock[0])

    def timer(seconds, callback):
        value = FakeTimer(seconds, callback)
        timers.append(value)
        return value

    manager = ConnectionManager(client, identities, mutex, verify, lambda: clock[0], timer)
    yield manager, identities, client, clock, current, timers
    manager.invalidate()
    manager.wait_idle()


def grant(identities, project=PROJECT):
    request = IdentityProbeRequest(
        project_id=project, request_id=str(uuid4()), endpoint=SshEndpoint(host="synthetic.invalid")
    )
    result = identities.probe(request)
    if result.observation.trust_state == "unknown":
        result = identities.confirm(
            IdentityConfirmRequest(
                project_id=project,
                request_id=request.request_id,
                confirmation=HostKeyConfirmation(
                    challenge_id=result.observation.challenge_id,
                    fingerprint=result.observation.fingerprint,
                ),
            )
        )
    return AuthenticationRequest(
        project_id=project,
        request_id=str(uuid4()),
        identity_request_id=request.request_id,
        expected_fingerprint=result.observation.fingerprint,
        username="synthetic-user",
    )


def control(info):
    return SessionControl(project_id=info.project_id, connection_id=info.scope.connection_id)


def test_grant_is_single_use_and_only_authentication_publishes_fixed_lease(setup):
    manager, identities, client, clock, current, timers = setup
    req = grant(identities)
    assert not client.sessions
    info = manager.authenticate_password(req, SYNTHETIC_PASSWORD)
    assert (
        info.authenticated and info.expires_in_seconds == 300 and client.sessions[0].auth_calls == 1
    )
    assert SYNTHETIC_PASSWORD not in repr(info) and SYNTHETIC_PASSWORD not in repr(manager._auth)
    clock[0] += 100
    assert manager.current(control(info)).expires_in_seconds == 200
    manager.close(control(info))
    manager.wait_idle()
    with pytest.raises(SshFailure, match="RETIRED"):
        manager.authenticate_password(req, SYNTHETIC_PASSWORD)
    retry = req.model_copy(update={"request_id": str(uuid4())})
    with pytest.raises(SshFailure, match="AUTHORIZATION_STALE"):
        manager.authenticate_password(retry, SYNTHETIC_PASSWORD)
    assert len(client.sessions) == 1


def test_new_pin_or_endpoint_cannot_receive_password_for_old_grant(setup):
    manager, identities, client, *_ = setup
    req = grant(identities)
    client.session_hook = lambda session: setattr(session, "host_fingerprint", "SHA256:" + "B" * 43)
    with pytest.raises(SshFailure, match="HOST_KEY_CHANGED"):
        manager.authenticate_password(req, SYNTHETIC_PASSWORD)
    manager.wait_idle()
    assert client.sessions[0].auth_calls == 0 and client.sessions[0].closed


def test_cancel_before_registration_and_late_dial_never_revive_or_run_parallel(setup):
    manager, identities, client, *_ = setup
    req = grant(identities)
    manager.cancel_auth(IdentityRequest(project_id=PROJECT, request_id=req.request_id))
    with pytest.raises(SshFailure, match="RETIRED"):
        manager.authenticate_password(req, SYNTHETIC_PASSWORD)
    assert client.sessions == []
    req = grant(identities)
    entered, release = threading.Event(), threading.Event()

    def block(cancel):
        entered.set()
        assert release.wait(2)

    client.connect_hook = block
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(manager.authenticate_password, req, SYNTHETIC_PASSWORD)
        assert entered.wait(1)
        try:
            manager.cancel_auth(IdentityRequest(project_id=PROJECT, request_id=req.request_id))
            with pytest.raises(SshFailure, match="BUSY"):
                manager.authenticate_password(
                    req.model_copy(update={"request_id": str(uuid4())}), SYNTHETIC_PASSWORD
                )
        finally:
            release.set()
        with pytest.raises(SshFailure, match="AUTH_CANCELLED"):
            future.result(timeout=2)
    manager.wait_idle()
    assert client.sessions[0].auth_calls == 0 and client.sessions[0].closed


@pytest.mark.parametrize("change", ["cancel", "project", "timeout"])
def test_late_auth_success_is_closed_without_lease(change, setup):
    manager, identities, client, clock, current, timers = setup
    entered, release = threading.Event(), threading.Event()

    def session_hook(session):
        def auth(cancel):
            entered.set()
            assert release.wait(2)

        session.auth_hook = auth

    client.session_hook = session_hook
    req = grant(identities)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(manager.authenticate_password, req, SYNTHETIC_PASSWORD)
        assert entered.wait(1)
        try:
            if change == "cancel":
                manager.cancel_auth(IdentityRequest(project_id=PROJECT, request_id=req.request_id))
            elif change == "project":
                current[0] = str(uuid4())
                manager.invalidate()
            else:
                clock[0] += 26
                timers[0].fire_late()
        finally:
            release.set()
        with pytest.raises(SshFailure):
            future.result(timeout=2)
    manager.wait_idle()
    assert manager._lease is None and client.sessions[0].closed


def test_old_timers_close_and_cancel_cannot_close_new_lease_and_expiry_is_backend_owned(setup):
    manager, identities, client, clock, current, timers = setup
    first = manager.authenticate_password(grant(identities), SYNTHETIC_PASSWORD)
    old_auth_timer, old_lease_timer = timers[:]
    manager.close(control(first))
    manager.wait_idle()
    second = manager.authenticate_password(grant(identities), SYNTHETIC_PASSWORD)
    old_auth_timer.fire_late()
    old_lease_timer.fire_late()
    manager.close(control(first))
    manager.cancel_auth(IdentityRequest(project_id=PROJECT, request_id=first.request_id))
    assert manager.current(control(second)) is not None and not client.sessions[1].closed
    clock[0] += 301
    timers[-1].fire_late()
    manager.wait_idle()
    assert manager.current(control(second)) is None and client.sessions[1].closed


def test_public_environment_core_uses_only_the_current_authenticated_lease(setup):
    manager, identities, client, *_ = setup
    info = manager.authenticate_password(grant(identities), SYNTHETIC_PASSWORD)
    req = EnvironmentDiscoveryRequest(
        project_id=PROJECT,
        connection_id=info.scope.connection_id,
        request_id=str(uuid4()),
        python_path="/synthetic/python",
    )
    catalog = manager.environments(req).discover(req)
    probe = EnvironmentProbeRequest(
        project_id=PROJECT,
        connection_id=info.scope.connection_id,
        request_id=str(uuid4()),
        environment_id=catalog.environments[0].environment_id,
    )
    result = manager.environments(probe).probe(probe)
    assert (
        result.environment_ready
        and result.scope == info.scope
        and client.sessions[0].channel_calls == 1
    )
    manager.cancel_environment(
        req
    )  # old completed request does not invalidate the live connection.
    assert manager.current(control(info)) is not None
    manager.close(control(info))
    manager.wait_idle()
    with pytest.raises(SshFailure, match="AUTHENTICATION_REQUIRED"):
        manager.environments(probe)


def test_raw_sdk_error_does_not_enter_exception_context_or_manager_state(setup):
    manager, identities, client, *_ = setup

    def fail(session):
        def authentication(cancel):
            raise RuntimeError(SYNTHETIC_PASSWORD)

        session.auth_hook = authentication

    client.session_hook = fail
    with pytest.raises(SshFailure) as raised:
        manager.authenticate_password(grant(identities), SYNTHETIC_PASSWORD)
    manager.wait_idle()
    assert str(raised.value) == "SSH_AUTH_FAILED" and raised.value.__context__ is None
    frames = []
    trace = raised.value.__traceback__
    while trace:
        if trace.tb_frame.f_code.co_name == "authenticate_password":
            frames.append(trace.tb_frame)
        trace = trace.tb_next
    assert frames and all(frame.f_locals.get("password", "") == "" for frame in frames)
    assert SYNTHETIC_PASSWORD not in repr(manager._auth) and SYNTHETIC_PASSWORD not in str(
        raised.value
    )


def test_cleanup_owner_blocks_new_auth_until_sdk_close_actually_returns(setup):
    manager, identities, client, *_ = setup
    info = manager.authenticate_password(grant(identities), SYNTHETIC_PASSWORD)
    entered, release = threading.Event(), threading.Event()

    def close():
        entered.set()
        assert release.wait(2)

    client.sessions[0].close_hook = close
    manager.close(control(info))
    assert entered.wait(1)
    try:
        with pytest.raises(SshFailure, match="BUSY"):
            manager.authenticate_password(grant(identities), SYNTHETIC_PASSWORD)
    finally:
        release.set()
    manager.wait_idle()


def test_authenticated_api_input_and_environment_validation_never_echo_secrets(tmp_path):
    workspace = LocalWorkspace(tmp_path / "app")
    client = Client(tmp_path / "keys", workspace._mutex)
    workspace._ssh_client = client
    folder = tmp_path / "project"
    folder.mkdir()
    session = workspace.create(
        workspace.select("project", folder).selection_id, "synthetic", "blank"
    )
    project = session.project.project_id
    api = TestClient(create_app("synthetic-api-token", workspace=workspace))
    headers = {"Authorization": "Bearer synthetic-api-token"}
    req = grant(workspace.identity(), project)
    body = {"request": req.model_dump(by_alias=True), "password": SYNTHETIC_PASSWORD}
    try:
        assert api.post("/api/v1/connections/auth/password", json=body).status_code == 401
        invalid = api.post(
            "/api/v1/connections/auth/password",
            json={**body, "freeCommand": "rejected"},
            headers=headers,
        )
        assert invalid.status_code == 422 and SYNTHETIC_PASSWORD not in invalid.text
        response = api.post("/api/v1/connections/auth/password", json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert SYNTHETIC_PASSWORD not in response.text
        value = response.json()
        cid = value["scope"]["connectionId"]
        # Replayed/foreign identity probes must fail before invalidating this lease.
        for pid, rid in ((project, req.identity_request_id), (str(uuid4()), str(uuid4()))):
            stale = api.post(
                "/api/v1/connections/identity/probe",
                json={
                    "projectId": pid,
                    "requestId": rid,
                    "endpoint": {"host": "synthetic.invalid", "port": 22},
                },
                headers=headers,
            )
            assert stale.status_code == 422
            assert (
                api.get(
                    "/api/v1/connections/session",
                    params={"projectId": project, "connectionId": cid},
                    headers=headers,
                ).json()["authenticated"]
                is True
            )
        discover = {
            "projectId": project,
            "connectionId": cid,
            "requestId": str(uuid4()),
            "pythonPath": "/synthetic/python",
        }
        invalid = api.post(
            "/api/v1/environments/discover",
            json={**discover, "password": SYNTHETIC_PASSWORD},
            headers=headers,
        )
        assert invalid.status_code == 422 and SYNTHETIC_PASSWORD not in invalid.text
        catalog = api.post("/api/v1/environments/discover", json=discover, headers=headers)
        assert catalog.status_code == 200, catalog.text
        result = api.post(
            "/api/v1/environments/probe",
            json={
                "projectId": project,
                "connectionId": cid,
                "requestId": str(uuid4()),
                "environmentId": catalog.json()["environments"][0]["environmentId"],
            },
            headers=headers,
        )
        assert result.status_code == 200 and result.json()["environmentReady"] is True
        assert (
            api.post(
                "/api/v1/connections/session/close",
                json={"projectId": project, "connectionId": cid},
                headers=headers,
            ).status_code
            == 200
        )
        assert (
            api.get(
                "/api/v1/connections/session",
                params={"projectId": project, "connectionId": cid},
                headers=headers,
            ).json()
            is None
        )
        assert (
            api.post(
                "/api/v1/environments/discover",
                json={**discover, "requestId": str(uuid4())},
                headers=headers,
            ).status_code
            == 503
        )
        model = PasswordAuthenticationInput.model_validate(body)
        assert SYNTHETIC_PASSWORD not in repr(model) and "password" not in model.model_dump()
        model.forget()
        assert model.password.get_secret_value() == ""
    finally:
        workspace.close()
