"""Telegram /stats and /burncredit commands, plus the 10 PM daily burn report."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx

from platform_api.config import environment_display_label
from platform_api.services.billing_calendar import BILLING_TIMEZONE
from platform_api.services.telegram_ops_alert_service import (
    _esc,
    _now_label,
    get_telegram_ops_service,
)

logger = logging.getLogger(__name__)

_POLLER_STARTED = False
_I_AM_POLLER = False
# Unique per process: a lock value lets the holder prove ownership before
# renewing. `pid` alone is not unique across restarts/reused PIDs.
_LOCK_VALUE = f"{os.getpid()}:{uuid4().hex}"
_LOCK_TTL_S = 40
_LOCK_KEY = "telegram:ops:poller"
_OFFSET_KEY = "telegram:ops:update_offset"
_DAILY_SENT_KEY = "telegram:ops:burncredit_daily"
_DAILY_BURN_HOUR = 22
_LAST_UPDATE_ID = 0  # in-process offset fallback when Redis is unavailable
_ALLOWED_COMMANDS = frozenset({"/stats", "/report", "/summary"})

_WINDOW_KEYS = ("today", "yesterday", "d7", "d30")
_TABLE_HEADERS = ("Today", "Yesterday", "Last 7 Days", "Last 30 Days")
_BURN_COMMANDS = frozenset({"/burncredit", "/burncredits"})
_USD_PER_SONG_REQUEST = 0.06
# Phnom Penh calendar-day boundaries as timestamptz. Casting the column
# (`(created_at AT TIME ZONE …)::date`) made every report a full table scan;
# range predicates on the raw column can use an index instead.
_PP_DAY_START = (
    "(date_trunc('day', NOW() AT TIME ZONE 'Asia/Phnom_Penh') "
    "AT TIME ZONE 'Asia/Phnom_Penh')"
)


def _count_sql(*, table: str, where: str = "") -> str:
    return f"""
SELECT
  COUNT(*) FILTER (WHERE created_at >= {_PP_DAY_START})::int AS today,
  COUNT(*) FILTER (
    WHERE created_at >= {_PP_DAY_START} - interval '1 day'
      AND created_at < {_PP_DAY_START}
  )::int AS yesterday,
  COUNT(*) FILTER (WHERE created_at >= {_PP_DAY_START} - interval '6 days')::int AS d7,
  COUNT(*) FILTER (WHERE created_at >= {_PP_DAY_START} - interval '29 days')::int AS d30
FROM {table}
{where}
"""


def _window_agg(expr: str) -> str:
    return f"""
  {expr} FILTER (WHERE created_at >= {_PP_DAY_START}) AS today,
  {expr} FILTER (
    WHERE created_at >= {_PP_DAY_START} - interval '1 day'
      AND created_at < {_PP_DAY_START}
  ) AS yesterday,
  {expr} FILTER (WHERE created_at >= {_PP_DAY_START} - interval '6 days') AS d7,
  {expr} FILTER (WHERE created_at >= {_PP_DAY_START} - interval '29 days') AS d30
"""


def _window_sum(expr: str) -> str:
    """FILTER must attach to the aggregate (SUM), not COALESCE."""
    return f"""
  COALESCE(SUM({expr}) FILTER (WHERE created_at >= {_PP_DAY_START}), 0) AS today,
  COALESCE(SUM({expr}) FILTER (
    WHERE created_at >= {_PP_DAY_START} - interval '1 day'
      AND created_at < {_PP_DAY_START}
  ), 0) AS yesterday,
  COALESCE(SUM({expr}) FILTER (WHERE created_at >= {_PP_DAY_START} - interval '6 days'), 0) AS d7,
  COALESCE(SUM({expr}) FILTER (WHERE created_at >= {_PP_DAY_START} - interval '29 days'), 0) AS d30
