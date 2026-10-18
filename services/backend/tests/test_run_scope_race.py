"""Bounded HTTP authorization barriers; owned files only, no processes or network."""

from concurrent.futures import ThreadPoolExecutor
import asyncio
import threading

import pytest
from fastapi.testclient import TestClient

from easyai.api import create_app
from easyai.compiler.pipeline import compile_project
from easyai.services.local_workspace import LocalWorkspace
from test_run_views import register_image, png


@pytest.fixture
def scoped(tmp_path):
    workspace = LocalWorkspace(tmp_path / "app")
    first = tmp_path / "a"
    first.mkdir()
    project = workspace.create(
        workspace.select("project", first).selection_id, "A", "mnist-cnn"
    ).project
    service = workspace._projects[project.project_id]
    run, _ = register_image(
        (
            service,
            workspace.runs,
            project,
            compile_project(project).result.program_hash,
            first / "data",
        ),
        png(),
    )
    second = tmp_path / "b"
    second.mkdir()
    workspace.create(workspace.select("project", second).selection_id, "B", "blank")
    workspace.open(workspace.select("project", first).selection_id)
    client = TestClient(create_app("scope-token", workspace=workspace))
    client.headers.update({"Authorization": "Bearer scope-token"})
    try:
        yield workspace, client, run, first, second
    finally:
        workspace.close()


@pytest.mark.parametrize(
    "suffix", ["cancel", "", "source", "logs", "artifacts", "artifacts/image-id/content"]
)
def test_switch_after_authorization_rejects_old_action(scoped, monkeypatch, suffix):
    workspace, client, run, _, second = scoped
    entered, release = threading.Event(), threading.Event()
    original = asyncio.to_thread

    async def paused(function, *args, **kwargs):
        value = await original(function, *args, **kwargs)
        if function.__name__ == "run_store":
            entered.set()
            assert await original(release.wait, 2)
        return value

    monkeypatch.setattr(asyncio, "to_thread", paused)
    route = f"/api/v1/runs/{run.run_id}" + ("/" + suffix if suffix else "")
    with ThreadPoolExecutor() as pool:
        response = pool.submit(client.post if suffix == "cancel" else client.get, route)
        assert entered.wait(2)
        workspace.open(workspace.select("project", second).selection_id)
        release.set()
        result = response.result(3)
    assert result.status_code == 404, result.text
    assert workspace.runs.get(run.run_id).status == "CREATED"


@pytest.mark.parametrize(
    "suffix", ["", "source", "logs", "artifacts", "artifacts/image-id/content"]
)
@pytest.mark.parametrize("back_to_a", [False, True])
def test_delivery_rechecks_generation_after_worker_returns(scoped, monkeypatch, suffix, back_to_a):
    workspace, client, run, first, second = scoped
    entered, release = threading.Event(), threading.Event()
    original = asyncio.to_thread

    async def paused(function, *args, **kwargs):
        value = await original(function, *args, **kwargs)
        if function.__name__ == "scoped_read":
            entered.set()
            assert await original(release.wait, 2)
        return value

    monkeypatch.setattr(asyncio, "to_thread", paused)
    route = f"/api/v1/runs/{run.run_id}" + ("/" + suffix if suffix else "")
    with ThreadPoolExecutor() as pool:
        response = pool.submit(client.get, route)
        assert entered.wait(2)
        workspace.open(workspace.select("project", second).selection_id)
        if back_to_a:
            workspace.open(workspace.select("project", first).selection_id)
        release.set()
        result = response.result(3)
    assert result.status_code == 404, result.text


@pytest.mark.parametrize("back_to_a", [False, True])
def test_sse_discards_batch_retired_after_read_before_yield(scoped, monkeypatch, back_to_a):
    workspace, client, run, first, second = scoped
    entered, release = threading.Event(), threading.Event()
    original = asyncio.to_thread

    async def paused(function, *args, **kwargs):
        value = await original(function, *args, **kwargs)
        if function.__name__ == "scoped_read" and args[1].__name__ == "batch":
            entered.set()
            assert await original(release.wait, 2)
        return value

    monkeypatch.setattr(asyncio, "to_thread", paused)
    with ThreadPoolExecutor() as pool:
        response = pool.submit(client.get, f"/api/v1/runs/{run.run_id}/events")
        assert entered.wait(2)
        workspace.open(workspace.select("project", second).selection_id)
        if back_to_a:
            workspace.open(workspace.select("project", first).selection_id)
        release.set()
        result = response.result(3)
    assert result.status_code == 200 and result.text == ""


def test_history_rejects_foreign_project_and_late_aba_result(scoped, monkeypatch):
    workspace, client, run, first, second = scoped
    route = f"/api/v1/projects/{run.project_id}/runs"
    assert client.get(route).status_code == 200
    workspace.open(workspace.select("project", second).selection_id)
    assert client.get(route).status_code == 404
    workspace.open(workspace.select("project", first).selection_id)
    entered, release = threading.Event(), threading.Event()
    original = asyncio.to_thread

    async def paused(function, *args, **kwargs):
        value = await original(function, *args, **kwargs)
        if function.__name__ == "history":
            entered.set()
            assert await original(release.wait, 2)
        return value

    monkeypatch.setattr(asyncio, "to_thread", paused)
    with ThreadPoolExecutor() as pool:
        response = pool.submit(client.get, route)
        assert entered.wait(2)
        workspace.open(workspace.select("project", second).selection_id)
        workspace.open(workspace.select("project", first).selection_id)
        release.set()
        result = response.result(3)
    assert result.status_code == 404


