"""Shared helpers for draining pending image job queues."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from platform_api.services import image_progress_log as image_log

if TYPE_CHECKING:
    from platform_api.services.image_job_service import ImageJobService

logger = logging.getLogger(__name__)


async def run_image_jobs_until_empty(
    service: ImageJobService,
    *,
    user_id: str,
    batch_id: str,
    job_ids: list[str] | None = None,
) -> None:
    """Run pending image jobs for a batch until the queue is drained.

    Auto-retries (pending after transient failure) are drained in the same loop.
    When ``job_ids`` is set, only those jobs are claimed (used by Manual Generation).
    """
    image_log.log_runner_started(user_id=user_id, batch_id=batch_id)
    total_ran = 0
    idle_rounds = 0
    resolved_job_ids = [str(job_id).strip() for job_id in (job_ids or []) if str(job_id).strip()] or None
    try:
        for iteration in range(1, 81):
            ran = await service.run_pending_jobs(
                user_id=user_id,
                batch_id=batch_id,
                limit=50,
                job_ids=resolved_job_ids,
            )
            image_log.log_runner_iteration(
                batch_id=batch_id,
                iteration=iteration,
                ran=ran,
            )
            if ran > 0:
                total_ran += ran
                idle_rounds = 0
                continue
            idle_rounds += 1
            # One empty claim after auto-retry requeue is enough to stop.
            if idle_rounds >= 2:
                break
            await asyncio.sleep(1.5)
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        image_log.log_runner_crashed(user_id=user_id, batch_id=batch_id, error=message)
        logger.exception(
            "Image job runner crashed for user %s batch=%s",
            user_id,
            batch_id,
        )
        return
    image_log.log_runner_finished(batch_id=batch_id, total_ran=total_ran)
