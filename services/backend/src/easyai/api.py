import secrets
import asyncio
import time
import re
from pathlib import Path
from typing import Literal, TypeVar, Callable, Any
from uuid import UUID, uuid4
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pydantic import Field

from easyai.domain.connections import (
    ConnectionProfile,
    ConnectionProfileInput,
    ConnectionProfileUpdate,
    AuthenticationRequest,
    AuthenticatedConnection,
    PasswordAuthenticationInput,
    SessionControl,
)
from easyai.domain.remote_execution import (
    RemoteBinding,
    RemoteBindingRequest,
    RemoteRunStartRequest,
)
from easyai.domain.environment import (
    EnvironmentCatalog,
    EnvironmentDiscoveryRequest,
    EnvironmentProbeRequest,
    EnvironmentProbeResult,
    EnvironmentRequest,
)
from easyai.services.environment_transport import EnvironmentFailure
from easyai.domain.catalog import load_catalog
from easyai.domain.contracts import (
    CompileRequest,
    CompileResponse,
    Contract,
    Event,
    ProjectDocument,
    Run,
    ArtifactRecord,
)
from easyai.domain.desktop import (
    LocalPreflightRequest,
    LocalPreflightResult,
    ProjectSession,
    RunStartRequest,
    RunSource,
    RunLogs,
    SelectionResult,
)
from easyai.domain.ssh import (
    IdentityRequest,
    IdentityProbeRequest,
    IdentityConfirmRequest,
    IdentityResult,
)
from easyai.domain.ssh import SshFailure
from easyai.compiler.pipeline import compile_project
from easyai.services.run_service import RunService
from easyai.services.local_workspace import LocalWorkspace, RunScope
from easyai.services.run_views import RunViews


class SelectionRequest(Contract):
    kind: Literal["project", "python", "data"]
    path: str = Field(min_length=1, max_length=4096)


class OpenRequest(Contract):
    selection_id: str


class CreateRequest(OpenRequest):
    name: str = Field(min_length=1, max_length=128)
    template: Literal["mnist-cnn", "blank"] = "mnist-cnn"


class ImportRequest(Contract):
    source_path: str = Field(min_length=1, max_length=4096)
    destination_path: str = Field(min_length=1, max_length=4096)


