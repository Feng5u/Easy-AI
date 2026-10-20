"""Unsupported hosts may inspect metadata, never instantiate a POSIX owner."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.services import install_runtime, install_service
from easyai.services.local_workspace import LocalWorkspace


def windows_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install_runtime, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(install_service, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(
        install_service,
        "platform",
        SimpleNamespace(system=lambda: "Windows", machine=lambda: "AMD64"),
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AttributeError("POSIX owner must not be reached on unsupported host")

    monkeypatch.setattr(install_runtime, "protected", forbidden)
    monkeypatch.setattr(install_runtime, "private_snapshot", forbidden)


def test_windows_catalog_and_blocked_plan_never_construct_posix_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = LocalWorkspace(tmp_path / "application")
    windows_policy(monkeypatch)
    try:
        with TestClient(
            create_app("a" * 64, workspace=workspace), raise_server_exceptions=False
        ) as client:
            assert client.get("/api/v1/catalog/packages").status_code == 401
            headers = {"Authorization": f"Bearer {'a' * 64}"}
            catalog = client.get("/api/v1/catalog/packages", headers=headers)
            assert catalog.status_code == 200
            assert catalog.json()["executionEnabled"] is False
            assert len(catalog.json()["packages"]) == 17
            plan = client.post(
                "/api/v1/environments/install-plan",
                headers=headers,
                json={
                    "targetId": "local",
                    "profileId": "easyai-cpu",
                    "packageIds": ["torch"],
                    "newEnvironmentSpec": {"name": "metadata_only"},
                },
            )
            assert plan.status_code == 200
            value = plan.json()
            assert value["blockers"] == ["INSTALL_PROFILE_PLATFORM_UNSUPPORTED"]
            assert value["executionEnabled"] is False
            confirmed = client.post(
                "/api/v1/install-jobs",
                headers=headers,
                json={
                    "planId": value["planId"],
                    "planHash": value["planHash"],
                    "confirmed": True,
                    "networkAcknowledged": True,
                },
            )
            assert confirmed.status_code == 409
            assert confirmed.json()["error"]["code"] == "INSTALL_PLAN_BLOCKED"
            source = client.post(
                "/api/v1/environments/install-source/preview",
                headers=headers,
                json={
                    "manifestPath": str(tmp_path / "must_not_read.json"),
                    "packageIds": ["torch"],
                },
            )
            assert source.status_code == 422
            assert source.json()["error"]["code"] == "INSTALL_RUNTIME_NOT_AVAILABLE"
            assert not (workspace.root / "install-processes").exists()
            assert not (workspace.root / "install-runtime.json").exists()
            assert workspace.installs().history().entries == []
    finally:
        workspace.close()


def test_direct_unsupported_runtime_rejects_before_any_private_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows_policy(monkeypatch)
    with pytest.raises(ValueError, match="INSTALL_PROFILE_PLATFORM_UNSUPPORTED"):
        install_runtime.InstallRuntime(tmp_path)
    assert not (tmp_path / "install-processes").exists()


def test_autocrlf_checkout_preserves_catalog_and_rejects_changed_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise real Git checkout conversion, not a permissive lock parser."""
    import shutil
    import subprocess

    from easyai.domain.catalog import SOURCE_ROOT

    repository = tmp_path / "git-input"
    repository.mkdir()
    profiles = Path("packages/training-profiles")
    shutil.copytree(SOURCE_ROOT / profiles, repository / profiles)
    attributes = SOURCE_ROOT / ".gitattributes"
    if attributes.exists():
        shutil.copyfile(attributes, repository / ".gitattributes")
    for arguments in (
        ["init", "--quiet"],
        ["config", "core.autocrlf", "true"],
        ["config", "core.safecrlf", "false"],
        ["add", "."],
    ):
        subprocess.run(["git", *arguments], cwd=repository, check=True, capture_output=True)
    checkout = tmp_path / "checkout"
    subprocess.run(
        ["git", "checkout-index", "--all", f"--prefix={checkout.as_posix()}/"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    windows_policy(monkeypatch)
    monkeypatch.setattr(install_service, "PROFILE_ROOT", checkout / profiles)
    workspace = LocalWorkspace(tmp_path / "application")
    try:
        with TestClient(
            create_app("a" * 64, workspace=workspace), raise_server_exceptions=False
        ) as client:
            headers = {"Authorization": f"Bearer {'a' * 64}"}
            catalog = client.get("/api/v1/catalog/packages", headers=headers)
            assert catalog.status_code == 200, catalog.json()
            assert len(catalog.json()["packages"]) == 17
            assert catalog.json()["executionEnabled"] is False
            for source in (SOURCE_ROOT / profiles).iterdir():
                assert (checkout / profiles / source.name).read_bytes() == source.read_bytes()
            lock = checkout / profiles / "easyai-ml-linux-cp311.lock"
            lock.write_bytes(lock.read_bytes().replace(b"scipy==", b"scipy==0", 1))
            rejected = client.get("/api/v1/catalog/packages", headers=headers)
            assert rejected.status_code == 422
            assert rejected.json()["error"]["code"] == "INSTALL_DEPENDENCIES_UNRESOLVED"
            assert not (workspace.root / "install-processes").exists()
    finally:
        workspace.close()
