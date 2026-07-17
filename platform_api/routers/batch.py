"""Batch generation router endpoints.

Provides batch creation and status retrieval for authenticated users.

Requirements: 13.1, 13.5
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.middleware.rate_limit import enforce_rate_limit
from platform_api.models.schemas import (
    BatchCreateRequest,
    BatchCreateResponse,
    BatchStatusResponse,
    MusicPlanPreflightRequest,
    MusicPlanPreflightResponse,
    SongRetryResponse,
)
from platform_api.services.batch_service import BatchService

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


# Type aliases for dependency injection
BatchServiceDep = Annotated[BatchService, Depends(_get_batch_service)]
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
    background_tasks: BackgroundTasks,
) -> BatchCreateResponse:
    """Create a new batch generation run for the authenticated user.

    Pre-checks total cost for the enabled automation path and creates
    batch + song records.

    Requirement 13.1: Pre-check total batch cost before starting.
    """
    await enforce_rate_limit(http_request, ctx.user_id)

    batch = await batch_service.create_batch(
        user_id=ctx.user_id,
        ok_profile_id=request.ok_profile_id,
        alt_profile_id=request.alt_profile_id,
        description_id=request.description_id,
        structure_id=request.structure_id,
        structure_mode=request.structure_mode,
        shuffle_structure=request.shuffle_structure,
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
    background_tasks.add_task(
        _execute_batch_with_logging,
        batch_service,
        str(batch.id),
        ctx.user_id,
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


async def _execute_batch_with_logging(
    batch_service: BatchService,
    batch_id: str,
    user_id: str,
) -> None:
    """Run background batch execution and keep failures visible in logs."""
    try:
        await batch_service.execute_batch(batch_id=batch_id, user_id=user_id)
    except Exception:
        logger.exception(
            "Background batch execution crashed for batch %s and user %s.",
            batch_id,
            user_id,
        )


async def _retry_song_draft_with_logging(
    batch_service: BatchService,
    batch_id: str,
    song_id: str,
    user_id: str,
) -> None:
    try:
        await batch_service.retry_song_draft(
            batch_id=UUID(batch_id),
            song_id=UUID(song_id),
            user_id=user_id,
        )
    except Exception:
        logger.exception(
            "Background draft retry crashed for song %s in batch %s and user %s.",
            song_id,
            batch_id,
            user_id,
        )


async def _retry_song_suno_with_logging(
    batch_service: BatchService,
    batch_id: str,
    song_id: str,
    user_id: str,
) -> None:
    try:
        await batch_service.retry_song_suno(
            batch_id=UUID(batch_id),
            song_id=UUID(song_id),
            user_id=user_id,
        )
    except Exception:
        logger.exception(
            "Background Suno retry crashed for song %s in batch %s and user %s.",
            song_id,
            batch_id,
            user_id,
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
    background_tasks: BackgroundTasks,
) -> SongRetryResponse:
    """Queue draft regeneration for one song marked pending or draft_failed."""
    await enforce_rate_limit(http_request, ctx.user_id)

    await batch_service.validate_song_draft_retry(
        batch_id=UUID(batch_id),
        song_id=UUID(song_id),
        user_id=ctx.user_id,
    )
    background_tasks.add_task(
        _retry_song_draft_with_logging,
        batch_service,
        batch_id,
        song_id,
        ctx.user_id,
    )
    return SongRetryResponse(
        batch_id=batch_id,
        song_id=song_id,
        status="retrying",
    )


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
    background_tasks: BackgroundTasks,
) -> SongRetryResponse:
    """Queue Suno submission for draft_ready or suno_failed songs."""
    await enforce_rate_limit(http_request, ctx.user_id)

    await batch_service.validate_song_suno_retry(
        batch_id=UUID(batch_id),
        song_id=UUID(song_id),
        user_id=ctx.user_id,
    )
    background_tasks.add_task(
        _retry_song_suno_with_logging,
        batch_service,
        batch_id,
        song_id,
        ctx.user_id,
    )
    return SongRetryResponse(
        batch_id=batch_id,
        song_id=song_id,
        status="retrying",
    )
