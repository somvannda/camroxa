"""Authenticated music-web generation API (no desktop license / channel profile)."""

from __future__ import annotations

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.middleware.rate_limit import enforce_rate_limit, enforce_rate_limit_for_endpoint
from platform_api.middleware.abuse_detection import track_generation_attempt, track_quota_exceeded
from platform_api.services.generation_freeze import (
    enforce_generation_freeze,
    reject_probe_payload,
)
from platform_api.services.web_music_service import WebMusicService, content_disposition
from platform_api.services.audio_origin_proxy import is_missing_range
from platform_api.exceptions import NotFoundError, QuotaExceededError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web-music", tags=["web-music"])

CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


async def _get_web_music_service() -> WebMusicService:
    raise NotImplementedError("WebMusicService dependency not configured.")


WebMusicServiceDep = Annotated[WebMusicService, Depends(_get_web_music_service)]


class WebMusicGenerateRequest(BaseModel):
    mode: Literal["simple", "advanced"] = "advanced"
    lyrics: str = Field(default="", max_length=5000)
    style: str = Field(default="", max_length=1000)
    title: str = Field(default="", max_length=200)
    # Suno V5/V5.5 customMode lyrics cap. Simple mode UI clamps to 1000 (style).
    prompt: str = Field(default="", max_length=5000)
    instrumental: bool = False
    model: str = Field(default="V5_5", pattern=r"^(V5|V5_5)$")
    negative_tags: str | None = Field(default=None, max_length=500)
    vocal_gender: Literal["m", "f", "both", ""] | None = None
    style_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    weirdness_constraint: float | None = Field(default=None, ge=0.0, le=1.0)
    audio_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    workspace_id: UUID | None = None


class WebMusicClipResponse(BaseModel):
    variant: str
    label: str
    audio_url: str
    download_url: str
    ready: bool = False
    package_status: str = "none"
    image_url: str | None = None
    duration_seconds: float | None = None
    title: str = ""


class WebMusicQuotaResponse(BaseModel):
    limit: int
    used: int
    remaining: int
    is_pro: bool = False
    requires_upgrade: bool = False
    can_download: bool = False
    has_subscription: bool = False
    queue_limit: int = 2
    queue_used: int = 0


class WebMusicPlaylistResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    is_public: bool = False
    song_count: int = 0
    is_owner: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class WebMusicPlaylistListResponse(BaseModel):
    items: list[WebMusicPlaylistResponse] = Field(default_factory=list)


class WebMusicPublicCreatorResponse(BaseModel):
    user_id: str
    artist_name: str
    avatar_url: str | None = None
    playlist_count: int = 0
    album_count: int = 0
    track_count: int = 0


class WebMusicPublicStreamingAlbumResponse(BaseModel):
    id: str
    album_name: str
    artist_name: str = ""
    user_id: str
    track_count: int = 0
    play_count: int = 0
    cover_url: str | None = None


class WebMusicPublicPlaylistResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    song_count: int = 0
    cover_url: str | None = None
    updated_at: str | None = None
    creator_user_id: str
    creator_name: str
    creator_avatar_url: str | None = None


