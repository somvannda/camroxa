from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from platform_api.exceptions import NotFoundError

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.repositories.job_queue_repo import JobQueueRepository
from platform_api.services.batch_service import BatchService
from platform_api.services.image_job_service import ImageJobService
from platform_api.services import image_progress_log as image_log
from platform_api.services.job_types import JOB_RUN_IMAGE_JOBS, PRI_RUN_IMAGE_JOBS

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


async def _get_job_queue_repo() -> JobQueueRepository:
    raise NotImplementedError(
        "JobQueueRepository dependency not configured. Wire via app.dependency_overrides."
    )


ImageJobServiceDep = Annotated[ImageJobService, Depends(_get_image_job_service)]
BatchServiceDep = Annotated[BatchService, Depends(_get_batch_service)]
JobQueueRepoDep = Annotated[JobQueueRepository, Depends(_get_job_queue_repo)]
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
    force: bool = False


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


class ImageJobsManualGenerateRequest(BaseModel):
    kind: str = Field(..., min_length=1)
    prompt: str | None = None
    channel_profile_id: str | None = None


class ImageJobsManualGenerateCreatedJob(BaseModel):
    id: str
    kind: str
    status: str


class ImageJobsManualGenerateResponse(BaseModel):
    batch_id: str
    job_id: str
    kind: str
    profile_id: str
    planned_date: str
    album_label: str = "Not available"
    created_jobs: list[ImageJobsManualGenerateCreatedJob] = Field(default_factory=list)


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
    job_queue: JobQueueRepoDep,
) -> ImageJobsRunResponse:
    image_log.log_run_scheduled(
        user_id=ctx.user_id,
        batch_id=request.batch_id,
        limit=request.limit,
    )
    if request.batch_id:
        await job_queue.enqueue_if_absent(
            user_id=UUID(ctx.user_id),
            batch_id=UUID(str(request.batch_id)),
            job_type=JOB_RUN_IMAGE_JOBS,
            payload={
                "user_id": ctx.user_id,
                "batch_id": str(request.batch_id),
                "limit": request.limit,
            },
            priority=PRI_RUN_IMAGE_JOBS,
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


@router.post("/manual-generate", response_model=ImageJobsManualGenerateResponse, status_code=200)
async def manual_generate_image_jobs(
    request: ImageJobsManualGenerateRequest,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
) -> ImageJobsManualGenerateResponse:
    """Create a today-dated Not available queue row and generate the clicked kind."""
    result = await batch_service.create_manual_image_generation(
        user_id=ctx.user_id,
        kind=request.kind,
        prompt=request.prompt,
        channel_profile_id=request.channel_profile_id,
    )
    return ImageJobsManualGenerateResponse(**result)


@router.post("/retry", response_model=ImageJobsRetryResponse, status_code=200)
async def retry_image_jobs(
    request: ImageJobsRetryRequest,
    ctx: CurrentUserDep,
    service: ImageJobServiceDep,
    batch_service: BatchServiceDep,
    job_queue: JobQueueRepoDep,
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
        force=bool(request.force),
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
        await job_queue.enqueue_if_absent(
            user_id=UUID(ctx.user_id),
            batch_id=UUID(str(resolved_batch_id)),
            job_type=JOB_RUN_IMAGE_JOBS,
            payload={
                "user_id": ctx.user_id,
                "batch_id": str(resolved_batch_id),
                "limit": 50,
            },
            priority=PRI_RUN_IMAGE_JOBS,
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
