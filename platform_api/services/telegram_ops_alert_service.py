"""Fire-and-forget Telegram group feed for signups, payments, and credit burns.

Delivery is **production-only**: sandbox/staging share the same bot token and
chat id as production, so `get_telegram_ops_service()` returns ``None`` outside
production to keep sandbox activity out of the live ops channel.

Never raises into product paths. Missing token/chat, env kill-switch, or
system_settings ``telegram_ops_alerts_enabled=false`` all no-op.

Web-music v2 credit/subscription modules are not always in this tree; those
are wrapped at process start when importable so sandbox/prod leftover files
still post.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx

from platform_api.config import (
    environment_display_label,
    get_settings,
    is_production,
)
from platform_api.services.credit_units import format_display_credits, units_to_credits

logger = logging.getLogger(__name__)

# httpx logs every request URL at INFO, and the Telegram bot token is part of the
# URL (`/bot<token>/sendMessage`). Production journals were retaining the live
# token that way, so keep httpx request logs out of ops output entirely.
logging.getLogger("httpx").setLevel(logging.WARNING)

KILL_SWITCH_SETTING_KEY = "telegram_ops_alerts_enabled"
_SETTING_CACHE_SECONDS = 15
_PHNOM_PENH = timezone(timedelta(hours=7))
_TELEGRAM_SEND_URL = "https://api.telegram.org/bot{token}/sendMessage"
_PATCHED_ATTR = "_telegram_ops_patched"

_SETTING_CACHE: dict[str, Any] = {"expires_at": 0.0, "enabled": True}
_V2_HOOKS_INSTALLED = False

# Before this, every message built and closed its own AsyncClient, paying DNS +
# TLS for each one (~330 ms from the production VPS to api.telegram.org).
_SHARED_CLIENT: httpx.AsyncClient | None = None
_SEND_LOCK: asyncio.Lock | None = None
_LAST_SEND_AT = 0.0
# ~24 messages/minute per process, just under Telegram's ~20/min group limit
# when the account-level burst allowance is shared across workers.
_MIN_SEND_INTERVAL_S = float(
    os.environ.get("PLATFORM_TELEGRAM_MIN_SEND_INTERVAL_S", "2.5")
)
# High-volume, low-value events are coalesced into one message per window. Money
# events (signup/login/payment/refund/quota) and alerts are never delayed.
_BULK_KINDS = frozenset({"spend", "download"})
_BULK_WINDOW_S = float(os.environ.get("PLATFORM_TELEGRAM_BULK_WINDOW_S", "2.0"))
_MAX_BATCH_CHARS = 3800
_BULK_BUFFER: list[dict[str, Any]] = []
_BULK_TASK: asyncio.Task[Any] | None = None
_PENDING_TASKS: set[asyncio.Task[Any]] = set()
_SNAPSHOT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_SNAPSHOT_TTL_S = 30.0


def classify_activity(reason: str, metadata: dict[str, Any] | None = None) -> str:
    """Map a credit reason / metadata blob to a short activity label."""
    parts = [str(reason or "")]
    if metadata:
        parts.append(str(metadata.get("operation") or metadata.get("operation_type") or ""))
        parts.append(str(metadata.get("purpose") or ""))
    blob = " ".join(parts).lower()
    if any(token in blob for token in ("lyric", "lyrics", "draft", "title", "album")):
        return "lyric"
    if any(token in blob for token in ("background", "thumbnail", "image")):
        return "image"
    if "merge" in blob:
        return "video_merge"
    if "video" in blob:
        return "video"
    if any(token in blob for token in ("music", "song", "suno", "generation", "web_music")):
        return "music"
    if "channel" in blob:
        return "channel_setup"
    cleaned = str(reason or "").strip()
    return cleaned[:40] if cleaned else "other"


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def _now_label() -> str:
    return datetime.now(_PHNOM_PENH).strftime("%d %b %Y %H:%M:%S +07")


def _user_short(user_id: Any) -> str:
    text = str(user_id or "").strip()
    return text[:8] if text else "—"


def format_ops_message(
    *,
    kind: str,
    env_label: str,
    account_status: str | None = None,
    email: str | None = None,
    display_name: str | None = None,
    activity: str | None = None,
    credits_label: str | None = None,
    pool: str | None = None,
    reason: str | None = None,
    plan_name: str | None = None,
    amount_label: str | None = None,
    product: str | None = None,
    user_id: Any = None,
    extra_lines: list[str] | None = None,
) -> str:
    """Build a compact HTML Telegram message."""
    kind_key = (kind or "event").strip().lower()
    status = (account_status or "").strip().upper()
    if kind_key == "signup":
        title = f"🆕 <b>SIGNUP</b> · {_esc(env_label)}"
    elif kind_key == "login":
        title = f"🔑 <b>LOGIN</b> · {_esc(env_label)}"
    elif kind_key == "payment":
        title = f"💳 <b>PAID</b> · {_esc(env_label)}"
    elif kind_key == "refund":
        title = f"♻️ <b>REFUND</b> · {_esc(env_label)}"
    elif kind_key == "plan_quota":
        title = f"📦 <b>PLAN QUOTA</b> · {_esc(env_label)}"
    elif kind_key == "download":
        title = f"⬇️ <b>DOWNLOAD</b> · {_esc(env_label)}"
    else:
        badge = f" · <b>{_esc(status)}</b>" if status else ""
        title = f"🔥 <b>SPEND</b>{badge} · {_esc(env_label)}"

    lines = [title]
    if email:
        lines.append(f"email: <code>{_esc(email)}</code>")
    if display_name:
        lines.append(f"name: {_esc(display_name)}")
    if status and kind_key in {"signup", "login", "payment", "refund", "plan_quota"}:
        lines.append(f"status: <b>{_esc(status)}</b>")
    if activity:
        lines.append(f"activity: <b>{_esc(activity)}</b>")
    if credits_label:
        lines.append(f"credits: {_esc(credits_label)}")
    if pool:
        lines.append(f"pool: {_esc(pool)}")
    if plan_name:
        lines.append(f"plan: {_esc(plan_name)}")
    if amount_label:
        lines.append(f"amount: {_esc(amount_label)}")
    if product:
        lines.append(f"product: {_esc(product)}")
    if reason:
        lines.append(f"reason: {_esc(reason)}")
    if extra_lines:
        lines.extend(extra_lines)
    lines.append(f"user: <code>{_esc(user_id)}</code> ({_esc(_user_short(user_id))})")
    lines.append(f"time: {_esc(_now_label())}")
    return "\n".join(lines)


class TelegramOpsAlertService:
    """Posts ops events to a Telegram group chat."""

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        enabled: bool,
        env_label: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._bot_token = (bot_token or "").strip()
        self._chat_id = str(chat_id or "").strip()
        self._enabled = bool(enabled)
        self._env_label = env_label or "Unknown"
        self._http_client = http_client
        # The default client is process-wide and shared; never close it from a
        # per-message service instance.
        self._owns_client = False

    @property
    def configured(self) -> bool:
        return bool(self._bot_token and self._chat_id and self._enabled)

    async def close(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def send_html(
        self,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        kind: str = "message",
    ) -> bool:
        if not self.configured:
            return False
        if not await _runtime_enabled():
            return False
        chunks = _chunk_text(text)
        if not chunks:
            return False
        # A long report is split instead of truncated, so no line silently
        # disappears from the ops channel.
        for index, chunk in enumerate(chunks):
            markup = reply_markup if index == len(chunks) - 1 else None
            ok, status = await self._post(chunk, markup)
            await _log_delivery(
                self._chat_id,
                kind=kind,
                text=chunk,
                status="sent" if ok else "failed",
                http_status=status,
            )
            if not ok:
                return False
        return True

    async def _post(
        self, body: str, reply_markup: dict[str, Any] | None = None
    ) -> tuple[bool, int | None]:
        client = await self._client()
        url = _TELEGRAM_SEND_URL.format(token=self._bot_token)
        payload: dict[str, Any] = {
            "chat_id": self._chat_id,
            "text": body,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        global _LAST_SEND_AT
        async with _send_lock():
            wait = _MIN_SEND_INTERVAL_S - (time.monotonic() - _LAST_SEND_AT)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                response = await client.post(url, json=payload)
                if response.status_code == 429:
                    delay = min(10.0, max(1.0, _retry_after_seconds(response)))
                    logger.warning(
                        "Telegram 429; retrying in %.1fs", delay
                    )
                    await asyncio.sleep(delay)
                    response = await client.post(url, json=payload)
                elif response.status_code >= 500:
                    await asyncio.sleep(1.0)
                    response = await client.post(url, json=payload)
            finally:
                _LAST_SEND_AT = time.monotonic()
        if response.status_code >= 400:
            logger.warning(
                "Telegram ops post failed status=%s body=%s",
                response.status_code,
                (response.text or "")[:200],
            )
            return False, response.status_code
        return True, response.status_code

    async def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = _shared_client()
        return self._http_client


def _shared_client() -> httpx.AsyncClient:
    """Process-wide keep-alive client (one TLS handshake, then reuse)."""
    global _SHARED_CLIENT
    if _SHARED_CLIENT is None or _SHARED_CLIENT.is_closed:
        _SHARED_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=4.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=60.0,
            ),
        )
    return _SHARED_CLIENT


def _send_lock() -> asyncio.Lock:
    global _SEND_LOCK
    if _SEND_LOCK is None:
        _SEND_LOCK = asyncio.Lock()
    return _SEND_LOCK


def _retry_after_seconds(response: Any) -> float:
    try:
        data = response.json()
        return float(((data.get("parameters") or {}).get("retry_after")) or 0)
    except Exception:
        return 0.0


async def _log_delivery(
    chat_id: str,
    *,
    kind: str,
    text: str,
    status: str,
    http_status: int | None = None,
) -> None:
    """Best-effort audit row; never blocks or fails a product path."""
    try:
        from platform_api.dependencies import get_db_pool

        pool = get_db_pool()
        await pool.execute(
            """
            INSERT INTO telegram_ops_messages
                (kind, chat_id, text, status, http_status)
            VALUES ($1, $2, $3, $4, $5)
            """,
            (kind or "message")[:32],
            str(chat_id)[:64],
            (text or "")[:3500],
            status,
            http_status,
        )
    except Exception as exc:
        logger.debug("Telegram delivery log skipped: %s", exc)


def _chunk_text(text: str, limit: int = 4000) -> list[str]:
    """Split on line boundaries so nothing is truncated at Telegram's cap."""
    body = (text or "").strip()
    if not body:
        return []
    if len(body) <= limit:
        return [body]
    chunks: list[str] = []
    current = ""
    for line in body.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    return chunks


