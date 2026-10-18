import secrets
import asyncio
import time
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from easyai.domain.catalog import load_catalog
from easyai.domain.contracts import CompileRequest, CompileResponse
from easyai.compiler.pipeline import compile_project
from easyai.services.run_service import RunService, TERMINAL


def create_app(token: str, runs: RunService | None = None) -> FastAPI:
    async def authorize(authorization: str | None = Header(default=None)) -> None:
        if authorization is None or not secrets.compare_digest(
            authorization.encode("utf-8"), f"Bearer {token}".encode("ascii")
        ):
            raise HTTPException(status_code=401, detail="Session authorization required")

    app = FastAPI(
        docs_url=None, redoc_url=None, openapi_url=None, dependencies=[Depends(authorize)]
    )

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
        result = compile_project(request.project).result
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
