"""Telegram /stats and /burncredit commands, plus the 10 PM daily burn report."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import httpx

from platform_api.config import environment_display_label
from platform_api.services.billing_calendar import BILLING_TIMEZONE
from platform_api.services.credit_units import units_to_credits
from platform_api.services.telegram_ops_alert_service import (
    _esc,
    _now_label,
    get_telegram_ops_service,
)
from platform_api.services.signup_domain_guard import (
    add_blocked_email_domain,
    suspend_user_by_id,
)

logger = logging.getLogger(__name__)

_POLLER_STARTED = False
_I_AM_POLLER = False
_LOCK_KEY = "telegram:ops:poller"
_OFFSET_KEY = "telegram:ops:update_offset"
_DAILY_SENT_KEY = "telegram:ops:burncredit_daily"
_DAILY_BURN_HOUR = 22
_ALLOWED_COMMANDS = frozenset({"/stats", "/report", "/summary"})

_WINDOW_KEYS = ("today", "yesterday", "d7", "d30")
_TABLE_HEADERS = ("Today", "Yesterday", "Last 7 Days", "Last 30 Days")
_BURN_COMMANDS = frozenset({"/burncredit", "/burncredits"})
_BLOCKDOMAIN_COMMANDS = frozenset({"/blockdomain", "blockdomain"})
_CB_BLOCK = "sg_block:"
_CB_SUSPEND_USER = "sg_suspend_user:"
_USD_PER_SONG_REQUEST = 0.06
_PP_DATE = "(created_at AT TIME ZONE 'Asia/Phnom_Penh')::date"
_PP_TODAY = "(NOW() AT TIME ZONE 'Asia/Phnom_Penh')::date"

_COUNT_SQL = """
SELECT
  COUNT(*) FILTER (
    WHERE (created_at AT TIME ZONE 'Asia/Phnom_Penh')::date
      = (NOW() AT TIME ZONE 'Asia/Phnom_Penh')::date
  )::int AS today,
  COUNT(*) FILTER (
    WHERE (created_at AT TIME ZONE 'Asia/Phnom_Penh')::date
      = (NOW() AT TIME ZONE 'Asia/Phnom_Penh')::date - 1
  )::int AS yesterday,
  COUNT(*) FILTER (
    WHERE (created_at AT TIME ZONE 'Asia/Phnom_Penh')::date
      > (NOW() AT TIME ZONE 'Asia/Phnom_Penh')::date - 7
  )::int AS d7,
  COUNT(*) FILTER (
    WHERE (created_at AT TIME ZONE 'Asia/Phnom_Penh')::date
      > (NOW() AT TIME ZONE 'Asia/Phnom_Penh')::date - 30
  )::int AS d30
FROM {table}
{where}
"""


def _window_agg(expr: str) -> str:
    return f"""
  {expr} FILTER (WHERE {_PP_DATE} = {_PP_TODAY}) AS today,
  {expr} FILTER (WHERE {_PP_DATE} = {_PP_TODAY} - 1) AS yesterday,
  {expr} FILTER (WHERE {_PP_DATE} > {_PP_TODAY} - 7) AS d7,
  {expr} FILTER (WHERE {_PP_DATE} > {_PP_TODAY} - 30) AS d30
"""


def _window_sum(expr: str) -> str:
    """FILTER must attach to the aggregate (SUM), not COALESCE."""
    return f"""
  COALESCE({expr} FILTER (WHERE {_PP_DATE} = {_PP_TODAY}), 0) AS today,
  COALESCE({expr} FILTER (WHERE {_PP_DATE} = {_PP_TODAY} - 1), 0) AS yesterday,
  COALESCE({expr} FILTER (WHERE {_PP_DATE} > {_PP_TODAY} - 7), 0) AS d7,
  COALESCE({expr} FILTER (WHERE {_PP_DATE} > {_PP_TODAY} - 30), 0) AS d30
"""


_WEB_CREDIT_SQL = f"""
SELECT
{_window_sum("SUM(-amount)")}
FROM credit_transactions
WHERE reason LIKE 'consumed_web_music%'
   OR reason LIKE 'refunded_web_music%'
"""

_STUDIO_CREDIT_SQL = f"""
SELECT
  (COALESCE(SUM(amount) FILTER (WHERE direction = 'debit' AND {_PP_DATE} = {_PP_TODAY}), 0)
   - COALESCE(SUM(amount) FILTER (WHERE direction = 'refund' AND {_PP_DATE} = {_PP_TODAY}), 0))::bigint AS today,
  (COALESCE(SUM(amount) FILTER (WHERE direction = 'debit' AND {_PP_DATE} = {_PP_TODAY} - 1), 0)
   - COALESCE(SUM(amount) FILTER (WHERE direction = 'refund' AND {_PP_DATE} = {_PP_TODAY} - 1), 0))::bigint AS yesterday,
  (COALESCE(SUM(amount) FILTER (WHERE direction = 'debit' AND {_PP_DATE} > {_PP_TODAY} - 7), 0)
   - COALESCE(SUM(amount) FILTER (WHERE direction = 'refund' AND {_PP_DATE} > {_PP_TODAY} - 7), 0))::bigint AS d7,
  (COALESCE(SUM(amount) FILTER (WHERE direction = 'debit' AND {_PP_DATE} > {_PP_TODAY} - 30), 0)
   - COALESCE(SUM(amount) FILTER (WHERE direction = 'refund' AND {_PP_DATE} > {_PP_TODAY} - 30), 0))::bigint AS d30
