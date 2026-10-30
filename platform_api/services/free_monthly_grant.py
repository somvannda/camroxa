"""Monthly 50-credit Free allowance.

Rules:
  * Only for users with **no live pack** (Free tier).
  * 50 credits per calendar month, **reset** (never stacks, max 50).
  * The previous month's free lot is removed before the new one is minted.
  * Credits from admin/referral lots are preserved; the free grant tops the
    balance up to 50, not on top of it.

See docs/credits-only-two-tier.md and docs/credits-e2e-audit.md.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from platform_api.services.billing_calendar import (
    billing_month_start,
    next_billing_month_start,
)
from platform_api.services.credit_units import credits_to_units

FREE_MONTHLY_CREDITS = 50
FREE_MONTHLY_UNITS = credits_to_units(FREE_MONTHLY_CREDITS)
FREE_MONTHLY_REF_PREFIX = "free_monthly:"


async def ensure_free_monthly_grant(
    pool: Any, user_id: UUID | str
) -> dict[str, Any]:
    """Apply this month's Free allowance once. Idempotent per period."""
    uid = UUID(str(user_id))
    period = billing_month_start()
    ref = f"{FREE_MONTHLY_REF_PREFIX}{period.isoformat()}"

    async with pool.acquire() as conn:
        async with conn.transaction():
            is_pro = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM credit_wallet_lots
                    WHERE user_id = $1
                      AND tag = 'pack'
                      AND remaining_units > 0
                      AND (expires_at IS NULL OR expires_at > now())
                )
                """,
                uid,
            )
            if is_pro:
                return {"granted": False, "reason": "pro", "user_id": str(uid)}

            done = await conn.fetchval(
                "SELECT 1 FROM credit_wallet_lots WHERE user_id = $1 AND ref_id = $2 LIMIT 1",
                uid,
                ref,
            )
            if done:
                return {"granted": False, "reason": "already_granted", "user_id": str(uid)}

            balance = int(
                await conn.fetchval(
                    "SELECT balance FROM credit_wallets WHERE user_id = $1 FOR UPDATE",
                    uid,
                )
                or 0
            )

            free_lots = await conn.fetch(
                """
                SELECT id, remaining_units
                FROM credit_wallet_lots
                WHERE user_id = $1
                  AND ref_id LIKE 'free_monthly:%'
                  AND remaining_units > 0
                FOR UPDATE
                """,
                uid,
            )
            free_remaining = sum(int(row["remaining_units"]) for row in free_lots)
            other = max(0, balance - free_remaining)

            if free_remaining > 0:
                await conn.execute(
                    """
                    UPDATE credit_wallet_lots
                    SET remaining_units = 0
                    WHERE user_id = $1 AND ref_id LIKE 'free_monthly:%'
                    """,
                    uid,
                )
                await conn.execute(
                    """
                    UPDATE credit_wallets
                    SET balance = balance - $2, updated_at = now()
                    WHERE user_id = $1
                    """,
                    uid,
                    free_remaining,
                )

            if other >= FREE_MONTHLY_UNITS:
                # Other credits already cover the cap; just mark this period.
                await conn.execute(
                    """
                    INSERT INTO credit_grant_claims (user_id, reason, ref_id, created_at)
                    VALUES ($1, 'free_monthly', $2, now())
                    ON CONFLICT (user_id, reason, ref_id) DO NOTHING
                    """,
                    uid,
                    period.isoformat(),
                )
                return {"granted": False, "reason": "above_cap", "user_id": str(uid)}

            grant_units = FREE_MONTHLY_UNITS - other
            await conn.execute(
                """
                UPDATE credit_wallets
                SET balance = balance + $2, updated_at = now()
                WHERE user_id = $1
                """,
                uid,
                grant_units,
            )
            await conn.execute(
                """
                INSERT INTO credit_wallet_lots
                    (id, user_id, tag, amount_units, remaining_units,
                     expires_at, period_start, created_at, ref_id)
                VALUES ($1, $2, 'grant', $3, $3, $4, $5, now(), $6)
                """,
                uuid4(),
                uid,
                grant_units,
                next_billing_month_start(),
                period,
                ref,
            )
            return {
                "granted": True,
                "credits": grant_units / 10_000,
                "user_id": str(uid),
                "period": period.isoformat(),
            }
