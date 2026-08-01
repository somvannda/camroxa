from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.services.batch_service import BatchService

router = APIRouter(prefix="/music/downloads", tags=["music-downloads"])


async def _get_batch_service() -> BatchService:
    raise NotImplementedError(
        "BatchService dependency not configured. Wire via app.dependency_overrides."
    )


BatchServiceDep = Annotated[BatchService, Depends(_get_batch_service)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


class SunoDownloadTargetResponse(BaseModel):
    download_url: str | None = None
    downloaded: bool = False
    output_dir: str | None = None
    target_path: str | None = None


class PendingMusicDownloadItemResponse(BaseModel):
    task_id: str
    song_id: str | None = None
    batch_id: str | None = None
    title: str | None = None
    track_number: int | None = None
    primary: SunoDownloadTargetResponse = Field(default_factory=SunoDownloadTargetResponse)
    secondary: SunoDownloadTargetResponse = Field(default_factory=SunoDownloadTargetResponse)


class PendingMusicDownloadsResponse(BaseModel):
    items: list[PendingMusicDownloadItemResponse] = Field(default_factory=list)


class MusicDownloadSyncItemRequest(BaseModel):
    task_id: str
    downloaded_primary: bool | None = None
    downloaded_secondary: bool | None = None
    output_dir_primary: str | None = None
    output_dir_secondary: str | None = None


class MusicDownloadSyncRequest(BaseModel):
    items: list[MusicDownloadSyncItemRequest] = Field(default_factory=list)


class MusicDownloadSyncResponse(BaseModel):
    updated: int


class BatchRedownloadItemResponse(BaseModel):
    song_id: str | None = None
    task_id: str
    title: str | None = None
    track_number: int | None = None
    download_url: str
    fallback_download_url: str | None = None
    target_path: str


class BatchRedownloadPlanRequest(BaseModel):
    batch_id: str
    role: str = "OK"
    run_dir: str


class BatchRedownloadPlanResponse(BaseModel):
    items: list[BatchRedownloadItemResponse] = Field(default_factory=list)


@router.get("/pending", response_model=PendingMusicDownloadsResponse, status_code=200)
async def list_pending_music_downloads(
    ctx: CurrentUserDep,
    service: BatchServiceDep,
    limit: int = 20,
) -> PendingMusicDownloadsResponse:
    items = await service.list_pending_suno_downloads(
        user_id=ctx.user_id,
        limit=max(1, min(int(limit or 20), 100)),
    )
    return PendingMusicDownloadsResponse(
        items=[PendingMusicDownloadItemResponse.model_validate(item) for item in items]
    )


@router.post("/sync", response_model=MusicDownloadSyncResponse, status_code=200)
async def sync_music_downloads(
    request: MusicDownloadSyncRequest,
    ctx: CurrentUserDep,
    service: BatchServiceDep,
) -> MusicDownloadSyncResponse:
    payload: list[dict[str, Any]] = [item.model_dump(exclude_none=True) for item in request.items]
    updated = await service.sync_suno_downloads(user_id=ctx.user_id, items=payload)
    return MusicDownloadSyncResponse(updated=updated)


@router.post("/batch-redownload-plan", response_model=BatchRedownloadPlanResponse, status_code=200)
async def batch_redownload_plan(
    request: BatchRedownloadPlanRequest,
    ctx: CurrentUserDep,
    service: BatchServiceDep,
) -> BatchRedownloadPlanResponse:
    """List already-successful Suno audio for one batch/channel, targeted at a new folder.

    Used by the desktop "change run folder + resume" recovery flow — ignores whether the
    account already marked a track downloaded, since that download may have landed on a
    bad/full drive and needs to be re-fetched into a different folder.
    """
    items = await service.build_batch_redownload_plan(
        user_id=ctx.user_id,
        batch_id=UUID(request.batch_id),
        role=request.role,
        run_dir=request.run_dir,
    )
    return BatchRedownloadPlanResponse(
        items=[BatchRedownloadItemResponse.model_validate(item) for item in items]
    )
