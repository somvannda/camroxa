"""Admin CRUD for the curated remix Staff Picks catalog."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, require_admin

router = APIRouter(prefix="/admin/remix/staff-picks", tags=["admin-remix"])
AdminDep = Annotated[AuthContext, Depends(require_admin)]


class StaffPickRow(BaseModel):
    id: str
    provider_clip_id: str
    title: str
    image_url: str | None = None
    styles: str | None = None
    model: str | None = None
    account_id: str | None = None
    sort_order: int = 0
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class StaffPickListResponse(BaseModel):
    items: list[StaffPickRow]


class CreateStaffPickRequest(BaseModel):
    provider_clip_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    image_url: str | None = None
    styles: str | None = None
    model: str | None = None
    account_id: str | None = None
    sort_order: int = 0
    is_active: bool = True

    @field_validator("provider_clip_id", "title")
    @classmethod
    def required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value is required.")
        return normalized


class UpdateStaffPickRequest(BaseModel):
    provider_clip_id: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    image_url: str | None = None
    styles: str | None = None
    model: str | None = None
    account_id: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


def _row(row: dict) -> StaffPickRow:
    return StaffPickRow(
        id=str(row["id"]),
        provider_clip_id=str(row["provider_clip_id"]),
        title=str(row["title"]),
        image_url=row["image_url"],
        styles=row["styles"],
        model=row["model"],
        account_id=row["account_id"],
        sort_order=int(row["sort_order"] or 0),
        is_active=bool(row["is_active"]),
        created_at=row["created_at"].isoformat() if row["created_at"] else None,
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
    )


@router.get("", response_model=StaffPickListResponse)
async def list_staff_picks_admin(_ctx: AdminDep) -> StaffPickListResponse:
    pool = get_db_pool()
    rows = await pool.fetch(
        """
        SELECT id, provider_clip_id, title, image_url, styles, model, account_id,
               sort_order, is_active, created_at, updated_at
        FROM remix_staff_picks
        ORDER BY sort_order ASC, created_at DESC
        """
    )
    return StaffPickListResponse(items=[_row(dict(r)) for r in rows])


@router.post("", response_model=StaffPickRow, status_code=201)
async def create_staff_pick(
    request: CreateStaffPickRequest,
    ctx: AdminDep,
) -> StaffPickRow:
    pool = get_db_pool()
    try:
        row = await pool.fetchrow(
            """
            INSERT INTO remix_staff_picks
                (provider_clip_id, title, image_url, styles, model, account_id, sort_order, is_active, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id, provider_clip_id, title, image_url, styles, model, account_id,
                      sort_order, is_active, created_at, updated_at
            """,
            request.provider_clip_id,
            request.title,
            request.image_url,
            request.styles,
            request.model,
            request.account_id,
            request.sort_order,
            request.is_active,
            UUID(ctx.user_id),
        )
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="This provider clip is already in Staff Picks.") from exc
        raise
    if row is None:
        raise HTTPException(status_code=500, detail="Could not create staff pick.")
    return _row(dict(row))


@router.patch("/{pick_id}", response_model=StaffPickRow)
async def update_staff_pick(
    pick_id: UUID,
    request: UpdateStaffPickRequest,
    _ctx: AdminDep,
) -> StaffPickRow:
    pool = get_db_pool()
    row = await pool.fetchrow(
        """
        UPDATE remix_staff_picks
        SET provider_clip_id = COALESCE($2, provider_clip_id),
            title = COALESCE($3, title),
            image_url = COALESCE($4, image_url),
            styles = COALESCE($5, styles),
            model = COALESCE($6, model),
            account_id = COALESCE($7, account_id),
            sort_order = COALESCE($8, sort_order),
            is_active = COALESCE($9, is_active),
            updated_at = NOW()
        WHERE id = $1
        RETURNING id, provider_clip_id, title, image_url, styles, model, account_id,
                  sort_order, is_active, created_at, updated_at
        """,
        pick_id,
        request.provider_clip_id,
        request.title,
        request.image_url,
        request.styles,
        request.model,
        request.account_id,
        request.sort_order,
        request.is_active,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Staff pick not found.")
    return _row(dict(row))


@router.delete("/{pick_id}", status_code=204, response_class=Response)
async def delete_staff_pick(pick_id: UUID, _ctx: AdminDep) -> Response:
    pool = get_db_pool()
    deleted = await pool.fetchrow(
        "DELETE FROM remix_staff_picks WHERE id = $1 RETURNING id", pick_id
    )
    if deleted is None:
        raise HTTPException(status_code=404, detail="Staff pick not found.")
    return Response(status_code=204)