FROM credit_transactions
WHERE direction IN ('debit', 'refund')
  AND COALESCE(reason, '') NOT LIKE 'consumed_web_music%'
  AND COALESCE(reason, '') NOT LIKE 'refunded_web_music%'
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
    if first in _BLOCKDOMAIN_COMMANDS:
        domain = parts[1].strip().lower() if len(parts) > 1 else ""
        if domain and "." in domain:
            return ("blockdomain", domain)
        return ("blockdomain", "help")
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
) -> str:
    if scope == "help":
        return "🔥 <b>BURN CREDIT</b>\n" + _BURN_HELP
    sections: list[str] = [
        f"🔥 <b>BURN CREDIT</b> · {_esc(env_label)}",
    ]
    if headline:
        sections.append(_esc(headline))
    sections.extend(
        [
            "Each period: songs generated · credits burned. USD = songs × $0.06 / request.",
            "Asia/Phnom_Penh calendar days. Last 7 / 30 include today.",
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
        _COUNT_SQL.format(
            table="users",
            where="WHERE COALESCE(status, 'active') <> 'deleted' AND COALESCE(role, 'user') = 'user'",
        )
    )
    songs = await pool.fetchrow(_COUNT_SQL.format(table="suno_tasks", where=""))
    return {"users": _row_windows(users), "songs": _row_windows(songs)}


def _add_windows(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {key: int(left.get(key, 0)) + int(right.get(key, 0)) for key in _WINDOW_KEYS}


def _add_credit_windows(
    left: dict[str, float],
    right: dict[str, float],
) -> dict[str, float]:
    return {key: float(left.get(key, 0)) + float(right.get(key, 0)) for key in _WINDOW_KEYS}


async def fetch_burncredit_stats(pool: Any) -> dict[str, dict[str, dict[str, float]]]:
    """Songs by suno_tasks.source; web/studio credits from credit_transactions."""
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
    web_credit_row = _row_windows(await pool.fetchrow(_WEB_CREDIT_SQL))
    web_credits = {key: float(web_credit_row[key]) for key in _WINDOW_KEYS}
    studio_units = _row_windows(await pool.fetchrow(_STUDIO_CREDIT_SQL))
    studio_credits = {key: units_to_credits(studio_units[key]) for key in _WINDOW_KEYS}
    return {
        "web": {"songs": web_songs, "credits": web_credits},
        "studio": {"songs": studio_songs, "credits": studio_credits},
        "both": {
            "songs": _add_windows(web_songs, studio_songs),
            "credits": _add_credit_windows(web_credits, studio_credits),
        },
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
            await _maybe_send_daily_burncredit()
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
        return today if raw else None
    except Exception:
        return None


async def _maybe_send_daily_burncredit() -> None:
    now = datetime.now(BILLING_TIMEZONE)
    if now.hour < _DAILY_BURN_HOUR:
        return
    date_iso = now.date().isoformat()
    redis = _try_redis()
    if redis is not None:
        try:
            acquired = await redis.set(_daily_key(date_iso), "1", nx=True, ex=172800)
        except Exception:
            acquired = _I_AM_POLLER
        if not acquired:
            return
    elif not _I_AM_POLLER:
        return
    try:
        await _send_daily_burncredit()
        logger.info("Telegram daily 10 PM burncredit report sent for %s.", date_iso)
    except Exception:
        if redis is not None:
            try:
                await redis.delete(_daily_key(date_iso))
            except Exception:
                pass
        raise


async def _send_daily_burncredit() -> None:
    service = get_telegram_ops_service()
    if service is None:
        raise RuntimeError("Telegram ops service is not configured.")
    from platform_api.dependencies import get_db_pool

    stats = await fetch_burncredit_stats(get_db_pool())
    text = format_burncredit_message(
        env_label=environment_display_label(),
        scope="all",
        web_songs=stats["web"]["songs"],
        web_credits=stats["web"]["credits"],
        studio_songs=stats["studio"]["songs"],
        studio_credits=stats["studio"]["credits"],
        both_songs=stats["both"]["songs"],
        both_credits=stats["both"]["credits"],
        headline="Daily 10:00 PM report (Asia/Phnom_Penh)",
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
                "allowed_updates": '["message", "callback_query"]',
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
        callback = item.get("callback_query") or {}
        if callback:
            cb_chat = str((((callback.get("message") or {}).get("chat")) or {}).get("id") or "")
            if cb_chat == chat_id:
                await _handle_callback_query(service, callback)
            continue
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
        elif kind == "blockdomain":
            await _reply_blockdomain(service, scope)
    if next_offset != offset:
        await _write_offset(redis, next_offset)


def _callback_author(callback: dict[str, Any]) -> str:
    who = (callback.get("from") or {}) or {}
    return str(who.get("username") or who.get("first_name") or "?")


def _callback_target(callback: dict[str, Any]) -> tuple[str, int]:
    message = callback.get("message") or {}
    chat_id = str(((message.get("chat") or {}).get("id")) or "")
    message_id = int((message or {}).get("message_id") or 0)
    return chat_id, message_id


async def _answer_callback(service: Any, callback: dict[str, Any], text: str) -> None:
    callback_id = str((callback or {}).get("id") or "")
    if not callback_id:
        return
    try:
        client = await service._client()
        await client.post(
            f"https://api.telegram.org/bot{service._bot_token}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": str(text)[:200]},
            timeout=httpx.Timeout(8.0, connect=4.0),
        )
    except Exception as exc:
        logger.debug("Telegram answerCallbackQuery skipped: %s", exc)


async def _clear_callback_buttons(service: Any, chat_id: str, message_id: int) -> None:
    if not chat_id or not message_id:
        return
    try:
        client = await service._client()
        await client.post(
            f"https://api.telegram.org/bot{service._bot_token}/editMessageReplyMarkup",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": {"inline_keyboard": []},
            },
            timeout=httpx.Timeout(8.0, connect=4.0),
        )
    except Exception as exc:
        logger.debug("Telegram clear callback buttons skipped: %s", exc)


async def _handle_callback_query(service: Any, callback: dict[str, Any]) -> None:
    """Handle signup-alert inline actions: block a domain or suspend a user."""
    data = str((callback or {}).get("data") or "")
    who = _callback_author(callback)
    chat_id, message_id = _callback_target(callback)
    try:
        if data.startswith(_CB_BLOCK):
            domain = data[len(_CB_BLOCK):].strip().lower()
            ok, message = await add_blocked_email_domain(domain)
            await _answer_callback(
                service,
                callback,
                f"{domain}: {'blocked' if ok else 'not changed'}",
            )
            await _clear_callback_buttons(service, chat_id, message_id)
            await service.send_html(
                f"⛔ <b>Domain blocked</b> by @{_esc(who)}\n{_esc(message)}"
            )
        elif data.startswith(_CB_SUSPEND_USER):
            user_id = data[len(_CB_SUSPEND_USER):].strip()
            ok, message = await suspend_user_by_id(
                user_id,
                "Suspected disposable-domain signup (Telegram ops)",
            )
            await _answer_callback(
                service,
                callback,
                f"User: {'suspended' if ok else 'not changed'}",
            )
            await _clear_callback_buttons(service, chat_id, message_id)
            await service.send_html(
                f"🚫 <b>User suspended</b> by @{_esc(who)}\n{_esc(message)}"
            )
        else:
            await _answer_callback(service, callback, "Unknown action")
    except Exception as exc:
        logger.warning("Telegram callback action failed: %s", str(exc)[:200])
        await _answer_callback(service, callback, "Action failed")


async def _reply_blockdomain(service: Any, scope: str) -> None:
    """/blockdomain <domain> — add a suspected email domain to the signup blocklist."""
    if scope == "help":
        await service.send_html(
            "Use <code>/blockdomain example.com</code> to add an email domain "
            "to the signup blocklist."
        )
        return
    try:
        ok, message = await add_blocked_email_domain(scope)
        await service.send_html(f"{'⛔' if ok else 'ℹ️'} {_esc(message)}")
    except Exception as exc:
        logger.warning("Telegram /blockdomain failed: %s", str(exc)[:200])
        await service.send_html("Could not update the signup blocklist right now.")


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
        return True
    try:
        if _I_AM_POLLER:
            await redis.expire(_LOCK_KEY, 40)
            return True
        acquired = await redis.set(_LOCK_KEY, str(os.getpid()), ex=40, nx=True)
        if acquired:
            _I_AM_POLLER = True
            await _register_bot_commands(redis)
            return True
        return False
    except Exception:
        return True


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
                    {
                        "command": "blockdomain",
                        "description": "Add a suspected email domain to the signup blocklist",
                    },
                ]
            },
            timeout=httpx.Timeout(8.0, connect=4.0),
        )
    except Exception as exc:
        logger.debug("Telegram setMyCommands skipped: %s", exc)


async def _read_offset(redis: Any | None) -> int:
    if redis is None:
        return 0
    try:
        raw = await redis.get(_OFFSET_KEY)
        return int(raw or 0)
    except Exception:
        return 0


async def _write_offset(redis: Any | None, offset: int) -> None:
    if redis is None:
        return
    try:
        await redis.set(_OFFSET_KEY, str(int(offset)))
    except Exception:
        return
