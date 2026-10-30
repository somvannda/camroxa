"""Daily credit-grant invariant check + Telegram alert.

Guards the class of bug that minted a ``v3_period_grant`` every day: it flags a
user holding **more than one live grant lot**, or receiving **more than one period
grant in a billing day**. Silent unless a violation is found.

Single-winner across uvicorn workers via a Postgres advisory lock plus a
``last_sent_at`` system_settings row (same pattern as the streaming health
report). Runs as an in-process scheduled loop started by ``main`` startup.

Env:
- ``CREDIT_INVARIANT_CHECK_ENABLED`` (default ``1``)
- ``CREDIT_INVARIANT_INTERVAL_S`` (default ``86400`` — daily)
- ``CREDIT_INVARIANT_WINDOW_HOURS`` (default ``26``)
- ``CREDIT_INVARIANT_MAX_SAMPLES`` (default ``10``)
- ``CREDIT_INVARIANT_DAILY_VOLUME_CREDITS`` (default ``50000``)
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from platform_api.config import environment_display_label
from platform_api.services.telegram_ops_alert_service import get_telegram_ops_service

logger = logging.getLogger(__name__)

_PHNOM_PENH = timezone(timedelta(hours=7))

_ENABLED = os.getenv("CREDIT_INVARIANT_CHECK_ENABLED", "1") != "0"
_INTERVAL_S = float(os.getenv("CREDIT_INVARIANT_INTERVAL_S", "86400"))
_WINDOW_HOURS = int(os.getenv("CREDIT_INVARIANT_WINDOW_HOURS", "26"))
_MAX_SAMPLES = int(os.getenv("CREDIT_INVARIANT_MAX_SAMPLES", "10"))
_DAILY_VOLUME_ALERT_CREDITS = float(
    os.getenv("CREDIT_INVARIANT_DAILY_VOLUME_CREDITS", "50000")
)

_CLAIM_KEY = "credit_invariant_check_last_sent"
_LOCK_ID = 774319001  # unique advisory-lock id for this report

_MULTI_LOT_SQL = """
SELECT u.email, count(*) AS lots,
       COALESCE(SUM(lot.remaining_units), 0) / 10000.0 AS credits
FROM credit_wallet_lots lot
JOIN users u ON u.id = lot.user_id
WHERE lot.tag = 'grant' AND lot.remaining_units > 0
GROUP BY u.id, u.email
HAVING count(*) > 1
ORDER BY count(*) DESC, credits DESC
LIMIT $1
"""

_MULTI_GRANT_DAY_SQL = """
SELECT u.email,
       (date_trunc('day', ct.created_at AT TIME ZONE 'Asia/Phnom_Penh'))::date AS day,
       count(*) AS grants, SUM(ct.amount) / 10000.0 AS credits
FROM credit_transactions ct
JOIN users u ON u.id = ct.user_id
WHERE ct.direction = 'credit' AND ct.reason = 'v3_period_grant'
  AND ct.created_at >= NOW() - make_interval(hours => $2)
GROUP BY u.id, u.email, day
HAVING count(*) > 1
ORDER BY day DESC, count(*) DESC
LIMIT $1
"""

_DAILY_VOLUME_SQL = """
SELECT (date_trunc('day', ct.created_at AT TIME ZONE 'Asia/Phnom_Penh'))::date AS day,
       count(*) AS grants, SUM(ct.amount) / 10000.0 AS credits
FROM credit_transactions ct
WHERE ct.direction = 'credit' AND ct.reason = 'v3_period_grant'
  AND ct.created_at >= NOW() - make_interval(hours => $1)
GROUP BY day
ORDER BY day DESC
LIMIT 3
"""

_WALLET_LOT_MISMATCH_SQL = """
SELECT u.email,
       w.balance / 10000.0 AS wallet_credits,
       COALESCE(SUM(l.remaining_units) FILTER (
           WHERE l.remaining_units > 0
             AND (l.expires_at IS NULL OR l.expires_at > NOW())
       ), 0) / 10000.0 AS lot_credits
