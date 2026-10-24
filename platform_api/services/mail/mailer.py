"""Resend delivery, queue claiming and the engagement ledger.

The single outbound path for platform mail. Every message is written to
``mail_sends`` before delivery, so the console can show what was sent to whom and
what happened next, and a restart resumes from the queue instead of losing work.

Engagement (opened/clicked) is recorded from our own signed pixel and redirect.
Delivery state (delivered/bounced/complained) comes from Resend webhooks. Keeping
that split means a provider setting can never double-count opens.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx

from platform_api.config import get_settings
from platform_api.services.mail import tracking

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"

MAIL_KINDS = ("transactional", "campaign", "automation")


def mail_configured() -> bool:
    settings = get_settings()
    return bool(settings.resend_api_key) and bool(settings.mail_enabled)


def tracking_secret() -> str:
    """HMAC key for tracking tokens; refuses to fall back to a guessable value."""
    secret = get_settings().mail_tracking_secret
    if not secret:
        raise RuntimeError(
            "PLATFORM_MAIL_TRACKING_SECRET is not set: tracking and unsubscribe "
            "tokens cannot be signed."
        )
    return secret


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


def public_base() -> str:
    return get_settings().mail_public_base_url.rstrip("/")


def unsubscribe_url(user_id: UUID | str) -> str:
    return f"{public_base()}/u/{tracking.build_unsub_token(tracking_secret(), str(user_id))}"


def open_pixel_url(send_id: UUID | str) -> str:
    return f"{public_base()}/o/{tracking.build_open_token(tracking_secret(), str(send_id))}.gif"


def click_url(send_id: UUID | str, target: str) -> str:
    return f"{public_base()}/c/{tracking.build_click_token(tracking_secret(), str(send_id), target)}"


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


async def is_suppressed(pool: Any, email: str) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT email FROM mail_suppressions WHERE email = lower($1)", email
        )
    return row is not None


async def add_suppression(pool: Any, email: str, reason: str, source: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO mail_suppressions (email, reason, source)
            VALUES (lower($1), $2, $3)
            ON CONFLICT (email) DO UPDATE
              SET reason = EXCLUDED.reason, source = EXCLUDED.source
            """,
            email,
            reason,
            source,
        )


