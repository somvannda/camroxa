"""Claw back stacked Free daily grants. Keep one day's credits (50).

Runs on the API host with the platform venv.
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import asyncpg

from platform_api.config import get_settings
from platform_api.services.credit_units import CREDIT_SCALE, units_to_credits

KEEP_DAILY_CREDITS = 50


async def main() -> None:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        rows = await pool.fetch(
            """
            SELECT
              u.id,
              u.email,
              w.balance,
              COALESCE(SUM(t.amount) FILTER (
                WHERE t.reason = 'v3_daily_grant' AND t.direction = 'credit'
              ), 0) AS daily_granted
            FROM users u
            JOIN credit_wallets w ON w.user_id = u.id
            LEFT JOIN credit_transactions t ON t.user_id = u.id
            GROUP BY u.id, u.email, w.balance
            HAVING COALESCE(SUM(t.amount) FILTER (
                WHERE t.reason = 'v3_daily_grant' AND t.direction = 'credit'
              ), 0) > $1
            ORDER BY u.email
            """,
            KEEP_DAILY_CREDITS * CREDIT_SCALE,
        )
        print(f"stacked_users {len(rows)}")
        keep_units = KEEP_DAILY_CREDITS * CREDIT_SCALE
        for row in rows:
            extra_minted = int(row["daily_granted"]) - keep_units
            wallet = int(row["balance"])
            claw = min(extra_minted, max(0, wallet - keep_units))
            print(
                f"{row['email']} wallet={units_to_credits(wallet)} "
                f"daily_granted={units_to_credits(int(row['daily_granted']))} "
                f"claw={units_to_credits(claw)}"
            )
            if claw <= 0:
                continue
            async with pool.acquire() as conn:
                async with conn.transaction():
                    updated = await conn.fetchrow(
                        """
                        UPDATE credit_wallets
                        SET balance = balance - $2, updated_at = NOW()
                        WHERE user_id = $1 AND balance >= $2
                        RETURNING balance
                        """,
                        row["id"],
                        claw,
                    )
                    if updated is None:
                        print(f"SKIP {row['email']} insufficient balance")
                        continue
                    await conn.execute(
                        """
                        INSERT INTO credit_transactions
                            (id, user_id, amount, direction, reason, ref_id, metadata, created_at)
                        VALUES ($1, $2, $3, 'debit', $4, $5, $6::jsonb, NOW())
                        """,
                        uuid4(),
                        row["id"],
                        claw,
                        "v3_daily_grant_clawback",
                        f"daily_clawback:{row['id']}",
                        json.dumps(
                            {
                                "source": "v3",
                                "keep_credits": KEEP_DAILY_CREDITS,
                                "stacked_daily_grant": True,
                            }
                        ),
                    )
                    print(
                        f"CLAWED {row['email']} new_wallet={units_to_credits(int(updated['balance']))}"
                    )
        print("DAILY_GRANT_CLAWBACK_DONE")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