class ExportRequest(Contract):
    path: str = Field(min_length=1, max_length=4096)
    project: ProjectDocument | None = None


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

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> Response:
        if (
            request.url.path.startswith(
                ("/api/v1/connections/", "/api/v1/environments/", "/api/v1/runs/")
            )
            or request.url.path == "/api/v1/connections"
            or request.url.path.endswith(("/runs", "/run-bindings"))
        ):
            # Validation errors normally echo input, including rejected secret fields.
            return JSONResponse(status_code=422, content={"error": {"code": "SSH_REQUEST_INVALID"}})
        return await request_validation_exception_handler(request, error)

    @app.exception_handler(ValueError)
    async def value_error(_request: Request, error: ValueError) -> JSONResponse:
        raw = str(error)
        code = raw if re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", raw) else "LOCAL_REQUEST_INVALID"
        status = 422
        if "FORBIDDEN" in code or code == "FILE_NOT_REGULAR":
            status = 403
        elif code in {
            "PROJECT_REVISION_CONFLICT",
            "PROGRAM_HASH_CONFLICT",
            "CONNECTION_PROFILE_REVISION_CONFLICT",
        }:
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

    @app.exception_handler(EnvironmentFailure)
    async def environment_failure(_request: Request, error: EnvironmentFailure) -> JSONResponse:
        code = str(error)
        if not re.fullmatch(r"ENVIRONMENT_[A-Z_]{1,80}", code):
            code = "ENVIRONMENT_OPERATION_FAILED"
        return JSONResponse(status_code=503, content={"error": {"code": code, "message": code}})

    @app.exception_handler(SshFailure)
    async def ssh_failure(_request: Request, error: SshFailure) -> JSONResponse:
        code = str(error)
        if not re.fullmatch(r"SSH_[A-Z_]{1,80}", code):
            code = "SSH_CONNECTION_FAILED"
        return JSONResponse(status_code=503, content={"error": {"code": code, "message": code}})

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

    @app.get("/api/v1/connections", response_model=list[ConnectionProfile])
    async def list_connection_profiles() -> list[ConnectionProfile]:
        return await asyncio.to_thread(local().list_connection_profiles)

    @app.post("/api/v1/connections", response_model=ConnectionProfile, status_code=201)
    async def create_connection_profile(request: ConnectionProfileInput) -> ConnectionProfile:
        return await asyncio.to_thread(local().create_connection_profile, request)

    @app.patch("/api/v1/connections/{target_id:uuid}", response_model=ConnectionProfile)
    async def update_connection_profile(
        target_id: UUID, request: ConnectionProfileUpdate
    ) -> ConnectionProfile:
        return await asyncio.to_thread(local().update_connection_profile, str(target_id), request)

    @app.post("/api/v1/connections/identity/probe", response_model=IdentityResult)
    async def probe_identity(request: IdentityProbeRequest) -> IdentityResult:
        service = local().identity()
        try:
            return await asyncio.to_thread(service.probe, request)
        except (Exception, asyncio.CancelledError):
            await asyncio.shield(asyncio.to_thread(service.cancel, request))
            raise

    @app.post("/api/v1/connections/identity/cancel")
    async def cancel_identity(request: IdentityRequest) -> dict[str, bool]:
        local().cancel_identity_connection(request)
        await asyncio.to_thread(local().identity().cancel, request)
        return {"cancelled": True}

    @app.post("/api/v1/connections/identity/confirm", response_model=IdentityResult)
    async def confirm_identity(request: IdentityConfirmRequest) -> IdentityResult:
        return await asyncio.to_thread(local().identity().confirm, request)

    @app.post("/api/v1/connections/auth/password", response_model=AuthenticatedConnection)
    async def authenticate_password(body: PasswordAuthenticationInput) -> AuthenticatedConnection:
        manager = local().connections()
        request: AuthenticationRequest = body.request
        password = body.password.get_secret_value()
        try:
            return await asyncio.to_thread(manager.authenticate_password, request, password)
        except asyncio.CancelledError:
            await asyncio.shield(
                asyncio.to_thread(
                    manager.cancel_auth,
                    IdentityRequest(project_id=request.project_id, request_id=request.request_id),
                )
            )
            raise
        finally:
            body.forget()
            password = ""

    @app.post("/api/v1/connections/auth/cancel")
    async def cancel_auth(request: IdentityRequest) -> dict[str, bool]:
        await asyncio.to_thread(local().connections().cancel_auth, request)
        return {"invalidated": True}

    @app.post("/api/v1/connections/session/close")
    async def close_connection(request: SessionControl) -> dict[str, bool]:
        await asyncio.to_thread(local().connections().close, request)
        return {"invalidated": True}

    @app.get("/api/v1/connections/session", response_model=AuthenticatedConnection | None)
    async def current_connection(
        project_id: str = Query(alias="projectId", pattern=r"^[0-9a-f-]{36}$"),
        connection_id: str = Query(alias="connectionId", pattern=r"^[0-9a-f-]{36}$"),
    ) -> AuthenticatedConnection | None:
        return await asyncio.to_thread(
            local().connections().current,
            SessionControl(project_id=project_id, connection_id=connection_id),
        )

    @app.post("/api/v1/environments/discover", response_model=EnvironmentCatalog)
    async def discover_environment(request: EnvironmentDiscoveryRequest) -> EnvironmentCatalog:
        manager = local().connections()
        service = manager.environments(request)
        try:
            return await asyncio.to_thread(service.discover, request)
        except asyncio.CancelledError:
            await asyncio.shield(asyncio.to_thread(manager.cancel_environment, request))
            raise

    @app.post("/api/v1/environments/probe", response_model=EnvironmentProbeResult)
    async def probe_environment(request: EnvironmentProbeRequest) -> EnvironmentProbeResult:
        manager = local().connections()
        service = manager.environments(request)
        try:
            return await asyncio.to_thread(service.probe, request)
        except asyncio.CancelledError:
            await asyncio.shield(asyncio.to_thread(manager.cancel_environment, request))
            raise

    @app.post("/api/v1/environments/cancel")
    async def cancel_environment(request: EnvironmentRequest) -> dict[str, bool]:
        await asyncio.to_thread(local().connections().cancel_environment, request)
        return {"invalidated": True}

    @app.post("/api/v1/local/selections", response_model=SelectionResult)
    async def select(request: SelectionRequest) -> SelectionResult:
        return await asyncio.to_thread(local().select, request.kind, Path(request.path))

    @app.get("/api/v1/local/session", response_model=ProjectSession | None)
    async def current() -> ProjectSession | None:
        return await asyncio.to_thread(local().current)

    @app.post("/api/v1/local/preflight", response_model=LocalPreflightResult)
    async def preflight_local(request: LocalPreflightRequest) -> LocalPreflightResult:
        workspace = local()
        generation = workspace.project_generation(request.project_id)
        workspace.verify_preflight_scope(request, generation)
        try:
            result = await asyncio.to_thread(workspace.preflight_local, request)
        except Exception:
            workspace.verify_preflight_scope(request, generation)
            raise
        workspace.verify_preflight_scope(request, generation)
        return result

    @app.get("/api/v1/local/activity")
    async def activity() -> dict[str, list[str]]:
        return await asyncio.to_thread(local().activity)

    @app.post("/api/v1/projects/open", response_model=ProjectSession)
    async def open_project(request: OpenRequest) -> ProjectSession:
        return await asyncio.to_thread(local().open, request.selection_id)

    @app.post("/api/v1/projects", response_model=ProjectSession)
    async def create_project(request: CreateRequest) -> ProjectSession:
        return await asyncio.to_thread(
            local().create, request.selection_id, request.name, request.template
        )

    @app.post("/api/v1/local/import", response_model=ProjectSession)
    async def import_project(request: ImportRequest) -> ProjectSession:
        return await asyncio.to_thread(
            local().import_project, Path(request.source_path), Path(request.destination_path)
        )

    @app.post("/api/v1/local/export")
    async def export_project(request: ExportRequest) -> dict[str, bool]:
        await asyncio.to_thread(local().export_current, Path(request.path), request.project)
        return {"exported": True}

    @app.get("/api/v1/projects/{project_id}/runs", response_model=list[Run])
    async def history(
        project_id: str,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=25, ge=1, le=50),
    ) -> list[Run]:
        generation = await asyncio.to_thread(local().project_generation, project_id)
        try:
            values = await asyncio.to_thread(local().history, project_id, offset, limit)
        except Exception:
            local().verify_project_generation(project_id, generation)
            raise
        local().verify_project_generation(project_id, generation)
        return values

    @app.put("/api/v1/projects/{project_id}", response_model=ProjectSession)
    async def save_project(project_id: str, request: SaveRequest) -> ProjectSession:
        return await asyncio.to_thread(
            local().save, project_id, request.project, request.expected_revision
        )

    @app.post("/api/v1/projects/{project_id}/run-bindings", response_model=RemoteBinding)
    async def bind_remote(project_id: str, request: RemoteBindingRequest) -> RemoteBinding:
        return await asyncio.to_thread(local().bind_remote, project_id, request)

    @app.post("/api/v1/runs/{run_id}/resume", response_model=Run, status_code=202)
    async def resume_remote(run_id: str, request: SessionControl) -> Run:
        return await asyncio.to_thread(local().resume_remote, run_id, request)

    @app.post("/api/v1/projects/{project_id}/runs", response_model=Run, status_code=202)
    async def start_run(
        project_id: str,
        request: RunStartRequest | RemoteRunStartRequest,
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

    def run_store(run_id: str) -> tuple[RunService, RunScope | None]:
        if runs is None:
            raise HTTPException(status_code=404, detail="Run store is not configured")
        try:
            scope = workspace.run_scope(run_id) if workspace is not None else None
            if workspace is None:
                runs.get(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown run") from None
        return runs, scope

    T = TypeVar("T")

    def scoped_read(scope: RunScope | None, action: Callable[..., T], *args: Any) -> T:
        if workspace is not None and scope is not None:
            return workspace.read_run(scope, action, *args)
        return action(*args)

    def deliver(scope: RunScope | None, value: T) -> T:
        if workspace is not None and scope is not None:
            workspace.verify_run_scope(scope)
        return value

    async def read_response(scope: RunScope | None, action: Callable[..., T], *args: Any) -> T:
        try:
            value = await asyncio.to_thread(scoped_read, scope, action, *args)
        except Exception:
            deliver(scope, None)  # Recheck after await before forwarding even an error.
            raise
        return deliver(scope, value)

    def scoped_cancel(service: RunService, scope: RunScope | None, run_id: str) -> Run:
        if workspace is not None and scope is not None:
            return workspace.cancel_run(scope)
        return service.cancel(run_id)

    @app.get("/api/v1/runs/{run_id}")
    async def run_status(run_id: str) -> dict[str, object]:
        service, scope = await asyncio.to_thread(run_store, run_id)
        return (await read_response(scope, service.get, run_id)).model_dump(by_alias=True)

    @app.post("/api/v1/runs/{run_id}/cancel")
    async def cancel_run(run_id: str) -> dict[str, object]:
        service, scope = await asyncio.to_thread(run_store, run_id)
        try:
            return deliver(
                scope, await asyncio.to_thread(scoped_cancel, service, scope, run_id)
            ).model_dump(by_alias=True)
        except ValueError as error:
            deliver(scope, None)
            raise HTTPException(status_code=409, detail=str(error)) from None

    @app.get("/api/v1/runs/{run_id}/source", response_model=RunSource)
    async def run_source(run_id: str) -> RunSource:
        service, scope = await asyncio.to_thread(run_store, run_id)
        return await read_response(scope, RunViews(service).source, run_id)

    @app.get("/api/v1/runs/{run_id}/logs", response_model=RunLogs)
    async def run_logs(
        run_id: str,
        stdoutAfter: int = Query(default=0, ge=0),
        stderrAfter: int = Query(default=0, ge=0),
    ) -> RunLogs:
        service, scope = await asyncio.to_thread(run_store, run_id)
        return await read_response(scope, RunViews(service).logs, run_id, stdoutAfter, stderrAfter)

    @app.get("/api/v1/runs/{run_id}/artifacts", response_model=list[ArtifactRecord])
    async def run_artifacts(run_id: str) -> list[ArtifactRecord]:
        service, scope = await asyncio.to_thread(run_store, run_id)
        return await read_response(scope, RunViews(service).artifacts, run_id)

    @app.get("/api/v1/runs/{run_id}/artifacts/{artifact_id}/content")
    async def run_image(run_id: str, artifact_id: str) -> Response:
        service, scope = await asyncio.to_thread(run_store, run_id)
        content = await read_response(scope, RunViews(service).image, run_id, artifact_id)
        return Response(
            deliver(scope, content),
            media_type="image/png",
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
        )

    @app.get("/api/v1/runs/{run_id}/events")
    async def run_events(
        run_id: str, request: Request, after: int = Query(default=0, ge=0)
    ) -> StreamingResponse:
        service, scope = await asyncio.to_thread(run_store, run_id)

        def batch(cursor: int) -> tuple[list[Event], bool]:
            events = RunViews(service).events(run_id, cursor)
            current = service.get(run_id)
            settled = service.remote.settled(current)
            if settled:
                events = RunViews(service).events(
                    run_id, cursor
                )  # Include the final immutable suffix.
            return events, settled

        async def stream() -> AsyncIterator[str]:
            cursor = after
            heartbeat = time.monotonic()
            while not await request.is_disconnected():
                try:
                    events, settled = await asyncio.to_thread(scoped_read, scope, batch, cursor)
                    for event in events:
                        if workspace is not None and scope is not None:
                            workspace.verify_run_scope(scope)
                        yield f"id: {event.seq}\nevent: {event.type}\ndata: {event.model_dump_json(by_alias=True)}\n\n"
                        cursor = event.seq
                    if settled:
                        return
                    if time.monotonic() - heartbeat >= 15:
                        if workspace is not None and scope is not None:
                            workspace.verify_run_scope(scope)
                        yield ": heartbeat\n\n"
                        heartbeat = time.monotonic()
                except (KeyError, ValueError):
                    return  # Scope retirement ends delivery, never reads another project's events.
                await asyncio.sleep(0.05)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    return app