"""


# `credit_transactions` is written by three generations of code with different
# sign and scale conventions:
#   * legacy studio debits — display credits, e.g. "music via suno"
#   * legacy web debits    — display credits, "consumed_web_music_*"
#   * v3 debits            — micro-units (1 display credit = 10_000), "v3_*"
#   * refunds              — mixed, so magnitude is used and direction decides.
# Only one attribution is provable from the row: a v3 music charge whose ref_id
# is a platform `suno_tasks` row is web music. Other v3 operations
# (image/lyric/title/album) are used by both products, so they land in
# `unattributed` rather than being guessed into studio.
_BURN_SQL = f"""
WITH classified AS (
  SELECT
    ct.direction,
    ABS(ct.amount)::numeric AS units,
    ct.created_at,
    CASE
      WHEN ct.reason LIKE 'consumed_web_music%'
        OR ct.reason LIKE 'refunded_web_music%' THEN 'web'
      WHEN ct.reason LIKE 'v3_%' AND ct.direction = 'debit'
        AND EXISTS (
          SELECT 1 FROM suno_tasks t WHERE t.id::text = ct.ref_id
        ) THEN 'web'
      WHEN ct.reason LIKE 'v3_%' THEN 'studio'
      WHEN ct.reason LIKE '% via %' THEN 'studio'
      ELSE 'unattributed'
    END AS family,
    CASE
      WHEN ct.reason LIKE 'consumed_web_music%'
        OR ct.reason LIKE 'refunded_web_music%'
        OR ct.reason LIKE '% via %' THEN 1.0
      ELSE 10000.0
    END AS per_credit
  FROM credit_transactions ct
  WHERE ct.direction IN ('debit', 'refund')
    AND ct.created_at >= {_PP_DAY_START} - interval '29 days'
), burn AS (
  SELECT
    family,
    created_at,
    (CASE WHEN direction = 'debit' THEN units ELSE -units END) / per_credit AS credits
  FROM classified
)
SELECT family, {_window_sum("credits")}
FROM burn
GROUP BY family
"""


def is_stats_command(text: str | None) -> bool:
    """Return True for /stats, /report, /summary (with optional @bot suffix)."""
    raw = str(text or "").strip().lower()
    if not raw:
        return False
    first = raw.split()[0]
    cmd = first.split("@", 1)[0]
    if cmd in _ALLOWED_COMMANDS:
        return True
    return first in {"stats", "report", "summary"}


def parse_ops_command(text: str | None) -> tuple[str, str] | None:
    """Return ('stats', '') or ('burncredit', scope) or None."""
    raw = str(text or "").strip()
    if not raw:
        return None
    parts = raw.split()
    first = parts[0].lower().split("@", 1)[0]
    extra = parts[1].lower() if len(parts) > 1 else ""
    if first in _ALLOWED_COMMANDS or first in {"stats", "report", "summary"}:
        return ("stats", "")
    if first in _BURN_COMMANDS or first in {"burncredit", "burncredits"}:
        if extra in {"", "all"}:
            return ("burncredit", "all")
        if extra in {"web", "music", "webmusic", "web_music"}:
            return ("burncredit", "web")
        if extra in {"studio", "desktop", "app"}:
            return ("burncredit", "studio")
        if extra in {"both", "total"}:
            return ("burncredit", "both")
        return ("burncredit", "help")
    return None


def format_stats_table(title: str, values: dict[str, int]) -> str:
    """Stacked rows so Telegram mobile does not clip a wide table."""
    lines = [f"<b>{_esc(title)}</b>"]
    for header, key in zip(_TABLE_HEADERS, _WINDOW_KEYS):
        lines.append(f"{_esc(header)}: <b>{int(values.get(key, 0))}</b>")
    return "\n".join(lines)


def format_ops_stats_message(
    *,
    env_label: str,
    users: dict[str, int],
    songs: dict[str, int],
) -> str:
    lines = [
        f"📊 <b>STATS</b> · {_esc(env_label)}",
        "Asia/Phnom_Penh calendar days. Last 7 / 30 include today.",
        "",
        format_stats_table("Users", users),
        "",
        format_stats_table("Songs generated", songs),
        "",
        f"time: {_esc(_now_label())}",
        "Reply <code>/stats</code> anytime for a fresh count.",
    ]
    return "\n".join(lines)


def _fmt_credits(value: float | int) -> str:
    number = float(value or 0)
    if abs(number - round(number)) < 0.005:
        return str(int(round(number)))
    return f"{number:.2f}"


def format_burn_table(
    title: str,
    songs: dict[str, int],
    credits: dict[str, float],
) -> str:
    """Stacked periods so Telegram mobile can read songs, credits, and USD."""
    lines = [f"<b>{_esc(title)}</b>"]
    for header, key in zip(_TABLE_HEADERS, _WINDOW_KEYS):
        song_count = int(songs.get(key, 0))
        usd = song_count * _USD_PER_SONG_REQUEST
        lines.extend(
            [
                f"<b>{_esc(header)}</b>",
                f"{song_count} songs · {_fmt_credits(credits.get(key, 0))} cr",
                f"${usd:.2f}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


_BURN_HELP = (
    "Use:\n"
    "<code>/burncredit web</code> — Camxora Music\n"
    "<code>/burncredit studio</code> — desktop studio\n"
    "<code>/burncredit both</code> — combined\n"
    "<code>/burncredit</code> — all three reports"
)


def format_burncredit_message(
    *,
    env_label: str,
    scope: str,
    web_songs: dict[str, int],
    web_credits: dict[str, float],
    studio_songs: dict[str, int],
    studio_credits: dict[str, float],
    both_songs: dict[str, int],
    both_credits: dict[str, float],
    headline: str | None = None,
    unattributed_credits: dict[str, float] | None = None,
) -> str:
    if scope == "help":
        return "🔥 <b>BURN CREDIT</b>\n" + _BURN_HELP
    sections: list[str] = [
        f"🔥 <b>BURN CREDIT</b> · {_esc(env_label)}",
    ]
    if headline:
        # Callers may pass HTML (bold numbers); plain text is still valid.
        sections.append(headline)
    sections.extend(
        [
            "Each period: songs generated · credits burned. USD = songs × $0.06 / request.",
            "Asia/Phnom_Penh calendar days. Last 7 / 30 include today.",
            "Web credits are proven against a web task; shared covers ops used by both products.",
            "",
        ]
    )
    if scope in {"all", "web"}:
        sections.append(format_burn_table("Web music", web_songs, web_credits))
        sections.append("")
    if scope in {"all", "studio"}:
        sections.append(format_burn_table("Desktop studio", studio_songs, studio_credits))
        sections.append("")
    if scope in {"all", "both"}:
        sections.append(format_burn_table("Both", both_songs, both_credits))
        sections.append("")
    if unattributed_credits and any(
        float(unattributed_credits.get(key, 0) or 0) for key in _WINDOW_KEYS
    ):
        sections.append(
            "Shared (image/lyric/title or net refunds): "
            + " · ".join(
                f"{header} {_fmt_credits(unattributed_credits.get(key, 0))} cr"
                for header, key in zip(_TABLE_HEADERS, _WINDOW_KEYS)
            )
        )
        sections.append("")
    sections.append(f"time: {_esc(_now_label())}")
    sections.append("Reply <code>/burncredit web</code> · <code>studio</code> · <code>both</code>")
    return "\n".join(sections)


def _row_windows(row: Any | None) -> dict[str, int]:
    if row is None:
        return {key: 0 for key in _WINDOW_KEYS}
    return {key: int(row[key] or 0) for key in _WINDOW_KEYS}


async def fetch_ops_stats(pool: Any) -> dict[str, dict[str, int]]:
    """Count new users and suno_tasks (same song metric as admin user details)."""
    users = await pool.fetchrow(
        _count_sql(
            table="users",
            where="WHERE COALESCE(status, 'active') <> 'deleted' AND COALESCE(role, 'user') = 'user'",
        )
    )
    songs = await pool.fetchrow(_count_sql(table="suno_tasks"))
    return {"users": _row_windows(users), "songs": _row_windows(songs)}


def _add_windows(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {key: int(left.get(key, 0)) + int(right.get(key, 0)) for key in _WINDOW_KEYS}


def _add_credit_windows(
    left: dict[str, float],
    right: dict[str, float],
) -> dict[str, float]:
    return {key: float(left.get(key, 0)) + float(right.get(key, 0)) for key in _WINDOW_KEYS}


async def fetch_burncredit_stats(pool: Any) -> dict[str, dict[str, dict[str, float]]]:
    """Songs by suno_tasks.source; credits by provable product attribution."""
    web_songs = _row_windows(
        await pool.fetchrow(
            f"SELECT {_window_agg('COUNT(*)')} FROM suno_tasks WHERE source = 'web_music'"
        )
    )
    studio_songs = _row_windows(
        await pool.fetchrow(
            "SELECT "
            + _window_agg("COUNT(*)")
            + " FROM suno_tasks WHERE COALESCE(source, 'studio') = 'studio'"
        )
    )

    empty_credits = {key: 0.0 for key in _WINDOW_KEYS}
    credits = {
        "web": dict(empty_credits),
        "studio": dict(empty_credits),
        "unattributed": dict(empty_credits),
    }
    # `fetch` (not `fetchrow`): one row per attribution family. A family absent
    # from the window keeps its zero row, so formatting is stable.
    for row in await pool.fetch(_BURN_SQL):
        family = str(row["family"] or "").strip().lower()
        if family not in credits:
            family = "unattributed"
        credits[family] = {key: float(row[key] or 0) for key in _WINDOW_KEYS}

    return {
        "web": {"songs": web_songs, "credits": credits["web"]},
        "studio": {"songs": studio_songs, "credits": credits["studio"]},
        "unattributed": {
            "songs": {key: 0 for key in _WINDOW_KEYS},
            "credits": credits["unattributed"],
        },
        "both": {
            "songs": _add_windows(web_songs, studio_songs),
            "credits": _add_credit_windows(credits["web"], credits["studio"]),
        },
    }


async def fetch_platform_revenue(pool: Any) -> dict[str, float]:
    """Fulfilled platform checkout revenue (cents) for today / last 7 days."""
    from platform_api.repositories.credit_repo import CreditRepository

    now = datetime.now(BILLING_TIMEZONE)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    repo = CreditRepository(pool)
    today = await repo.sum_fulfilled_subscription_revenue(
        from_date=day_start, to_date=now
    )
    week = await repo.sum_fulfilled_subscription_revenue(
        from_date=day_start - timedelta(days=6), to_date=now
    )
    return {
        "today_cents": float(today.get("subscription_revenue_cents") or 0),
        "d7_cents": float(week.get("subscription_revenue_cents") or 0),
        "pack_today_cents": float(today.get("credit_pack_revenue_cents") or 0),
    }


def next_daily_burncredit_at(now: datetime | None = None) -> datetime:
    """Next 10:00 PM Asia/Phnom_Penh (or tomorrow if that time has passed)."""
    current = now.astimezone(BILLING_TIMEZONE) if now else datetime.now(BILLING_TIMEZONE)
    target = current.replace(
        hour=_DAILY_BURN_HOUR, minute=0, second=0, microsecond=0
    )
    if current >= target:
        target += timedelta(days=1)
    return target


def daily_burncredit_should_send(
    now: datetime,
    last_sent_date: str | None,
) -> bool:
    """True at/after 10 PM local if today's report has not been sent."""
    current = now.astimezone(BILLING_TIMEZONE) if now.tzinfo else now.replace(
        tzinfo=BILLING_TIMEZONE
    )
    if current.hour < _DAILY_BURN_HOUR:
        return False
    return last_sent_date != current.date().isoformat()


