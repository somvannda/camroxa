"""Batch generation router endpoints.

Provides batch creation and status retrieval for authenticated users.

Requirements: 13.1, 13.5
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.middleware.rate_limit import enforce_rate_limit
from platform_api.models.schemas import (
    AlbumRewriteRequest,
    AlbumRewriteResponse,
    BatchCreateRequest,
    BatchCreateResponse,
    BatchDeleteResponse,
    BatchStatusResponse,
    MusicPlanPreflightRequest,
    MusicPlanPreflightResponse,
    SongRetryResponse,
    SongSunoRetryRequest,
    TitleRewriteResponse,
)
from platform_api.repositories.job_queue_repo import JobQueueRepository
from platform_api.services.batch_service import BatchService
from platform_api.services.job_types import (
    JOB_EXECUTE_BATCH,
    JOB_RETRY_SONG_DRAFT,
    JOB_RETRY_SONG_SUNO,
    PRI_EXECUTE_BATCH,
    PRI_RETRY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/batches", tags=["batches"])


# ---------------------------------------------------------------------------
# Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_batch_service() -> BatchService:
    """Placeholder dependency for BatchService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "BatchService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_job_queue_repo() -> JobQueueRepository:
    """Placeholder dependency for JobQueueRepository — override via wire_dependencies."""
    raise NotImplementedError(
        "JobQueueRepository dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases for dependency injection
BatchServiceDep = Annotated[BatchService, Depends(_get_batch_service)]
JobQueueRepoDep = Annotated[JobQueueRepository, Depends(_get_job_queue_repo)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/preflight",
    response_model=MusicPlanPreflightResponse,
    status_code=200,
    summary="Preflight an entire music automation plan",
)
async def preflight_music_plan(
    request: MusicPlanPreflightRequest,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
) -> MusicPlanPreflightResponse:
    """Check subscription quota, daily limits, and wallet before creating batches."""
    result = await batch_service.preflight_music_plan(
        user_id=ctx.user_id,
        ok_profile_ids=request.ok_profile_ids,
        alt_profile_ids=request.alt_profile_ids,
        from_date=request.from_date,
        to_date=request.to_date,
        song_count=request.song_count,
        auto_gen_image=request.auto_gen_image,
        auto_gsuno=request.auto_gsuno,
    )
    return MusicPlanPreflightResponse(**result)


@router.post(
    "",
    response_model=BatchCreateResponse,
    status_code=201,
    summary="Create a batch generation run",
)
async def create_batch(
    request: BatchCreateRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
    job_queue: JobQueueRepoDep,
) -> BatchCreateResponse:
    """Create a new batch generation run for the authenticated user.

    Pre-checks total cost for the enabled automation path and creates
    batch + song records. Execution is enqueued on ``job_queue`` for
    ``platform_api.worker`` (not in-process BackgroundTasks).

    Requirement 13.1: Pre-check total batch cost before starting.
    """
    await enforce_rate_limit(http_request, ctx.user_id)

    batch = await batch_service.create_batch(
        user_id=ctx.user_id,
        ok_profile_id=request.ok_profile_id,
        alt_profile_id=request.alt_profile_id,
        description_id=request.description_id,
        structure_id=request.structure_id,
        mood_id=request.mood_id,
        structure_mode=request.structure_mode,
        shuffle_structure=request.shuffle_structure,
        shuffle_mood=request.shuffle_mood,
        auto_gen_image=request.auto_gen_image,
        auto_gsuno=request.auto_gsuno,
        song_count=request.song_count,
        language=request.language,
        secondary_language=request.secondary_language,
        creativity_level=request.creativity_level,
        pairing_mode=request.pairing_mode,
        from_date=request.from_date,
        to_date=request.to_date,
        ok_run_dir=request.ok_run_dir,
        alt_run_dir=request.alt_run_dir,
        album=request.album,
    )
    await job_queue.enqueue(
        user_id=UUID(ctx.user_id),
        batch_id=batch.id,
        job_type=JOB_EXECUTE_BATCH,
        payload={"batch_id": str(batch.id), "user_id": ctx.user_id},
        priority=PRI_EXECUTE_BATCH,
    )
    return BatchCreateResponse(
        batch_id=str(batch.id),
        status=batch.status,
        song_count=batch.song_count,
        from_date=batch.planned_from_date or request.from_date,
        to_date=batch.planned_to_date or request.to_date,
        planned_days=((batch.planned_to_date or request.to_date) - (batch.planned_from_date or request.from_date)).days + 1,
        ok_run_dir=batch.ok_run_dir,
        alt_run_dir=batch.alt_run_dir,
    )


@router.get(
    "/{batch_id}",
    response_model=BatchStatusResponse,
    status_code=200,
    summary="Get batch status",
)
async def get_batch_status(
    batch_id: str,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
) -> BatchStatusResponse:
    """Return the current status and counters for a batch.

    Requirement 13.5: Return batch status with all counters.
    """
    status = await batch_service.get_batch_status(
        batch_id=batch_id,
        user_id=ctx.user_id,
    )
    return BatchStatusResponse(
        batch_id=status["batch_id"],
        status=status["status"],
        total_songs=status.get("total_songs", 0),
        drafts_completed=status.get("drafts_completed", 0),
        drafts_failed=status.get("drafts_failed", 0),
        suno_submitted=status.get("suno_submitted", 0),
        suno_completed=status.get("suno_completed", 0),
        suno_failed=status.get("suno_failed", 0),
        audio_downloaded=status.get("audio_downloaded", 0),
        images_completed=status.get("images_completed", 0),
        ok_run_dir=status.get("ok_run_dir"),
        alt_run_dir=status.get("alt_run_dir"),
    )


@router.delete(
    "/{batch_id}",
    response_model=BatchDeleteResponse,
    status_code=200,
    summary="Delete a failed batch with no Suno audio",
)
async def delete_failed_batch(
    batch_id: str,
    http_request: Request,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
) -> BatchDeleteResponse:
    """Hard-delete a batch when every song is pending/draft-failed/draft-ready/suno-failed.

    Restores leftover draft-meter slots for draft_failed songs. Does not re-credit
    the wallet or gift song quota.
    """
    await enforce_rate_limit(http_request, ctx.user_id)
    result = await batch_service.delete_failed_batch(
        batch_id=UUID(batch_id),
        user_id=ctx.user_id,
    )
    return BatchDeleteResponse(**result)


@router.post(
    "/{batch_id}/songs/{song_id}/retry-draft",
    response_model=SongRetryResponse,
    status_code=202,
    summary="Retry draft generation for a failed song",
)
async def retry_song_draft(
    batch_id: str,
    song_id: str,
    http_request: Request,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
    job_queue: JobQueueRepoDep,
) -> SongRetryResponse:
    """Queue draft regeneration for one song marked pending or draft_failed."""
    await enforce_rate_limit(http_request, ctx.user_id)

    await batch_service.validate_song_draft_retry(
        batch_id=UUID(batch_id),
        song_id=UUID(song_id),
        user_id=ctx.user_id,
    )
    await job_queue.enqueue(
        user_id=UUID(ctx.user_id),
        batch_id=UUID(batch_id),
        song_id=UUID(song_id),
        job_type=JOB_RETRY_SONG_DRAFT,
        payload={
            "batch_id": batch_id,
            "song_id": song_id,
            "user_id": ctx.user_id,
        },
        priority=PRI_RETRY,
    )
    return SongRetryResponse(
        batch_id=batch_id,
        song_id=song_id,
        status="retrying",
    )


@router.post(
    "/{batch_id}/rewrite-album",
    response_model=AlbumRewriteResponse,
    summary="Rewrite Primary or Secondary album name",
)
async def rewrite_batch_album(
    batch_id: str,
    http_request: Request,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
    request: AlbumRewriteRequest | None = None,
) -> AlbumRewriteResponse:
    """Regenerate album 1 (ok) or album 2 (alt). Allowed even after Suno success."""
    await enforce_rate_limit(http_request, ctx.user_id)
    payload = request or AlbumRewriteRequest()
    result = await batch_service.rewrite_batch_album(
        batch_id=UUID(batch_id),
        user_id=ctx.user_id,
        role=payload.role,
    )
    return AlbumRewriteResponse(**result)


@router.post(
    "/{batch_id}/songs/{song_id}/rewrite-title",
    response_model=TitleRewriteResponse,
    summary="Rewrite one song title",
)
async def rewrite_song_title(
    batch_id: str,
    song_id: str,
    http_request: Request,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
) -> TitleRewriteResponse:
    """Regenerate a song title without changing lyrics or status."""
    await enforce_rate_limit(http_request, ctx.user_id)
    result = await batch_service.rewrite_song_title(
        batch_id=UUID(batch_id),
        song_id=UUID(song_id),
        user_id=ctx.user_id,
    )
    return TitleRewriteResponse(**result)


@router.post(
    "/{batch_id}/songs/{song_id}/retry-suno",
    response_model=SongRetryResponse,
    status_code=202,
    summary="Retry or continue Suno submission for a song",
)
async def retry_song_suno(
    batch_id: str,
    song_id: str,
    http_request: Request,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
    job_queue: JobQueueRepoDep,
    request: SongSunoRetryRequest | None = None,
) -> SongRetryResponse:
    """Queue Suno submission for draft_ready or suno_failed songs."""
    await enforce_rate_limit(http_request, ctx.user_id)

    payload = request or SongSunoRetryRequest()
    await batch_service.validate_song_suno_retry(
        batch_id=UUID(batch_id),
        song_id=UUID(song_id),
        user_id=ctx.user_id,
        lyrics_override=payload.lyrics,
        title_override=payload.title,
    )
    await job_queue.enqueue(
        user_id=UUID(ctx.user_id),
        batch_id=UUID(batch_id),
        song_id=UUID(song_id),
        job_type=JOB_RETRY_SONG_SUNO,
        payload={
            "batch_id": batch_id,
            "song_id": song_id,
            "user_id": ctx.user_id,
            "title": payload.title,
            "album": payload.album,
            "lyrics": payload.lyrics,
        },
        priority=PRI_RETRY,
    )
    return SongRetryResponse(
        batch_id=batch_id,
        song_id=song_id,
        status="retrying",
    )
