"""Client log upload + admin retrieval endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.services.client_log_service import ClientLogService

router = APIRouter(tags=["client-logs"])


def _get_client_log_service() -> ClientLogService:
    raise RuntimeError("ClientLogService dependency not wired")


ClientLogServiceDep = Annotated[ClientLogService, Depends(_get_client_log_service)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


class ClientLogUploadRequest(BaseModel):
    content: str = Field(min_length=1)
    line_count: int | None = Field(default=None, alias="lineCount")
    app_version: str | None = Field(default=None, alias="appVersion")
    client_label: str | None = Field(default=None, alias="clientLabel")

    model_config = {"populate_by_name": True}


class ClientLogBatchSummary(BaseModel):
    id: str
    user_id: str
    client_id: str | None = None
    client_label: str | None = None
    app_version: str | None = None
    line_count: int
    size_bytes: int
    created_at: str
    preview: str | None = None


class ClientLogUploadResponse(BaseModel):
    id: str
    line_count: int
    size_bytes: int
    created_at: str


class ClientLogListResponse(BaseModel):
    items: list[ClientLogBatchSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class ClientLogDetailResponse(BaseModel):
    id: str
    user_id: str
    client_id: str | None = None
    client_label: str | None = None
    app_version: str | None = None
    line_count: int
    size_bytes: int
    created_at: str
    content: str


def _summary(batch: Any, *, include_preview: bool = True) -> ClientLogBatchSummary:
    preview = None
    if include_preview:
        text = str(batch.content or "")
        preview = text[:400] + ("…" if len(text) > 400 else "")
    return ClientLogBatchSummary(
        id=str(batch.id),
        user_id=str(batch.user_id),
        client_id=batch.client_id,
        client_label=batch.client_label,
        app_version=batch.app_version,
        line_count=int(batch.line_count),
        size_bytes=int(batch.size_bytes),
        created_at=batch.created_at.isoformat() if batch.created_at else "",
        preview=preview,
    )


@router.post("/client-logs", response_model=ClientLogUploadResponse, status_code=201)
async def upload_client_logs(
    request: ClientLogUploadRequest,
    ctx: CurrentUserDep,
    service: ClientLogServiceDep,
    http_request: Request,
    x_client_id: Annotated[str | None, Header(alias="X-Client-ID")] = None,
) -> ClientLogUploadResponse:
    try:
        batch = await service.upload(
            user_id=UUID(ctx.user_id),
            content=request.content,
            line_count=request.line_count,
            client_id=x_client_id or http_request.headers.get("X-Client-Id"),
            client_label=request.client_label,
            app_version=request.app_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ClientLogUploadResponse(
        id=str(batch.id),
        line_count=int(batch.line_count),
        size_bytes=int(batch.size_bytes),
        created_at=batch.created_at.isoformat() if batch.created_at else "",
    )


@router.get("/admin/users/{user_id}/client-logs", response_model=ClientLogListResponse)
async def list_user_client_logs(
    user_id: UUID,
    ctx: AdminDep,
    service: ClientLogServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> ClientLogListResponse:
    batches, total = await service.list_for_user(user_id=user_id, page=page, page_size=page_size)
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 0
    return ClientLogListResponse(
        items=[_summary(batch) for batch in batches],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/admin/client-logs/{batch_id}", response_model=ClientLogDetailResponse)
async def get_client_log_batch(
    batch_id: UUID,
    ctx: AdminDep,
    service: ClientLogServiceDep,
) -> ClientLogDetailResponse:
    batch = await service.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Client log batch not found.")
    return ClientLogDetailResponse(
        id=str(batch.id),
        user_id=str(batch.user_id),
        client_id=batch.client_id,
        client_label=batch.client_label,
        app_version=batch.app_version,
        line_count=int(batch.line_count),
        size_bytes=int(batch.size_bytes),
        created_at=batch.created_at.isoformat() if batch.created_at else "",
        content=batch.content,
    )
