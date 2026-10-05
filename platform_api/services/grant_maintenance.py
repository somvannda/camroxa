"""Proactive period/daily credit-grant minting.

Moves grant minting off the read path (``GET /me/credits``) onto a scheduler: each
run scans active wallets and issues any due period/daily grant. The grant service
is idempotent (per-period lot), so re-runs are no-ops and this is safe to run
often. Single-winner across uvicorn workers via a Postgres advisory lock.

Env:
- ``CREDIT_GRANT_MAINTENANCE_ENABLED`` (default ``1``)
- ``CREDIT_GRANT_MAINTENANCE_INTERVAL_S`` (default ``3600``)
- ``CREDIT_GRANT_MAINTENANCE_BATCH`` (default ``5000``)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_ENABLED = os.getenv("CREDIT_GRANT_MAINTENANCE_ENABLED", "1") != "0"
_INTERVAL_S = float(os.getenv("CREDIT_GRANT_MAINTENANCE_INTERVAL_S", "3600"))
_BATCH = int(os.getenv("CREDIT_GRANT_MAINTENANCE_BATCH", "5000"))
_LOCK_ID = 774319002

_ELIGIBLE_SQL = """
SELECT u.id
FROM users u
JOIN credit_wallets w ON w.user_id = u.id
WHERE u.status = 'active'
ORDER BY u.created_at
LIMIT $1
"""


async def run_grant_maintenance(pool: Any) -> dict[str, int]:
    """Issue any due period/daily grant for active wallets. Idempotent."""
    from platform_api.dependencies import get_v3_grant_service

    grants = get_v3_grant_service()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_ELIGIBLE_SQL, _BATCH)

    period_granted = daily_granted = failed = 0
    for row in rows:
        user_id = row["id"]
        try:
            period = await grants.ensure_period_grant(user_id)
            if period.get("granted"):
                period_granted += 1
            daily = await grants.ensure_daily_grant(user_id)
            if daily.get("granted"):
                daily_granted += 1
        except Exception:
            failed += 1
            logger.debug("Grant maintenance failed for user %s", user_id, exc_info=True)
    return {
        "users": len(rows),
        "period_granted": period_granted,
        "daily_granted": daily_granted,
        "failed": failed,
    }


async def _run_once(pool: Any) -> dict[str, int] | None:
    """Run one sweep; only one uvicorn worker wins the advisory lock."""
    async with pool.acquire() as conn:
        acquired = await conn.fetchval("SELECT pg_try_advisory_lock($1)", _LOCK_ID)
        if not acquired:
            return None
        try:
            return await run_grant_maintenance(pool)
        finally:
            try:
                await conn.fetchval("SELECT pg_advisory_unlock($1)", _LOCK_ID)
            except Exception:
                pass


async def run_grant_maintenance_loop(pool: Any) -> None:
    """Background loop (started by main startup): run immediately, then every interval."""
    while True:
        try:
            stats = await _run_once(pool)
            if stats and (stats.get("period_granted") or stats.get("daily_granted")):
                logger.info("Credit grant maintenance: %s", stats)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Credit grant maintenance failed (non-fatal)")
        await asyncio.sleep(_INTERVAL_S)