def seconds_until_daily_burncredit_check(
    now: datetime | None = None,
    last_sent_date: str | None = None,
) -> float:
    current = now.astimezone(BILLING_TIMEZONE) if now else datetime.now(BILLING_TIMEZONE)
    if daily_burncredit_should_send(current, last_sent_date):
        return 1.0
    return max(1.0, (next_daily_burncredit_at(current) - current).total_seconds())


def start_telegram_ops_command_poller() -> None:
    """Start a single-leader getUpdates loop in this process, if an event loop is running."""
    global _POLLER_STARTED
    if _POLLER_STARTED:
        return
    try:
        from platform_api.config import get_settings

        if not get_settings().telegram_poller_enabled:
            logger.info(
                "Telegram ops poller disabled by PLATFORM_TELEGRAM_POLLER_ENABLED."
            )
            return
    except Exception:
        pass
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _POLLER_STARTED = True
    loop.create_task(_command_poll_loop(), name="telegram-ops-commands")
    loop.create_task(_daily_burncredit_loop(), name="telegram-ops-daily-burncredit")
    logger.info("Telegram ops /stats command poller scheduled.")
    logger.info("Telegram ops daily 10 PM burncredit report scheduled.")


async def _command_poll_loop() -> None:
    await asyncio.sleep(2)
    while True:
        try:
            await _poll_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Telegram ops command poll failed: %s", str(exc)[:200])
            await asyncio.sleep(5)


