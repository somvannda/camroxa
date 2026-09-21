"""Hourly Telegram report for streaming (B2) capture failures.

Complements the streaming auto-retry loop: this never recovers anything, it only
tells ops when MP3 / asset capture is failing for the desktop catalog or for web
music. Silent unless there is something to report. Single-winner across uvicorn
workers via a Postgres advisory lock + ``last_sent_at`` row.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from platform_api.config import environment_display_label
from platform_api.repositories.streaming_repo import (
    STREAMING_HEALTH_REPORT_ADVISORY_LOCK_ID,
    STREAMING_HEALTH_REPORT_SETTING_KEY,
    StreamingRepository,
)
from platform_api.services.telegram_ops_alert_service import get_telegram_ops_service

logger = logging.getLogger(__name__)

_PHNOM_PENH = timezone(timedelta(hours=7))

_HEALTH_REPORT_ENABLED = os.getenv("STREAMING_HEALTH_REPORT_ENABLED", "1") != "0"
_HEALTH_REPORT_INTERVAL_S = float(
    os.getenv("STREAMING_HEALTH_REPORT_INTERVAL_S", "3600")
)
_HEALTH_REPORT_WINDOW_HOURS = int(
    os.getenv("STREAMING_HEALTH_REPORT_WINDOW_HOURS", "24")
)
_HEALTH_REPORT_MAX_ERRORS = int(os.getenv("STREAMING_HEALTH_REPORT_MAX_ERRORS", "5"))


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


async def collect_streaming_health(pool: Any) -> dict[str, Any]:
    """Snapshot the current streaming-capture failure counts."""
    repo = StreamingRepository(pool)
    window = _HEALTH_REPORT_WINDOW_HOURS
    return {
        "failed_total": await repo.count_failed_mp3_jobs(),
        "failed_window": await repo.count_failed_mp3_jobs_since(hours=window),
        "web_missing_mp3": await repo.count_web_music_missing_mp3(
            max_age_hours=window
        ),
        "web_missing_assets": await repo.count_web_music_missing_assets(
            max_age_hours=window
        ),
        "errors": await repo.list_recent_failed_mp3_errors(
            limit=_HEALTH_REPORT_MAX_ERRORS
        ),
        "window_hours": window,
    }


def has_failures(health: dict[str, Any]) -> bool:
    return bool(
        health.get("failed_total")
        or health.get("web_missing_mp3")
        or health.get("web_missing_assets")
    )


def format_streaming_health_message(
    health: dict[str, Any], env_label: str
) -> str:
    window = int(health.get("window_hours") or 24)
    lines = [
        f"🎵 <b>STREAMING CAPTURE</b> · {_esc(env_label)}",
        "⚠️ <b>Capture failures need attention</b>",
        "",
        (
            "desktop failed mp3: "
            f"<b>{int(health.get('failed_total') or 0)}</b> "
            f"(last {window}h: {int(health.get('failed_window') or 0)})"
        ),
        (
            "web music missing mp3: "
            f"<b>{int(health.get('web_missing_mp3') or 0)}</b> (last {window}h)"
        ),
        (
            "web music missing assets: "
            f"<b>{int(health.get('web_missing_assets') or 0)}</b> (last {window}h)"
        ),
    ]
    errors = health.get("errors") or []
    if errors:
        lines.append("")
        lines.append("<b>recent errors</b>")
        for row in errors:
            job = _esc(str(row.get("id") or "")[:8])
            kind = _esc(row.get("kind") or "")
            err = _esc(row.get("error") or "—")
            lines.append(f"• <code>{job}</code> {kind}: {err}")
    lines.append("")
    lines.append(
        "time: "
        + _esc(datetime.now(_PHNOM_PENH).strftime("%d %b %Y %H:%M:%S +07"))
    )
    return "\n".join(lines)


async def maybe_send_streaming_health_report(pool: Any) -> bool:
    """Send one report if failures exist and this worker wins the hourly claim."""
    if not _HEALTH_REPORT_ENABLED:
        return False
    service = get_telegram_ops_service()
    if service is None:
        return False
    health = await collect_streaming_health(pool)
    if not has_failures(health):
        return False
    claimed = await StreamingRepository(pool).claim_periodic_report(
        key=STREAMING_HEALTH_REPORT_SETTING_KEY,
        lock_id=STREAMING_HEALTH_REPORT_ADVISORY_LOCK_ID,
        interval_s=_HEALTH_REPORT_INTERVAL_S,
    )
    if not claimed:
        return False
    try:
        env_label = environment_display_label()
    except Exception:
        env_label = "Unknown"
    ok = await service.send_html(format_streaming_health_message(health, env_label))
    if ok:
        logger.info("Streaming capture health report sent: %s", health)
    return ok


async def run_streaming_health_report_loop(pool: Any) -> None:
    """Background loop (started by main startup) sending the hourly report."""
    while True:
        await asyncio.sleep(_HEALTH_REPORT_INTERVAL_S)
        try:
            await maybe_send_streaming_health_report(pool)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Streaming capture health report failed (non-fatal)")
