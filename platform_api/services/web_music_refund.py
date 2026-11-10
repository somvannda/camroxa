"""Refund a failed web-music generation, from any terminal-status path.

Web Create charges ``WEB_MUSIC_CREDITS_PER_SONG`` credits before the Suno task
exists. The charge must come back when the task fails, whether the failure
arrives as the provider callback or is discovered by the reconcile poll.

Two defects lived here until 2026-11-10 and are fixed in one place now:

* the refund was skipped for anyone holding a live pack (``is_pro``) — a leftover
  from the retired plan model where Pro generations were included, not charged.
  Paying customers were the only ones never refunded.
* the reconcile path never called this helper (web tasks have no song/batch id),
  so a missed callback left the charge in place forever.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from platform_api.models.products import WEB_MUSIC_CREDITS_PER_SONG
from platform_api.repositories.credit_repo import CreditRepository
from platform_api.services.credit_units import CREDIT_SCALE

logger = logging.getLogger(__name__)


async def release_web_music_preview(
    pool: Any,
    *,
    user_id: str,
    task_id: UUID,
) -> None:
    """Free a preview slot when a preview generation fails upstream."""
    from platform_api.services.billing_calendar import (
        billing_month_start,
        billing_usage_date,
    )

    try:
        row = await pool.fetchrow(
            """
            UPDATE suno_tasks
            SET preview_released = TRUE
            WHERE id = $1 AND user_id = $2
              AND is_preview = TRUE AND preview_released = FALSE
            RETURNING model, created_at
            """,
            task_id,
            UUID(user_id),
        )
        if row is None:
            return
        period = billing_month_start(billing_usage_date(row["created_at"]))
        await pool.execute(
            """
            UPDATE web_music_preview_entitlements
            SET used = GREATEST(0, used - 1)
            WHERE user_id = $1 AND period_start = $2 AND model = $3
            """,
            UUID(user_id),
            period,
            str(row["model"] or "").strip().upper(),
        )
    except Exception as exc:  # noqa: BLE001 - never block the refund
        logger.warning(
            "Web music preview slot release failed for task %s user=%s: %s",
            task_id,
            user_id,
            exc,
        )


async def refund_web_music_generation_on_failure(
    pool: Any,
    *,
    user_id: str,
    task_id: UUID,
    prior_status: Any = None,
) -> bool:
    """Return generation credits when a web-music Suno task fails.

    Idempotent per ``(user, reason, task)``: a duplicate callback or a
    reconcile that races the callback settles once. Returns ``True`` when this
    call performed the refund.

    ``prior_status`` is only a fast path: a task already recorded as FAILED was
    settled by the caller that made the transition, so skip the write. A missing
    value (reconcile path) is treated as "not yet settled".
    """
    from platform_api.models.enums import TaskStatus

    prior = str(getattr(prior_status, "value", prior_status) or "").strip().lower()
    if prior == TaskStatus.FAILED.value:
        return False

    await release_web_music_preview(pool, user_id=user_id, task_id=task_id)

    try:
        applied = await CreditRepository(pool).refund_once(
            UUID(user_id),
            int(WEB_MUSIC_CREDITS_PER_SONG) * CREDIT_SCALE,
            reason="web_music_generation_failed",
            ref_id=str(task_id),
            metadata={"source": "web_music", "op": "music", "billing": "v3"},
        )
    except Exception as exc:  # noqa: BLE001 - logged, retried by the sweep
        logger.warning(
            "Web music credit refund failed for task %s user=%s: %s",
            task_id,
            user_id,
            exc,
        )
        return False
    if applied:
        logger.info(
            "Refunded %s web music credits for failed task %s user=%s",
            WEB_MUSIC_CREDITS_PER_SONG,
            task_id,
            user_id,
        )
    return bool(applied)
