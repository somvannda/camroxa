"""Mail endpoints: public tracking/webhook plus the admin console API.

Mounted on /api/v1 and /api/v3, so the console calls /api/v3/mail/*. Public
delivery paths live on the same prefix, which is why mail.camxora.com gets an
explicit nginx location for /api/mail/:

    /api/mail/o/{token}.gif    open pixel
    /api/mail/c/{token}        302 to a signed destination
    /api/mail/u/{token}        unsubscribe
    /api/mail/webhook/resend   delivery state from Resend

The musicapi stack already owns /mail/* on that host, so these paths can never be
confused with its tokens.
"""

from __future__ import annotations

import base64
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from platform_api.config import get_settings
from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.services.mail import mailer, segments, tracking
from platform_api.services.mail.resend_webhook import (
    map_event,
    suppression_reason,
    verify_signature,
)

router = APIRouter(prefix="/mail", tags=["mail"])

PIXEL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)
NO_CACHE = "no-store, no-cache, must-revalidate, private"


async def _pool() -> Any:
    from platform_api.dependencies import get_db_pool

    return get_db_pool()


PoolDep = Annotated[Any, Depends(_pool)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


def _unsub_page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title></head>
<body style="margin:0;background:#0a0e27;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#e5e7eb;">
  <div style="max-width:520px;margin:64px auto;padding:32px;background:#081028;border-radius:16px;">
    <div style="font-weight:700;letter-spacing:.12em;color:#a855f7;font-size:11px;margin-bottom:16px;">CAMXORA</div>
    <h1 style="margin:0 0 12px;font-size:22px;color:#fff;">{title}</h1>
    <div style="font-size:14px;line-height:1.65;color:#9ca3af;">{body}</div>
  </div>
</body></html>"""
    return HTMLResponse(html, status_code=status_code)


# ---------------------------------------------------------------------------
# Public: tracking
# ---------------------------------------------------------------------------


@router.get("/o/{token}", include_in_schema=False)
async def open_pixel(token: str, pool: PoolDep) -> Response:
    """Always returns the GIF, even for a bad token, so the inbox never shows a
    broken image."""
    token = token.removesuffix(".gif")
    try:
        send_id = tracking.parse_open_token(mailer.tracking_secret(), token)
    except RuntimeError:
        send_id = None

    if send_id:
        try:
            await mailer.record_event(pool, send_id, "opened")
        except Exception:  # never fail the pixel on a database hiccup
            pass

    return Response(
        content=PIXEL_GIF,
        media_type="image/gif",
        headers={"Cache-Control": NO_CACHE, "Content-Length": str(len(PIXEL_GIF))},
    )


@router.get("/c/{token}", include_in_schema=False)
async def click_redirect(token: str, pool: PoolDep) -> Response:
    parsed = tracking.parse_click_token(mailer.tracking_secret(), token)
    if parsed is None:
        raise NotFoundError("This link is not valid or has expired.")
    send_id, target = parsed
    try:
        await mailer.record_event(pool, send_id, "clicked", url=target)
    except Exception:
        pass  # still redirect: the reader wants the page, not our analytics
    return RedirectResponse(target, status_code=302)


@router.get("/u/{token}", include_in_schema=False)
async def unsubscribe_page(token: str, pool: PoolDep) -> Response:
    return await _unsubscribe(token, pool, one_click=False)


@router.post("/u/{token}", include_in_schema=False)
async def unsubscribe_one_click(token: str, pool: PoolDep) -> Response:
    return await _unsubscribe(token, pool, one_click=True)


async def _unsubscribe(token: str, pool: Any, *, one_click: bool) -> Response:
    user_id = tracking.parse_unsub_token(mailer.tracking_secret(), token)
    if user_id is None:
        return _unsub_page(
            "Link not valid",
            "This unsubscribe link is not valid. Sign in and change your email "
            "preferences in Account settings.",
            status_code=400,
        )

    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id, email FROM users WHERE id = $1", UUID(user_id))
        if user is None:
            return _unsub_page(
                "Account not found",
                "This account no longer exists, so no further email will be sent to it.",
                status_code=404,
            )
        await conn.execute("UPDATE users SET email_subscription = false WHERE id = $1", user["id"])

    await mailer.add_suppression(pool, user["email"], "unsubscribe", "one-click")

    # RFC 8058: a bare 200 is all a mail client needs.
    if one_click:
        return Response("Unsubscribed", status_code=200, media_type="text/plain")
    return _unsub_page(
        "You're unsubscribed",
        "You will no longer receive marketing email from CAMXORA.<br />"
        "Receipts, payment confirmations and account notices will still be delivered.",
    )


# ---------------------------------------------------------------------------
# Public: Resend webhook
# ---------------------------------------------------------------------------


@router.post("/webhook/resend", include_in_schema=False)
async def resend_webhook(request: Request, pool: PoolDep) -> dict[str, Any]:
    settings = get_settings()
    if not settings.resend_webhook_secret:
        # 503, not 200: the endpoint is not ready, and Resend should retry rather
        # than treat the delivery as accepted and drop it.
        return JSONResponse({"error": "Webhook secret is not configured."}, status_code=503)

    raw = await request.body()
    verified = verify_signature(
        raw,
        svix_id=request.headers.get("svix-id"),
        svix_timestamp=request.headers.get("svix-timestamp"),
        svix_signature=request.headers.get("svix-signature"),
        secret=settings.resend_webhook_secret,
    )
    if not verified:
        # 400 so a forged delivery is rejected loudly, matching musicapi.
        return JSONResponse({"error": "Invalid signature."}, status_code=400)

    event = map_event(await request.json())
    if event is None:
        return {"ok": True, "ignored": "unmapped event"}

    # The svix id is stable across provider retries, so a retry cannot inflate
    # counters (unique index on provider_event_id).
    svix_id = request.headers.get("svix-id")
    recorded = await mailer.record_event_by_provider_id(
        pool,
        str(event["email_id"]),
        str(event["type"]),
        recipient=event["recipient"],  # type: ignore[arg-type]
        provider_event_id=f"svix:{svix_id}" if svix_id else None,
    )

    reason = suppression_reason(str(event["type"]))
    if reason and event["recipient"]:
        await mailer.add_suppression(pool, str(event["recipient"]), reason, "resend")

    return {"ok": True, "recorded": recorded}


# ---------------------------------------------------------------------------
# Admin: health, templates
# ---------------------------------------------------------------------------


@router.get("/health")
async def mail_health(pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    settings = get_settings()
    async with pool.acquire() as conn:
        counts = await conn.fetch(
            "SELECT status, COUNT(*) AS n FROM mail_sends GROUP BY status"
        )
        suppressed = await conn.fetchrow("SELECT COUNT(*) AS n FROM mail_suppressions")
    return {
        "configured": bool(settings.resend_api_key) and settings.mail_enabled,
        "enabled": settings.mail_enabled,
        "from_transactional": settings.mail_from_transactional,
        "from_campaign": settings.mail_from_campaign,
        "base_url": settings.mail_public_base_url,
        "queue_depth": next((int(r["n"]) for r in counts if r["status"] == "queued"), 0),
        "counts": {r["status"]: int(r["n"]) for r in counts},
        "suppressed": int(suppressed["n"]) if suppressed else 0,
    }


@router.get("/templates")
async def list_templates(pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, key, locale, name, subject, send_mode, is_active, updated_at,
                   COALESCE(array_length(vars, 1), 0) AS var_count
            FROM mail_templates
            ORDER BY is_active DESC, name
            """
        )
    return {"rows": [dict(row) for row in rows]}


