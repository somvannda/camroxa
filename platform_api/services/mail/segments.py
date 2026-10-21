"""Audience selection over ``user_mail_value``.

Segments are evaluated at send time rather than frozen into a list, so a user who
unsubscribes between preview and send is excluded, and "active in the last 7
days" is still true tomorrow.

Two rules are enforced here rather than left to the operator:
  * marketing cooldown — nobody gets two marketing mails inside N days;
  * price integrity — anyone who paid in the last 14 days is excluded from
    discount mail, otherwise the next purchase waits for a sale.
"""

from __future__ import annotations

from typing import Any

LIFECYCLES = ("active", "warm", "dormant")
SPEND_TIERS = ("never", "small", "big")

MAX_RECIPIENTS = 2000


def coerce(audience: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize untrusted JSON into a known-shape audience."""
    raw = audience or {}
    lifecycle = raw.get("lifecycle")
    spend_tier = raw.get("spendTier")
    language = raw.get("language")
    return {
        "lifecycle": lifecycle if lifecycle in LIFECYCLES else None,
        "spend_tier": spend_tier if spend_tier in SPEND_TIERS else None,
        "language": language if isinstance(language, str) and len(language) == 2 else None,
        "exclude_recent_payers": raw.get("excludeRecentPayers") is True,
        "cooldown_days": raw.get("cooldownDays")
        if isinstance(raw.get("cooldownDays"), int) and raw["cooldownDays"] >= 0
        else None,
    }


def where_clause(audience: dict[str, Any], default_cooldown_days: int) -> tuple[str, list[Any]]:
    """Build the WHERE over ``user_mail_value v``; values are always parameterized."""
    params: list[Any] = []
    clauses = [
        "v.status = 'active'",
        "v.role = 'user'",
        "v.email_subscription = true",
        "v.suppressed = false",
    ]

    if audience.get("lifecycle"):
        params.append(audience["lifecycle"])
        clauses.append(f"v.lifecycle = ${len(params)}")
    if audience.get("spend_tier"):
        params.append(audience["spend_tier"])
        clauses.append(f"v.spend_tier = ${len(params)}")

    cooldown = audience.get("cooldown_days")
    cooldown = default_cooldown_days if cooldown is None else cooldown
    if cooldown > 0:
        params.append(cooldown)
        clauses.append(
            f"""NOT EXISTS (
                  SELECT 1 FROM mail_sends s
                  WHERE s.user_id = v.user_id
                    AND s.kind IN ('campaign', 'automation')
                    AND s.status NOT IN ('failed', 'skipped', 'suppressed')
                    AND s.created_at > now() - (${len(params)}::int * interval '1 day')
                )"""
        )

    if audience.get("exclude_recent_payers"):
        clauses.append(
            """NOT EXISTS (
                 SELECT 1 FROM billing_payments p
                 WHERE p.user_id = v.user_id
                   AND p.status = 'paid'
                   AND COALESCE(p.approved_at, p.fulfilled_at, p.created_at)
                       > now() - interval '14 days'
               )"""
        )

    return " AND ".join(clauses), params


async def audience_count(pool: Any, audience: dict[str, Any], default_cooldown_days: int) -> int:
    where, params = where_clause(audience, default_cooldown_days)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT COUNT(*) AS n FROM user_mail_value v WHERE {where}", *params
        )
    return int(row["n"]) if row else 0


async def recipients(
    pool: Any,
    audience: dict[str, Any],
    default_cooldown_days: int,
    limit: int = MAX_RECIPIENTS,
) -> list[dict[str, Any]]:
    """Most recently active first, so the first slice is the warmest audience."""
    where, params = where_clause(audience, default_cooldown_days)
    params.append(limit)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT v.user_id, v.email
            FROM user_mail_value v
            WHERE {where}
            ORDER BY v.last_seen_at DESC NULLS LAST
            LIMIT ${len(params)}
            """,
            *params,
        )
    return [dict(row) for row in rows]


# The nine-cell strategy matrix, as ready-made segments. "Active, never paid"
# is first because it is the highest-converting email in the set.
PRESETS: list[dict[str, Any]] = [
    {"key": "active-never", "label": "Active, never paid", "audience": {"lifecycle": "active", "spendTier": "never"}},
    {"key": "active-small", "label": "Active, small payer", "audience": {"lifecycle": "active", "spendTier": "small"}},
    {"key": "active-big", "label": "Active, big payer", "audience": {"lifecycle": "active", "spendTier": "big"}},
    {"key": "warm-never", "label": "Warm, never paid", "audience": {"lifecycle": "warm", "spendTier": "never"}},
    {"key": "warm-small", "label": "Warm, small payer", "audience": {"lifecycle": "warm", "spendTier": "small"}},
    {"key": "warm-big", "label": "Warm, big payer", "audience": {"lifecycle": "warm", "spendTier": "big"}},
    {"key": "dormant-never", "label": "Dormant, never paid", "audience": {"lifecycle": "dormant", "spendTier": "never"}},
    {"key": "dormant-small", "label": "Dormant, small payer", "audience": {"lifecycle": "dormant", "spendTier": "small"}},
    {"key": "dormant-big", "label": "Dormant, big payer", "audience": {"lifecycle": "dormant", "spendTier": "big"}},
]
