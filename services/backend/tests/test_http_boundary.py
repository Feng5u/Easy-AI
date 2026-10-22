"""In-memory ASGI only: never send a large/slow body to a real server."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.security.http_boundary import BODY_LIMIT, SessionRequestBoundary


def invoke(headers=(), chunks=(), *, authorized=True, limit=16, slow=False, method="POST"):
    seen, sent = [], []
    reads = 0
    messages = iter(chunks)

    async def receive():
        nonlocal reads
        reads += 1
        if slow:
            await asyncio.Event().wait()
        return next(messages, {"type": "http.disconnect"})

    async def send(message):
        sent.append(message)

    async def downstream(scope, read, write):
        seen.append(await read())
        seen.append(await read())
        await write({"type": "http.response.start", "status": 204, "headers": []})
        await write({"type": "http.response.body", "body": b""})

    raw_headers = list(headers)
    if authorized:
        raw_headers.append((b"authorization", b"Bearer private-token"))
    scope = {"type": "http", "method": method, "path": "/test", "headers": raw_headers}
    asyncio.run(
        SessionRequestBoundary(
            downstream,
            "private-token",
            body_limit=limit,
            body_seconds=0.01,
        )(scope, receive, send)
    )
    status = next((m["status"] for m in sent if m["type"] == "http.response.start"), None)
    return status, reads, seen, sent


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [(b"authorization", b"Bearer wrong")],
        [(b"authorization", b"Bearer private-token"), (b"authorization", b"Bearer private-token")],
        [(b"authorization", b"\xff")],
    ],
)
def test_unauthorized_never_reads_even_slow_invalid_or_oversized_body(headers):
    status, reads, seen, sent = invoke(headers, authorized=False, slow=True)
    assert (status, reads, seen) == (401, 0, [])
    assert b"private-token" not in b"".join(m.get("body", b"") for m in sent)


@pytest.mark.parametrize(
    "headers,status,reads",
    [
        ([(b"content-length", b"17")], 413, 0),
        ([(b"content-length", b"0")], 413, 2),
        ([(b"content-length", b"1")], 413, 2),
        ([(b"transfer-encoding", b"chunked")], 413, 2),
        ([], 413, 2),
        ([(b"content-length", b"x")], 400, 0),
        ([(b"content-length", b"-1")], 400, 0),
        ([(b"content-length", b"1"), (b"content-length", b"1")], 400, 0),
        ([(b"content-length", b"1"), (b"transfer-encoding", b"chunked")], 400, 0),
    ],
)
def test_length_claims_cannot_bypass_chunk_budget_or_enter_downstream(headers, status, reads):
    result = invoke(
        headers,
        [
            {"type": "http.request", "body": b"a" * 8, "more_body": True},
            {"type": "http.request", "body": b"b" * 9, "more_body": True},
            {"type": "http.request", "body": b"must not read", "more_body": False},
        ],
    )
    assert result[:3] == (status, reads, [])
    assert sum(m["type"] == "http.response.start" for m in result[3]) == 1


def test_authenticated_slow_body_has_total_deadline_and_no_downstream_response():
    status, reads, seen, sent = invoke(slow=True)
    assert (status, reads, seen) == (408, 1, [])
    assert json.loads(sent[-1]["body"])["error"]["code"] == "HTTP_REQUEST_BODY_TIMEOUT"


@pytest.mark.parametrize("method,body", [("GET", b""), ("POST", b"{" + b" " * 14 + b"}")])
def test_complete_body_replays_once_and_keeps_real_disconnect_for_streaming(method, body):
    status, reads, seen, _ = invoke(
        [(b"content-length", str(len(body)).encode())],
        [
            {"type": "http.request", "body": body[:5], "more_body": True},
            {"type": "http.request", "body": body[5:], "more_body": False},
        ],
        method=method,
    )
    assert status == 204 and reads == 3
    assert seen == [
        {"type": "http.request", "body": body, "more_body": False},
        {"type": "http.disconnect"},
    ]


def test_partial_body_disconnect_does_not_parse_or_respond():
    assert invoke(chunks=[{"type": "http.request", "body": b"{", "more_body": True}])[:3] == (
        None,
        2,
        [],
    )


def test_real_factory_authenticates_before_json_validation_and_preserves_legal_project():
    app = create_app("private-token")
    client = TestClient(app)
    assert client.post("/api/v1/projects", content=b"{invalid").status_code == 401
    assert (
        client.get("/api/v1/health", headers={"Authorization": "Bearer private-token"}).status_code
        == 200
    )
    # A legal 5 MiB JSON string can use six-byte Unicode escapes on the wire.
    assert BODY_LIMIT > 6 * 5 * 1024 * 1024 + 1024
    received = []

    @app.post("/boundary-fixture")
    async def fixture(value: dict):
        received.append(value)
        return {"ok": True}

    value = {"project": "a" * (5 * 1024 * 1024)}
    body = b'{"project":"' + b"\\u0061" * len(value["project"]) + b'"}'
    response = client.post(
        "/boundary-fixture",
        content=body,
        headers={
            "Authorization": "Bearer private-token",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200 and received == [value]


def test_real_compile_route_accepts_a_five_mib_valid_project_request():
    from easyai.domain.catalog import SOURCE_ROOT

    document = json.loads((SOURCE_ROOT / "packages/contracts/fixtures/mnist.json").read_text())
    body = json.dumps({"project": document, "requestId": 1}).encode()
    body += b" " * (5 * 1024 * 1024 - len(body))
    client = TestClient(create_app("private-token"))
    result = client.post(
        f"/api/v1/projects/{document['projectId']}/compile",
        content=body,
        headers={
            "Authorization": "Bearer private-token",
            "Content-Type": "application/json",
        },
    )
    assert result.status_code == 200 and result.json()["runnable"]
