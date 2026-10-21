"""State-triggered journeys for the platform stack.

An automation is "when the user looks like X, send template Y, at most once per
cooldown window". Two guards stack: the automation's own ``cooldown_days`` and the
shared marketing cooldown applied by the sender's consent/suppression checks.

Manual-only templates never run here: the query joins ``mail_templates`` and
filters ``send_mode = 'auto'``, so a discount or seasonal message cannot be
triggered by a timer even if a row was inserted by hand.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from platform_api.services.mail import mailer

logger = logging.getLogger(__name__)

TRIGGERS: list[dict[str, Any]] = [
    {
        "key": "welcome",
        "label": "Welcome",
        "description": "Signed up at least N minutes ago and has not received this journey.",
        "paramLabel": "Minutes after signup",
        "defaultParam": 30,
        "defaultCooldownDays": 3650,
    },
    {
        "key": "never_generated",
        "label": "Signed up, never generated",
        "description": "Account older than N minutes with no credit ever spent.",
        "paramLabel": "Minutes after signup",
        "defaultParam": 60 * 24 * 3,
        "defaultCooldownDays": 3650,
    },
    {
        "key": "low_balance",
        "label": "Low credit balance",
        "description": "Balance below N credits, for users who have paid at least once.",
        "paramLabel": "Credit threshold",
        "defaultParam": 50,
        "defaultCooldownDays": 7,
    },
    {
        "key": "inactive",
        "label": "Inactive",
        "description": "Last seen more than N days ago.",
        "paramLabel": "Days inactive",
        "defaultParam": 30,
        "defaultCooldownDays": 30,
    },
    {
        "key": "payment_expired",
        "label": "Payment expired",
        "description": "Reached checkout and the payment expired in the last 7 days.",
        "paramLabel": "Days to look back",
        "defaultParam": 7,
        "defaultCooldownDays": 7,
    },
    {
        "key": "credits_expiring",
        "label": "Credits expiring",
        "description": "A credit batch with credits left expires within N days.",
        "paramLabel": "Days before expiry",
        "defaultParam": 5,
        "defaultCooldownDays": 5,
    },
]

TRIGGER_KEYS = {t["key"] for t in TRIGGERS}


def coerce_trigger(value: Any) -> str:
    return value if isinstance(value, str) and value in TRIGGER_KEYS else "welcome"


def _where(trigger: str, param: int, automation_id: UUID, cooldown_days: int) -> tuple[str, list[Any]]:
    params: list[Any] = [automation_id, max(1, cooldown_days)]
    clauses = [
        "v.status = 'active'",
        "v.role = 'user'",
        "v.email_subscription = true",
        "v.suppressed = false",
    ]

    if trigger in ("welcome", "never_generated"):
        params.append(max(0, param))
        clauses.append(
            f"v.created_at <= now() - (${len(params)}::int * interval '1 minute')"
        )
        if trigger == "never_generated":
            clauses.append(
                """NOT EXISTS (
                     SELECT 1 FROM credit_transactions t
                     WHERE t.user_id = v.user_id AND t.direction = 'debit'
                   )"""
            )
    elif trigger == "low_balance":
        params.append(max(0, param))
        clauses.append(f"v.balance < ${len(params)}")
        # A free account at zero is a campaign audience, not an account notice.
        clauses.append("v.payment_count > 0")
    elif trigger == "inactive":
        params.append(max(1, param))
        clauses.append(
            f"v.last_seen_at <= now() - (${len(params)}::int * interval '1 day')"
        )
    elif trigger == "payment_expired":
        params.append(max(1, param))
        clauses.append(
            f"""EXISTS (
                  SELECT 1 FROM billing_payments p
                  WHERE p.user_id = v.user_id
                    AND p.status = 'expired'
                    AND p.created_at > now() - (${len(params)}::int * interval '1 day')
                )"""
        )
    elif trigger == "credits_expiring":
        params.append(max(1, param))
        clauses.append(
            f"""EXISTS (
                  SELECT 1 FROM credit_wallet_lots l
                  WHERE l.user_id = v.user_id
                    AND l.remaining_units > 0
                    AND l.expires_at IS NOT NULL
                    AND l.expires_at <= now() + (${len(params)}::int * interval '1 day')
                )"""
        )
    else:
        clauses.append("false")

    # The journey's own cooldown, on top of the shared marketing one enforced
    # when the message is queued.
    clauses.append(
        """NOT EXISTS (
             SELECT 1 FROM mail_sends s
             WHERE s.user_id = v.user_id
               AND s.automation_id = $1
               AND s.status NOT IN ('failed', 'skipped', 'suppressed')
               AND s.created_at > now() - ($2::int * interval '1 day')
           )"""
    )
    return " AND ".join(clauses), params


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


def _param(automation: Any) -> int:
    audience = automation["audience"] or {}
    if isinstance(audience, dict):
        value = audience.get("triggerValue")
        if isinstance(value, int) and value >= 0:
            return value
    for trigger in TRIGGERS:
        if trigger["key"] == automation["trigger"]:
            return int(trigger["defaultParam"])
    return 0


async def run_due(pool: Any, limit_per_journey: int = 200) -> int:
    """Evaluate every active journey. Returns how many messages were queued."""
    if not mailer.mail_configured():
        return 0

    async with pool.acquire() as conn:
        automations = await conn.fetch(
            """
            SELECT a.id, a.key, a.name, a.trigger, a.audience, a.cooldown_days,
                   a.template_id, t.subject, t.html, t.text
            FROM mail_automations a
            JOIN mail_templates t ON t.id = a.template_id
            WHERE a.is_active AND t.send_mode = 'auto'
            ORDER BY a.key
            """
        )

    queued = 0
    for automation in automations:
        try:
            where, params = _where(
                coerce_trigger(automation["trigger"]),
                _param(automation),
                automation["id"],
                int(automation["cooldown_days"]),
            )
            params.append(limit_per_journey)
            async with pool.acquire() as conn:
                recipients = await conn.fetch(
                    f"""
                    SELECT v.user_id, v.email
                    FROM user_mail_value v
                    WHERE {where}
                    ORDER BY v.last_seen_at DESC NULLS LAST
                    LIMIT ${len(params)}
                    """,
                    *params,
                )

            for recipient in recipients:
                bucket = int(
                    __import__("time").time()
                    // (max(1, int(automation["cooldown_days"])) * 86400)
                )
                _sid, outcome = await mailer.queue_mail(
                    pool,
                    to=recipient["email"],
                    subject=automation["subject"],
                    html=automation["html"],
                    text=automation["text"],
                    kind="automation",
                    user_id=recipient["user_id"],
                    template_id=automation["template_id"],
                    automation_id=automation["id"],
                    dedupe_key=f"automation:{automation['id']}:{recipient['user_id']}:{bucket}",
                    values=await _user_vars(pool, recipient["user_id"]),
                )
                if outcome == "queued":
                    queued += 1

            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE mail_automations SET last_run_at = now() WHERE id = $1",
                    automation["id"],
                )
        except Exception:
            # One broken journey must not stop the others.
            logger.exception("mail automation %s failed", automation["key"])

    return queued
