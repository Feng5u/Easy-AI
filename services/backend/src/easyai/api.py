import secrets

from fastapi import Depends, FastAPI, Header, HTTPException

from easyai.domain.catalog import load_catalog
from easyai.domain.contracts import CompileRequest, CompileResponse
from easyai.compiler.pipeline import compile_project


def create_app(token: str) -> FastAPI:
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

    return app
