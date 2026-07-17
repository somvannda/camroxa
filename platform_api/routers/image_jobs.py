from __future__ import annotations

import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from platform_api.exceptions import NotFoundError

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.services.batch_service import BatchService
from platform_api.services.image_job_service import ImageJobService
from platform_api.services import image_progress_log as image_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/image-jobs", tags=["image-jobs"])


async def _get_image_job_service() -> ImageJobService:
    raise NotImplementedError(
        "ImageJobService dependency not configured. Wire via app.dependency_overrides."
    )

async def _get_batch_service() -> BatchService:
    raise NotImplementedError(
        "BatchService dependency not configured. Wire via app.dependency_overrides."
    )


ImageJobServiceDep = Annotated[ImageJobService, Depends(_get_image_job_service)]
BatchServiceDep = Annotated[BatchService, Depends(_get_batch_service)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


class ImageJobListItem(BaseModel):
    id: str
    batch_id: str | None
    song_id: str | None
    profile_id: str | None
    kind: str
    channel_role: str
    prompt: str | None
    provider: str | None
    resolution: str
    style_strength: float
    input_image_path: str | None
    style_reference_path: str | None
    source_job_id: str | None
    status: str
    attempt_count: int
    output_image_path: str | None
    error: str | None
    created_at: str
    updated_at: str


class ImageJobsListResponse(BaseModel):
    items: list[ImageJobListItem] = Field(default_factory=list)

class ImageJobsEnqueueRequest(BaseModel):
    batch_ids: list[str] = Field(default_factory=list, min_length=1)


class ImageJobsEnqueueResponse(BaseModel):
    created: int


class ImageJobsRunRequest(BaseModel):
    batch_id: str | None = None
    limit: int = Field(default=8, ge=1, le=50)


class ImageJobsRunResponse(BaseModel):
    scheduled: int


class ImageJobsRetryRequest(BaseModel):
    job_ids: list[str] | None = None
    batch_id: str | None = None


class ImageJobsRetryResponse(BaseModel):
    updated: int


class ImageJobsClearRequest(BaseModel):
    batch_id: str | None = None
    statuses: list[str] | None = None


class ImageJobsClearResponse(BaseModel):
    deleted: int


class ImageJobsSyncManualRequest(BaseModel):
    batch_id: str


class ImageJobsSyncManualResponse(BaseModel):
    updated: int


@router.get("", response_model=ImageJobsListResponse, status_code=200)
async def list_image_jobs(
    ctx: CurrentUserDep,
    service: ImageJobServiceDep,
    batch_id: str | None = None,
    status: list[str] | None = None,
    limit: int = 200,
) -> ImageJobsListResponse:
    jobs = await service.list_jobs(
        ctx.user_id,
        batch_id=batch_id,
        statuses=status,
        limit=max(1, min(500, limit)),
    )
    return ImageJobsListResponse(
        items=[
            ImageJobListItem(
                id=str(job.id),
                batch_id=str(job.batch_id) if job.batch_id else None,
                song_id=str(job.song_id) if job.song_id else None,
                profile_id=str(job.profile_id) if job.profile_id else None,
                kind=job.kind.value,
                channel_role=job.channel_role.value,
                prompt=job.prompt,
                provider=job.provider,
                resolution=job.resolution,
                style_strength=float(job.style_strength or 0.6),
                input_image_path=job.input_image_path,
                style_reference_path=job.style_reference_path,
                source_job_id=str(job.source_job_id) if job.source_job_id else None,
                status=job.status.value,
                attempt_count=int(job.attempt_count or 0),
                output_image_path=job.output_image_path,
                error=job.error,
                created_at=job.created_at.isoformat() if hasattr(job, "created_at") else "",
                updated_at=job.updated_at.isoformat() if hasattr(job, "updated_at") else "",
            )
            for job in jobs
        ]
    )


@router.get("/{job_id}/output", status_code=200)
async def get_image_job_output(
    job_id: UUID,
    ctx: CurrentUserDep,
    service: ImageJobServiceDep,
) -> Response:
    try:
        image_bytes, media_type = await service.read_job_output_bytes(job_id, ctx.user_id)
    except NotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    return Response(content=image_bytes, media_type=media_type)


@router.post("/run", response_model=ImageJobsRunResponse, status_code=202)
async def run_image_jobs(
    request: ImageJobsRunRequest,
    ctx: CurrentUserDep,
    service: ImageJobServiceDep,
) -> ImageJobsRunResponse:
    image_log.log_run_scheduled(
        user_id=ctx.user_id,
        batch_id=request.batch_id,
        limit=request.limit,
    )
    asyncio.create_task(
        _run_image_jobs_with_logging(
            service,
            ctx.user_id,
            request.batch_id,
            request.limit,
        )
    )
    return ImageJobsRunResponse(scheduled=request.limit)

@router.post("/enqueue", response_model=ImageJobsEnqueueResponse, status_code=200)
async def enqueue_image_jobs(
    request: ImageJobsEnqueueRequest,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
) -> ImageJobsEnqueueResponse:
    created = await batch_service.enqueue_image_jobs_for_batches(
        user_id=ctx.user_id,
        batch_ids=request.batch_ids,
    )
    return ImageJobsEnqueueResponse(created=created)


@router.post("/sync-manual", response_model=ImageJobsSyncManualResponse, status_code=200)
async def sync_manual_image_jobs(
    request: ImageJobsSyncManualRequest,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
) -> ImageJobsSyncManualResponse:
    updated = await batch_service.sync_manual_assets_for_batch(
        user_id=ctx.user_id,
        batch_id=request.batch_id,
    )
    return ImageJobsSyncManualResponse(updated=updated)


async def _run_image_jobs_with_logging(
    service: ImageJobService,
    user_id: str,
    batch_id: str | None,
    limit: int,
) -> None:
    from platform_api.services.image_job_runner import run_image_jobs_until_empty

    _ = limit
    if not batch_id:
        return
    try:
        await run_image_jobs_until_empty(
            service,
            user_id=user_id,
            batch_id=batch_id,
        )
    except Exception:
        logger.exception(
            "Image job runner crashed for user %s batch=%s",
            user_id,
            batch_id,
        )


@router.post("/retry", response_model=ImageJobsRetryResponse, status_code=200)
async def retry_image_jobs(
    request: ImageJobsRetryRequest,
    ctx: CurrentUserDep,
    service: ImageJobServiceDep,
    batch_service: BatchServiceDep,
) -> ImageJobsRetryResponse:
    image_log.log_retry_requested(
        user_id=ctx.user_id,
        batch_id=request.batch_id,
        job_ids=request.job_ids,
    )
    await batch_service.refresh_image_job_prompts_for_retry(
        user_id=ctx.user_id,
        job_ids=request.job_ids,
        batch_id=request.batch_id,
    )
    updated = await service.retry_jobs(
        ctx.user_id,
        job_ids=request.job_ids,
        batch_id=request.batch_id,
    )
    image_log.log_retry_reset(batch_id=request.batch_id, updated=updated)
    resolved_batch_id = request.batch_id
    if not resolved_batch_id and request.job_ids:
        jobs = await service.list_jobs(ctx.user_id, limit=500)
        requested = {str(job_id).strip() for job_id in request.job_ids if str(job_id).strip()}
        for job in jobs:
            if str(job.id) in requested and job.batch_id is not None:
                resolved_batch_id = str(job.batch_id)
                break
    if updated > 0 and resolved_batch_id:
        asyncio.create_task(
            _run_image_jobs_with_logging(
                service,
                ctx.user_id,
                resolved_batch_id,
                50,
            )
        )
    return ImageJobsRetryResponse(updated=updated)


@router.post("/clear", response_model=ImageJobsClearResponse, status_code=200)
async def clear_image_jobs(
    request: ImageJobsClearRequest,
    ctx: CurrentUserDep,
    service: ImageJobServiceDep,
) -> ImageJobsClearResponse:
    deleted = await service.clear_jobs(
        ctx.user_id,
        batch_id=request.batch_id,
        statuses=request.statuses,
    )
    return ImageJobsClearResponse(deleted=deleted)
