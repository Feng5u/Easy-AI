"""Entry safety only: no credentials, socket dialing, training or mock SSH pass."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4

import pytest

from easyai.domain.catalog import SOURCE_ROOT

SCRIPT = SOURCE_ROOT / "services/backend/integration/ssh_acceptance.py"
spec = importlib.util.spec_from_file_location("easyai_ssh_acceptance_entry", SCRIPT)
assert spec is not None and spec.loader is not None
entry = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = entry
spec.loader.exec_module(entry)


@pytest.fixture
def configured(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("Entry checks must never dial sockets")

    monkeypatch.setattr(socket, "create_connection", no_network)
    now = datetime.now(timezone.utc)
    value = {
        "endpoint": {"host": "synthetic.invalid", "port": 22},
        "username": "isolated",
        "fingerprint": "SHA256:" + "A" * 43,
        "pythonPath": "/synthetic/existing/bin/python",
        "dataRoot": "/synthetic/existing-mnist",
        "runBase": "/synthetic/.easyai/ssh-acceptance/" + str(uuid4()),
        "localRoot": str(tmp_path / "new-private-result"),
        "isolatedAccount": True,
        "authorizationReference": "synthetic-not-authorization",
        "windowStart": (now - timedelta(minutes=1)).isoformat(),
        "windowEnd": (now + timedelta(minutes=20)).isoformat(),
        "operations": sorted(entry.OPERATIONS),
        "maxSeconds": 180,
    }
    path = tmp_path / "private-config.json"
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    monkeypatch.setenv("EASYAI_SSH_TEST_CONFIG", str(path))
    return path, value


def test_missing_config_is_not_pass_and_launches_no_product(configured, monkeypatch, capsys):
    monkeypatch.delenv("EASYAI_SSH_TEST_CONFIG")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    assert entry.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "NOT RUN"
    assert not Path(configured[1]["localRoot"]).exists()


def test_configured_default_and_check_never_execute(configured, monkeypatch, capsys):
    def forbidden(*args):
        pytest.fail("Read-only precheck must not invoke execute")

    monkeypatch.setattr(entry, "execute", forbidden)
    for arguments, expected, reason in (
        ([], 3, "NOT_AUTHORIZED"),
        (["--check"], 5, "READY_NOT_RUN"),
    ):
        monkeypatch.setattr(sys, "argv", [str(SCRIPT), *arguments])
        assert entry.main() == expected
        assert json.loads(capsys.readouterr().out) == {"status": "NOT RUN", "reason": reason}
    assert not Path(configured[1]["localRoot"]).exists()


def test_permission_or_scope_failure_is_not_configured_or_pass(configured):
    path, value = configured
    path.chmod(0o644)
    with pytest.raises(entry.Stop) as error:
        entry.load(str(path))
    assert error.value.code == 4
    path.chmod(0o600)
    value["operations"].remove("cancel")
    path.write_text(json.dumps(value))
    with pytest.raises(entry.Stop) as error:
        entry.load(str(path))
    assert error.value.code == 4


def test_execute_outside_window_cannot_read_credentials_or_dial(configured, monkeypatch, capsys):
    path, value = configured
    now = datetime.now(timezone.utc)
    value.update(
        windowStart=(now - timedelta(hours=1)).isoformat(),
        windowEnd=(now - timedelta(minutes=1)).isoformat(),
    )
    path.write_text(json.dumps(value))
    monkeypatch.setattr(
        entry, "credentials", lambda: pytest.fail("No credential read outside window")
    )
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--execute"])
    assert entry.main() == 3
    assert json.loads(capsys.readouterr().out)["reason"] == "NOT_AUTHORIZED"


def test_normal_node_entry_reports_check_only_and_missing_config(configured):
    import os

    env = {**os.environ, "PYTHONOPTIMIZE": "2"}
    checked = subprocess.run(
        ["node", str(SOURCE_ROOT / "scripts/test-ssh.mjs"), "--check"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert checked.returncode == 5 and json.loads(checked.stdout)["reason"] == "READY_NOT_RUN"
    del env["EASYAI_SSH_TEST_CONFIG"]
    missing = subprocess.run(
        ["node", str(SOURCE_ROOT / "scripts/test-ssh.mjs")],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert missing.returncode == 2 and json.loads(missing.stdout)["reason"] == "NOT_CONFIGURED"


def test_attestation_is_strict_and_actual_read_fd_is_private(configured, monkeypatch):
    path, value = configured
    value["isolatedAccount"] = 1
    path.write_text(json.dumps(value))
    with pytest.raises(entry.Stop) as error:
        entry.load(str(path))
    assert error.value.code == 4
    value["isolatedAccount"] = True
    path.write_text(json.dumps(value))
    other = path.with_name("nonprivate.json")
    other.write_text(json.dumps(value))
    other.chmod(0o644)
    real_open = entry.os.open

    def substituted(selected, flags):
        return real_open(other if Path(selected) == path else selected, flags)

    monkeypatch.setattr(entry.os, "open", substituted)
    with pytest.raises(entry.Stop) as error:
        entry.load(str(path))
    assert error.value.code == 4  # Checks actual opened fd, not earlier path stat.


def test_window_reaches_product_project_and_background_lease_guards(configured, monkeypatch):
    config = entry.load(str(configured[0]))
    workspace = entry.authorized_workspace(config, Path(config.local_root))
    folder = configured[0].parent / "protocol-project"
    folder.mkdir(mode=0o700)
    project = workspace.create(
        workspace.select("project", folder).selection_id, "entry only"
    ).project
    manager = workspace.connections()  # No authentication, session or socket.

    def expired(*args):
        raise entry.Stop("NOT_AUTHORIZED", 3)

    try:
        monkeypatch.setattr(entry, "window", expired)
        with pytest.raises(entry.Stop):
            workspace.project_generation(project.project_id)
        with pytest.raises(entry.Stop):
            manager._verify_project(project.project_id)  # Callback used by actual lease/I/O guards.
        with pytest.raises(entry.Stop):
            workspace.ssh()
    finally:
        workspace.close()
