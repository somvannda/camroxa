"""Authenticated music library API (likes) for music_web."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from platform_api.exceptions import NotFoundError
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.services.streaming_catalog_service import StreamingCatalogService

router = APIRouter(prefix="/streaming/library", tags=["streaming-library"])

CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


async def _get_catalog_service() -> StreamingCatalogService:
    raise NotImplementedError("StreamingCatalogService dependency not configured.")


CatalogServiceDep = Annotated[StreamingCatalogService, Depends(_get_catalog_service)]


class LikeIdsResponse(BaseModel):
    track_ids: list[str] = Field(default_factory=list)


class LikeMutationResponse(BaseModel):
    ok: bool
    liked: bool
    created: bool | None = None
    removed: bool | None = None


@router.get("/likes/ids", response_model=LikeIdsResponse)
async def list_like_ids(
    ctx: CurrentUserDep,
    service: CatalogServiceDep,
) -> LikeIdsResponse:
    ids = await service.list_liked_track_ids(UUID(ctx.user_id))
    return LikeIdsResponse(track_ids=ids)


@router.get("/likes")
async def list_likes(
    ctx: CurrentUserDep,
    service: CatalogServiceDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    return await service.list_liked_tracks(UUID(ctx.user_id), limit=limit, offset=offset)


@router.put("/likes/{track_id}", response_model=LikeMutationResponse)
async def like_track(
    track_id: UUID,
    ctx: CurrentUserDep,
    service: CatalogServiceDep,
) -> LikeMutationResponse:
    result = await service.like_track(UUID(ctx.user_id), track_id)
    if not result.get("ok"):
        raise NotFoundError("Track not found.")
    return LikeMutationResponse(
        ok=True,
        liked=True,
        created=bool(result.get("created")),
    )


@router.delete("/likes/{track_id}", response_model=LikeMutationResponse)
async def unlike_track(
    track_id: UUID,
    ctx: CurrentUserDep,
    service: CatalogServiceDep,
) -> LikeMutationResponse:
    result = await service.unlike_track(UUID(ctx.user_id), track_id)
    return LikeMutationResponse(
        ok=True,
        liked=False,
        removed=bool(result.get("removed")),
    )