async def _daily_burncredit_loop() -> None:
    await asyncio.sleep(8)
    while True:
        try:
            last_sent = await _daily_sent_date(_try_redis())
            wait = seconds_until_daily_burncredit_check(last_sent_date=last_sent)
            await asyncio.sleep(wait)
            sent = await _maybe_send_daily_burncredit()
            if not sent and datetime.now(BILLING_TIMEZONE).hour >= _DAILY_BURN_HOUR:
                # Another worker may hold the claim, or it died mid-send. Retry
                # soon instead of sleeping until tomorrow (the old bug: a crash
                # at 22:00 left the claim behind and skipped the day entirely).
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Telegram daily burncredit loop failed: %s", str(exc)[:200])
            await asyncio.sleep(30)


def _daily_key(date_iso: str) -> str:
    return f"{_DAILY_SENT_KEY}:{date_iso}"


async def _daily_sent_date(redis: Any | None) -> str | None:
    now = datetime.now(BILLING_TIMEZONE)
    today = now.date().isoformat()
    if redis is None:
        return None
    try:
        raw = await redis.get(_daily_key(today))
        # "sending" is a short in-progress claim, not a completed send.
        return today if str(raw) in {"1", "b'1'"} else None
    except Exception:
        return None


async def _maybe_send_daily_burncredit() -> bool:
    now = datetime.now(BILLING_TIMEZONE)
    if now.hour < _DAILY_BURN_HOUR:
        return False
    date_iso = now.date().isoformat()
    redis = _try_redis()
    if redis is not None:
        try:
            if str(await redis.get(_daily_key(date_iso))) in {"1", "b'1'"}:
                return True
            # Short in-progress claim: a crashed sender retries after 10
            # minutes instead of blocking the day with a 48h marker.
            acquired = await redis.set(
                _daily_key(date_iso), "sending", nx=True, ex=600
            )
        except Exception:
            acquired = _I_AM_POLLER
        if not acquired:
            return False
    elif not _I_AM_POLLER:
        return False
    try:
        await _send_daily_burncredit()
    except Exception:
        if redis is not None:
            try:
                await redis.delete(_daily_key(date_iso))
            except Exception:
                pass
        raise
    if redis is not None:
        try:
            await redis.set(_daily_key(date_iso), "1", ex=172800)
        except Exception:
            pass
    logger.info("Telegram daily 10 PM burncredit report sent for %s.", date_iso)
    return True


