"""Authenticated DistroKid WAV conversion and upload-history API."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.services.distrokid_service import DistroKidService

router = APIRouter(prefix="/distrokid", tags=["distrokid"])


async def _get_distrokid_service() -> DistroKidService:
    raise NotImplementedError("DistroKidService dependency not configured.")


DistroKidDep = Annotated[DistroKidService, Depends(_get_distrokid_service)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


class WavConvertRequest(BaseModel):
    suno_task_id: str = Field(min_length=1, max_length=255)
    audio_id: str | None = Field(default=None, max_length=255)
    role: str = Field(default="primary", pattern="^(primary|secondary)$")
    song_id: UUID | None = None
    batch_id: UUID | None = None


class HistoryTrack(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    track_role: str | None = Field(default=None, max_length=32)
    wav_byte_size: int | None = Field(default=None, ge=0)
    wav_sha256: str | None = Field(default=None, max_length=128)
    status: str = Field(default="success", max_length=32)


class HistoryCheckRequest(BaseModel):
    album_name: str = Field(min_length=1, max_length=255)
    tracks: list[HistoryTrack] = Field(min_length=1, max_length=200)


class HistoryRecordRequest(HistoryCheckRequest):
    directory_path: str | None = Field(default=None, max_length=2000)
    batch_id: str | None = Field(default=None, max_length=255)


@router.post("/wav/convert")
async def convert_wav(request: WavConvertRequest, ctx: CurrentUserDep, service: DistroKidDep) -> dict[str, Any]:
    return await service.convert(user_id=UUID(ctx.user_id), **request.model_dump())


@router.get("/wav/jobs/{job_id}")
async def get_wav_job(job_id: UUID, ctx: CurrentUserDep, service: DistroKidDep) -> dict[str, Any]:
    return await service.get_job(user_id=UUID(ctx.user_id), job_id=job_id)


@router.get("/batch-context/{batch_id}")
async def get_batch_context(batch_id: UUID, ctx: CurrentUserDep, service: DistroKidDep) -> dict[str, Any]:
    return await service.get_batch_context(user_id=UUID(ctx.user_id), batch_id=batch_id)


@router.get("/wav/usage")
async def get_wav_usage(ctx: CurrentUserDep, service: DistroKidDep) -> dict[str, Any]:
    return await service.usage(UUID(ctx.user_id))


@router.get("/wav/sources")
async def list_wav_sources(
    ctx: CurrentUserDep,
    service: DistroKidDep,
    batch_id: UUID,
) -> dict[str, Any]:
    items = await service.list_wav_sources(user_id=UUID(ctx.user_id), batch_id=batch_id)
    return {"items": items}


@router.post("/history/check")
async def check_history(request: HistoryCheckRequest, ctx: CurrentUserDep, service: DistroKidDep) -> dict[str, Any]:
    matches = await service.check_history(
        user_id=UUID(ctx.user_id), album_name=request.album_name,
        tracks=[track.model_dump(exclude_none=True) for track in request.tracks],
    )
    return {"duplicate": bool(matches), "matches": matches}


@router.post("/history")
async def record_history(request: HistoryRecordRequest, ctx: CurrentUserDep, service: DistroKidDep) -> dict[str, Any]:
    records = await service.record_history(
        user_id=UUID(ctx.user_id), album_name=request.album_name,
        directory_path=request.directory_path, batch_id=request.batch_id,
        tracks=[track.model_dump(exclude_none=True) for track in request.tracks],
    )
    return {"records": records}


@router.get("/history")
async def list_history(ctx: CurrentUserDep, service: DistroKidDep, limit: int = 50) -> dict[str, Any]:
    return {"items": await service.list_history(user_id=UUID(ctx.user_id), limit=limit)}
