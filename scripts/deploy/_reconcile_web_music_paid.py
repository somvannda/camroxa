"""Reconcile web-music PAID subscribers to the credit they really earned.

For every user with a paid ``web_subscriptions`` row (the $79 desktop / license
plans are ``desktop_pro`` and excluded), compute:

    real = current paid-period allowance + non-grant credits - net generations

where "non-grant" = quota_conversion / pack / admin lots (never touched), and
"net generations" = all v3 debits minus v3 refunds. This charges the user for the
songs/ops they actually ran, so the wallet reflects what they may really use now.

Free users and desktop/license users are not touched. Dry-run by default.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import timezone
from uuid import uuid4

import asyncpg

from platform_api.config import get_settings
from platform_api.services.billing_calendar import billing_month_start, next_billing_month_start
from platform_api.services.credit_units import CREDIT_SCALE, units_to_credits

DEFAULT_FREE_CREDITS = 50

PAID_WEB_USERS_SQL = """
SELECT u.id, u.email, w.balance
FROM users u
JOIN credit_wallets w ON w.user_id = u.id
WHERE EXISTS (
    SELECT 1 FROM web_subscriptions ws
    WHERE ws.user_id = u.id
      AND ws.status IN ('active', 'expired')
      AND ws.last_payment_at IS NOT NULL
)
ORDER BY u.email
"""


async def _free_monthly(pool: asyncpg.Pool) -> int:
    value = await pool.fetchval(
        "SELECT monthly_credits FROM plans "
        "WHERE lower(name) = 'free' AND is_active = true "
        "ORDER BY updated_at DESC LIMIT 1"
    )
    return int(value) if value is not None else DEFAULT_FREE_CREDITS


async def _target_units(conn, uid, free_units: int) -> tuple[int, dict]:
    sub = await conn.fetchrow(
        """
        SELECT ws.monthly_credits_granted, ws.current_period_end, p.name AS plan, p.monthly_credits
        FROM web_subscriptions ws JOIN plans p ON p.id = ws.plan_id
        WHERE ws.user_id = $1 AND ws.status = 'active'
        ORDER BY ws.current_period_end DESC LIMIT 1
        """,
        uid,
    )
    now = await conn.fetchval("SELECT NOW()")
    if sub is not None and sub["current_period_end"] > now:
        allowance = max(int(sub["monthly_credits_granted"] or 0), int(sub["monthly_credits"] or 0))
        plan = sub["plan"]
    else:
        allowance = free_units // CREDIT_SCALE  # lapsed -> back on Free
        plan = "Free (lapsed)"
    non_grant = int(
        await conn.fetchval(
            "SELECT COALESCE(SUM(remaining_units),0) FROM credit_wallet_lots "
            "WHERE user_id = $1 AND tag <> 'grant'",
            uid,
        )
    )
    net_spend = int(
        await conn.fetchval(
            """
            SELECT COALESCE(SUM(amount) FILTER (
                     WHERE direction='debit' AND reason LIKE 'v3_%'
                       AND reason NOT IN ('v3_period_grant_clawback','v3_paid_web_reconcile')), 0)
                 - COALESCE(SUM(amount) FILTER (
                     WHERE direction='refund' AND reason LIKE 'v3_%'), 0)
            FROM credit_transactions WHERE user_id = $1
            """,
            uid,
        )
    )
    target = max(0, allowance * CREDIT_SCALE + non_grant - net_spend)
    return target, {
        "plan": plan,
        "allowance": allowance,
        "non_grant": non_grant,
        "net_spend": net_spend,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        free_units = (await _free_monthly(pool)) * CREDIT_SCALE
        rows = await pool.fetch(PAID_WEB_USERS_SQL)
        print(f"mode={'APPLY' if args.apply else 'DRY-RUN'} paid_web_users={len(rows)}")
        for row in rows:
            uid = row["id"]
            async with pool.acquire() as conn:
                async with conn.transaction():
                    balance = int(
                        await conn.fetchval(
                            "SELECT balance FROM credit_wallets WHERE user_id=$1 FOR UPDATE", uid
                        )
                    )
                    target, info = await _target_units(conn, uid, free_units)
                    delta = target - balance
                    if balance == 0 and info["net_spend"] == 0:
                        # No credit history on this account; don't mint anything.
                        print(f"SKIP {row['email']} plan={info['plan']} (no credit activity)")
                        continue
                    if delta == 0:
                        print(f"OK {row['email']} plan={info['plan']} balance={units_to_credits(balance)}")
                        continue
                    action = "CREDIT" if delta > 0 else "DEBIT"
                    print(
                        f"{action} {row['email']} plan={info['plan']} "
                        f"allowance={info['allowance']} non_grant={units_to_credits(info['non_grant'])} "
                        f"net_spend={units_to_credits(info['net_spend'])} "
                        f"balance={units_to_credits(balance)} -> real={units_to_credits(target)} "
                        f"(delta {units_to_credits(delta)})"
                    )
                    if not args.apply:
                        continue
                    await conn.execute(
                        "UPDATE credit_wallets SET balance=$2, updated_at=NOW() WHERE user_id=$1",
                        uid,
                        target,
                    )
                    await conn.execute(
                        """
                        INSERT INTO credit_transactions
                            (id, user_id, amount, direction, reason, ref_id, metadata, created_at)
                        VALUES ($1,$2,$3,$4,'v3_paid_web_reconcile',$5,$6::jsonb,NOW())
                        """,
                        uuid4(),
                        uid,
                        abs(delta),
                        "credit" if delta > 0 else "debit",
                        f"paid_web_reconcile:{uid}:{billing_month_start().isoformat()}",
                        json.dumps({"plan": info["plan"], "allowance": info["allowance"]}),
                    )
                    # Normalise grant lots to one current-month lot.
                    await conn.execute(
                        "UPDATE credit_wallet_lots SET remaining_units=0 "
                        "WHERE user_id=$1 AND tag='grant'",
                        uid,
                    )
                    month_start = billing_month_start()
                    next_start = next_billing_month_start(from_date=month_start)
                    lot_remaining = min(info["allowance"] * CREDIT_SCALE, max(0, target - info["non_grant"]))
                    existing = await conn.fetchval(
                        "SELECT id FROM credit_wallet_lots "
                        "WHERE user_id=$1 AND tag='grant' AND period_start=$2",
                        uid,
                        month_start,
                    )
                    if existing is not None:
                        await conn.execute(
                            "UPDATE credit_wallet_lots SET amount_units=$2, remaining_units=$3, expires_at=$4 WHERE id=$1",
                            existing,
                            info["allowance"] * CREDIT_SCALE,
                            lot_remaining,
                            next_start,
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO credit_wallet_lots
                                (id,user_id,tag,amount_units,remaining_units,expires_at,period_start,created_at)
                            VALUES ($1,$2,'grant',$3,$4,$5,$6,NOW())
                            """,
                            uuid4(),
                            uid,
                            info["allowance"] * CREDIT_SCALE,
                            lot_remaining,
                            next_start,
                            month_start,
                        )
        print(f"WEB_MUSIC_PAID_RECONCILE_DONE applied={args.apply}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