@router.get("/templates/{template_id}")
async def get_template(template_id: UUID, pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, key, locale, name, subject, html, text, vars, send_mode, is_active "
            "FROM mail_templates WHERE id = $1",
            template_id,
        )
    if row is None:
        raise NotFoundError("Template not found.")
    return dict(row)


@router.post("/templates")
async def create_template(
    pool: PoolDep,
    _: AdminDep,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    html = str(payload.get("html") or "")
    if not name or not subject or not html.strip():
        raise ValidationError("name, subject and html are required.")

    send_mode = payload.get("sendMode")
    if send_mode not in (None, "auto", "manual"):
        raise ValidationError("sendMode must be 'auto' or 'manual'.")

    vars_used = sorted(set(tracking._VAR_RE.findall(f"{subject}{html}")))

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO mail_templates (name, subject, html, text, locale, vars, send_mode)
            VALUES ($1, $2, $3, $4, $5, $6, COALESCE($7, 'auto'))
            RETURNING id
            """,
            name,
            subject,
            html,
            payload.get("text") or None,
            str(payload.get("locale") or "en"),
            vars_used,
            send_mode,
        )
    return {"id": str(row["id"])}


@router.put("/templates/{template_id}")
async def update_template(
    template_id: UUID,
    pool: PoolDep,
    _: AdminDep,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    html = str(payload.get("html") or "")
    if not name or not subject or not html.strip():
        raise ValidationError("name, subject and html are required.")

    send_mode = payload.get("sendMode")
    if send_mode not in (None, "auto", "manual"):
        raise ValidationError("sendMode must be 'auto' or 'manual'.")

    vars_used = sorted(set(tracking._VAR_RE.findall(f"{subject}{html}")))

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE mail_templates
            SET name = $2, subject = $3, html = $4, text = $5, locale = $6,
                vars = $7, send_mode = COALESCE($8, send_mode), updated_at = now()
            WHERE id = $1
            RETURNING id
            """,
            template_id,
            name,
            subject,
            html,
            payload.get("text") or None,
            str(payload.get("locale") or "en"),
            vars_used,
            send_mode,
        )
    if row is None:
        raise NotFoundError("Template not found.")
    return {"ok": True}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: UUID, pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    async with pool.acquire() as conn:
        used = await conn.fetchrow(
            "SELECT COUNT(*) AS n FROM mail_campaigns WHERE template_id = $1", template_id
        )
        if used and int(used["n"]) > 0:
            raise ValidationError(
                "This template is used by a campaign. Deactivate it instead."
            )
        await conn.execute("DELETE FROM mail_templates WHERE id = $1", template_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin: segments and campaigns
# ---------------------------------------------------------------------------


@router.get("/segments")
async def list_segments(pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    settings = get_settings()
    cooldown = 7
    presets = []
    for preset in segments.PRESETS:
        presets.append(
            {
                "key": preset["key"],
                "label": preset["label"],
                "count": await segments.audience_count(
                    pool, segments.coerce(preset["audience"]), cooldown
                ),
            }
        )
    return {"presets": presets, "cooldownDays": cooldown}


@router.post("/audience/count")
async def audience_count(
    pool: PoolDep,
    _: AdminDep,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    audience = segments.coerce(payload.get("audience"))
    count = await segments.audience_count(pool, audience, 7)
    return {"count": count, "cappedAt": segments.MAX_RECIPIENTS}


@router.get("/campaigns")
async def list_campaigns(pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.id, c.name, c.status, c.audience, c.recipient_count,
                   c.scheduled_at, c.started_at, c.sent_at, c.created_at,
                   t.name AS template_name,
                   (SELECT COUNT(*) FROM mail_sends s WHERE s.campaign_id = c.id) AS queued,
                   (SELECT COUNT(*) FROM mail_sends s WHERE s.campaign_id = c.id AND s.open_count > 0) AS opened,
                   (SELECT COUNT(*) FROM mail_sends s WHERE s.campaign_id = c.id AND s.click_count > 0) AS clicked
            FROM mail_campaigns c
            JOIN mail_templates t ON t.id = c.template_id
            ORDER BY c.created_at DESC
            LIMIT 100
            """
        )
    return {"rows": [dict(row) for row in rows]}


@router.post("/campaigns")
async def create_campaign(
    pool: PoolDep,
    admin: AdminDep,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    template_id = payload.get("templateId")
    if not name or not template_id:
        raise ValidationError("name and templateId are required.")

    async with pool.acquire() as conn:
        template = await conn.fetchrow(
            "SELECT id FROM mail_templates WHERE id = $1 AND is_active", template_id
        )
        if template is None:
            raise ValidationError("Template not found or inactive.")
        row = await conn.fetchrow(
            """
            INSERT INTO mail_campaigns (name, template_id, audience, created_by)
            VALUES ($1, $2, $3::jsonb, $4)
            RETURNING id
            """,
            name,
            template_id,
            segments_json(payload.get("audience")),
            admin.user_id,
        )
    return {"id": str(row["id"])}


def segments_json(audience: Any) -> str:
    import json

    return json.dumps(segments.coerce(audience if isinstance(audience, dict) else None))


async def _user_vars(pool: Any, user_id: Any) -> dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT email, display_name, balance FROM user_mail_value WHERE user_id = $1",
            user_id,
        )
    if row is None:
        return {}
    first = (row["display_name"] or "").strip().split(" ")[0] or "there"
    balance = int(row["balance"] or 0)
    return {
        "first_name": first,
        "name": row["display_name"] or first,
        "email": row["email"],
        "credits": f"{balance:,}",
        "songs_left": str(max(0, balance // 10)),
    }


@router.post("/campaigns/{campaign_id}/send")
async def send_campaign(campaign_id: UUID, pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow(
            """
            SELECT c.id, c.status, c.audience, c.template_id, t.subject, t.html, t.text
            FROM mail_campaigns c JOIN mail_templates t ON t.id = c.template_id
            WHERE c.id = $1
            """,
            campaign_id,
        )
    if campaign is None:
        raise NotFoundError("Campaign not found.")
    if campaign["status"] in ("sent", "sending"):
        raise ValidationError("This campaign was already sent or is sending.")
    if not mailer.mail_configured():
        raise ValidationError("Resend is not configured; nothing to send with.")

    audience = segments.coerce(campaign["audience"])
    recipients = await segments.recipients(pool, audience, 7)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mail_campaigns SET status = 'sending', started_at = now(), updated_at = now() WHERE id = $1",
            campaign_id,
        )

    queued = 0
    skipped = 0
    for recipient in recipients:
        _sid, outcome = await mailer.queue_mail(
            pool,
            to=recipient["email"],
            subject=campaign["subject"],
            html=campaign["html"],
            text=campaign["text"],
            kind="campaign",
            user_id=recipient["user_id"],
            template_id=campaign["template_id"],
            campaign_id=campaign_id,
            dedupe_key=f"campaign:{campaign_id}:{recipient['user_id']}",
            values=await _user_vars(pool, recipient["user_id"]),
        )
        if outcome == "queued":
            queued += 1
        else:
            skipped += 1

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE mail_campaigns
            SET status = 'sent', sent_at = now(), recipient_count = $2, updated_at = now()
            WHERE id = $1
            """,
            campaign_id,
            queued,
        )
    return {"queued": queued, "skipped": skipped, "audience": len(recipients)}


@router.post("/campaigns/{campaign_id}/test")
async def test_campaign(
    campaign_id: UUID,
    pool: PoolDep,
    admin: AdminDep,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    async with pool.acquire() as conn:
        campaign = await conn.fetchrow(
            "SELECT t.subject, t.html, t.text FROM mail_campaigns c "
            "JOIN mail_templates t ON t.id = c.template_id WHERE c.id = $1",
            campaign_id,
        )
    if campaign is None:
        raise NotFoundError("Campaign not found.")

    to = str(payload.get("to") or admin.email)
    sid, outcome = await mailer.queue_mail(
        pool,
        to=to,
        subject=f"[TEST] {campaign['subject']}",
        html=campaign["html"],
        text=campaign["text"],
        kind="transactional",
        values=await _user_vars(pool, admin.user_id),
    )
    if outcome != "queued":
        raise ValidationError(f"Test send rejected: {outcome}")
    return {"ok": True, "to": to, "id": sid}


# ---------------------------------------------------------------------------
# Admin: deliveries, suppressions, automations
# ---------------------------------------------------------------------------


@router.get("/deliveries")
async def list_deliveries(
    pool: PoolDep,
    _: AdminDep,
    status: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    limit = max(1, min(200, limit))
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT id, email, kind, subject, status, open_count, click_count,
                       sent_at, delivered_at, error, created_at
                FROM mail_sends WHERE status = $1
                ORDER BY created_at DESC LIMIT $2
                """,
                status,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, email, kind, subject, status, open_count, click_count,
                       sent_at, delivered_at, error, created_at
                FROM mail_sends ORDER BY created_at DESC LIMIT $1
                """,
                limit,
            )
        stats = await conn.fetchrow(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE delivered_at IS NOT NULL) AS delivered,
                   COUNT(*) FILTER (WHERE open_count > 0) AS opened,
                   COUNT(*) FILTER (WHERE click_count > 0) AS clicked,
                   COUNT(*) FILTER (WHERE status IN ('bounced', 'complained')) AS bounced
            FROM mail_sends
            """
        )
    return {"rows": [dict(r) for r in rows], "stats": dict(stats) if stats else {}}


@router.get("/suppressions")
async def list_suppressions(pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT email, reason, source, created_at FROM mail_suppressions "
            "ORDER BY created_at DESC LIMIT 200"
        )
    return {"rows": [dict(r) for r in rows]}


@router.post("/suppressions")
async def add_suppression(
    pool: PoolDep,
    _: AdminDep,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    email = str(payload.get("email") or "").strip().lower()
    if "@" not in email:
        raise ValidationError("A valid email is required.")
    await mailer.add_suppression(pool, email, "manual", "admin")
    return {"ok": True}


@router.delete("/suppressions/{email}")
async def delete_suppression(email: str, pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    await mailer.remove_suppression(pool, email)
    return {"ok": True}


@router.get("/automations")
async def list_automations(pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.id, a.key, a.name, a.trigger, a.audience, a.cooldown_days,
                   a.delay_minutes, a.is_active, a.last_run_at, t.name AS template_name,
                   t.send_mode
            FROM mail_automations a
            JOIN mail_templates t ON t.id = a.template_id
            ORDER BY a.key
            """
        )
    return {"rows": [dict(r) for r in rows]}


@router.post("/automations")
async def create_automation(
    pool: PoolDep,
    _: AdminDep,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    template_id = payload.get("templateId")
    trigger = str(payload.get("trigger") or "").strip()
    if not name or not template_id or not trigger:
        raise ValidationError("name, templateId and trigger are required.")

    async with pool.acquire() as conn:
        template = await conn.fetchrow(
            "SELECT id, send_mode FROM mail_templates WHERE id = $1 AND is_active", template_id
        )
        if template is None:
            raise ValidationError("Template not found or inactive.")
        # A discount must be priced by a human and a dated holiday message must
        # not keep firing, so manual templates cannot be automated.
        if template["send_mode"] == "manual":
            raise ValidationError(
                "This template is manual-only and cannot be attached to an automation. "
                "Use a campaign instead."
            )
        row = await conn.fetchrow(
            """
            INSERT INTO mail_automations
              (key, name, template_id, trigger, audience, delay_minutes, cooldown_days, is_active)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
            ON CONFLICT (key) DO NOTHING
            RETURNING id
            """,
            name.lower().replace(" ", "-")[:60],
            name,
            template_id,
            trigger,
            segments_json(payload.get("audience")),
            int(payload.get("delayMinutes") or 0),
            int(payload.get("cooldownDays") or 30),
            bool(payload.get("isActive")),
        )
    if row is None:
        raise ValidationError("A journey with this name already exists.")
    return {"id": str(row["id"])}


@router.put("/automations/{automation_id}")
async def update_automation(
    automation_id: UUID,
    pool: PoolDep,
    _: AdminDep,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    is_active = payload.get("isActive")
    cooldown = payload.get("cooldownDays")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE mail_automations
            SET is_active = COALESCE($2::boolean, is_active),
                cooldown_days = COALESCE($3::int, cooldown_days)
            WHERE id = $1
            RETURNING id
            """,
            automation_id,
            is_active if isinstance(is_active, bool) else None,
            int(cooldown) if isinstance(cooldown, int) and cooldown >= 1 else None,
        )
    if row is None:
        raise NotFoundError("Automation not found.")
    return {"ok": True}


@router.delete("/automations/{automation_id}")
async def delete_automation(automation_id: UUID, pool: PoolDep, _: AdminDep) -> dict[str, Any]:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM mail_automations WHERE id = $1", automation_id)
    return {"ok": True}
