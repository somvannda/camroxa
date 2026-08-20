"""Content license, device registry, encrypted segment serving."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from platform_api.exceptions import ForbiddenError, NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.middleware.rate_limit import enforce_rate_limit_for_endpoint
from platform_api.services.audio_packager import GCM_MIME, parse_package_header
from platform_api.services.content_license_service import (
    ContentLicenseService,
    decrypt_module_hash,
)

router = APIRouter(prefix="/web-music/licenses", tags=["web-music-licenses"])


async def _get_license_service() -> ContentLicenseService:
    raise NotImplementedError("ContentLicenseService is not configured.")


LicenseServiceDep = Annotated[ContentLicenseService, Depends(_get_license_service)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


class RegisterDeviceRequest(BaseModel):
    device_public_id: str = Field(..., min_length=8, max_length=128)
    platform: str = "music_web"


class CreateSessionRequest(BaseModel):
    device_public_id: str = Field(..., min_length=8, max_length=128)
    subject_type: Literal["stream_track", "suno_task"]
    subject_id: str
    variant: Literal["ok", "alt"] = "ok"
    purpose: Literal["play", "export"] = "play"
    wasm_hash: str | None = None
    play_source: str | None = None
    search_query: str | None = None


class HeartbeatRequest(BaseModel):
    token: str
    event: str = "heartbeat"
    bytes_served: int = 0
    position_seconds: float = 0
    playback_rate: float = 1.0
    seq: int = 0
    session_bind: str | None = None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/devices/register")
async def register_device(
    body: RegisterDeviceRequest,
    request: Request,
    ctx: CurrentUserDep,
    service: LicenseServiceDep,
) -> dict[str, Any]:
    return await service.register_device(
        UUID(ctx.user_id),
        device_public_id=body.device_public_id,
        platform=body.platform,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/sessions")
async def create_session(
    body: CreateSessionRequest,
    request: Request,
    ctx: CurrentUserDep,
    service: LicenseServiceDep,
) -> dict[str, Any]:
    await enforce_rate_limit_for_endpoint(ctx.user_id, "web_music_play")
    try:
        subject_id = UUID(body.subject_id)
    except ValueError as exc:
        raise ValidationError("subject_id must be a UUID.") from exc
    return await service.create_session(
        UUID(ctx.user_id),
        device_public_id=body.device_public_id,
        subject_type=body.subject_type,
        subject_id=subject_id,
        variant=body.variant,
        purpose=body.purpose,
        wasm_hash=body.wasm_hash or decrypt_module_hash(),
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        play_source=body.play_source,
        search_query=body.search_query,
        country=(request.headers.get("cf-ipcountry") or "").strip() or None,
    )


@router.post("/heartbeat")
async def heartbeat(
    body: HeartbeatRequest,
    request: Request,
    ctx: CurrentUserDep,
    service: LicenseServiceDep,
) -> dict[str, Any]:
    return await service.heartbeat(
        UUID(ctx.user_id),
        body.token,
        event=body.event,
        bytes_served=body.bytes_served,
        position_seconds=body.position_seconds,
        playback_rate=body.playback_rate,
        seq=body.seq,
        session_bind=body.session_bind,
        is_admin=ctx.is_admin,
        user_agent=request.headers.get("user-agent"),
        ip=_client_ip(request),
    )


@router.get("/module-hash")
async def module_hash() -> dict[str, str]:
    return {"hash": decrypt_module_hash()}


@router.get("/segments/{token}")
async def get_segment(
    token: str,
    request: Request,
    ctx: CurrentUserDep,
    service: LicenseServiceDep,
    chunk: int = Query(default=0, ge=0, le=4096),
) -> Response:
    await enforce_rate_limit_for_endpoint(ctx.user_id, "web_music_play")
    session = await service.resolve_session(token)
    if session is None or str(session.get("user_id")) != ctx.user_id:
        raise NotFoundError("License session expired or invalid.")
    if str(session.get("purpose") or "play") not in {"play", "admin_play"}:
        raise ForbiddenError("This license cannot stream.")
    storage_key = str(session.get("packaged_storage_key") or "").strip()
    if not storage_key:
        raise NotFoundError("Packaged audio is not ready.")

    from platform_api.services.storage_service import StorageService
    from platform_api.services.streaming_config_service import resolve_streaming_storage_config
    from platform_api.dependencies import get_db_pool

    config = await resolve_streaming_storage_config(get_db_pool())
    if not config.configured:
        raise NotFoundError("Streaming storage is not configured.")
    blob = await StorageService.from_config(config).download_bytes(key=storage_key)
    if not blob:
        raise NotFoundError("Packaged audio is missing.")
    header, _ = parse_package_header(blob)
    if chunk >= header.chunk_count:
        raise NotFoundError("Chunk out of range.")
    key_hex = None
    # Prefer server unwrap so the client can decrypt; also return raw encrypted chunk.
    # Client decrypts with session content_key. We still send ciphertext only.
    from platform_api.services.audio_packager import iter_encrypted_chunks

    records = iter_encrypted_chunks(blob)
    payload = records[chunk]
    headers = {
        "Cache-Control": "private, no-store",
        "X-Camxora-Chunk": str(chunk),
        "X-Camxora-Chunk-Count": str(header.chunk_count),
        "X-Camxora-Chunk-Size": str(header.chunk_size),
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
    }
    del request, key_hex
    return Response(content=payload, media_type=GCM_MIME, headers=headers)


@router.post("/admin/backfill")
async def admin_backfill_packages(
    ctx: AdminDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    del ctx
    from platform_api.dependencies import get_db_pool
    from platform_api.services.audio_package_service import AudioPackageService

    return await AudioPackageService(get_db_pool()).backfill(limit=limit)


@router.get("/admin/playback-events")
async def admin_playback_events(
    ctx: AdminDep,
    service: LicenseServiceDep,
    user_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    del ctx
    return await service.list_playback_events(user_id=user_id, limit=limit, offset=offset)


@router.get("/admin/export-events")
async def admin_export_events(
    ctx: AdminDep,
    service: LicenseServiceDep,
    user_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    del ctx
    return await service.list_export_events(user_id=user_id, limit=limit, offset=offset)