async def _send_daily_burncredit() -> None:
    service = get_telegram_ops_service()
    if service is None:
        raise RuntimeError("Telegram ops service is not configured.")
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    stats = await fetch_burncredit_stats(pool)
    headline: list[str] = ["Daily 10:00 PM report (Asia/Phnom_Penh)"]
    try:
        users = (await fetch_ops_stats(pool))["users"]
        headline.append(
            f"new users today: <b>{users['today']}</b> · "
            f"songs today: <b>{stats['both']['songs']['today']}</b>"
        )
    except Exception as exc:
        logger.debug("Daily report user/song line skipped: %s", exc)
    try:
        revenue = await fetch_platform_revenue(pool)
        headline.append(
            f"platform revenue today: <b>${revenue['today_cents'] / 100:,.2f}</b> "
            f"(7d ${revenue['d7_cents'] / 100:,.2f})"
        )
    except Exception as exc:
        logger.debug("Daily report revenue line skipped: %s", exc)
    text = format_burncredit_message(
        env_label=environment_display_label(),
        scope="all",
        web_songs=stats["web"]["songs"],
        web_credits=stats["web"]["credits"],
        studio_songs=stats["studio"]["songs"],
        studio_credits=stats["studio"]["credits"],
        both_songs=stats["both"]["songs"],
        both_credits=stats["both"]["credits"],
        unattributed_credits=stats["unattributed"]["credits"],
        headline="\n".join(headline),
    )
    ok = await service.send_html(text)
    if not ok:
        raise RuntimeError("Telegram daily burncredit send failed.")


