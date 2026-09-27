"""Production: ensure_period_grant must not change an already-granted wallet."""

from __future__ import annotations

import asyncio

import asyncpg

from platform_api.config import get_settings
from platform_api.dependencies import get_v3_grant_service, set_db_pool
from platform_api.services.credit_units import units_to_credits

EMAIL = "iamduke1987@gmail.com"


async def _state(pool, user_id):
    wallet = int(await pool.fetchval("SELECT balance FROM credit_wallets WHERE user_id=$1", user_id) or 0)
    lots = int(
        await pool.fetchval(
            "SELECT COUNT(*) FROM credit_wallet_lots WHERE user_id=$1 AND tag='grant'", user_id
        )
        or 0
    )
    return wallet, lots


async def main() -> None:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    set_db_pool(pool)
    try:
        user_id = await pool.fetchval("SELECT id FROM users WHERE lower(email)=lower($1)", EMAIL)
        if user_id is None:
            raise SystemExit(f"missing {EMAIL}")
        before = await _state(pool, user_id)
        grants = get_v3_grant_service()
        for i in range(3):
            result = await grants.ensure_period_grant(user_id)
            print(f"call {i+1} granted={result.get('granted')} reason={result.get('reason')}")
        after = await _state(pool, user_id)
        print(
            f"wallet_before={units_to_credits(before[0])} wallet_after={units_to_credits(after[0])} "
            f"lots_before={before[1]} lots_after={after[1]}"
        )
        if after != before:
            raise SystemExit("PERIOD_GRANT_CHANGED_WALLET_OR_LOTS")
        print("PROD_PERIOD_GRANT_STABLE_OK")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
