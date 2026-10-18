import json
import select
import subprocess
import sys
from collections.abc import Iterator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


@pytest.fixture
def backend() -> Iterator[tuple[subprocess.Popen[bytes], dict[str, int], str]]:
    token = "ab" * 32
    child = subprocess.Popen(
        [sys.executable, "-m", "easyai.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert child.stdin is not None and child.stdout is not None
    child.stdin.write(json.dumps({"token": token}).encode() + b"\n")
    child.stdin.flush()
    try:
        if sys.platform != "win32":
            assert select.select([child.stdout], [], [], 10)[0], "sidecar startup timed out"
        ready = json.loads(child.stdout.readline())
        yield child, ready, token
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=3)
            pytest.fail("Sidecar did not exit after parent EOF")
        assert child.returncode == 0


def test_ready_auth_and_shutdown(
    backend: tuple[subprocess.Popen[bytes], dict[str, int], str],
) -> None:
    child, ready, token = backend
    assert set(ready) == {"port", "protocolVersion", "pid"}
    assert ready["pid"] == child.pid and ready["protocolVersion"] == 1
    url = f"http://127.0.0.1:{ready['port']}/api/v1/health"
    for value in [None, "Bearer wrong"]:
        with pytest.raises(HTTPError) as error:
            urlopen(
                Request(url, headers={} if value is None else {"Authorization": value}), timeout=3
            )
        assert error.value.code == 401
    with urlopen(Request(url, headers={"Authorization": f"Bearer {token}"}), timeout=3) as result:
        assert json.load(result) == {"appVersion": "0.0.0", "protocolVersion": 1, "ready": True}
        assert result.headers.get("Access-Control-Allow-Origin") is None


def test_bad_handshake_exits_without_leaking() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "easyai.main"],
        input=b'{"token":"secret"}\n',
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 2
    assert b"secret" not in result.stderr and result.stdout == b""


def test_non_ascii_authorization_is_rejected() -> None:
    from fastapi.testclient import TestClient
    from easyai.api import create_app

    with TestClient(create_app("ab" * 32)) as client:
        response = client.get("/api/v1/health", headers=[(b"authorization", b"Bearer \xff")])
        assert response.status_code == 401
