"""Authenticated music-web generation API (no desktop license / channel profile)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from platform_api.ai.registry import DEFAULT_SUNO_MUSIC_MODEL, SUNO_MODEL_PATTERN
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.middleware.rate_limit import enforce_rate_limit, enforce_rate_limit_for_endpoint
from platform_api.middleware.abuse_detection import track_generation_attempt, track_quota_exceeded
from platform_api.services.generation_freeze import (
    enforce_generation_freeze,
    reject_probe_payload,
)
from platform_api.services.web_music_service import WebMusicService, content_disposition
from platform_api.services.audio_origin_proxy import is_missing_range
from platform_api.exceptions import NotFoundError, QuotaExceededError, ValidationError

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
    # Suno V6 customMode lyrics cap (V5 series also accepts 5000).
    prompt: str = Field(default="", max_length=5000)
    instrumental: bool = False
    model: str = Field(default=DEFAULT_SUNO_MUSIC_MODEL, pattern=SUNO_MODEL_PATTERN)
    negative_tags: str | None = Field(default=None, max_length=1000)
    vocal_gender: Literal["m", "f", "both", ""] | None = None
    style_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    weirdness_constraint: float | None = Field(default=None, ge=0.0, le=1.0)
    audio_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    image_urls: list[str] = Field(default_factory=list, max_length=4)
    video_urls: list[str] = Field(default_factory=list, max_length=1)
    persona_id: str | None = Field(default=None, max_length=128)
    workspace_id: UUID | None = None


class TrashClipsRequest(BaseModel):
    trash: bool
    clip_ids: list[str] = Field(default_factory=list, max_length=200)


class ReportClipRequest(BaseModel):
    variant: Literal["ok", "alt"] = "ok"
    reason: Literal["copyright", "explicit", "spam", "harassment", "other"]
    details: str | None = Field(default=None, max_length=1000)


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
    is_preview: bool = False
    preview_seconds: int | None = None


class WebMusicPreviewModelResponse(BaseModel):
    model: str
    label: str
    limit: int = 1
    used: int = 0
    remaining: int = 0
    seconds: int = 60


class WebMusicPreviewsResponse(BaseModel):
    eligible: bool = False
    seconds: int = 60
    models: list[WebMusicPreviewModelResponse] = Field(default_factory=list)


class WebMusicQuotaResponse(BaseModel):
    limit: int
    used: int
    remaining: int
    is_pro: bool = False
    requires_upgrade: bool = False
    can_download: bool = False
    has_subscription: bool = False
    credits_remaining: int = 0
    credits_per_song: int = 10
    premium_unlocked: bool = False
    free_model: str = "V6-MINI"
    queue_limit: int = 2
    queue_used: int = 0
    previews: WebMusicPreviewsResponse | None = None


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
    model: str = DEFAULT_SUNO_MUSIC_MODEL
    model_label: str = "V6 Pro"
    is_preview: bool = False
    preview_seconds: int | None = None
    quota: WebMusicQuotaResponse


class WebMusicGenerationResponse(BaseModel):
    id: str
    title: str
    lyrics: str = ""
    style: str = ""
    model: str = "V5"
    model_label: str = "V6 Pro"
    instrumental: bool = False
    status: str
    error_message: str | None = None
    created_at: str | None = None
    is_preview: bool = False
    unlockable: bool = False
    preview_seconds: int | None = None
    negative_tags: str | None = None
    vocal_gender: str | None = None
    style_weight: float | None = None
    weirdness_constraint: float | None = None
    audio_weight: float | None = None
    trashed_variants: list[str] = Field(default_factory=list)
    purged_variants: list[str] = Field(default_factory=list)
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
        model_label=str(payload.get("model_label") or payload.get("model") or "V5"),
        instrumental=bool(payload.get("instrumental")),
        status=str(payload.get("status") or "PENDING"),
        error_message=payload.get("error_message"),
        created_at=created_text,
        is_preview=bool(payload.get("is_preview")),
        unlockable=bool(payload.get("unlockable")),
        preview_seconds=(
            int(payload["preview_seconds"])
            if payload.get("preview_seconds") is not None
            else None
        ),
        negative_tags=payload.get("negative_tags") or None,
        vocal_gender=payload.get("vocal_gender") or None,
        style_weight=_optional_float(payload.get("style_weight")),
        weirdness_constraint=_optional_float(payload.get("weirdness_constraint")),
        audio_weight=_optional_float(payload.get("audio_weight")),
        trashed_variants=[
            str(value) for value in (payload.get("trashed_variants") or [])
        ],
        purged_variants=[
            str(value) for value in (payload.get("purged_variants") or [])
        ],
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


class StudioProjectCreateRequest(BaseModel):
    title: str = Field(default="Untitled Project", min_length=1, max_length=120)
    major_version: int = Field(default=2, ge=1, le=10)
    bpm: int = Field(default=120, ge=20, le=300)
    time_signature: str = Field(default="4/4", pattern=r"^\d{1,2}/\d{1,2}$")
    data: dict[str, object] = Field(default_factory=dict)


class StudioProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    major_version: int | None = Field(default=None, ge=1, le=10)
    bpm: int | None = Field(default=None, ge=20, le=300)
    time_signature: str | None = Field(default=None, pattern=r"^\d{1,2}/\d{1,2}$")
    data: dict[str, object] | None = None
    pinned: bool | None = None
    archived: bool | None = None
    tags: list[str] | None = None
    expected_updated_at: datetime | None = None


class StudioProjectForkRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)


@router.get("/studio/projects")
async def list_studio_projects(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_archived: bool = Query(False),
) -> dict:
    return await service.list_studio_projects(
        UUID(ctx.user_id),
        limit=limit,
        offset=offset,
        include_archived=include_archived,
    )


@router.post("/studio/projects", status_code=201)
async def create_studio_project(
    body: StudioProjectCreateRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.create_studio_project(
        UUID(ctx.user_id),
        title=body.title,
        major_version=body.major_version,
        bpm=body.bpm,
        time_signature=body.time_signature,
        data=body.data,
    )


@router.get("/studio/projects/{project_id}")
async def get_studio_project(
    project_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.get_studio_project(UUID(ctx.user_id), project_id)


@router.patch("/studio/projects/{project_id}")
async def update_studio_project(
    project_id: UUID,
    body: StudioProjectUpdateRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.update_studio_project(
        UUID(ctx.user_id),
        project_id,
        title=body.title,
        major_version=body.major_version,
        bpm=body.bpm,
        time_signature=body.time_signature,
        data=body.data,
        pinned=body.pinned,
        archived=body.archived,
        tags=body.tags,
    )


@router.delete("/studio/projects/{project_id}", status_code=204)
async def delete_studio_project(
    project_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> Response:
    await service.delete_studio_project(UUID(ctx.user_id), project_id)
    return Response(status_code=204)


@router.post("/studio/projects/{project_id}/fork", status_code=201)
async def fork_studio_project(
    project_id: UUID,
    body: StudioProjectForkRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.fork_studio_project(
        UUID(ctx.user_id),
        project_id,
        title=body.title,
    )


class StudioVersionCreateRequest(BaseModel):
    label: str | None = Field(default=None, max_length=120)


@router.get("/studio/projects/{project_id}/versions")
async def list_studio_project_versions(
    project_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    limit: int = Query(30, ge=1, le=100),
) -> dict:
    return await service.list_studio_project_versions(
        UUID(ctx.user_id),
        project_id,
        limit=limit,
    )


@router.post("/studio/projects/{project_id}/versions", status_code=201)
async def create_studio_project_version(
    project_id: UUID,
    body: StudioVersionCreateRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.create_studio_project_version(
        UUID(ctx.user_id),
        project_id,
        label=body.label,
    )


@router.post("/studio/projects/{project_id}/versions/{version_id}/restore")
async def restore_studio_project_version(
    project_id: UUID,
    version_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.restore_studio_project_version(
        UUID(ctx.user_id),
        project_id,
        version_id,
    )


class StudioShareCreateRequest(BaseModel):
    expires_days: int = Field(default=7, ge=1, le=90)
    permission: Literal["view", "edit"] = "view"


@router.post("/studio/projects/{project_id}/shares", status_code=201)
async def create_studio_project_share(
    project_id: UUID,
    body: StudioShareCreateRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.create_studio_project_share(
        UUID(ctx.user_id),
        project_id,
        expires_days=body.expires_days,
        permission=body.permission,
    )


class StudioPresenceRequest(BaseModel):
    display_name: str = Field(default="Collaborator", max_length=80)
    playhead_seconds: float | None = None
    selected_lane_id: str | None = Field(default=None, max_length=120)


@router.post("/studio/shares/{token}/presence")
async def touch_studio_shared_presence(
    token: str,
    body: StudioPresenceRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.touch_studio_shared_presence(
        token,
        UUID(ctx.user_id),
        display_name=body.display_name,
        playhead_seconds=body.playhead_seconds,
        selected_lane_id=body.selected_lane_id,
    )


class StudioCommentCreateRequest(BaseModel):
    author_name: str = Field(default="Guest", max_length=80)
    body: str = Field(min_length=1, max_length=2000)
    parent_id: UUID | None = None


@router.get("/studio/projects/{project_id}/comments")
async def list_studio_project_comments(
    project_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    limit: int = Query(100, ge=1, le=100),
) -> dict:
    return await service.list_studio_project_comments(
        UUID(ctx.user_id),
        project_id,
        limit=limit,
    )


@router.post("/studio/shares/{token}/fork", status_code=201)
async def fork_studio_shared_project(
    token: str,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.fork_studio_shared_project(UUID(ctx.user_id), token)


@router.get("/studio/shares/{token}/comments")
async def list_studio_share_comments(
    token: str,
    service: WebMusicServiceDep,
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    return await service.list_studio_share_comments(token, limit=limit)


@router.get("/studio/shares/{token}/updates")
async def wait_studio_share_update(
    token: str,
    service: WebMusicServiceDep,
    since: datetime | None = Query(None),
    timeout: int = Query(20, ge=1, le=25),
) -> dict:
    return await service.wait_studio_share_update(
        token,
        since=since,
        timeout_seconds=timeout,
    )


@router.post("/studio/shares/{token}/comments", status_code=201)
async def add_studio_share_comment(
    token: str,
    body: StudioCommentCreateRequest,
    service: WebMusicServiceDep,
) -> dict:
    return await service.add_studio_share_comment(
        token,
        author_name=body.author_name,
        body=body.body,
        parent_id=body.parent_id,
    )


@router.get("/studio/projects/{project_id}/shares")
async def list_studio_project_shares(
    project_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.list_studio_project_shares(
        UUID(ctx.user_id),
        project_id,
    )


@router.delete("/studio/projects/{project_id}/shares/{share_id}", status_code=204)
async def revoke_studio_project_share(
    project_id: UUID,
    share_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> Response:
    await service.revoke_studio_project_share(
        UUID(ctx.user_id),
        project_id,
        share_id,
    )
    return Response(status_code=204)


@router.patch("/studio/shares/{token}")
async def update_studio_shared_project(
    token: str,
    body: StudioProjectUpdateRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.update_studio_shared_project(
        token,
        UUID(ctx.user_id),
        title=body.title,
        bpm=body.bpm,
        time_signature=body.time_signature,
        data=body.data,
        expected_updated_at=body.expected_updated_at,
    )


@router.get("/studio/shares/{token}")
async def get_studio_shared_project(
    token: str,
    service: WebMusicServiceDep,
) -> dict:
    return await service.get_studio_shared_project(token)


class StudioStemsRequest(BaseModel):
    variant: Literal["ok", "alt"] = "ok"
    mode: Literal["vocal", "stems", "advanced"] = "vocal"
    project_id: UUID | None = None


@router.post("/studio/generations/{task_id}/stems", status_code=202)
async def request_studio_stems(
    task_id: UUID,
    body: StudioStemsRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_stems(
        UUID(ctx.user_id),
        task_id,
        variant=body.variant,
        mode=body.mode,
        project_id=body.project_id,
    )


class StudioExtendRequest(BaseModel):
    variant: Literal["ok", "alt"] = "ok"
    continue_at: float | None = None
    project_id: UUID | None = None


class StudioCoverRequest(BaseModel):
    variant: Literal["ok", "alt"] = "ok"
    prompt: str = ""
    project_id: UUID | None = None


class StudioPromptRequest(BaseModel):
    variant: Literal["ok", "alt"] = "ok"
    prompt: str
    project_id: UUID | None = None


class StudioUploadExtendRequest(BaseModel):
    prompt: str = ""
    continue_at: float | None = None
    title: str = ""
    tags: str = ""
    project_id: UUID | None = None


class StudioUploadCoverRequest(BaseModel):
    prompt: str = ""
    cover_start_s: float | None = None
    cover_end_s: float | None = None
    title: str = ""
    tags: str = ""
    project_id: UUID | None = None


class StudioCoverImageRequest(BaseModel):
    variant: Literal["ok", "alt"] = "ok"
    prompt: str
    project_id: UUID | None = None


class StudioMashupRequest(BaseModel):
    task_ids: list[UUID] = Field(min_length=2, max_length=4)
    variants: list[Literal["ok", "alt"]] = Field(min_length=2, max_length=4)
    prompt: str = ""
    project_id: UUID | None = None


class StudioRemasterRequest(BaseModel):
    variant: Literal["ok", "alt"] = "ok"
    model: str | None = None
    project_id: UUID | None = None


class StudioPersonaRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    styles: str = ""
    description: str = ""
    vocal_start_s: float | None = None
    vocal_end_s: float | None = None
    variant: Literal["ok", "alt"] = "ok"


class StudioReplaceSectionRequest(BaseModel):
    variant: Literal["ok", "alt"] = "ok"
    start_s: float
    end_s: float
    lyrics: str
    prompt: str = ""
    model: str | None = None
    persona_id: str | None = None
    project_id: UUID | None = None


class StudioLyricsSaveRequest(BaseModel):
    title: str = Field(default="", max_length=120)
    content: str = Field(min_length=1, max_length=5000)
    id: UUID | None = None


class StudioVoicePersonaRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    styles: str = ""
    voice_id: str = Field(min_length=1, max_length=200)


class StudioVideoRequest(BaseModel):
    task_id: UUID
    variant: Literal["ok", "alt"] = "ok"
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    # Optional user clip used instead of the song's cover art.
    background_video_url: str | None = Field(default=None, max_length=2048)
    project_id: UUID | None = None


class StaffPickRemixRequest(BaseModel):
    prompt: str = Field(default="", max_length=2000)


class OperationRemixRequest(BaseModel):
    prompt: str = Field(default="", max_length=2000)
    clip_id: str | None = Field(default=None, max_length=200)


@router.post("/studio/generations/{task_id}/extend", status_code=202)
async def request_studio_extend(
    task_id: UUID,
    body: StudioExtendRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_extend(
        UUID(ctx.user_id),
        task_id,
        variant=body.variant,
        continue_at=body.continue_at,
        project_id=body.project_id,
    )


@router.post("/studio/generations/{task_id}/cover", status_code=202)
async def request_studio_cover(
    task_id: UUID,
    body: StudioCoverRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_cover(
        UUID(ctx.user_id),
        task_id,
        variant=body.variant,
        prompt=body.prompt,
        project_id=body.project_id,
    )


@router.post("/studio/generations/{task_id}/add-vocals", status_code=202)
async def request_studio_add_vocals(
    task_id: UUID,
    body: StudioPromptRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_add_vocals(
        UUID(ctx.user_id),
        task_id,
        variant=body.variant,
        prompt=body.prompt,
        project_id=body.project_id,
    )


@router.post("/studio/generations/{task_id}/add-instrumental", status_code=202)
async def request_studio_add_instrumental(
    task_id: UUID,
    body: StudioPromptRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_add_instrumental(
        UUID(ctx.user_id),
        task_id,
        variant=body.variant,
        prompt=body.prompt,
        project_id=body.project_id,
    )


@router.get("/studio/generations/{task_id}/lyrics")
async def get_studio_lyrics(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
) -> dict:
    return await service.get_studio_lyrics(
        UUID(ctx.user_id),
        task_id,
        variant=variant,
    )


@router.post("/studio/generations/{task_id}/cover-image", status_code=202)
async def request_studio_cover_image(
    task_id: UUID,
    body: StudioCoverImageRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_cover_image(
        UUID(ctx.user_id),
        task_id,
        variant=body.variant,
        prompt=body.prompt,
        project_id=body.project_id,
    )


@router.post("/studio/videos", status_code=202)
async def create_studio_video(
    body: StudioVideoRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.create_studio_video(
        UUID(ctx.user_id),
        body.task_id,
        variant=body.variant,
        aspect_ratio=body.aspect_ratio,
        background_video_url=body.background_video_url,
        project_id=body.project_id,
    )


@router.post("/studio/uploads/{upload_id}/extend", status_code=202)
async def request_studio_upload_extend(
    upload_id: UUID,
    body: StudioUploadExtendRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_upload_extend(
        UUID(ctx.user_id),
        upload_id,
        prompt=body.prompt,
        continue_at=body.continue_at,
        title=body.title,
        tags=body.tags,
        project_id=body.project_id,
    )


@router.post("/studio/uploads/{upload_id}/cover", status_code=202)
async def request_studio_upload_cover(
    upload_id: UUID,
    body: StudioUploadCoverRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_upload_cover(
        UUID(ctx.user_id),
        upload_id,
        prompt=body.prompt,
        cover_start_s=body.cover_start_s,
        cover_end_s=body.cover_end_s,
        title=body.title,
        tags=body.tags,
        project_id=body.project_id,
    )


@router.post("/studio/mashup", status_code=202)
async def request_studio_mashup(
    body: StudioMashupRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_mashup(
        UUID(ctx.user_id),
        body.task_ids,
        variants=list(body.variants),
        prompt=body.prompt,
        project_id=body.project_id,
    )


@router.post("/studio/generations/{task_id}/remaster", status_code=202)
async def request_studio_remaster(
    task_id: UUID,
    body: StudioRemasterRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_remaster(
        UUID(ctx.user_id),
        task_id,
        variant=body.variant,
        model=body.model,
        project_id=body.project_id,
    )


@router.post("/studio/generations/{task_id}/replace-section", status_code=202)
async def request_studio_replace_section(
    task_id: UUID,
    body: StudioReplaceSectionRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_studio_replace_section(
        UUID(ctx.user_id),
        task_id,
        variant=body.variant,
        start_s=body.start_s,
        end_s=body.end_s,
        lyrics=body.lyrics,
        prompt=body.prompt,
        model=body.model,
        persona_id=body.persona_id,
        project_id=body.project_id,
    )


@router.post("/studio/generations/{task_id}/personas", status_code=202)
async def create_studio_persona(
    task_id: UUID,
    body: StudioPersonaRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.create_studio_persona(
        UUID(ctx.user_id),
        task_id,
        name=body.name,
        styles=body.styles,
        description=body.description,
        vocal_start_s=body.vocal_start_s,
        vocal_end_s=body.vocal_end_s,
        variant=body.variant,
    )


@router.get("/studio/personas")
async def list_studio_personas(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> list[dict]:
    return await service.list_studio_personas(UUID(ctx.user_id))


@router.post("/studio/voice/samples", status_code=201)
async def create_voice_sample(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    file: UploadFile = File(...),
) -> dict:
    content_type = str(file.content_type or "").split(";")[0].strip().lower()
    if not content_type.startswith("audio/"):
        raise ValidationError("Only audio files can be used as voice samples.", details={"field": "file"})
    return await service.create_voice_sample(
        UUID(ctx.user_id),
        filename=file.filename or "voice-sample",
        content_type=content_type,
        data=await file.read(),
    )


@router.get("/studio/voice/phrase")
async def get_voice_phrase(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    _ = ctx
    return await service.get_voice_phrase()


@router.post("/studio/voice/verify")
async def verify_voice_sample(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    file: UploadFile = File(...),
    phrase_id: str = Form(...),
    source_voice_recording_id: str = Form(...),
) -> dict:
    content_type = str(file.content_type or "").split(";")[0].strip().lower()
    if not content_type.startswith("audio/"):
        raise ValidationError("Only audio recordings can be verified.", details={"field": "file"})
    return await service.verify_voice_sample(
        UUID(ctx.user_id),
        filename=file.filename or "voice-verification",
        content_type=content_type,
        data=await file.read(),
        phrase_id=phrase_id,
        source_voice_recording_id=source_voice_recording_id,
    )


@router.post("/studio/voice/personas", status_code=201)
async def create_voice_persona(
    body: StudioVoicePersonaRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.create_voice_persona(
        UUID(ctx.user_id),
        name=body.name,
        styles=body.styles,
        voice_id=body.voice_id,
    )


@router.get("/remix/staff-picks")
async def list_remix_staff_picks(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    _ = ctx
    return await service.list_staff_picks(active_only=True)


@router.post("/remix/staff-picks/{pick_id}", status_code=202)
async def request_staff_pick_remix(
    pick_id: UUID,
    body: StaffPickRemixRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_staff_pick_remix(
        UUID(ctx.user_id),
        pick_id,
        prompt=body.prompt,
    )


@router.get("/studio/lyrics")
async def list_saved_lyrics(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    return await service.list_saved_lyrics(UUID(ctx.user_id), limit=limit)


@router.post("/studio/lyrics", status_code=201)
async def save_saved_lyrics(
    body: StudioLyricsSaveRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.save_saved_lyrics(
        UUID(ctx.user_id),
        title=body.title,
        content=body.content,
        lyrics_id=body.id,
    )


@router.delete("/studio/lyrics/{lyrics_id}", status_code=204)
async def delete_saved_lyrics(
    lyrics_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> Response:
    await service.delete_saved_lyrics(UUID(ctx.user_id), lyrics_id)
    return Response(status_code=204)


@router.post("/studio/images", status_code=201)
async def upload_studio_image(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    file: UploadFile = File(...),
) -> dict:
    content_type = str(file.content_type or "").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        raise ValidationError(
            "Only image files can be attached.",
            details={"field": "file"},
        )
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise ValidationError(
            "Reference images are limited to 10 MB.",
            details={"field": "file"},
        )
    return await service.create_studio_image(
        UUID(ctx.user_id),
        filename=file.filename or "reference-image",
        content_type=content_type,
        data=data,
    )


@router.post("/studio/video-uploads", status_code=201)
async def upload_studio_video_file(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    file: UploadFile = File(...),
) -> dict:
    """Store the one reference clip the create composer can attach.

    Mirrors Suno's `+ → Video` picker, which accepts
    `video/mp4`, `video/quicktime`, and `video/webm`.
    """
    content_type = str(file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ("video/mp4", "video/quicktime", "video/webm"):
        raise ValidationError(
            "Attach an MP4, MOV, or WebM clip.",
            details={"field": "file"},
        )
    data = await file.read()
    if len(data) > 100 * 1024 * 1024:
        raise ValidationError(
            "Reference clips are limited to 100 MB.",
            details={"field": "file"},
        )
    return await service.create_studio_video_file(
        UUID(ctx.user_id),
        filename=file.filename or "reference-video",
        content_type=content_type,
        data=data,
    )


@router.post("/studio/uploads", status_code=201)
async def upload_studio_audio(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    file: UploadFile = File(...),
    duration_seconds: float | None = Form(default=None),
) -> dict:
    content_type = str(file.content_type or "").split(";")[0].strip().lower()
    if not content_type.startswith("audio/"):
        raise ValidationError(
            "Only audio files can be imported into Studio.",
            details={"field": "file"},
        )
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise ValidationError(
            "Studio audio uploads are limited to 50 MB.",
            details={"field": "file"},
        )
    return await service.create_studio_upload(
        UUID(ctx.user_id),
        filename=file.filename or "studio-audio",
        content_type=content_type,
        data=data,
        duration_seconds=duration_seconds,
    )


@router.get("/studio/uploads")
async def list_studio_uploads(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    return await service.list_studio_uploads(UUID(ctx.user_id), limit=limit)


@router.get("/studio/uploads/{upload_id}")
async def get_studio_audio(
    upload_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.get_studio_upload(UUID(ctx.user_id), upload_id)


@router.get("/studio/pricing")
async def get_studio_pricing(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.studio_operation_pricing(UUID(ctx.user_id))


@router.get("/studio/readiness")
async def get_studio_readiness(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.get_studio_readiness()


@router.get("/studio/operations")
async def list_studio_operations(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    limit: int = Query(20, ge=1, le=50),
    operation_type: str | None = Query(default=None),
) -> dict:
    return await service.list_studio_operations(
        UUID(ctx.user_id),
        limit=limit,
        operation_type=operation_type,
    )


@router.get("/studio/operations/{operation_id}")
async def get_studio_operation(
    operation_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.get_studio_operation(UUID(ctx.user_id), operation_id)


@router.post("/studio/operations/{operation_id}/remix", status_code=202)
async def request_operation_remix(
    operation_id: UUID,
    body: OperationRemixRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.request_operation_clip_remix(
        UUID(ctx.user_id),
        operation_id,
        clip_id=body.clip_id,
        prompt=body.prompt,
    )


@router.delete("/studio/operations/{operation_id}")
async def delete_studio_operation(
    operation_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    return await service.delete_studio_operation(UUID(ctx.user_id), operation_id)


@router.get("/studio/clips/{clip_id}/wav")
async def download_studio_clip_wav(
    clip_id: str,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> Response:
    await enforce_rate_limit_for_endpoint(ctx.user_id, "web_music_download")
    url = await service.get_operation_clip_wav_url(UUID(ctx.user_id), clip_id)
    return RedirectResponse(url, status_code=302)


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
    # Credit-funded users are gated by their balance, not the per-IP farm cap.
    credited = await service.has_generation_credits(UUID(ctx.user_id))
    await track_generation_attempt(
        http_request,
        ctx.user_id,
        credited=credited,
    )
    
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
            image_urls=body.image_urls,
            video_urls=body.video_urls,
            persona_id=body.persona_id,
            workspace_id=body.workspace_id,
        )
    except QuotaExceededError:
        # A paying user hitting a preview/plan limit is not farm abuse.
        if not credited:
            await track_quota_exceeded(http_request, ctx.user_id)
        raise
    
    return WebMusicGenerateResponse(
        task_id=str(payload["task_id"]),
        status=str(payload["status"]),
        title=str(payload["title"]),
        style=str(payload["style"]),
        model=str(payload.get("model") or DEFAULT_SUNO_MUSIC_MODEL),
        model_label=str(payload.get("model_label") or payload.get("model") or DEFAULT_SUNO_MUSIC_MODEL),
        is_preview=bool(payload.get("is_preview")),
        preview_seconds=(
            int(payload["preview_seconds"])
            if payload.get("preview_seconds") is not None
            else None
        ),
        quota=WebMusicQuotaResponse(**payload["quota"]),
    )


class WebMusicGenerationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    lyrics: str | None = Field(default=None, max_length=20000)
    variant: Literal["ok", "alt"] | None = None


@router.get("/generations", response_model=WebMusicGenerationListResponse)
async def list_generations(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
    workspace_id: UUID | None = None,
    trashed: bool = False,
) -> WebMusicGenerationListResponse:
    payload = await service.list_generations(
        UUID(ctx.user_id),
        limit=limit,
        offset=offset,
        workspace_id=workspace_id,
        trashed=trashed,
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


@router.get("/generations/{task_id}/radio")
async def song_radio(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    return await service.radio_station(UUID(ctx.user_id), task_id, limit=limit)


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
        lyrics=body.lyrics,
        variant=body.variant,
    )
    return _generation_response(payload)


@router.post(
    "/generations/{task_id}/unlock-preview",
    response_model=WebMusicGenerationResponse,
)
async def unlock_preview(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicGenerationResponse:
    try:
        payload = await service.unlock_preview(UUID(ctx.user_id), task_id)
    except ValidationError as exc:
        # Old previews created before private masters cannot be recovered.
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "preview_unlock_unavailable",
                    "message": exc.message,
                }
            },
        )
    return _generation_response(payload)


@router.post("/generations/{task_id}/report", status_code=201)
async def report_web_music_generation(
    task_id: UUID,
    body: ReportClipRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    await service.report_generation(
        UUID(ctx.user_id),
        task_id,
        variant=body.variant,
        reason=body.reason,
        details=body.details,
    )
    return {"ok": True}


@router.post("/generations/trash", status_code=200)
async def set_generations_trash(
    body: TrashClipsRequest,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    """Batch move/restore clips, mirroring Suno's `POST /api/gen/trash`."""
    updated = await service.set_trash(
        UUID(ctx.user_id), body.clip_ids, trashed=body.trash
    )
    return {"updated": updated}