async def _poll_once() -> None:
    service = get_telegram_ops_service()
    if service is None:
        await asyncio.sleep(20)
        return
    redis = _try_redis()
    if not await _hold_poller_lock(redis):
        await asyncio.sleep(8)
        return
    token = service._bot_token
    chat_id = str(service._chat_id)
    offset = await _read_offset(redis)
    client = await service._client()
    try:
        response = await client.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={
                "timeout": 25,
                "offset": offset,
                "allowed_updates": '["message"]',
            },
            timeout=httpx.Timeout(35.0, connect=5.0),
        )
    except httpx.TimeoutException:
        return
    if response.status_code >= 400:
        logger.warning(
            "Telegram getUpdates failed status=%s body=%s",
            response.status_code,
            (response.text or "")[:200],
        )
        if response.status_code == 409:
            # Another process is polling with this token: we no longer own the
            # leader key, so stop pretending we do (the old sticky flag caused
            # thousands of conflicts until restart).
            await _release_leader(redis)
        await asyncio.sleep(5)
        return
    payload = response.json()
    if not payload.get("ok"):
        await asyncio.sleep(5)
        return
    updates = payload.get("result") or []
    next_offset = offset
    for item in updates:
        update_id = int(item.get("update_id") or 0)
        next_offset = max(next_offset, update_id + 1)
        message = item.get("message") or {}
        incoming_chat = str((message.get("chat") or {}).get("id") or "")
        if incoming_chat != chat_id:
            continue
        parsed = parse_ops_command(message.get("text"))
        if parsed is None:
            continue
        kind, scope = parsed
        if kind == "stats":
            await _reply_stats(service)
        elif kind == "burncredit":
            await _reply_burncredit(service, scope)
    if next_offset != offset:
        await _write_offset(redis, next_offset)


async def _reply_stats(service: Any) -> None:
    try:
        from platform_api.dependencies import get_db_pool

        stats = await fetch_ops_stats(get_db_pool())
        text = format_ops_stats_message(
            env_label=environment_display_label(),
            users=stats["users"],
            songs=stats["songs"],
        )
        await service.send_html(text)
    except Exception as exc:
        logger.warning("Telegram /stats reply failed: %s", str(exc)[:200])
        try:
            await service.send_html("Could not load stats right now. Try /stats again in a moment.")
        except Exception:
            return


async def _reply_burncredit(service: Any, scope: str) -> None:
    try:
        from platform_api.dependencies import get_db_pool

        if scope == "help":
            await service.send_html(format_burncredit_message(
                env_label=environment_display_label(),
                scope="help",
                web_songs={},
                web_credits={},
                studio_songs={},
                studio_credits={},
                both_songs={},
                both_credits={},
            ))
            return
        stats = await fetch_burncredit_stats(get_db_pool())
        text = format_burncredit_message(
            env_label=environment_display_label(),
            scope=scope,
            web_songs=stats["web"]["songs"],
            web_credits=stats["web"]["credits"],
            studio_songs=stats["studio"]["songs"],
            studio_credits=stats["studio"]["credits"],
            both_songs=stats["both"]["songs"],
            both_credits=stats["both"]["credits"],
            unattributed_credits=stats["unattributed"]["credits"],
        )
        await service.send_html(text)
    except Exception as exc:
        logger.warning("Telegram /burncredit reply failed: %s", str(exc)[:200])
        try:
            await service.send_html(
                "Could not load credit burn right now. Try /burncredit again in a moment."
            )
        except Exception:
            return


