"""Admin CRUD for Suno lyrics blocklist terms."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from platform_api.dependencies import get_suno_blocklist_service
from platform_api.exceptions import DuplicateError, NotFoundError, PlatformAPIError, ValidationError
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.services.suno_blocklist_service import SunoBlocklistService

router = APIRouter(prefix="/admin/suno-blocklist", tags=["admin-suno-blocklist"])

AdminDep = Annotated[AuthContext, Depends(require_admin)]
BlocklistServiceDep = Annotated[SunoBlocklistService, Depends(get_suno_blocklist_service)]


class SunoBlocklistTermResponse(BaseModel):
    id: str
    term: str
    replacement: str | None = None
    severity: Literal["block", "warn"]
    source: Literal["manual", "learned"]
    enabled: bool
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SunoBlocklistListResponse(BaseModel):
    items: list[SunoBlocklistTermResponse]


class CreateSunoBlocklistRequest(BaseModel):
    term: str = Field(min_length=1, max_length=120)
    replacement: str | None = Field(default=None, max_length=120)
    severity: Literal["block", "warn"] = "block"
    enabled: bool = True
    notes: str | None = None


class UpdateSunoBlocklistRequest(BaseModel):
    term: str | None = Field(default=None, min_length=1, max_length=120)
    replacement: str | None = Field(default=None, max_length=120)
    severity: Literal["block", "warn"] | None = None
    enabled: bool | None = None
    notes: str | None = None
    clear_replacement: bool = False


class PromoteSunoBlocklistRequest(BaseModel):
    term: str = Field(min_length=1, max_length=120)
    replacement: str | None = Field(default=None, max_length=120)
    severity: Literal["block", "warn"] = "block"
    notes: str | None = None


def _row_to_response(row: dict) -> SunoBlocklistTermResponse:
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")
    return SunoBlocklistTermResponse(
        id=str(row["id"]),
        term=str(row["term"]),
        replacement=str(row["replacement"]) if row.get("replacement") is not None else None,
        severity=str(row["severity"]),  # type: ignore[arg-type]
        source=str(row["source"]),  # type: ignore[arg-type]
        enabled=bool(row.get("enabled")),
        notes=str(row["notes"]) if row.get("notes") is not None else None,
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


def _raise_http(error: PlatformAPIError) -> None:
    if isinstance(error, ValidationError):
        raise HTTPException(status_code=400, detail=error.message) from error
    if isinstance(error, DuplicateError):
        raise HTTPException(status_code=409, detail=error.message) from error
    if isinstance(error, NotFoundError):
        raise HTTPException(status_code=404, detail=error.message) from error
    raise HTTPException(status_code=500, detail=error.message) from error


@router.get("", response_model=SunoBlocklistListResponse)
async def list_suno_blocklist_terms(
    _ctx: AdminDep,
    service: BlocklistServiceDep,
) -> SunoBlocklistListResponse:
    rows = await service.list_terms()
    return SunoBlocklistListResponse(items=[_row_to_response(row) for row in rows])


@router.post("", response_model=SunoBlocklistTermResponse, status_code=201)
async def create_suno_blocklist_term(
    request: CreateSunoBlocklistRequest,
    _ctx: AdminDep,
    service: BlocklistServiceDep,
) -> SunoBlocklistTermResponse:
    try:
        row = await service.create_term(
            term=request.term,
            replacement=request.replacement,
            severity=request.severity,
            enabled=request.enabled,
            notes=request.notes,
            source="manual",
        )
    except PlatformAPIError as exc:
        _raise_http(exc)
    return _row_to_response(row)


@router.put("/{term_id}", response_model=SunoBlocklistTermResponse)
async def update_suno_blocklist_term(
    term_id: UUID,
    request: UpdateSunoBlocklistRequest,
    _ctx: AdminDep,
    service: BlocklistServiceDep,
) -> SunoBlocklistTermResponse:
    try:
        row = await service.update_term(
            term_id,
            term=request.term,
            replacement=request.replacement,
            severity=request.severity,
            enabled=request.enabled,
            notes=request.notes,
            clear_replacement=request.clear_replacement,
        )
    except PlatformAPIError as exc:
        _raise_http(exc)
    return _row_to_response(row)


@router.delete("/{term_id}", status_code=204, response_class=Response)
async def delete_suno_blocklist_term(
    term_id: UUID,
    _ctx: AdminDep,
    service: BlocklistServiceDep,
) -> Response:
    try:
        deleted = await service.delete_term(term_id)
    except PlatformAPIError as exc:
        _raise_http(exc)
    if not deleted:
        raise HTTPException(status_code=404, detail="Blocklist term not found.")
    return Response(status_code=204)


@router.post("/promote", response_model=SunoBlocklistTermResponse, status_code=201)
async def promote_suno_blocklist_term(
    request: PromoteSunoBlocklistRequest,
    _ctx: AdminDep,
    service: BlocklistServiceDep,
) -> SunoBlocklistTermResponse:
    try:
        row = await service.promote_learned_term(
            term=request.term,
            replacement=request.replacement,
            severity=request.severity,
            notes=request.notes,
        )
    except PlatformAPIError as exc:
        _raise_http(exc)
    return _row_to_response(row)


class SunoFailureMetricBucket(BaseModel):
    failure_type: str
    submit_kind: Literal["first_submit", "retry"]
    count: int


class SunoFailureMetricsResponse(BaseModel):
    days: int
    total: int
    buckets: list[SunoFailureMetricBucket]


@router.get("/failure-metrics", response_model=SunoFailureMetricsResponse)
async def get_suno_failure_metrics(
    _ctx: AdminDep,
    days: int = 30,
) -> SunoFailureMetricsResponse:
    from platform_api.dependencies import get_db_pool
    from platform_api.repositories.batch_repo import BatchRepository
    from platform_api.services.suno_status_messages import classify_suno_failure_type

    repo = BatchRepository(get_db_pool())
    rows = await repo.list_suno_failure_metrics_rows(days=days)
    bucket_counts: dict[tuple[str, str], int] = {}
    for row in rows:
        failure_type = classify_suno_failure_type(error_message=row.get("error_message"))
        submit_kind = "first_submit" if int(row.get("submit_order") or 1) <= 1 else "retry"
        key = (failure_type, submit_kind)
        bucket_counts[key] = bucket_counts.get(key, 0) + 1

    buckets = [
        SunoFailureMetricBucket(
            failure_type=failure_type,
            submit_kind=submit_kind,  # type: ignore[arg-type]
            count=count,
        )
        for (failure_type, submit_kind), count in sorted(bucket_counts.items())
    ]
    return SunoFailureMetricsResponse(
        days=max(1, min(int(days or 30), 365)),
        total=len(rows),
        buckets=buckets,
    )