@router.delete("/generations/{task_id}", status_code=204)
async def delete_generation(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    permanent: bool = Query(False),
    variant: Literal["ok", "alt"] | None = Query(None),
) -> Response:
    await service.delete_generation(
        UUID(ctx.user_id), task_id, variant=variant, permanent=permanent
    )
    return Response(status_code=204)


@router.post("/generations/{task_id}/restore", status_code=200)
async def restore_generation(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] | None = Query(None),
) -> dict:
    await service.restore_generation(UUID(ctx.user_id), task_id, variant=variant)
    return {"status": "restored"}


@router.delete("/trash", status_code=200)
async def empty_trash(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> dict:
    deleted = await service.empty_trash(UUID(ctx.user_id))
    return {"deleted": deleted}


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


@router.get("/dislikes/keys", response_model=WebMusicLikeIdsResponse)
async def list_web_music_dislike_keys(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicLikeIdsResponse:
    keys = await service.list_disliked_generation_keys(UUID(ctx.user_id))
    return WebMusicLikeIdsResponse(keys=keys)


@router.put(
    "/generations/{task_id}/dislike",
    response_model=WebMusicLikeMutationResponse,
)
async def dislike_web_music_generation(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
) -> WebMusicLikeMutationResponse:
    created = await service.dislike_generation(
        UUID(ctx.user_id),
        task_id,
        variant=variant,
    )
    return WebMusicLikeMutationResponse(ok=True, liked=False, created=created)


@router.delete(
    "/generations/{task_id}/dislike",
    response_model=WebMusicLikeMutationResponse,
)
async def undislike_web_music_generation(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
) -> WebMusicLikeMutationResponse:
    removed = await service.undislike_generation(
        UUID(ctx.user_id),
        task_id,
        variant=variant,
    )
    return WebMusicLikeMutationResponse(ok=True, liked=False, removed=removed)


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