def _try_redis() -> Any | None:
    try:
        from platform_api.dependencies import get_redis

        return get_redis()
    except Exception:
        return None


async def _hold_poller_lock(redis: Any | None) -> bool:
    global _I_AM_POLLER
    if redis is None:
        # No Redis: stay a poller in this process. The offset is also kept in
        # memory so updates are confirmed instead of being replayed forever.
        _I_AM_POLLER = True
        return True
    try:
        if _I_AM_POLLER:
            if await _renew_leader(redis):
                return True
            _I_AM_POLLER = False
        acquired = await redis.set(
            _LOCK_KEY, _LOCK_VALUE, ex=_LOCK_TTL_S, nx=True
        )
        if acquired:
            _I_AM_POLLER = True
            await _register_bot_commands(redis)
            return True
        return False
    except Exception:
        # Redis trouble must fail closed: assuming leadership here is what made
        # API workers and job workers poll the same bot simultaneously.
        _I_AM_POLLER = False
        return False


# Compare-and-renew / compare-and-delete keep a stale holder from extending or
# deleting a lock that now belongs to another process.
_LOCK_RENEW_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end"
)
_LOCK_RELEASE_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)


async def _renew_leader(redis: Any) -> bool:
    try:
        result = await redis.eval(
            _LOCK_RENEW_LUA, 1, _LOCK_KEY, _LOCK_VALUE, _LOCK_TTL_S
        )
        return bool(result)
    except Exception:
        try:
            current = await redis.get(_LOCK_KEY)
            if str(current) != _LOCK_VALUE:
                return False
            await redis.expire(_LOCK_KEY, _LOCK_TTL_S)
            return True
        except Exception:
            return False


async def _release_leader(redis: Any | None) -> None:
    global _I_AM_POLLER
    _I_AM_POLLER = False
    if redis is None:
        return
    try:
        await redis.eval(_LOCK_RELEASE_LUA, 1, _LOCK_KEY, _LOCK_VALUE)
    except Exception:
        try:
            if str(await redis.get(_LOCK_KEY)) == _LOCK_VALUE:
                await redis.delete(_LOCK_KEY)
        except Exception:
            pass


async def _register_bot_commands(redis: Any | None) -> None:
    service = get_telegram_ops_service()
    if service is None:
        return
    try:
        client = await service._client()
        await client.post(
            f"https://api.telegram.org/bot{service._bot_token}/setMyCommands",
            json={
                "commands": [
                    {
                        "command": "stats",
                        "description": "Users and songs: today / yesterday / 7d / 30d",
                    },
                    {
                        "command": "burncredit",
                        "description": "Credit burn + USD: /burncredit web|studio|both",
                    },
                ]
            },
            timeout=httpx.Timeout(8.0, connect=4.0),
        )
    except Exception as exc:
        logger.debug("Telegram setMyCommands skipped: %s", exc)


async def _read_offset(redis: Any | None) -> int:
    global _LAST_UPDATE_ID
    if redis is None:
        return _LAST_UPDATE_ID
    try:
        raw = await redis.get(_OFFSET_KEY)
        return int(raw or 0) if raw is not None else _LAST_UPDATE_ID
    except Exception:
        return _LAST_UPDATE_ID


async def _write_offset(redis: Any | None, offset: int) -> None:
    global _LAST_UPDATE_ID
    _LAST_UPDATE_ID = int(offset)
    if redis is None:
        return
    try:
        await redis.set(_OFFSET_KEY, str(int(offset)))
    except Exception:
        return