async def remove_suppression(pool: Any, email: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM mail_suppressions WHERE email = lower($1)", email)


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------


async def queue_mail(
    pool: Any,
    *,
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    kind: str = "campaign",
    user_id: UUID | str | None = None,
    template_id: UUID | str | None = None,
    campaign_id: UUID | str | None = None,
    automation_id: UUID | str | None = None,
    dedupe_key: str | None = None,
    redeem_code_id: UUID | str | None = None,
    values: dict[str, Any] | None = None,
    text_override: str | None = None,
) -> tuple[str | None, str]:
    """Render, instrument and persist one queued message.

    Returns ``(send_id, outcome)`` where outcome is ``queued``, ``suppressed``,
    ``duplicate`` or ``skipped``. The row id is generated before rendering
    because the tracking URLs embed it.
    """
    to = (to or "").strip().lower()
    if "@" not in to:
        return None, "skipped"

    settings = get_settings()
    if not settings.mail_enabled:
        return None, "skipped"
    if not settings.resend_api_key:
        return None, "skipped"

    # A hard bounce or complaint blocks every kind of mail, including receipts:
    # continuing to send damages the domain that carries them.
    if await is_suppressed(pool, to):
        return None, "suppressed"

    if kind != "transactional" and user_id:
        async with pool.acquire() as conn:
            prefs = await conn.fetchrow(
                "SELECT email_subscription FROM users WHERE id = $1", user_id
            )
        if prefs is None:
            return None, "skipped"
        if not prefs["email_subscription"]:
            return None, "skipped"

    send_id = uuid4()
    merge = {
        "app_url": settings.mail_app_url.rstrip("/"),
        "year": str(datetime.now(timezone.utc).year),
        "unsubscribe_url": unsubscribe_url(user_id) if user_id else f"{public_base()}/u/invalid",
        **(values or {}),
    }

    body = tracking.render_vars(html, merge)
    if kind != "transactional" and user_id and "/api/mail/u/" not in body:
        body += (
            '<div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;'
            'font-size:12px;line-height:1.5;color:#6b7280;text-align:center;">'
            "You received this because you have a CAMXORA account. "
            f'<a href="{merge["unsubscribe_url"]}" style="color:#6b7280;">Unsubscribe</a></div>'
        )

    body, _links = tracking.instrument_html(
        body,
        click_url=lambda target: click_url(send_id, target),
        open_url=open_pixel_url(send_id),
    )

    plain = text_override or tracking.html_to_text(body)

    async with pool.acquire() as conn:
        inserted = await conn.fetchrow(
            """
            INSERT INTO mail_sends
              (id, user_id, email, kind, campaign_id, automation_id, template_id,
               subject, html, text, status, dedupe_key, redeem_code_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'queued', $11, $12)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            send_id,
            user_id,
            to,
            kind,
            campaign_id,
            automation_id,
            template_id,
            tracking.render_vars(subject, merge, escape=False),
            body,
            plain,
            dedupe_key,
            redeem_code_id,
        )

    if inserted is None:
        return None, "duplicate"
    return str(send_id), "queued"


async def claim(pool: Any, limit: int = 25) -> list[dict[str, Any]]:
    """Claim queued rows atomically; safe when several workers run at once."""
    settings = get_settings()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            UPDATE mail_sends s
            SET status = 'sending', claimed_at = now(), attempts = s.attempts + 1
            WHERE s.id IN (
              SELECT id FROM mail_sends
              WHERE status = 'queued'
                AND attempts < $2
                AND (claimed_at IS NULL OR claimed_at < now() - interval '2 minutes')
              ORDER BY created_at
              FOR UPDATE SKIP LOCKED
              LIMIT $1
            )
            RETURNING s.id, s.user_id, s.email, s.kind, s.subject, s.html, s.text,
                      s.attempts, s.campaign_id
            """,
            limit,
            settings.mail_max_attempts,
        )
    return [dict(row) for row in rows]


async def _post_resend(payload: dict[str, Any]) -> tuple[bool, str | None, str | None]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                RESEND_ENDPOINT,
                headers={
                    "authorization": f"Bearer {settings.resend_api_key}",
                    "content-type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError as exc:  # network timeout, DNS, TLS
        return False, None, str(exc)

    if response.status_code < 400:
        try:
            return True, str(response.json().get("id") or ""), None
        except ValueError:
            return True, None, None
    try:
        detail = response.json().get("message") or response.text[:200]
    except ValueError:
        detail = response.text[:200]
    return False, None, f"Resend {response.status_code}: {detail}"


async def deliver(pool: Any, row: dict[str, Any]) -> bool:
    settings = get_settings()
    headers: dict[str, str] = {}

    if row["kind"] != "transactional" and row["user_id"]:
        url = unsubscribe_url(row["user_id"])
        # RFC 8058 one-click: mail clients surface this as the native
        # unsubscribe button, which is what keeps complaint rates down.
        headers["List-Unsubscribe"] = f"<{url}>"
        headers["List-Unsubscribe-Post"] = "Unsubscribe=One-Click"

    payload: dict[str, Any] = {
        "from": settings.mail_from_transactional
        if row["kind"] == "transactional"
        else settings.mail_from_campaign,
        "to": [row["email"]],
        "subject": row["subject"],
        "html": row["html"] or "",
    }
    if row["text"]:
        payload["text"] = row["text"]
    if settings.mail_reply_to:
        payload["reply_to"] = settings.mail_reply_to
    if headers:
        payload["headers"] = headers

    ok, provider_id, error = await _post_resend(payload)

    async with pool.acquire() as conn:
        if ok:
            await conn.execute(
                """
                UPDATE mail_sends
                SET status = 'sent', provider_id = $2, sent_at = now(),
                    error = NULL, claimed_at = now()
                WHERE id = $1
                """,
                row["id"],
                provider_id,
            )
            return True

        exhausted = row["attempts"] >= settings.mail_max_attempts
        await conn.execute(
            "UPDATE mail_sends SET status = $2, error = $3, claimed_at = now() WHERE id = $1",
            row["id"],
            "failed" if exhausted else "queued",
            error,
        )
    logger.warning("mail delivery failed for %s: %s", row["email"], error)
    return False


async def process_queue(pool: Any, limit: int = 25) -> int:
    """Claim and deliver a batch, paced to the provider's per-second limit."""
    if not mail_configured():
        return 0

    import asyncio

    rows = await claim(pool, limit)
    sent = 0
    pause = 1.0 / max(1, get_settings().mail_rate_per_second)
    for row in rows:
        if await deliver(pool, row):
            sent += 1
        await asyncio.sleep(pause)
    return sent


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


async def record_event(
    pool: Any,
    send_id: UUID | str,
    event_type: str,
    *,
    url: str | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
    provider_event_id: str | None = None,
) -> bool:
    """Record one event and advance the delivery row. False when already known."""
    async with pool.acquire() as conn:
        inserted = await conn.fetchrow(
            """
            INSERT INTO mail_events (send_id, type, url, user_agent, ip, provider_event_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            send_id,
            event_type,
            url,
            user_agent,
            ip,
            provider_event_id,
        )
        if inserted is None:
            return False

        if event_type == "opened":
            await conn.execute(
                """
                UPDATE mail_sends
                SET open_count = open_count + 1,
                    first_opened_at = COALESCE(first_opened_at, now()),
                    last_opened_at = now(),
                    status = CASE WHEN status IN ('sent', 'delivered') THEN 'opened' ELSE status END
                WHERE id = $1
                """,
                send_id,
            )
        elif event_type == "clicked":
            await conn.execute(
                """
                UPDATE mail_sends
                SET click_count = click_count + 1,
                    first_clicked_at = COALESCE(first_clicked_at, now()),
                    last_clicked_at = now(),
                    status = CASE
                      WHEN status IN ('bounced', 'complained', 'failed') THEN status
                      ELSE 'clicked' END
                WHERE id = $1
                """,
                send_id,
            )
        elif event_type == "delivered":
            await conn.execute(
                """
                UPDATE mail_sends
                SET status = CASE WHEN status = 'sent' THEN 'delivered' ELSE status END,
                    delivered_at = COALESCE(delivered_at, now())
                WHERE id = $1
                """,
                send_id,
            )
        else:
            await conn.execute(
                "UPDATE mail_sends SET status = $2 WHERE id = $1", send_id, event_type
            )
    return True


async def record_event_by_provider_id(
    pool: Any,
    provider_id: str,
    event_type: str,
    *,
    recipient: str | None = None,
    provider_event_id: str | None = None,
) -> bool:
    """Webhook path: Resend gives us its message id, not ours."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM mail_sends WHERE provider_id = $1 LIMIT 1", provider_id
        )
    if row is None:
        return False
    return await record_event(
        pool,
        row["id"],
        event_type,
        provider_event_id=provider_event_id,
    )
