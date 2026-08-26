"""Call ensure_daily_grant several times and print the wallet. Must not stack."""

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
        user_id = await pool.fetchval("SELECT id FROM users WHERE lower(email)=lower($1)", EMAIL)
        if user_id is None:
            raise SystemExit(f"missing {EMAIL}")
        grants = get_v3_grant_service()
        for i in range(5):
            result = await grants.ensure_daily_grant(user_id)
            print(f"call {i+1} granted={result.get('granted')} reason={result.get('reason')}")
        wallet = await pool.fetchval("SELECT balance FROM credit_wallets WHERE user_id=$1", user_id)
        print(f"WALLET_CREDITS {units_to_credits(int(wallet))}")
        if int(wallet) != 50 * 10000:
            raise SystemExit("DAILY_GRANT_STILL_STACKING")
        print("DAILY_GRANT_IDEMPOTENT_OK")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
