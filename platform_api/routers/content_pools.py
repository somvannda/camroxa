"""Read-only content-pool endpoints for Electron visibility surfaces."""

from __future__ import annotations

from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.services.content_pool_service import (
    ClaimedPoolItem,
    claim_pool_item,
    finalize_pool_item,
    release_pool_item,
)

router = APIRouter(prefix="/content-pools", tags=["content-pools"])

PoolKind = Literal["titles", "albums", "openings"]
_RESERVATION_STALE_SECONDS = 900


class ContentPoolStat(BaseModel):
    total: int
    unused: int


class ContentPoolStatsResponse(BaseModel):
    titles: ContentPoolStat
    albums: ContentPoolStat
    openings: ContentPoolStat


class ContentPoolRow(BaseModel):
    id: int
    text: str
    secondary_text: str | None = None
    used_count: int
    created_at: str | None = None


class ContentPoolListResponse(BaseModel):
    kind: PoolKind
    total: int
    limit: int
    offset: int
    items: list[ContentPoolRow]


class ClaimContentPoolRequest(BaseModel):
    reservation_token: str | None = None
    consumer: str = Field(default="generation", min_length=1, max_length=80)
    limit: int = Field(default=50, ge=1, le=1000)
    ttl_seconds: int = Field(default=_RESERVATION_STALE_SECONDS, ge=60, le=7200)


class ClaimedContentPoolItem(BaseModel):
    id: int
    text: str
    secondary_text: str | None = None
    used_count: int
    reservation_token: str
    reserved_by: str
    reserved_at: str | None = None
    created_at: str | None = None


class ClaimContentPoolResponse(BaseModel):
    kind: PoolKind
    item: ClaimedContentPoolItem


class ReservationActionRequest(BaseModel):
    item_id: int = Field(ge=1)
    reservation_token: str = Field(min_length=1, max_length=120)


class ReservationActionResponse(BaseModel):
    ok: bool


def _get_table_name(kind: PoolKind) -> str:
    if kind == "titles":
        return "title_pool"
    if kind == "albums":
        return "album_pool"
    return "opening_pairs"


def _claimed_item_response(kind: PoolKind, item, *, reservation_owner: str) -> ClaimedContentPoolItem:
    return ClaimedContentPoolItem(
        id=int(item.item_id),
        text=str(item.text or ""),
        secondary_text=item.secondary_text,
        used_count=0,
        reservation_token=str(item.reservation_token or ""),
        reserved_by=reservation_owner,
        reserved_at=None,
        created_at=None,
    )


@router.get("/stats", response_model=ContentPoolStatsResponse)
async def get_content_pool_stats(
    _ctx: AuthContext = Depends(get_current_user),
) -> ContentPoolStatsResponse:
    pool = get_db_pool()

    async def fetch_stat(table_name: str) -> ContentPoolStat:
        row = await pool.fetchrow(
            f"""
            SELECT
                COUNT(*)::int AS total,
                COUNT(*) FILTER (WHERE COALESCE(used_count, 0) = 0)::int AS unused
            FROM {table_name}
            """
        )
        return ContentPoolStat(
            total=int(row["total"] or 0) if row else 0,
            unused=int(row["unused"] or 0) if row else 0,
        )

    return ContentPoolStatsResponse(
        titles=await fetch_stat("title_pool"),
        albums=await fetch_stat("album_pool"),
        openings=await fetch_stat("opening_pairs"),
    )


@router.get("/{kind}", response_model=ContentPoolListResponse)
async def list_content_pool_items(
    kind: PoolKind,
    _ctx: AuthContext = Depends(get_current_user),
    limit: int = Query(default=100, ge=10, le=500),
    offset: int = Query(default=0, ge=0),
) -> ContentPoolListResponse:
    pool = get_db_pool()
    table_name = _get_table_name(kind)
    total = int(await pool.fetchval(f"SELECT COUNT(*) FROM {table_name}") or 0)

    if kind == "openings":
        rows = await pool.fetch(
            """
            SELECT id, line1, line2, COALESCE(used_count, 0) AS used_count, created_at
            FROM opening_pairs
            ORDER BY id DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        items = [
            ContentPoolRow(
                id=int(row["id"]),
                text=str(row["line1"] or ""),
                secondary_text=str(row["line2"] or "") or None,
                used_count=int(row["used_count"] or 0),
                created_at=row["created_at"].isoformat() if row.get("created_at") else None,
            )
            for row in rows
        ]
    else:
        column_name = "title" if kind == "titles" else "album"
        rows = await pool.fetch(
            f"""
            SELECT id, {column_name} AS text, COALESCE(used_count, 0) AS used_count, created_at
            FROM {table_name}
            ORDER BY id DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        items = [
            ContentPoolRow(
                id=int(row["id"]),
                text=str(row["text"] or ""),
                used_count=int(row["used_count"] or 0),
                created_at=row["created_at"].isoformat() if row.get("created_at") else None,
            )
            for row in rows
        ]

    return ContentPoolListResponse(
        kind=kind,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.post("/{kind}/claim", response_model=ClaimContentPoolResponse)
async def claim_content_pool_item(
    kind: PoolKind,
    request: ClaimContentPoolRequest,
    ctx: AuthContext = Depends(get_current_user),
) -> ClaimContentPoolResponse:
    reservation_token = str(request.reservation_token or "").strip() or str(uuid4())
    consumer = str(request.consumer or "").strip() or "generation"
    reservation_owner = f"{ctx.user_id}:{consumer}"
    try:
        item = await claim_pool_item(
            kind=kind,
            reservation_token=reservation_token,
            reservation_owner=reservation_owner,
            limit=int(request.limit),
            ttl_seconds=int(request.ttl_seconds or _RESERVATION_STALE_SECONDS),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ClaimContentPoolResponse(
        kind=kind,
        item=_claimed_item_response(kind, item, reservation_owner=reservation_owner),
    )


@router.post("/{kind}/release", response_model=ReservationActionResponse)
async def release_content_pool_item(
    kind: PoolKind,
    request: ReservationActionRequest,
    _ctx: AuthContext = Depends(get_current_user),
) -> ReservationActionResponse:
    try:
        await release_pool_item(
            item=ClaimedPoolItem(
                kind=kind,
                item_id=int(request.item_id),
                text="",
                secondary_text=None,
                reservation_token=str(request.reservation_token).strip(),
            )
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReservationActionResponse(ok=True)


@router.post("/{kind}/finalize", response_model=ReservationActionResponse)
async def finalize_content_pool_item(
    kind: PoolKind,
    request: ReservationActionRequest,
    _ctx: AuthContext = Depends(get_current_user),
) -> ReservationActionResponse:
    try:
        await finalize_pool_item(
            item=ClaimedPoolItem(
                kind=kind,
                item_id=int(request.item_id),
                text="",
                secondary_text=None,
                reservation_token=str(request.reservation_token).strip(),
            )
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReservationActionResponse(ok=True)
