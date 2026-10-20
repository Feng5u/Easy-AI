"""Non-secret configuration storage and authority tests, entirely offline."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.domain.connections import (
    ConnectionProfileInput,
    ConnectionProfileUpdate,
    AuthenticationRequest,
)
from easyai.domain.ssh import SshEndpoint
from easyai.services.connection_profiles import ConnectionProfiles
from easyai.services.local_workspace import LocalWorkspace


def input_profile(alias="课堂", host="SYNTHETIC.invalid.", username="student"):
    return ConnectionProfileInput(alias=alias, endpoint=SshEndpoint(host=host), username=username)


def test_persistence_stable_id_and_optimistic_revision(tmp_path):
    store = ConnectionProfiles(tmp_path)
    first = store.create(input_profile())
    assert first.endpoint.host == "synthetic.invalid"
    assert ConnectionProfiles(tmp_path).list() == [first]
    change = ConnectionProfileUpdate(
        **input_profile(alias="新名称").model_dump(), expected_revision=1
    )
    updated = store.update(first.target_id, change, lambda _: None)
    before = store.path.read_bytes()
    assert updated.target_id == first.target_id and updated.revision == 2
    with pytest.raises(ValueError, match="CONNECTION_PROFILE_REVISION_CONFLICT"):
        store.update(first.target_id, change, lambda _: None)
    assert store.path.read_bytes() == before
    assert ConnectionProfiles(tmp_path).list() == [updated]


@pytest.mark.parametrize(
    "field", ["password", "privateKey", "privateKeyPath", "token", "passphrase"]
)
def test_http_rejects_and_redacts_credentials(tmp_path, field):
    workspace = LocalWorkspace(tmp_path / "state")
    try:
        client = TestClient(create_app("offline-test", workspace=workspace))
        body = input_profile().model_dump(mode="json", by_alias=True)
        assert client.get("/api/v1/connections").status_code == 401
        client.headers.update({"Authorization": "Bearer offline-test"})
        response = client.post(
            "/api/v1/connections", json={**body, field: "synthetic-must-not-echo"}
        )
        assert response.status_code == 422 and "synthetic-must-not-echo" not in response.text
        assert client.get("/api/v1/connections").json() == []
        saved = client.post("/api/v1/connections", json=body)
        assert saved.status_code == 201
        response = client.patch(
            f"/api/v1/connections/{saved.json()['targetId']}",
            json={**body, "expectedRevision": 1, field: "synthetic-must-not-echo"},
        )
        assert response.status_code == 422 and "synthetic-must-not-echo" not in response.text
        raw = workspace.profiles.path.read_text()
        assert field not in raw and "synthetic-must-not-echo" not in raw
        assert not workspace.runs._ledger.entries and workspace._ssh_client is None
    finally:
        workspace.close()


@pytest.mark.parametrize("kind", ["symlink", "fifo", "corrupt", "unknown", "duplicate"])
def test_invalid_storage_is_preserved(tmp_path, kind):
    store = ConnectionProfiles(tmp_path)
    if kind == "symlink":
        other = tmp_path / "other"
        other.write_bytes(b"original")
        store.path.symlink_to(other)
    elif kind == "fifo":
        import os

        if os.name != "posix":
            pytest.skip("POSIX FIFO")
        os.mkfifo(store.path)
    elif kind == "corrupt":
        store.path.write_bytes(b"bad json")
    elif kind == "unknown":
        store.path.write_bytes(b'{"version":2,"profiles":[]}')
    else:
        first = store.create(input_profile())
        import json

        store.path.write_text(
            json.dumps(
                {"version": 1, "profiles": [first.model_dump(mode="json", by_alias=True)] * 2}
            )
        )
    with pytest.raises((ValueError, OSError)):
        store.list()
    with pytest.raises((ValueError, OSError)):
        store.create(input_profile())
    if kind == "symlink":
        assert other.read_bytes() == b"original" and store.path.is_symlink()
    elif kind == "corrupt":
        assert store.path.read_bytes() == b"bad json"


def test_catalog_encoded_size_rejected_before_publish_on_create_and_update(tmp_path):
    store = ConnectionProfiles(tmp_path)
    small = store.create(input_profile(alias="small"))
    huge = input_profile(
        alias="😀" * 80,
        username="😀" * 128,
        host="a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 61,
    )
    while True:
        before = store.path.read_bytes()
        try:
            store.create(huge)
        except ValueError as error:
            assert str(error) == "CONNECTION_PROFILE_SIZE_LIMIT"
            break
    assert store.path.read_bytes() == before and len(before) <= 128 * 1024
    # Fill the remaining byte gap with small valid entries, so expanding an
    # existing small entry also crosses the same write/read bound.
    while True:
        try:
            store.create(input_profile(alias="p"))
        except ValueError as error:
            assert str(error) == "CONNECTION_PROFILE_SIZE_LIMIT"
            break
    before = store.path.read_bytes()
    profiles = store.list()
    update = ConnectionProfileUpdate(**huge.model_dump(), expected_revision=1)
    with pytest.raises(ValueError, match="CONNECTION_PROFILE_SIZE_LIMIT"):
        store.update(small.target_id, update, lambda _: None)
    assert store.path.read_bytes() == before and store.list() == profiles


def test_identity_guard_and_no_silent_fallback_on_stale_reference(tmp_path):
    workspace = LocalWorkspace(tmp_path / "state")
    try:
        profile = workspace.create_connection_profile(input_profile())
        request = AuthenticationRequest(
            project_id=str(uuid4()),
            request_id=str(uuid4()),
            identity_request_id=str(uuid4()),
            expected_fingerprint="SHA256:" + "A" * 43,
            username=profile.username,
            target_id=profile.target_id,
            target_revision=1,
        )
        workspace.verify_connection_target(request, profile.endpoint)
        for changed, endpoint in [
            (request.model_copy(update={"target_revision": 2}), profile.endpoint),
            (request.model_copy(update={"username": "other"}), profile.endpoint),
            (request, SshEndpoint(host="other.invalid")),
        ]:
            with pytest.raises(ValueError, match="SSH_TARGET_REFERENCE_STALE"):
                workspace.verify_connection_target(changed, endpoint)
        assert workspace._ssh_client is None
    finally:
        workspace.close()
