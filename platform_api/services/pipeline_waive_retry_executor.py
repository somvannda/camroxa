"""Execute dual-control-approved platform-paid Pipeline Ops retries."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from platform_api.services.job_types import (
    JOB_RETRY_SONG_DRAFT,
    JOB_RETRY_SONG_SUNO,
    JOB_RUN_IMAGE_JOBS,
    PRI_RETRY,
    PRI_RUN_IMAGE_JOBS,
)

logger = logging.getLogger(__name__)


async def execute_approved_waive_retry(
    *,
    payload: dict[str, Any],
    admin_id: str,
    waive_reason: str,
) -> None:
    """Run a queued waive retry by enqueuing the matching job_queue work."""
    _ = (admin_id, waive_reason)
    kind = str(payload.get("retry_kind") or "").strip().lower()
    batch_id = str(payload.get("batch_id") or "").strip()
    owner_user_id = str(payload.get("owner_user_id") or "").strip()
    if not kind or not batch_id or not owner_user_id:
        raise ValueError("Invalid waive-retry payload (missing kind/batch/owner).")

    from platform_api.dependencies import get_batch_service, get_image_job_service, get_job_queue_repo

    job_queue = get_job_queue_repo()
    parsed_batch = UUID(batch_id)
    owner_uuid = UUID(owner_user_id)

    if kind == "draft":
        song_id = str(payload.get("song_id") or "").strip()
        if not song_id:
            raise ValueError("draft waive-retry requires song_id.")
        await job_queue.enqueue(
            user_id=owner_uuid,
            batch_id=parsed_batch,
            song_id=UUID(song_id),
            job_type=JOB_RETRY_SONG_DRAFT,
            payload={
                "batch_id": batch_id,
                "song_id": song_id,
                "user_id": owner_user_id,
            },
            priority=PRI_RETRY,
        )
        return

    if kind == "suno":
        song_id = str(payload.get("song_id") or "").strip()
        if not song_id:
            raise ValueError("suno waive-retry requires song_id.")
        await job_queue.enqueue(
            user_id=owner_uuid,
            batch_id=parsed_batch,
            song_id=UUID(song_id),
            job_type=JOB_RETRY_SONG_SUNO,
            payload={
                "batch_id": batch_id,
                "song_id": song_id,
                "user_id": owner_user_id,
            },
            priority=PRI_RETRY,
        )
        return

    if kind == "images":
        job_ids = [str(jid).strip() for jid in (payload.get("job_ids") or []) if str(jid).strip()]
        if not job_ids:
            raise ValueError("images waive-retry requires job_ids.")
        batch_service = get_batch_service()
        image_service = get_image_job_service()
        await batch_service.refresh_image_job_prompts_for_retry(
            user_id=owner_user_id,
            job_ids=job_ids,
            batch_id=batch_id,
        )
        updated = await image_service.retry_jobs(
            owner_user_id,
            job_ids=job_ids,
            batch_id=batch_id,
        )
        if updated > 0:
            await job_queue.enqueue_if_absent(
                user_id=owner_uuid,
                batch_id=parsed_batch,
                job_type=JOB_RUN_IMAGE_JOBS,
                payload={
                    "user_id": owner_user_id,
                    "batch_id": batch_id,
                    "limit": 50,
                },
                priority=PRI_RUN_IMAGE_JOBS,
            )
        return

    raise ValueError(f"Unsupported waive retry_kind: {kind}")