class WebMusicPublicPlaylistListResponse(BaseModel):
    items: list[WebMusicPublicPlaylistResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 24
    offset: int = 0


class WebMusicPublicArtistListResponse(BaseModel):
    items: list[WebMusicPublicCreatorResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 48
    offset: int = 0


class WebMusicPublicArtistDetailResponse(WebMusicPublicCreatorResponse):
    playlists: list[WebMusicPublicPlaylistResponse] = Field(default_factory=list)
    albums: list[WebMusicPublicStreamingAlbumResponse] = Field(default_factory=list)


class WebMusicPublicRecentTrackResponse(BaseModel):
    id: str
    task_id: str
    variant: str = "ok"
    title: str
    artist_name: str
    user_id: str
    playlist_name: str = ""
    style: str = ""
    genre: str | None = None
    cover_url: str | None = None
    play_url: str
    added_at: str | None = None
    play_count: int = 0


class WebMusicPublicRecentTrackListResponse(BaseModel):
    items: list[WebMusicPublicRecentTrackResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 12
    offset: int = 0


class WebMusicPlaylistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_public: bool = False


class WebMusicPlaylistUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_public: bool | None = None


class WebMusicPlaylistItemResponse(BaseModel):
    id: str
    task_id: str
    variant: str
    position: int
    title: str
    style: str = ""
    status: str = ""
    ready: bool = False
    package_status: str = "none"
    audio_url: str = ""
    image_url: str | None = None
    added_at: str | None = None


class WebMusicPlaylistItemListResponse(BaseModel):
    items: list[WebMusicPlaylistItemResponse] = Field(default_factory=list)


class WebMusicPlaylistMembershipResponse(BaseModel):
    playlist_id: str
    playlist_name: str
    task_id: str
    variant: str


class WebMusicPlaylistMembershipListResponse(BaseModel):
    items: list[WebMusicPlaylistMembershipResponse] = Field(default_factory=list)


class WebMusicPlaylistAddItemRequest(BaseModel):
    task_id: UUID
    variant: Literal["ok", "alt"] = "ok"


class WebMusicGenerateResponse(BaseModel):
    task_id: str
    status: str
    title: str
    style: str
    quota: WebMusicQuotaResponse


class WebMusicGenerationResponse(BaseModel):
    id: str
    title: str
    lyrics: str = ""
    style: str = ""
    model: str = "V5"
    instrumental: bool = False
    status: str
    error_message: str | None = None
    created_at: str | None = None
    negative_tags: str | None = None
    vocal_gender: str | None = None
    style_weight: float | None = None
    weirdness_constraint: float | None = None
    audio_weight: float | None = None
    clips: list[WebMusicClipResponse] = Field(default_factory=list)


class WebMusicGenerationListResponse(BaseModel):
    items: list[WebMusicGenerationResponse]
    total: int
    limit: int
    offset: int


def _generation_response(payload: dict) -> WebMusicGenerationResponse:
    created = payload.get("created_at")
    created_text = created.isoformat() if hasattr(created, "isoformat") else (str(created) if created else None)
    return WebMusicGenerationResponse(
        id=str(payload["id"]),
        title=str(payload.get("title") or "Untitled"),
        lyrics=str(payload.get("lyrics") or ""),
        style=str(payload.get("style") or ""),
        model=str(payload.get("model") or "V5"),
        instrumental=bool(payload.get("instrumental")),
        status=str(payload.get("status") or "PENDING"),
        error_message=payload.get("error_message"),
        created_at=created_text,
        negative_tags=payload.get("negative_tags") or None,
        vocal_gender=payload.get("vocal_gender") or None,
        style_weight=_optional_float(payload.get("style_weight")),
        weirdness_constraint=_optional_float(payload.get("weirdness_constraint")),
        audio_weight=_optional_float(payload.get("audio_weight")),
        clips=[WebMusicClipResponse(**clip) for clip in payload.get("clips") or []],
    )


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class WebMusicDraftRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)


class WebMusicDraftResponse(BaseModel):
    lyrics: str
    title: str


class WebMusicStyleRequest(BaseModel):
    style: str = Field(default="", max_length=1000)
    lyrics: str = Field(default="", max_length=5000)
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=5000)
    prompt: str = Field(default="", max_length=5000)


class WebMusicStyleResponse(BaseModel):
    style: str
    credits_charged: int = 0


class WebMusicWorkspaceResponse(BaseModel):
    id: str
    name: str
    is_default: bool = False
    created_at: str | None = None


class WebMusicWorkspaceListResponse(BaseModel):
    items: list[WebMusicWorkspaceResponse] = Field(default_factory=list)


class WebMusicWorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WebMusicWorkspaceUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@router.get("/workspaces", response_model=WebMusicWorkspaceListResponse)
async def list_workspaces(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicWorkspaceListResponse:
    items = await service.list_workspaces(UUID(ctx.user_id))
    return WebMusicWorkspaceListResponse(
        items=[WebMusicWorkspaceResponse(**item) for item in items],
    )


@router.post("/workspaces", response_model=WebMusicWorkspaceResponse, status_code=201)
async def create_workspace(
    body: WebMusicWorkspaceCreateRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicWorkspaceResponse:
    payload = await service.create_workspace(UUID(ctx.user_id), name=body.name)
    return WebMusicWorkspaceResponse(**payload)


@router.patch("/workspaces/{workspace_id}", response_model=WebMusicWorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    body: WebMusicWorkspaceUpdateRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicWorkspaceResponse:
    payload = await service.update_workspace(
        UUID(ctx.user_id),
        workspace_id,
        name=body.name,
    )
    return WebMusicWorkspaceResponse(**payload)


@router.get("/quota", response_model=WebMusicQuotaResponse)
async def get_quota(ctx: CurrentUserDep, service: WebMusicServiceDep) -> WebMusicQuotaResponse:
    return WebMusicQuotaResponse(**await service.usage_today(UUID(ctx.user_id)))


@router.post("/generate-draft", response_model=WebMusicDraftResponse)
async def generate_draft(
    body: WebMusicDraftRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicDraftResponse:
    logger.info(
        "web-music /generate-draft called user=%s prompt_len=%s",
        ctx.user_id,
        len(body.prompt or ""),
    )
    await enforce_generation_freeze(http_request, ctx.user_id)
    await reject_probe_payload(http_request, ctx.user_id, body.prompt)
    await enforce_rate_limit(http_request, ctx.user_id)
    try:
        lyrics, title = await service.generate_draft(UUID(ctx.user_id), body.prompt)
    except Exception:
        logger.exception(
            "web-music /generate-draft failed user=%s prompt_len=%s",
            ctx.user_id,
            len(body.prompt or ""),
        )
        raise
    return WebMusicDraftResponse(lyrics=lyrics, title=title)


@router.post("/generate-styles", response_model=WebMusicStyleResponse)
async def generate_styles(
    body: WebMusicStyleRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicStyleResponse:
    logger.info(
        "web-music /generate-styles called user=%s style_len=%s lyrics_len=%s title_len=%s desc_len=%s prompt_len=%s",
        ctx.user_id,
        len(body.style or ""),
        len(body.lyrics or ""),
        len(body.title or ""),
        len(body.description or ""),
        len(body.prompt or ""),
    )
    await enforce_generation_freeze(http_request, ctx.user_id)
    await reject_probe_payload(
        http_request,
        ctx.user_id,
        body.style,
        body.lyrics,
        body.title,
        body.description,
        body.prompt,
    )
    await enforce_rate_limit(http_request, ctx.user_id)
    try:
        style = await service.generate_styles(
            UUID(ctx.user_id),
            style=body.style,
            lyrics=body.lyrics,
            title=body.title,
            description=body.description,
            prompt=body.prompt,
        )
    except Exception:
        logger.exception(
            "web-music /generate-styles failed user=%s style_len=%s lyrics_len=%s title_len=%s",
            ctx.user_id,
            len(body.style or ""),
            len(body.lyrics or ""),
            len(body.title or ""),
        )
        raise
    return WebMusicStyleResponse(style=style)


@router.post("/generate", response_model=WebMusicGenerateResponse, status_code=202)
async def generate(
    body: WebMusicGenerateRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicGenerateResponse:
    await enforce_generation_freeze(http_request, ctx.user_id)
    await reject_probe_payload(
        http_request,
        ctx.user_id,
        body.lyrics,
        body.style,
        body.title,
        body.prompt,
        body.negative_tags,
    )
    await enforce_rate_limit(http_request, ctx.user_id)
    await track_generation_attempt(http_request, ctx.user_id)
    
    try:
        payload = await service.generate(
            UUID(ctx.user_id),
            mode=body.mode,
            lyrics=body.lyrics,
            style=body.style,
            title=body.title,
            instrumental=body.instrumental,
            model=body.model,
            prompt=body.prompt,
            negative_tags=body.negative_tags,
            vocal_gender=body.vocal_gender,
            style_weight=body.style_weight,
            weirdness_constraint=body.weirdness_constraint,
            audio_weight=body.audio_weight,
            workspace_id=body.workspace_id,
        )
    except QuotaExceededError as exc:
        # Track quota exceeded for abuse detection
        await track_quota_exceeded(http_request, ctx.user_id)
        raise
    
    return WebMusicGenerateResponse(
        task_id=str(payload["task_id"]),
        status=str(payload["status"]),
        title=str(payload["title"]),
        style=str(payload["style"]),
        quota=WebMusicQuotaResponse(**payload["quota"]),
    )


class WebMusicGenerationUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    variant: Literal["ok", "alt"] | None = None


@router.get("/generations", response_model=WebMusicGenerationListResponse)
async def list_generations(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
    workspace_id: UUID | None = None,
) -> WebMusicGenerationListResponse:
    payload = await service.list_generations(
        UUID(ctx.user_id),
        limit=limit,
        offset=offset,
        workspace_id=workspace_id,
    )
    return WebMusicGenerationListResponse(
        items=[_generation_response(item) for item in payload["items"]],
        total=int(payload["total"]),
        limit=int(payload["limit"]),
        offset=int(payload["offset"]),
    )


@router.get("/generations/{task_id}", response_model=WebMusicGenerationResponse)
async def get_generation(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicGenerationResponse:
    payload = await service.get_generation(UUID(ctx.user_id), task_id)
    return _generation_response(payload)


@router.patch("/generations/{task_id}", response_model=WebMusicGenerationResponse)
async def update_generation(
    task_id: UUID,
    body: WebMusicGenerationUpdateRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicGenerationResponse:
    payload = await service.update_generation_title(
        UUID(ctx.user_id),
        task_id,
        title=body.title,
        variant=body.variant,
    )
    return _generation_response(payload)


@router.get("/generations/{task_id}/download")
async def download_generation(
    task_id: UUID,
    request: Request,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
) -> Response:
    await enforce_rate_limit_for_endpoint(ctx.user_id, "web_music_download")
    data, filename, content_type = await service.download_mp3(
        UUID(ctx.user_id), task_id, variant=variant
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": content_disposition(filename, inline=False),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/generations/{task_id}/download-wav")
async def download_generation_wav(
    task_id: UUID,
    request: Request,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
) -> Response:
    await enforce_rate_limit_for_endpoint(ctx.user_id, "web_music_download")
    data, filename, content_type = await service.download_wav(
        UUID(ctx.user_id), task_id, variant=variant
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": content_disposition(filename, inline=False),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/generations/{task_id}/timed-lyrics")
async def download_timed_lyrics(
    task_id: UUID,
    request: Request,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
    format: Literal["lrc", "srt"] = Query(default="lrc", alias="format"),
) -> Response:
    await enforce_rate_limit_for_endpoint(ctx.user_id, "web_music_download")
    data, filename, content_type = await service.download_timed_lyrics(
        UUID(ctx.user_id),
        task_id,
        variant=variant,
        lyric_format=format,
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": content_disposition(filename, inline=False),
            "Cache-Control": "private, no-store",
        },
    )


async def _enforce_stream_rate_limit(user_id: str, range_header: str | None) -> None:
    if is_missing_range(range_header):
        await enforce_rate_limit_for_endpoint(user_id, "web_music_download")
    await enforce_rate_limit_for_endpoint(user_id, "web_music_play")


@router.get("/generations/{task_id}/stream/{variant}")
async def stream_generation_variant(
    task_id: UUID,
    variant: Literal["ok", "alt"],
    request: Request,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> Response:
    range_header = request.headers.get("range")
    await _enforce_stream_rate_limit(ctx.user_id, range_header)
    return await service.proxy_playback(
        UUID(ctx.user_id),
        task_id,
        variant=variant,
        range_header=range_header,
        request_headers=request.headers,
    )


@router.get("/generations/{task_id}/stream")
async def stream_generation(
    task_id: UUID,
    request: Request,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
) -> Response:
    range_header = request.headers.get("range")
    await _enforce_stream_rate_limit(ctx.user_id, range_header)
    return await service.proxy_playback(
        UUID(ctx.user_id),
        task_id,
        variant=variant,
        range_header=range_header,
        request_headers=request.headers,
    )


@router.get("/play/{token}")
async def play_by_token(
    token: str,
    request: Request,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> Response:
    range_header = request.headers.get("range")
    await _enforce_stream_rate_limit(ctx.user_id, range_header)
    return await service.proxy_playback_from_token(
        token,
        session_user_id=ctx.user_id,
        range_header=range_header,
        request_headers=request.headers,
    )


@router.get("/public/tracks/recent", response_model=WebMusicPublicRecentTrackListResponse)
async def list_public_recent_tracks(
    service: WebMusicServiceDep,
    limit: int = Query(default=12, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> WebMusicPublicRecentTrackListResponse:
    page = await service.list_public_recent_tracks(limit=limit, offset=offset)
    return WebMusicPublicRecentTrackListResponse(
        items=[WebMusicPublicRecentTrackResponse(**item) for item in page["items"]],
        total=int(page["total"]),
        limit=int(page["limit"]),
        offset=int(page["offset"]),
    )


@router.get("/public/playlists", response_model=WebMusicPublicPlaylistListResponse)
async def list_public_playlists(
    service: WebMusicServiceDep,
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> WebMusicPublicPlaylistListResponse:
    page = await service.list_public_playlists(limit=limit, offset=offset)
    return WebMusicPublicPlaylistListResponse(
        items=[WebMusicPublicPlaylistResponse(**item) for item in page["items"]],
        total=int(page["total"]),
        limit=int(page["limit"]),
        offset=int(page["offset"]),
    )


@router.get("/public/artists", response_model=WebMusicPublicArtistListResponse)
async def list_public_artists(
    service: WebMusicServiceDep,
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> WebMusicPublicArtistListResponse:
    page = await service.list_public_artists(limit=limit, offset=offset)
    return WebMusicPublicArtistListResponse(
        items=[WebMusicPublicCreatorResponse(**item) for item in page["items"]],
        total=int(page["total"]),
        limit=int(page["limit"]),
        offset=int(page["offset"]),
    )


@router.get("/public/artists/{user_id}", response_model=WebMusicPublicArtistDetailResponse)
async def get_public_artist(
    user_id: UUID,
    service: WebMusicServiceDep,
) -> WebMusicPublicArtistDetailResponse:
    artist = await service.get_public_artist(user_id)
    if artist is None:
        raise NotFoundError("Artist not found.")
    playlists = [WebMusicPublicPlaylistResponse(**item) for item in artist.get("playlists") or []]
    albums = [WebMusicPublicStreamingAlbumResponse(**item) for item in artist.get("albums") or []]
    return WebMusicPublicArtistDetailResponse(
        user_id=str(artist["user_id"]),
        artist_name=str(artist["artist_name"]),
        avatar_url=artist.get("avatar_url"),
        playlist_count=int(artist.get("playlist_count") or 0),
        album_count=int(artist.get("album_count") or 0),
        track_count=int(artist.get("track_count") or 0),
        playlists=playlists,
        albums=albums,
    )


@router.get("/playlists", response_model=WebMusicPlaylistListResponse)
async def list_playlists(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicPlaylistListResponse:
    items = await service.list_playlists(UUID(ctx.user_id))
    return WebMusicPlaylistListResponse(items=[WebMusicPlaylistResponse(**item) for item in items])


@router.get("/playlists/memberships", response_model=WebMusicPlaylistMembershipListResponse)
async def list_playlist_memberships(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicPlaylistMembershipListResponse:
    items = await service.list_playlist_memberships(UUID(ctx.user_id))
    return WebMusicPlaylistMembershipListResponse(
        items=[WebMusicPlaylistMembershipResponse(**item) for item in items]
    )


@router.post("/playlists", response_model=WebMusicPlaylistResponse, status_code=201)
async def create_playlist(
    body: WebMusicPlaylistCreateRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicPlaylistResponse:
    item = await service.create_playlist(
        UUID(ctx.user_id),
        name=body.name,
        description=body.description,
        is_public=body.is_public,
    )
    return WebMusicPlaylistResponse(**item)


@router.get("/playlists/{playlist_id}", response_model=WebMusicPlaylistResponse)
async def get_playlist(
    playlist_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicPlaylistResponse:
    item = await service.get_playlist(UUID(ctx.user_id), playlist_id, allow_public=True)
    return WebMusicPlaylistResponse(**item)


@router.patch("/playlists/{playlist_id}", response_model=WebMusicPlaylistResponse)
async def update_playlist(
    playlist_id: UUID,
    body: WebMusicPlaylistUpdateRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicPlaylistResponse:
    item = await service.update_playlist(
        UUID(ctx.user_id),
        playlist_id,
        name=body.name,
        description=body.description,
        is_public=body.is_public,
    )
    return WebMusicPlaylistResponse(**item)


@router.delete("/playlists/{playlist_id}", status_code=204)
async def delete_playlist(
    playlist_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> Response:
    await service.delete_playlist(UUID(ctx.user_id), playlist_id)
    return Response(status_code=204)


@router.get("/playlists/{playlist_id}/items", response_model=WebMusicPlaylistItemListResponse)
async def list_playlist_items(
    playlist_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicPlaylistItemListResponse:
    items = await service.list_playlist_items(UUID(ctx.user_id), playlist_id, allow_public=True)
    return WebMusicPlaylistItemListResponse(items=[WebMusicPlaylistItemResponse(**item) for item in items])


@router.post("/playlists/{playlist_id}/items", response_model=WebMusicPlaylistItemResponse, status_code=201)
async def add_playlist_item(
    playlist_id: UUID,
    body: WebMusicPlaylistAddItemRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicPlaylistItemResponse:
    item = await service.add_playlist_item(
        UUID(ctx.user_id),
        playlist_id,
        task_id=body.task_id,
        variant=body.variant,
    )
    return WebMusicPlaylistItemResponse(**item)


@router.delete("/playlists/{playlist_id}/items/{item_id}", status_code=204)
async def remove_playlist_item(
    playlist_id: UUID,
    item_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> Response:
    await service.remove_playlist_item(UUID(ctx.user_id), playlist_id, item_id=item_id)
    return Response(status_code=204)


class WebMusicLikeIdsResponse(BaseModel):
    keys: list[str] = Field(default_factory=list)


class WebMusicLikeMutationResponse(BaseModel):
    ok: bool = True
    liked: bool
    created: bool | None = None
    removed: bool | None = None


@router.get("/likes/keys", response_model=WebMusicLikeIdsResponse)
async def list_web_music_like_keys(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicLikeIdsResponse:
    keys = await service.list_liked_generation_keys(UUID(ctx.user_id))
    return WebMusicLikeIdsResponse(keys=keys)


@router.put(
    "/generations/{task_id}/like",
    response_model=WebMusicLikeMutationResponse,
)
async def like_web_music_generation(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
) -> WebMusicLikeMutationResponse:
    created = await service.like_generation(
        UUID(ctx.user_id),
        task_id,
        variant=variant,
    )
    return WebMusicLikeMutationResponse(ok=True, liked=True, created=created)


@router.delete(
    "/generations/{task_id}/like",
    response_model=WebMusicLikeMutationResponse,
)
async def unlike_web_music_generation(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
) -> WebMusicLikeMutationResponse:
    removed = await service.unlike_generation(
        UUID(ctx.user_id),
        task_id,
        variant=variant,
    )
    return WebMusicLikeMutationResponse(ok=True, liked=False, removed=removed)
