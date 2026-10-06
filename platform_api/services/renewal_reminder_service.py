"""Send web-music renewal reminder emails for subscriptions in the window.

CutLuy is one-time, so this is the nudge that brings users back to the renewal
checkout before their period ends. Idempotent per period via
``web_subscriptions.renewal_reminder_sent_at`` (reset when a renewal fulfills).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Single-winner across uvicorn workers (distinct from grant maintenance's lock).
_LOCK_ID = 774319003


def _format_price(cents: int) -> str:
    return f"${cents / 100:.2f}"


async def run_renewal_reminders(pool: Any) -> int:
    """Single-winner wrapper so multiple workers don't send duplicate reminders."""
    async with pool.acquire() as conn:
        acquired = await conn.fetchval("SELECT pg_try_advisory_lock($1)", _LOCK_ID)
        if not acquired:
            return 0
        try:
            return await _run_renewal_reminders(pool)
        finally:
            try:
                await conn.fetchval("SELECT pg_advisory_unlock($1)", _LOCK_ID)
            except Exception:
                pass


async def _run_renewal_reminders(pool: Any) -> int:
    """Email owners of active subs entering the renewal window. Returns count sent."""
    from platform_api.config import get_settings
    from platform_api.db.asyncpg_adapter import wrap_pool
    from platform_api.services.email_service import send_renewal_reminder_email
    from platform_api.services.v2.subscription_service import (
        RENEWAL_WINDOW_DAYS,
        SubscriptionService,
    )

    service = SubscriptionService(wrap_pool(pool))
    rows = await service.list_renewal_reminders_due(within_days=RENEWAL_WINDOW_DAYS)
    if not rows:
        return 0

    base = get_settings().music_web_base_url.rstrip("/")
    renew_url = f"{base}/profile"
    now = dt.datetime.now(dt.timezone.utc)
    sent = 0
    for row in rows:
        end = row.get("current_period_end")
        days_left = max(0, (end - now).days) if end is not None else None
        ok = await asyncio.to_thread(
            send_renewal_reminder_email,
            row["email"],
            display_name=row.get("display_name") or "there",
            plan_name=row.get("plan_name") or "your",
            price_display=_format_price(int(row.get("price_cents") or 0)),
            renew_url=renew_url,
            days_left=days_left,
        )
        if ok:
            await service.mark_renewal_reminder_sent(str(row["id"]))
            sent += 1
    return sent
