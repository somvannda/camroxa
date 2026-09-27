"""Sandbox: call ensure_period_grant several times for a Free user; wallet must not stack."""

from __future__ import annotations

import asyncio

import asyncpg

from platform_api.config import get_settings
from platform_api.dependencies import get_v3_grant_service, set_db_pool
from platform_api.services.credit_units import units_to_credits

EMAIL = "duke@test.com"


async def main() -> None:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    set_db_pool(pool)
    try:
        free = await pool.fetchrow(
            "SELECT id, name, monthly_credits, daily_credits FROM plans "
            "WHERE lower(name)='free' AND is_active=true ORDER BY updated_at DESC LIMIT 1"
        )
        print("FREE_PLAN", dict(free) if free else None)
        user_id = await pool.fetchval("SELECT id FROM users WHERE lower(email)=lower($1)", EMAIL)
        if user_id is None:
            raise SystemExit(f"missing {EMAIL}")
        # Clean slate for the test user.
        await pool.execute("DELETE FROM credit_wallet_lots WHERE user_id=$1", user_id)
        await pool.execute(
            "UPDATE credit_wallets SET balance=0, updated_at=NOW() WHERE user_id=$1", user_id
        )
        grants = get_v3_grant_service()
        for i in range(5):
            result = await grants.ensure_period_grant(user_id)
            print(
                f"call {i+1} granted={result.get('granted')} "
                f"reason={result.get('reason')} credits={result.get('credits')}"
            )
        wallet = int(await pool.fetchval("SELECT balance FROM credit_wallets WHERE user_id=$1", user_id) or 0)
        lots = int(
            await pool.fetchval(
                "SELECT COUNT(*) FROM credit_wallet_lots WHERE user_id=$1 AND tag='grant'", user_id
            )
            or 0
        )
        print(f"WALLET_CREDITS {units_to_credits(wallet)} GRANT_LOTS {lots}")
        if lots != 1:
            raise SystemExit("PERIOD_GRANT_STACKED")
        if wallet != 50 * 10000:
            raise SystemExit(f"PERIOD_GRANT_WRONG_BALANCE {units_to_credits(wallet)}")
        print("PERIOD_GRANT_IDEMPOTENT_OK")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
