"""Batch generation router endpoints.

Provides batch creation and status retrieval for authenticated users.

Requirements: 13.1, 13.5
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.models.schemas import (
    BatchCreateRequest,
    BatchCreateResponse,
    BatchStatusResponse,
)
from platform_api.services.batch_service import BatchService

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
    "",
    response_model=BatchCreateResponse,
    status_code=201,
    summary="Create a batch generation run",
)
async def create_batch(
    request: BatchCreateRequest,
    ctx: CurrentUserDep,
    batch_service: BatchServiceDep,
) -> BatchCreateResponse:
    """Create a new batch generation run for the authenticated user.

    Pre-checks total cost (LLM + Suno credits × song_count) and creates
    batch + song records.

    Requirement 13.1: Pre-check total batch cost before starting.
    """
    batch = await batch_service.create_batch(
        user_id=ctx.user_id,
        ok_profile_id=request.ok_profile_id,
        alt_profile_id=request.alt_profile_id,
        song_count=request.song_count,
        language=request.language,
        creativity_level=request.creativity_level,
        pairing_mode=request.pairing_mode,
    )
    return BatchCreateResponse(
        batch_id=str(batch.id),
        status=batch.status,
        song_count=batch.song_count,
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
    )
