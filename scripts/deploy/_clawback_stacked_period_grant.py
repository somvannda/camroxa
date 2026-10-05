"""Claw back stacked Free *period* grants, keeping one month's allowance.

Companion to ``_clawback_stacked_daily_grant.py`` for the monthly-grant bug: a
license-less Free account was minted a ``v3_period_grant`` every day, and each
lot lived a full billing cycle, so grants stacked. This keeps the Free plan's
``monthly_credits`` (one month's allowance) and claws back the rest, using the
grant lots as the source of truth (top-ups / ``quota_conversion`` lots are left
untouched).

Idempotent: after a run the grant lots total exactly the kept allowance, so a
second run is a no-op.

Dry-run by default. Pass ``--apply`` to write. Runs on the API host with the
platform venv:

    python /tmp/_clawback_stacked_period_grant.py            # dry run
    python /tmp/_clawback_stacked_period_grant.py --apply    # write
"""

from __future__ import annotations

import argparse
import asyncio
import json
from uuid import uuid4

import asyncpg

from platform_api.config import get_settings
from platform_api.services.billing_calendar import billing_month_start, next_billing_month_start
from platform_api.services.credit_units import CREDIT_SCALE, units_to_credits

DEFAULT_KEEP_CREDITS = 50

FREE_USERS_SQL = """
SELECT u.id, u.email, w.balance,
       COALESCE(SUM(lot.remaining_units), 0) AS grant_remaining
FROM users u
JOIN credit_wallets w ON w.user_id = u.id
LEFT JOIN credit_wallet_lots lot ON lot.user_id = u.id AND lot.tag = 'grant'
WHERE NOT EXISTS (
        SELECT 1 FROM licenses l WHERE l.user_id = u.id AND l.status = 'active'
          AND (l.expires_at IS NULL OR l.expires_at > NOW()))
  AND NOT EXISTS (
        SELECT 1 FROM web_subscriptions ws WHERE ws.user_id = u.id AND ws.status = 'active'
          AND ws.current_period_end > NOW())
GROUP BY u.id, u.email, w.balance
HAVING COALESCE(SUM(lot.remaining_units), 0) > $1
ORDER BY w.balance DESC
"""


async def _free_plan_keep_units(pool: asyncpg.Pool) -> int:
    monthly = await pool.fetchval(
        "SELECT monthly_credits FROM plans "
        "WHERE lower(name) = 'free' AND is_active = true "
        "ORDER BY updated_at DESC LIMIT 1"
    )
    keep_credits = int(monthly) if monthly is not None else DEFAULT_KEEP_CREDITS
    if keep_credits <= 0:
        return 0
    return keep_credits * CREDIT_SCALE


async def _reconcile_user(pool: asyncpg.Pool, row, keep_units: int, apply: bool) -> bool:
    uid = row["id"]
    async with pool.acquire() as conn:
        async with conn.transaction():
            balance = int(
                await conn.fetchval(
                    "SELECT balance FROM credit_wallets WHERE user_id = $1 FOR UPDATE", uid
                )
            )
            grant_remaining = int(
                await conn.fetchval(
                    "SELECT COALESCE(SUM(remaining_units), 0) FROM credit_wallet_lots "
                    "WHERE user_id = $1 AND tag = 'grant'",
                    uid,
                )
            )
            # Non-grant lots (top-ups, quota_conversion, admin, daily) are legitimate
            # and must survive: cap the claw so the wallet never drops below them.
            non_grant_remaining = int(
                await conn.fetchval(
                    "SELECT COALESCE(SUM(remaining_units), 0) FROM credit_wallet_lots "
                    "WHERE user_id = $1 AND tag <> 'grant'",
                    uid,
                )
            )
            # Spend-adjusted grant still in the wallet, then keep one month of it.
            grant_portion = max(0, balance - non_grant_remaining)
            excess = max(0, grant_remaining - keep_units)
            claw = min(excess, max(0, grant_portion - keep_units))
            month_start = billing_month_start()
            next_start = next_billing_month_start(from_date=month_start)
            if not apply:
                print(
                    f"DRY {row['email']} wallet={units_to_credits(balance)} "
                    f"grant_lots={units_to_credits(grant_remaining)} "
                    f"non_grant={units_to_credits(non_grant_remaining)} "
                    f"claw={units_to_credits(claw)} "
                    f"new_wallet={units_to_credits(balance - claw)}"
                )
                return claw > 0

            new_balance = balance
            if claw > 0:
                updated = await conn.fetchrow(
                    """
                    UPDATE credit_wallets
                    SET balance = balance - $2, updated_at = NOW()
                    WHERE user_id = $1 AND balance >= $2
                    RETURNING balance
                    """,
                    uid,
                    claw,
                )
                if updated is None:
                    print(f"SKIP {row['email']} insufficient balance")
                    return False
                new_balance = int(updated["balance"])
                await conn.execute(
                    """
                    INSERT INTO credit_transactions
                        (id, user_id, amount, direction, reason, ref_id, metadata, created_at)
                    VALUES ($1, $2, $3, 'debit', $4, $5, $6::jsonb, NOW())
                    """,
                    uuid4(),
                    uid,
                    claw,
                    "v3_period_grant_clawback",
                    f"period_grant_clawback:{uid}:{month_start.isoformat()}",
                    json.dumps(
                        {
                            "source": "v3",
                            "keep_credits": keep_units // CREDIT_SCALE,
                            "stacked_period_grant": True,
                        }
                    ),
                )
            # Zero every grant lot, then ensure exactly one current-month lot so
            # later expiry cannot double-claw the reconciled balance.
            await conn.execute(
                "UPDATE credit_wallet_lots SET remaining_units = 0 "
                "WHERE user_id = $1 AND tag = 'grant'",
                uid,
            )
            existing_lot = await conn.fetchval(
                "SELECT id FROM credit_wallet_lots "
                "WHERE user_id = $1 AND tag = 'grant' AND period_start = $2",
                uid,
                month_start,
            )
            lot_remaining = min(keep_units, max(0, new_balance - non_grant_remaining))
            if existing_lot is not None:
                await conn.execute(
                    "UPDATE credit_wallet_lots "
                    "SET amount_units = $2, remaining_units = $3, expires_at = $4 "
                    "WHERE id = $1",
                    existing_lot,
                    keep_units,
                    lot_remaining,
                    next_start,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO credit_wallet_lots
                        (id, user_id, tag, amount_units, remaining_units, expires_at, period_start, created_at)
                    VALUES ($1, $2, 'grant', $3, $4, $5, $6, NOW())
                    """,
                    uuid4(),
                    uid,
                    keep_units,
                    lot_remaining,
                    next_start,
                    month_start,
                )
            print(
                f"RECONCILED {row['email']} wallet={units_to_credits(balance)} -> "
                f"{units_to_credits(new_balance)} (claw {units_to_credits(claw)}, "
                f"keep {units_to_credits(keep_units)})"
            )
            return True


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = parser.parse_args()

    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        keep_units = await _free_plan_keep_units(pool)
        print(f"mode={'APPLY' if args.apply else 'DRY-RUN'} keep_credits={units_to_credits(keep_units)}")
        if keep_units <= 0:
            print("NO_FREE_MONTHLY_ALLOWANCE; nothing to do")
            return
        rows = await pool.fetch(FREE_USERS_SQL, keep_units)
        print(f"affected_users {len(rows)}")
        changed = 0
        for row in rows:
            if await _reconcile_user(pool, row, keep_units, args.apply):
                changed += 1
        print(f"CLAWBACK_DONE changed={changed} applied={args.apply}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