FROM credit_wallets w
JOIN users u ON u.id = w.user_id
LEFT JOIN credit_wallet_lots l ON l.user_id = w.user_id
GROUP BY u.id, u.email, w.balance
HAVING w.balance <> COALESCE(SUM(l.remaining_units) FILTER (
    WHERE l.remaining_units > 0
      AND (l.expires_at IS NULL OR l.expires_at > NOW())
), 0)
ORDER BY ABS(w.balance - COALESCE(SUM(l.remaining_units) FILTER (
    WHERE l.remaining_units > 0
      AND (l.expires_at IS NULL OR l.expires_at > NOW())
), 0)) DESC
LIMIT $1
"""


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=False)


async def collect_credit_invariants(pool: Any) -> dict[str, Any]:
    """Snapshot current credit-grant invariant violations."""
    async with pool.acquire() as conn:
        multi_lot_users = [dict(r) for r in await conn.fetch(_MULTI_LOT_SQL, _MAX_SAMPLES)]
        multi_grant_user_days = [
            dict(r) for r in await conn.fetch(_MULTI_GRANT_DAY_SQL, _MAX_SAMPLES, _WINDOW_HOURS)
        ]
        daily_volume = [dict(r) for r in await conn.fetch(_DAILY_VOLUME_SQL, _WINDOW_HOURS)]
        wallet_lot_mismatches = [
            dict(r) for r in await conn.fetch(_WALLET_LOT_MISMATCH_SQL, _MAX_SAMPLES)
        ]
    return {
        "multi_lot_users": multi_lot_users,
        "multi_grant_user_days": multi_grant_user_days,
        "daily_volume": daily_volume,
        "wallet_lot_mismatches": wallet_lot_mismatches,
        "window_hours": _WINDOW_HOURS,
        "volume_threshold": _DAILY_VOLUME_ALERT_CREDITS,
    }


def has_credit_violations(invariants: dict[str, Any]) -> bool:
    """True when a user has stacked lots / multiple grants, or volume spikes."""
    if invariants.get("multi_lot_users") or invariants.get("multi_grant_user_days"):
        return True
    if invariants.get("wallet_lot_mismatches"):
        return True
    threshold = float(invariants.get("volume_threshold") or 0)
    for row in invariants.get("daily_volume") or []:
        if float(row.get("credits") or 0) > threshold:
            return True
    return False


def format_credit_invariants_message(invariants: dict[str, Any], env_label: str) -> str:
    lines = [
        f"🧾 <b>CREDIT INVARIANTS</b> · {_esc(env_label)}",
        "⚠️ <b>Possible bad credit grant detected</b>",
        "",
    ]
    lots = invariants.get("multi_lot_users") or []
    if lots:
        lines.append(f"<b>multiple live grant lots</b> ({len(lots)})")
        for row in lots:
            lines.append(
                f"• {_esc(row.get('email'))}: {int(row.get('lots') or 0)} lots, "
                f"{float(row.get('credits') or 0):,.2f} cr"
            )
        lines.append("")
    grants = invariants.get("multi_grant_user_days") or []
    if grants:
        lines.append(f"<b>&gt;1 period grant in a day</b> ({len(grants)})")
        for row in grants:
            lines.append(
                f"• {_esc(row.get('email'))}: {int(row.get('grants') or 0)}× on "
                f"{_esc(row.get('day'))} ({float(row.get('credits') or 0):,.2f} cr)"
            )
        lines.append("")
    threshold = float(invariants.get("volume_threshold") or 0)
    mismatches = invariants.get("wallet_lot_mismatches") or []
    if mismatches:
        lines.append(f"<b>wallet ≠ live lots</b> ({len(mismatches)})")
        for row in mismatches:
            lines.append(
                f"• {_esc(row.get('email'))}: wallet "
                f"{float(row.get('wallet_credits') or 0):,.2f} vs lots "
                f"{float(row.get('lot_credits') or 0):,.2f} cr"
            )
        lines.append("")
    volume = [
        row
        for row in (invariants.get("daily_volume") or [])
        if float(row.get("credits") or 0) > threshold
    ]
    if volume:
        lines.append(f"<b>daily granted volume &gt; {threshold:,.0f} cr</b>")
        for row in volume:
            lines.append(
                f"• {_esc(row.get('day'))}: {int(row.get('grants') or 0)} grants, "
                f"{float(row.get('credits') or 0):,.2f} cr"
            )
        lines.append("")
    lines.append(
        "time: " + _esc(datetime.now(_PHNOM_PENH).strftime("%d %b %Y %H:%M:%S +07"))
    )
    return "\n".join(lines)


async def _claim_report(pool: Any) -> bool:
    """Single-winner claim across uvicorn workers (advisory lock + last_sent_at)."""
    now_dt = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        acquired = await conn.fetchval("SELECT pg_try_advisory_lock($1)", _LOCK_ID)
        if not acquired:
            return False
        try:
            row = await conn.fetchrow(
                "SELECT value FROM system_settings WHERE key = $1", _CLAIM_KEY
            )
            last: datetime | None = None
            if row:
                try:
                    last = datetime.fromisoformat(
                        str(json.loads(row["value"]).get("last_sent_at"))
                    )
                except (TypeError, ValueError):
                    last = None
            if last is not None:
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if (now_dt - last).total_seconds() < _INTERVAL_S * 0.9:
                    return False
            await conn.execute(
                """
                INSERT INTO system_settings (key, value_type, value, updated_at)
                VALUES ($1, 'json', $2, NOW())
                ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
                """,
                _CLAIM_KEY,
                json.dumps({"last_sent_at": now_dt.isoformat()}),
            )
            return True
        finally:
            try:
                await conn.fetchval("SELECT pg_advisory_unlock($1)", _LOCK_ID)
            except Exception:
                pass


async def maybe_send_credit_invariant_report(pool: Any) -> bool:
    """Send one alert if a violation exists and this worker wins the claim."""
    if not _ENABLED:
        return False
    service = get_telegram_ops_service()
    if service is None:
        return False
    invariants = await collect_credit_invariants(pool)
    if not has_credit_violations(invariants):
        return False
    if not await _claim_report(pool):
        return False
    try:
        env_label = environment_display_label()
    except Exception:
        env_label = "Unknown"
    ok = await service.send_html(
        format_credit_invariants_message(invariants, env_label),
        kind="credit_invariant",
    )
    if ok:
        logger.warning("Credit invariant alert sent: %s", invariants)
    return ok


async def run_credit_invariant_loop(pool: Any) -> None:
    """Background loop (started by main startup) checking every interval."""
    while True:
        await asyncio.sleep(_INTERVAL_S)
        try:
            await maybe_send_credit_invariant_report(pool)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Credit invariant check failed (non-fatal)")
