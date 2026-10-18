import secrets
import asyncio
import time
import re
from pathlib import Path
from typing import Literal
from uuid import uuid4
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pydantic import Field

from easyai.domain.catalog import load_catalog
from easyai.domain.contracts import (
    CompileRequest,
    CompileResponse,
    Contract,
    ProjectDocument,
    Run,
    ArtifactRecord,
)
from easyai.domain.desktop import (
    ProjectSession,
    RunStartRequest,
    RunSource,
    RunLogs,
    SelectionResult,
)
from easyai.compiler.pipeline import compile_project
from easyai.services.run_service import RunService, TERMINAL
from easyai.services.local_workspace import LocalWorkspace
from easyai.services.run_views import RunViews


class SelectionRequest(Contract):
    kind: Literal["project", "python", "data"]
    path: str = Field(min_length=1, max_length=4096)


class OpenRequest(Contract):
    selection_id: str


class CreateRequest(OpenRequest):
    name: str = Field(min_length=1, max_length=128)
    template: Literal["mnist-cnn"] = "mnist-cnn"


class SaveRequest(Contract):
    project: ProjectDocument
    expected_revision: int = Field(ge=1)


def create_app(
    token: str, runs: RunService | None = None, workspace: LocalWorkspace | None = None
) -> FastAPI:
    if workspace is not None:
        if runs is not None and runs is not workspace.runs:
            raise ValueError("LOCAL_RUN_STORE_CONFLICT")
        runs = workspace.runs

    async def authorize(authorization: str | None = Header(default=None)) -> None:
        if authorization is None or not secrets.compare_digest(
            authorization.encode("utf-8"), f"Bearer {token}".encode("ascii")
        ):
            raise HTTPException(status_code=401, detail="Session authorization required")

    app = FastAPI(
        docs_url=None, redoc_url=None, openapi_url=None, dependencies=[Depends(authorize)]
    )

    @app.exception_handler(ValueError)
    async def value_error(_request: Request, error: ValueError) -> JSONResponse:
        raw = str(error)
        code = raw if re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", raw) else "LOCAL_REQUEST_INVALID"
        status = 422
        if "FORBIDDEN" in code or code == "FILE_NOT_REGULAR":
            status = 403
        elif code in {"PROJECT_REVISION_CONFLICT", "PROGRAM_HASH_CONFLICT"}:
            status = 412
        elif any(
            term in code
            for term in ("CONFLICT", "HELD", "READ_ONLY", "ALREADY_EXISTS", "IDENTITY_UNKNOWN")
        ):
            status = 409
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": code, "requestId": str(uuid4())}},
        )

    @app.exception_handler(KeyError)
    async def unknown_resource(_request: Request, _error: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": {"code": "RESOURCE_NOT_FOUND"}})

    @app.exception_handler(FileNotFoundError)
    async def missing_file(_request: Request, _error: FileNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": {"code": "LOCAL_FILE_NOT_FOUND"}})

    @app.exception_handler(PermissionError)
    async def forbidden_file(_request: Request, _error: PermissionError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"error": {"code": "LOCAL_PATH_FORBIDDEN"}})

    def local() -> LocalWorkspace:
        if workspace is None:
            raise HTTPException(status_code=404, detail="Local workspace is not configured")
        return workspace

    @app.post("/api/v1/local/selections", response_model=SelectionResult)
    async def select(request: SelectionRequest) -> SelectionResult:
        return await asyncio.to_thread(local().select, request.kind, Path(request.path))

    @app.get("/api/v1/local/session", response_model=ProjectSession | None)
    async def current() -> ProjectSession | None:
        return await asyncio.to_thread(local().current)

    @app.get("/api/v1/local/activity")
    async def activity() -> dict[str, list[str]]:
        return await asyncio.to_thread(local().activity)

    @app.post("/api/v1/projects/open", response_model=ProjectSession)
    async def open_project(request: OpenRequest) -> ProjectSession:
        return await asyncio.to_thread(local().open, request.selection_id)

    @app.post("/api/v1/projects", response_model=ProjectSession)
    async def create_project(request: CreateRequest) -> ProjectSession:
        return await asyncio.to_thread(local().create, request.selection_id, request.name)

    @app.put("/api/v1/projects/{project_id}", response_model=ProjectSession)
    async def save_project(project_id: str, request: SaveRequest) -> ProjectSession:
        return await asyncio.to_thread(
            local().save, project_id, request.project, request.expected_revision
        )

    @app.post("/api/v1/projects/{project_id}/runs", response_model=Run, status_code=202)
    async def start_run(
        project_id: str,
        request: RunStartRequest,
        idempotency_key: str = Header(min_length=1, max_length=256),
    ) -> Run:
        return await asyncio.to_thread(local().start, project_id, request, idempotency_key)

    @app.get("/api/v1/health")
    async def health() -> dict[str, str | int | bool]:
        return {"appVersion": "0.0.0", "protocolVersion": 1, "ready": True}

    @app.get("/api/v1/catalog/blocks")
    async def catalog() -> dict[str, object]:
        return load_catalog()

    @app.post("/api/v1/projects/{project_id}/compile", response_model=CompileResponse)
    async def compile_preview(project_id: str, request: CompileRequest) -> CompileResponse:
        if project_id != request.project.project_id:
            raise HTTPException(status_code=422, detail="Project identity does not match")
        # This endpoint is pure preview: it never saves, executes or installs.
        result = (await asyncio.to_thread(compile_project, request.project)).result
        return CompileResponse(**result.model_dump(), request_id=request.request_id)

    def run_store(run_id: str) -> RunService:
        if runs is None:
            raise HTTPException(status_code=404, detail="Run store is not configured")
        try:
            runs.get(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown run") from None
        return runs

    @app.get("/api/v1/runs/{run_id}")
    async def run_status(run_id: str) -> dict[str, object]:
        service = await asyncio.to_thread(run_store, run_id)
        return (await asyncio.to_thread(service.get, run_id)).model_dump(by_alias=True)

    @app.post("/api/v1/runs/{run_id}/cancel")
    async def cancel_run(run_id: str) -> dict[str, object]:
        service = await asyncio.to_thread(run_store, run_id)
        try:
            return (await asyncio.to_thread(service.cancel, run_id)).model_dump(by_alias=True)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

    @app.get("/api/v1/runs/{run_id}/source", response_model=RunSource)
    async def run_source(run_id: str) -> RunSource:
        service = await asyncio.to_thread(run_store, run_id)
        return await asyncio.to_thread(RunViews(service).source, run_id)

    @app.get("/api/v1/runs/{run_id}/logs", response_model=RunLogs)
    async def run_logs(
        run_id: str,
        stdoutAfter: int = Query(default=0, ge=0),
        stderrAfter: int = Query(default=0, ge=0),
    ) -> RunLogs:
        service = await asyncio.to_thread(run_store, run_id)
        return await asyncio.to_thread(RunViews(service).logs, run_id, stdoutAfter, stderrAfter)

    @app.get("/api/v1/runs/{run_id}/artifacts", response_model=list[ArtifactRecord])
    async def run_artifacts(run_id: str) -> list[ArtifactRecord]:
        service = await asyncio.to_thread(run_store, run_id)
        return await asyncio.to_thread(RunViews(service).artifacts, run_id)

    @app.get("/api/v1/runs/{run_id}/artifacts/{artifact_id}/content")
    async def run_image(run_id: str, artifact_id: str) -> Response:
        service = await asyncio.to_thread(run_store, run_id)
        content = await asyncio.to_thread(RunViews(service).image, run_id, artifact_id)
        return Response(
            content,
            media_type="image/png",
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
        )

    @app.get("/api/v1/runs/{run_id}/events")
    async def run_events(
        run_id: str, request: Request, after: int = Query(default=0, ge=0)
    ) -> StreamingResponse:
        service = await asyncio.to_thread(run_store, run_id)

        async def stream() -> AsyncIterator[str]:
            cursor = after
            heartbeat = time.monotonic()
            while not await request.is_disconnected():
                for event in await asyncio.to_thread(service.events, run_id, cursor):
                    yield f"id: {event.seq}\nevent: {event.type}\ndata: {event.model_dump_json(by_alias=True)}\n\n"
                    cursor = event.seq
                current = await asyncio.to_thread(service.get, run_id)
                if current.status in TERMINAL:
                    # get() may have ingested the final event between the first read
                    # and status check. Drain that immutable terminal suffix too.
                    for event in await asyncio.to_thread(service.events, run_id, cursor):
                        yield f"id: {event.seq}\nevent: {event.type}\ndata: {event.model_dump_json(by_alias=True)}\n\n"
                    return
                if time.monotonic() - heartbeat >= 15:
                    yield ": heartbeat\n\n"
                    heartbeat = time.monotonic()
                await asyncio.sleep(0.05)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    return app
