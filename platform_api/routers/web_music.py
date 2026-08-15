"""Authenticated music-web generation API (no desktop license / channel profile)."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.middleware.rate_limit import enforce_rate_limit
from platform_api.middleware.abuse_detection import track_generation_attempt, track_quota_exceeded
from platform_api.services.web_music_service import WebMusicService, content_disposition
from platform_api.exceptions import QuotaExceededError

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
    prompt: str = Field(default="", max_length=500)
    instrumental: bool = False
    model: str = Field(default="V5", pattern=r"^(V5|V5_5)$")
    negative_tags: str | None = Field(default=None, max_length=500)
    vocal_gender: Literal["m", "f"] | None = None
    style_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    weirdness_constraint: float | None = Field(default=None, ge=0.0, le=1.0)
    audio_weight: float | None = Field(default=None, ge=0.0, le=1.0)


class WebMusicClipResponse(BaseModel):
    variant: str
    label: str
    audio_url: str
    download_url: str
    ready: bool = False


class WebMusicQuotaResponse(BaseModel):
    limit: int
    used: int
    remaining: int
    is_pro: bool = False
    requires_upgrade: bool = False


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
        clips=[WebMusicClipResponse(**clip) for clip in payload.get("clips") or []],
    )


class WebMusicDraftRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)


class WebMusicDraftResponse(BaseModel):
    lyrics: str
    title: str


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
    await enforce_rate_limit(http_request, ctx.user_id)
    lyrics, title = await service.generate_draft(body.prompt)
    return WebMusicDraftResponse(lyrics=lyrics, title=title)


@router.post("/generate", response_model=WebMusicGenerateResponse, status_code=202)
async def generate(
    body: WebMusicGenerateRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
) -> WebMusicGenerateResponse:
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


@router.get("/generations", response_model=WebMusicGenerationListResponse)
async def list_generations(
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> WebMusicGenerationListResponse:
    payload = await service.list_generations(UUID(ctx.user_id), limit=limit, offset=offset)
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


@router.get("/generations/{task_id}/download")
async def download_generation(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
) -> Response:
    data, filename, content_type = await service.download_mp3(
        UUID(ctx.user_id), task_id, variant=variant
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": content_disposition(filename, inline=False)},
    )


@router.get("/generations/{task_id}/stream")
async def stream_generation(
    task_id: UUID,
    ctx: CurrentUserDep,
    service: WebMusicServiceDep,
    variant: Literal["ok", "alt"] = "ok",
) -> Response:
    data, filename, content_type = await service.download_mp3(
        UUID(ctx.user_id), task_id, variant=variant
    )
    return StreamingResponse(
        iter([data]),
        media_type=content_type,
        headers={"Content-Disposition": content_disposition(filename, inline=True)},
    )
