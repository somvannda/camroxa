"""Admin CRUD for Suno lyrics blocklist terms."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
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


@router.delete("/{term_id}", status_code=204)
async def delete_suno_blocklist_term(
    term_id: UUID,
    _ctx: AdminDep,
    service: BlocklistServiceDep,
) -> None:
    try:
        deleted = await service.delete_term(term_id)
    except PlatformAPIError as exc:
        _raise_http(exc)
    if not deleted:
        raise HTTPException(status_code=404, detail="Blocklist term not found.")


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
