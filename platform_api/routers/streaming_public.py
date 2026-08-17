"""Public music streaming API for music.camxora.com."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from platform_api.exceptions import NotFoundError
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.middleware.rate_limit import enforce_rate_limit_for_endpoint
from platform_api.services.streaming_catalog_service import StreamingCatalogService

router = APIRouter(prefix="/public/streaming", tags=["streaming-public"])


async def _get_catalog_service() -> StreamingCatalogService:
    raise NotImplementedError("StreamingCatalogService dependency not configured.")


CatalogServiceDep = Annotated[StreamingCatalogService, Depends(_get_catalog_service)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


class PlayUrlResponse(BaseModel):
    track_id: str
    url: str
    expires_at: str
    title: str | None = None
    album_id: str | None = None
    album_name: str | None = None
    user_id: str | None = None
    artist_name: str | None = None
    variant: str | None = None
    cover_url: str | None = None
    duration_seconds: float | None = None
    play_count: int = 0
    genre: str | None = None
    lyrics: str | None = None


@router.get("/home")
async def get_streaming_home(service: CatalogServiceDep) -> dict:
    return await service.get_home()


@router.get("/albums")
async def list_streaming_albums(
    service: CatalogServiceDep,
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return await service.list_albums(limit=limit, offset=offset)


@router.get("/albums/{album_id}")
async def get_streaming_album(album_id: UUID, service: CatalogServiceDep) -> dict:
    album = await service.get_album(album_id)
    if album is None:
        raise NotFoundError("Album not found.")
    return album


@router.get("/genres")
async def list_streaming_genres(service: CatalogServiceDep) -> dict:
    items = await service.list_genres()
    return {"items": items}


@router.get("/genres/{slug}")
async def get_streaming_genre(slug: str, service: CatalogServiceDep) -> dict:
    genre = await service.get_genre(slug)
    if genre is None:
        raise NotFoundError("Genre not found.")
    return genre


@router.get("/artists")
async def list_streaming_artists(
    service: CatalogServiceDep,
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return await service.list_artists(limit=limit, offset=offset)


@router.get("/artists/{user_id}")
async def get_streaming_artist(user_id: UUID, service: CatalogServiceDep) -> dict:
    artist = await service.get_artist(user_id)
    if artist is None:
        raise NotFoundError("Artist not found.")
    return artist


@router.get("/search")
async def search_streaming_catalog(
    service: CatalogServiceDep,
    q: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return await service.search(q, limit=limit, offset=offset)


@router.get("/tracks/{track_id}/play-url", response_model=PlayUrlResponse)
async def get_track_play_url(
    track_id: UUID,
    ctx: CurrentUserDep,
    service: CatalogServiceDep,
) -> PlayUrlResponse:
    await enforce_rate_limit_for_endpoint(ctx.user_id, "web_music_play")
    payload = await service.get_play_url(track_id)
    if payload is None:
        raise NotFoundError("Track not found or streaming is not configured.")
    return PlayUrlResponse.model_validate(payload)


@router.get("/tracks/{track_id}/stream")
async def stream_track(
    track_id: UUID,
    request: Request,
    ctx: CurrentUserDep,
    service: CatalogServiceDep,
) -> Response:
    await enforce_rate_limit_for_endpoint(ctx.user_id, "web_music_play")
    return await service.proxy_track_audio(
        track_id,
        range_header=request.headers.get("range"),
    )