def _telegram_delivery_allowed() -> bool:
    """Whether this process may post to the ops Telegram channel.

    Sandbox/staging share the production bot token + chat id, so a bare
    "configured" check let non-production traffic (signups, spend feed, sweeps,
    health reports) land in the live ops channel. Delivery is production-only;
    the admin panel and settings still expose configuration everywhere.
    """
    try:
        return is_production()
    except Exception:
        # Settings resolution failed: fall back to the raw env var and fail closed.
        return (os.environ.get("PLATFORM_ENVIRONMENT") or "").strip().lower() in {
            "production",
            "prod",
        }


def get_telegram_ops_service() -> TelegramOpsAlertService | None:
    # Only production may deliver to the shared ops channel (see
    # `_telegram_delivery_allowed`). Returning ``None`` here makes every caller
    # (activity feed, health report, sweeps, /stats poller) a no-op on sandbox.
    if not _telegram_delivery_allowed():
        return None
    token = (os.environ.get("PLATFORM_TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = str(os.environ.get("PLATFORM_TELEGRAM_CHAT_ID") or "").strip()
    raw_enabled = (os.environ.get("PLATFORM_TELEGRAM_OPS_ENABLED") or "true").strip().lower()
    env_enabled = raw_enabled not in {"0", "false", "no", "off"}
    if not token or not chat_id:
        try:
            settings = get_settings()
            token = token or (settings.telegram_bot_token or "").strip()
            chat_id = chat_id or str(settings.telegram_chat_id or "").strip()
            env_enabled = env_enabled and bool(settings.telegram_ops_enabled)
        except Exception:
            pass
    if not token or not chat_id or not env_enabled:
        return None
    try:
        env_label = environment_display_label()
    except Exception:
        env_label = "Unknown"
    return TelegramOpsAlertService(
        bot_token=token,
        chat_id=chat_id,
        enabled=True,
        env_label=env_label,
    )


async def _runtime_enabled() -> bool:
    now = time.monotonic()
    if now < float(_SETTING_CACHE.get("expires_at") or 0):
        return bool(_SETTING_CACHE.get("enabled", True))
    enabled = True
    try:
        from platform_api.dependencies import get_db_pool

        pool = get_db_pool()
        row = await pool.fetchrow(
            "SELECT value, value_type FROM system_settings WHERE key = $1",
            KILL_SWITCH_SETTING_KEY,
        )
        if row is not None:
            raw = str(row["value"] or "").strip().lower()
            enabled = raw not in {"false", "0", "off", "no"}
    except Exception:
        enabled = True
    _SETTING_CACHE["enabled"] = enabled
    _SETTING_CACHE["expires_at"] = now + _SETTING_CACHE_SECONDS
    return enabled


async def _user_snapshot(user_id: Any) -> dict[str, Any]:
    snapshot = {
        "email": None,
        "display_name": None,
        "account_status": "FREE",
        "has_web_sub": False,
        "has_studio_license": False,
    }
    if not user_id:
        return snapshot
    key = str(user_id)
    now = time.monotonic()
    cached = _SNAPSHOT_CACHE.get(key)
    if cached is not None and now - cached[0] < _SNAPSHOT_TTL_S:
        return cached[1]
    fresh = False
    try:
        from platform_api.dependencies import get_db_pool

        pool = get_db_pool()
        # One round trip instead of three: the web-subscription and licence
        # probes are EXISTS subselects on the same user row.
        row = await pool.fetchrow(
            """
            SELECT u.email,
                   u.display_name,
                   EXISTS(
                     SELECT 1 FROM licenses l
                     WHERE l.user_id = u.id AND l.status = 'active'
                   ) AS has_studio_license,
                   EXISTS(
                     SELECT 1 FROM web_subscriptions w
                     WHERE w.user_id = $2
                       AND w.status = 'active'
                       AND w.current_period_end > NOW()
                   ) AS has_web_sub
            FROM users u
            WHERE u.id = $1
            """,
            user_id if isinstance(user_id, UUID) else UUID(str(user_id)),
            str(user_id),
        )
        if row is not None:
            snapshot["email"] = row["email"]
            snapshot["display_name"] = row["display_name"]
            snapshot["has_studio_license"] = bool(row["has_studio_license"])
            snapshot["has_web_sub"] = bool(row["has_web_sub"])
            snapshot["account_status"] = (
                "PAID"
                if snapshot["has_web_sub"] or snapshot["has_studio_license"]
                else "FREE"
            )
            fresh = True
    except Exception as exc:
        logger.debug("Telegram ops user snapshot skipped: %s", exc)
    if fresh:
        _SNAPSHOT_CACHE[key] = (now, snapshot)
        if len(_SNAPSHOT_CACHE) > 512:
            for stale in list(_SNAPSHOT_CACHE)[:256]:
                _SNAPSHOT_CACHE.pop(stale, None)
    return snapshot


def schedule_ops_message(text: str, *, kind: str = "message") -> None:
    """Queue a Telegram post without blocking the caller."""
    if get_telegram_ops_service() is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _run() -> None:
        service = get_telegram_ops_service()
        if service is None:
            return
        try:
            await service.send_html(text, kind=kind)
        except Exception as exc:
            logger.warning("Telegram ops post failed: %s", str(exc)[:200])

    _spawn(loop, _run(), "telegram-ops-alert")


def _spawn(loop: asyncio.AbstractEventLoop, coro: Any, name: str) -> asyncio.Task[Any]:
    task = loop.create_task(coro, name=name)
    _PENDING_TASKS.add(task)
    task.add_done_callback(_PENDING_TASKS.discard)
    return task


# Provider-capacity failures (no paid Suno account / no credits) hit every song
# in a batch; debounce so ops gets one page per window instead of a flood.
_PROVIDER_CAPACITY_ALERT_COOLDOWN_S = 900.0
_provider_capacity_alert_last: dict[str, float] = {}


def notify_provider_capacity_failure(
    *,
    failure_type: str = "provider_capacity",
    error_message: str = "",
    batch_id: Any = None,
    song_id: Any = None,
) -> None:
    """Debounced ops alert when the music provider has no usable account.

    Operational, not user error: a missing paid Suno account or an unfunded key
    makes every song fail, so page ops once per cooldown window rather than once
    per song.
    """
    key = str(failure_type or "provider_capacity").strip() or "provider_capacity"
    now = time.monotonic()
    last = _provider_capacity_alert_last.get(key, 0.0)
    if last and (now - last) < _PROVIDER_CAPACITY_ALERT_COOLDOWN_S:
        return
    _provider_capacity_alert_last[key] = now

    detail = str(error_message or "").strip()[:300] or "no usable Suno account / credits"
    lines = [
        f"🚨 <b>SUNO PROVIDER UNAVAILABLE</b> · {_esc(environment_display_label())}",
        f"issue: <b>{_esc(key)}</b>",
        f"detail: {_esc(detail)}",
    ]
    if batch_id:
        lines.append(f"batch: <code>{_esc(batch_id)}</code>")
    if song_id:
        lines.append(f"song: <code>{_esc(song_id)}</code>")
    lines.append(f"time: {_esc(_now_label())}")
    schedule_ops_message("\n".join(lines), kind="provider_capacity")


def _schedule_enriched(
    kind: str,
    *,
    user_id: Any,
    reply_markup: dict[str, Any] | None = None,
    **fields: Any,
) -> None:
    if get_telegram_ops_service() is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    if kind in _BULK_KINDS:
        # Spend/download events arrive in bursts. Buffer them for a short
        # window and post one combined message, so a batch generation cannot
        # trip Telegram's group rate limit (and drop alerts on 429).
        _BULK_BUFFER.append(
            {"kind": kind, "user_id": user_id, "fields": dict(fields)}
        )
        global _BULK_TASK
        if _BULK_TASK is None or _BULK_TASK.done():
            _BULK_TASK = _spawn(
                loop, _flush_bulk_after_window(), "telegram-ops-bulk"
            )
        return

    async def _run() -> None:
        snapshot = await _user_snapshot(user_id)
        account_status = fields.pop("account_status", None) or snapshot["account_status"]
        text = format_ops_message(
            kind=kind,
            env_label=environment_display_label(),
            user_id=user_id,
            email=fields.pop("email", None) or snapshot["email"],
            display_name=fields.pop("display_name", None) or snapshot["display_name"],
            account_status=account_status,
            **fields,
        )
        service = get_telegram_ops_service()
        if service is None:
            return
        try:
            await service.send_html(text, reply_markup=reply_markup, kind=kind)
        except Exception as exc:
            logger.warning("Telegram ops post failed: %s", str(exc)[:200])

    _spawn(loop, _run(), "telegram-ops-alert")


async def _flush_bulk_after_window() -> None:
    """Render buffered spend/download facts into as few messages as possible."""
    await asyncio.sleep(_BULK_WINDOW_S)
    items = _BULK_BUFFER[:]
    _BULK_BUFFER.clear()
    if not items:
        return
    service = get_telegram_ops_service()
    if service is None:
        return
    env_label = environment_display_label()
    rendered: list[str] = []
    for item in items:
        try:
            snapshot = await _user_snapshot(item["user_id"])
            fields = dict(item["fields"])
            rendered.append(
                format_ops_message(
                    kind=item["kind"],
                    env_label=env_label,
                    user_id=item["user_id"],
                    email=fields.pop("email", None) or snapshot["email"],
                    display_name=fields.pop("display_name", None)
                    or snapshot["display_name"],
                    account_status=fields.pop("account_status", None)
                    or snapshot["account_status"],
                    **fields,
                )
            )
        except Exception as exc:
            logger.debug("Telegram bulk render skipped: %s", exc)
    batch = ""
    for text in rendered:
        candidate = f"{batch}\n\n{text}" if batch else text
        if len(candidate) > _MAX_BATCH_CHARS and batch:
            await _send_text(service, batch, kind="spend_download")
            batch = text
        else:
            batch = candidate
    if batch:
        await _send_text(service, batch, kind="spend_download")


async def _send_text(
    service: TelegramOpsAlertService, text: str, *, kind: str = "message"
) -> None:
    try:
        await service.send_html(text, kind=kind)
    except Exception as exc:
        logger.warning("Telegram ops post failed: %s", str(exc)[:200])


async def drain_telegram_ops(timeout: float = 5.0) -> None:
    """Best-effort flush of buffered/in-flight posts before shutdown."""
    global _BULK_TASK
    if _BULK_BUFFER:
        try:
            await asyncio.wait_for(_flush_bulk_after_window(), timeout=timeout)
        except Exception:
            pass
    pending = [task for task in _PENDING_TASKS if not task.done()]
    if pending:
        await asyncio.wait(pending, timeout=timeout)
    await close_shared_http_client()


async def close_shared_http_client() -> None:
    global _SHARED_CLIENT
    client, _SHARED_CLIENT = _SHARED_CLIENT, None
    if client is not None:
        try:
            await client.aclose()
        except Exception:
            pass


def notify_signup(
    *,
    user_id: Any,
    email: str | None = None,
    display_name: str | None = None,
    product: str | None = None,
) -> None:
    _schedule_enriched(
        "signup",
        user_id=user_id,
        email=email,
        display_name=display_name,
        product=product or "unknown",
        account_status="FREE",
    )


def notify_login(
    *,
    user_id: Any,
    email: str | None = None,
    display_name: str | None = None,
) -> None:
    _schedule_enriched(
        "login",
        user_id=user_id,
        email=email,
        display_name=display_name,
        activity="login",
    )


def notify_payment(
    *,
    user_id: Any,
    plan_name: str | None = None,
    amount_cents: int | None = None,
    product: str | None = None,
    extra_lines: list[str] | None = None,
) -> None:
    amount_label = None
    if amount_cents is not None:
        try:
            amount_label = f"${int(amount_cents) / 100:.2f}"
        except (TypeError, ValueError):
            amount_label = str(amount_cents)
    _schedule_enriched(
        "payment",
        user_id=user_id,
        plan_name=plan_name,
        amount_label=amount_label,
        product=product or "plan",
        extra_lines=extra_lines,
        account_status="PAID",
    )


def notify_wallet_spend(
    *,
    user_id: Any,
    amount_units: int,
    reason: str,
    ref_id: Any | None = None,
    metadata: dict[str, Any] | None = None,
    new_balance_units: int | None = None,
) -> None:
    credits = format_display_credits(units_to_credits(int(amount_units)))
    if new_balance_units is not None:
        credits = f"{credits} (balance {format_display_credits(units_to_credits(int(new_balance_units)))})"
    extra = [f"ref: {_esc(ref_id)}"] if ref_id else None
    _schedule_enriched(
        "spend",
        user_id=user_id,
        activity=classify_activity(reason, metadata),
        credits_label=credits,
        pool="studio wallet",
        reason=reason,
        extra_lines=extra,
    )


def notify_wallet_refund(
    *,
    user_id: Any,
    amount_units: int,
    reason: str,
    ref_id: Any | None = None,
) -> None:
    credits = format_display_credits(units_to_credits(int(amount_units)))
    extra = [f"ref: {_esc(ref_id)}"] if ref_id else None
    _schedule_enriched(
        "refund",
        user_id=user_id,
        activity=classify_activity(reason),
        credits_label=credits,
        pool="studio wallet",
        reason=reason,
        extra_lines=extra,
    )


def notify_plan_quota(
    *,
    user_id: Any,
    operation_type: str,
    ai_service: str,
) -> None:
    _schedule_enriched(
        "plan_quota",
        user_id=user_id,
        activity=classify_activity(operation_type),
        pool="studio plan quota",
        reason=f"{operation_type} via {ai_service}",
        account_status="PAID",
    )


def notify_web_music_spend(
    *,
    user_id: Any,
    amount: int,
    source: str,
    reference_id: Any | None = None,
) -> None:
    extra = [f"ref: {_esc(reference_id)}"] if reference_id else None
    _schedule_enriched(
        "spend",
        user_id=user_id,
        activity=classify_activity(source),
        credits_label=str(int(amount)),
        pool="web music",
        reason=source,
        extra_lines=extra,
    )


def notify_web_music_refund(
    *,
    user_id: Any,
    amount: int,
    source: str,
    reference_id: Any | None = None,
) -> None:
    extra = [f"ref: {_esc(reference_id)}"] if reference_id else None
    _schedule_enriched(
        "refund",
        user_id=user_id,
        activity=classify_activity(source),
        credits_label=str(int(amount)),
        pool="web music",
        reason=source,
        extra_lines=extra,
    )


def notify_web_music_download(
    *,
    user_id: Any,
    format: str | None = None,
    variant: str = "ok",
    filename: str | None = None,
    reference_id: Any | None = None,
) -> None:
    fmt = str(format or "file").strip().lower()
    extra: list[str] = []
    if filename:
        extra.append(f"file: {_esc(filename)}")
    if reference_id is not None:
        extra.append(f"task: {_esc(str(reference_id))[:12]}")
    _schedule_enriched(
        "download",
        user_id=user_id,
        activity=classify_activity(fmt),
        pool="web music",
        reason=f"{fmt} download (variant {variant})",
        extra_lines=extra or None,
    )


def _patch_web_music_downloads() -> None:
    try:
        from platform_api.services.web_music_service import WebMusicService
    except Exception:
        return

    def _make_wrap(format_name: str):
        def _wrap(original):  # type: ignore[no-untyped-def]
            async def download(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                result = await original(self, *args, **kwargs)
                try:
                    user_id = kwargs.get("user_id", args[0] if args else None)
                    task_id = kwargs.get("task_id", args[1] if len(args) > 1 else None)
                    variant = str(kwargs.get("variant") or "ok")
                    fmt = format_name
                    if format_name == "lyrics":
                        fmt = str(kwargs.get("lyric_format") or "lrc")
                    filename = None
                    if isinstance(result, tuple) and len(result) > 1:
                        filename = str(result[1])
                    if user_id is not None:
                        notify_web_music_download(
                            user_id=user_id,
                            format=fmt,
                            variant=variant,
                            filename=filename,
                            reference_id=task_id,
                        )
                except Exception:
                    pass
                return result

            return download

        return _wrap

    _patch_method(WebMusicService, "download_mp3", _make_wrap("mp3"))
    _patch_method(WebMusicService, "download_wav", _make_wrap("wav"))
    _patch_method(WebMusicService, "download_timed_lyrics", _make_wrap("lyrics"))
    logger.info("Telegram ops hooks installed on web music downloads.")


def notify_billing_row(row: Any) -> None:
    """Notify from a billing_payments asyncpg record after a new fulfill."""
    if row is None:
        return
    try:
        metadata = row["metadata"] if "metadata" in row else {}
    except Exception:
        metadata = {}
    if isinstance(metadata, str):
        import json

        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    plan_name = None
    try:
        plan_name = row["plan_name"]
    except Exception:
        plan_name = metadata.get("plan_name")
    amount_cents = None
    try:
        amount_cents = int(row["amount_cents"])
    except Exception:
        amount_cents = None
    product = str(metadata.get("product_type") or "plan")
    notify_payment(
        user_id=row["user_id"],
        plan_name=plan_name,
        amount_cents=amount_cents,
        product=product,
    )


def install_telegram_ops_hooks() -> None:
    """Wrap signup, billing, wallet, plan-quota, and web-music credit paths."""
    global _V2_HOOKS_INSTALLED
    if _V2_HOOKS_INSTALLED:
        return
    _V2_HOOKS_INSTALLED = True
    _patch_wallet_credits()
    _patch_signup()
    _patch_login()
    _patch_billing_fulfill()
    _patch_plan_quota_log()
    _patch_v2_credit_service()
    _patch_v2_subscription_service()
    _patch_web_music_downloads()
    try:
        from platform_api.services.telegram_ops_commands import (
            start_telegram_ops_command_poller,
        )

        start_telegram_ops_command_poller()
    except Exception as exc:
        logger.warning("Telegram ops /stats poller not started: %s", exc)


def install_optional_v2_hooks() -> None:
    """Backward-compatible alias used by older call sites."""
    install_telegram_ops_hooks()


def _patch_method(cls: Any, name: str, factory: Any) -> None:
    original = getattr(cls, name, None)
    if original is None or getattr(original, _PATCHED_ATTR, False):
        return
    wrapped = factory(original)
    setattr(wrapped, _PATCHED_ATTR, True)
    setattr(cls, name, wrapped)


def _patch_function(module: Any, name: str, factory: Any) -> None:
    original = getattr(module, name, None)
    if original is None or getattr(original, _PATCHED_ATTR, False):
        return
    wrapped = factory(original)
    setattr(wrapped, _PATCHED_ATTR, True)
    setattr(module, name, wrapped)


def _patch_wallet_credits() -> None:
    try:
        from platform_api.repositories.credit_repo import CreditRepository
    except Exception:
        return

    def _wrap_deduct(original):  # type: ignore[no-untyped-def]
        async def atomic_deduct(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            result = await original(self, *args, **kwargs)
            user_id = kwargs.get("user_id", args[0] if args else None)
            amount = kwargs.get("amount", args[1] if len(args) > 1 else None)
            reason = kwargs.get("reason", args[2] if len(args) > 2 else "")
            ref_id = kwargs.get("ref_id", args[3] if len(args) > 3 else None)
            metadata = kwargs.get("metadata")
            if result and user_id is not None and amount is not None:
                notify_wallet_spend(
                    user_id=user_id,
                    amount_units=int(amount),
                    reason=str(reason or ""),
                    ref_id=ref_id,
                    metadata=metadata if isinstance(metadata, dict) else None,
                )
            return result

        return atomic_deduct

    def _wrap_refund(original):  # type: ignore[no-untyped-def]
        async def refund(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            result = await original(self, *args, **kwargs)
            user_id = kwargs.get("user_id", args[0] if args else None)
            amount = kwargs.get("amount", args[1] if len(args) > 1 else None)
            reason = kwargs.get("reason", args[2] if len(args) > 2 else "")
            ref_id = kwargs.get("ref_id", args[3] if len(args) > 3 else None)
            if user_id is not None and amount is not None:
                notify_wallet_refund(
                    user_id=user_id,
                    amount_units=int(amount),
                    reason=str(reason or ""),
                    ref_id=ref_id,
                )
            return result

        return refund

    _patch_method(CreditRepository, "atomic_deduct", _wrap_deduct)
    _patch_method(CreditRepository, "refund", _wrap_refund)
    logger.info("Telegram ops hooks installed on studio wallet credits.")


def _patch_signup() -> None:
    try:
        from platform_api.repositories.user_repo import UserRepository
    except Exception:
        return

    def _wrap_create(original):  # type: ignore[no-untyped-def]
        async def create(self, user, *, conn=None, **kwargs):  # type: ignore[no-untyped-def]
            created = await original(self, user, conn=conn, **kwargs)
            try:
                notify_signup(
                    user_id=getattr(created, "id", None),
                    email=getattr(created, "email", None),
                    display_name=getattr(created, "display_name", None),
                    product=os.environ.get("CAMXORA_SIGNUP_PRODUCT") or "user",
                )
            except Exception:
                pass
            return created

        return create

    _patch_method(UserRepository, "create", _wrap_create)
    logger.info("Telegram ops hooks installed on user signup.")


def _patch_login() -> None:
    try:
        from platform_api.services.auth_service import AuthService
    except Exception:
        return

    def _wrap_authenticate(original):  # type: ignore[no-untyped-def]
        async def authenticate(self, email, password, *args, **kwargs):  # type: ignore[no-untyped-def]
            result = await original(self, email, password, *args, **kwargs)
            try:
                user = None
                repo = getattr(self, "_user_repo", None)
                if repo is not None:
                    user = await repo.get_by_email(email)
                notify_login(
                    user_id=getattr(user, "id", None),
                    email=getattr(user, "email", None) or email,
                    display_name=getattr(user, "display_name", None),
                )
            except Exception:
                pass
            return result

        return authenticate

    _patch_method(AuthService, "authenticate", _wrap_authenticate)
    logger.info("Telegram ops hooks installed on user login.")


def _patch_billing_fulfill() -> None:
    try:
        from platform_api.routers import billing as billing_mod
    except Exception:
        return

    def _wrap_fulfill(original):  # type: ignore[no-untyped-def]
        async def _fulfill_paid_payment(pool, row, *args, **kwargs):  # type: ignore[no-untyped-def]
            already = False
            try:
                already = row["fulfilled_at"] is not None
            except Exception:
                already = False
            result = await original(pool, row, *args, **kwargs)
            if not already:
                try:
                    if result is not None and result["fulfilled_at"] is not None:
                        notify_billing_row(result)
                except Exception:
                    pass
            return result

        return _fulfill_paid_payment

    _patch_function(billing_mod, "_fulfill_paid_payment", _wrap_fulfill)
    logger.info("Telegram ops hooks installed on billing fulfillment.")


def _patch_plan_quota_log() -> None:
    try:
        from platform_api.services import credit_progress_log as credit_log
    except Exception:
        return

    def _wrap_quota(original):  # type: ignore[no-untyped-def]
        def log_subscription_quota(*, user_id, operation_type, ai_service, **kwargs):  # type: ignore[no-untyped-def]
            original(
                user_id=user_id,
                operation_type=operation_type,
                ai_service=ai_service,
                **kwargs,
            )
            notify_plan_quota(
                user_id=user_id,
                operation_type=str(operation_type or ""),
                ai_service=str(ai_service or ""),
            )

        return log_subscription_quota

    _patch_function(credit_log, "log_subscription_quota", _wrap_quota)
    logger.info("Telegram ops hooks installed on plan-quota log.")


def _patch_v2_credit_service() -> None:
    try:
        from platform_api.services.v2.credit_service import CreditService
    except Exception:
        return

    def _wrap_consume(original):  # type: ignore[no-untyped-def]
        async def consume_credits(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            result = await original(self, *args, **kwargs)
            user_id = kwargs.get("user_id", args[0] if args else None)
            amount = kwargs.get("amount", args[1] if len(args) > 1 else None)
            source = kwargs.get("source", args[2] if len(args) > 2 else "")
            reference_id = kwargs.get(
                "reference_id", args[3] if len(args) > 3 else None
            )
            if result and user_id is not None and amount is not None:
                notify_web_music_spend(
                    user_id=user_id,
                    amount=int(amount),
                    source=str(source or ""),
                    reference_id=reference_id,
                )
            return result

        return consume_credits

    def _wrap_refund(original):  # type: ignore[no-untyped-def]
        async def refund_credits(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            result = await original(self, *args, **kwargs)
            user_id = kwargs.get("user_id", args[0] if args else None)
            amount = kwargs.get("amount", args[1] if len(args) > 1 else None)
            source = kwargs.get("source", args[2] if len(args) > 2 else "")
            reference_id = kwargs.get(
                "reference_id", args[3] if len(args) > 3 else None
            )
            if result and user_id is not None and amount is not None:
                notify_web_music_refund(
                    user_id=user_id,
                    amount=int(amount),
                    source=str(source or ""),
                    reference_id=reference_id,
                )
            return result

        return refund_credits

    _patch_method(CreditService, "consume_credits", _wrap_consume)
    _patch_method(CreditService, "refund_credits", _wrap_refund)
    logger.info("Telegram ops hooks installed on web-music credit service.")


def _patch_v2_subscription_service() -> None:
    try:
        from platform_api.services.v2.subscription_service import SubscriptionService
    except Exception:
        return

    def _wrap_payment_completed(original):  # type: ignore[no-untyped-def]
        async def _handle_payment_completed(self, data):  # type: ignore[no-untyped-def]
            result = await original(self, data)
            payload = data or {}
            metadata = payload.get("metadata") if isinstance(payload, dict) else {}
            if not isinstance(metadata, dict):
                metadata = {}
            amount = payload.get("amount_cents")
            if amount is None:
                amount = payload.get("amount")
            try:
                amount_cents = int(amount) if amount is not None else None
            except (TypeError, ValueError):
                amount_cents = None
            notify_payment(
                user_id=metadata.get("user_id") or payload.get("user_id"),
                plan_name=metadata.get("plan_name") or payload.get("plan_name"),
                amount_cents=amount_cents,
                product="web_music_subscription",
                extra_lines=[
                    f"subscription: {_esc(metadata.get('subscription_id'))}",
                ]
                if metadata.get("subscription_id")
                else None,
            )
            return result

        return _handle_payment_completed

    def _wrap_renewed(original):  # type: ignore[no-untyped-def]
        async def _handle_subscription_renewed(self, data):  # type: ignore[no-untyped-def]
            result = await original(self, data)
            payload = data or {}
            notify_payment(
                user_id=payload.get("user_id"),
                plan_name="renewal",
                product="web_music_renewal",
            )
            return result

        return _handle_subscription_renewed

    _patch_method(SubscriptionService, "_handle_payment_completed", _wrap_payment_completed)
    _patch_method(SubscriptionService, "_handle_subscription_renewed", _wrap_renewed)
    logger.info("Telegram ops hooks installed on web-music subscription service.")