def test_local_cancel_rechecks_scope_at_commit(scoped, monkeypatch):
    from contextlib import contextmanager

    workspace, client, run, _, second = scoped
    entered, release = threading.Event(), threading.Event()
    original = workspace.run_commit_scope

    @contextmanager
    def paused(scope):
        entered.set()
        assert release.wait(2)
        with original(scope):
            yield

    monkeypatch.setattr(workspace, "run_commit_scope", paused)
    with ThreadPoolExecutor() as pool:
        response = pool.submit(client.post, f"/api/v1/runs/{run.run_id}/cancel")
        assert entered.wait(2)
        workspace.open(workspace.select("project", second).selection_id)
        release.set()
        result = response.result(3)
    assert result.status_code == 404
    assert workspace.runs.get(run.run_id).status == "CREATED"


def test_sse_stops_remaining_batch_after_first_delivery_switches_project(scoped):
    workspace, _, run, _, second = scoped
    app = create_app("scope-token", workspace=workspace)
    messages = []
    delivered = 0

    async def receive():
        await asyncio.Event().wait()

    async def send(message):
        nonlocal delivered
        messages.append(message)
        if message["type"] == "http.response.body" and message.get("body"):
            delivered += 1
            if delivered == 1:
                workspace.open(workspace.select("project", second).selection_id)

    async def request():
        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.4"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": f"/api/v1/runs/{run.run_id}/events",
                "query_string": b"",
                "headers": [(b"authorization", b"Bearer scope-token")],
                "server": ("testserver", 80),
                "client": ("testclient", 123),
                "root_path": "",
            },
            receive,
            send,
        )

    asyncio.run(asyncio.wait_for(request(), 3))
    assert delivered == 1
    assert messages[-1]["type"] == "http.response.body" and not messages[-1].get("more_body", False)


def test_retired_get_failure_cannot_deliver_old_project_error(scoped, monkeypatch):
    workspace, client, run, _, second = scoped
    entered, release = threading.Event(), threading.Event()

    def failed_get(run_id):
        assert run_id == run.run_id
        entered.set()
        assert release.wait(2)
        raise ValueError("OLD_PROJECT_PRIVATE_ERROR")

    monkeypatch.setattr(workspace.runs, "get", failed_get)
    with ThreadPoolExecutor() as pool:
        response = pool.submit(client.get, f"/api/v1/runs/{run.run_id}")
        assert entered.wait(2)
        workspace.open(workspace.select("project", second).selection_id)
        release.set()
        result = response.result(3)
    assert result.status_code == 404 and "OLD_PROJECT_PRIVATE_ERROR" not in result.text


@pytest.mark.parametrize("operation", ["source", "history", "cancel"])
def test_retired_errors_are_rechecked_after_worker_await(scoped, monkeypatch, operation):
    from easyai.services.run_views import RunViews

    workspace, client, run, _, second = scoped
    entered, release = threading.Event(), threading.Event()
    original = asyncio.to_thread

    def private_failure(*args):
        raise ValueError("OLD_PROJECT_PRIVATE_ERROR")

    if operation == "source":
        monkeypatch.setattr(RunViews, "source", private_failure)
    else:
        monkeypatch.setattr(
            workspace, "history" if operation == "history" else "cancel_run", private_failure
        )

    async def paused(function, *args, **kwargs):
        try:
            return await original(function, *args, **kwargs)
        except ValueError as error:
            if str(error) == "OLD_PROJECT_PRIVATE_ERROR":
                entered.set()
                assert await original(release.wait, 2)
            raise

    monkeypatch.setattr(asyncio, "to_thread", paused)
    route = (
        f"/api/v1/projects/{run.project_id}/runs"
        if operation == "history"
        else f"/api/v1/runs/{run.run_id}/{operation}"
    )
    with ThreadPoolExecutor() as pool:
        response = pool.submit(client.post if operation == "cancel" else client.get, route)
        assert entered.wait(2)
        workspace.open(workspace.select("project", second).selection_id)
        release.set()
        result = response.result(3)
    assert result.status_code == 404 and "OLD_PROJECT_PRIVATE_ERROR" not in result.text


@pytest.mark.parametrize("back_to_a", [False, True])
def test_diagnostic_report_delivery_rejects_project_switch_and_aba(scoped, monkeypatch, back_to_a):
    from easyai.domain.contracts import Event
    from easyai.services.run_views import RunViews

    workspace, client, run, first, second = scoped
    event = workspace.runs._journal(run.run_id).ingest(
        Event(
            run_id=run.run_id,
            seq=1,
            source="runtime",
            source_seq=1,
            timestamp="test",
            type="runtime_error",
            payload={"exceptionType": "NameError"},
        )
    )
    assert event is not None
    route = f"/api/v1/runs/{run.run_id}/diagnostics/{event.seq}/report"
    assert client.get(route).status_code == 200
    entered, release = threading.Event(), threading.Event()
    original = asyncio.to_thread

    async def paused(function, *args, **kwargs):
        value = await original(function, *args, **kwargs)
        if function.__name__ == "scoped_read" and args[1].__name__ == "report":
            entered.set()
            assert await original(release.wait, 2)
        return value

    monkeypatch.setattr(asyncio, "to_thread", paused)
    with ThreadPoolExecutor() as pool:
        response = pool.submit(client.get, route)
        assert entered.wait(2)
        workspace.open(workspace.select("project", second).selection_id)
        if back_to_a:
            workspace.open(workspace.select("project", first).selection_id)
        release.set()
        result = response.result(3)
    assert result.status_code == 404, result.text
    # The report itself is still available in owned storage; only delivery was revoked.
    assert RunViews(workspace.runs).report(run.run_id, event.seq).run_id == run.run_id
