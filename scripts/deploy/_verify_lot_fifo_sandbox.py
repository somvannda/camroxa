"""Sandbox: verify atomic_deduct consumes lots FIFO and refund restores them."""

from __future__ import annotations

import asyncio
import uuid

import asyncpg

from platform_api.config import get_settings
from platform_api.dependencies import get_credit_repo, get_v3_grant_service, set_db_pool
from platform_api.services.credit_units import credits_to_units, units_to_credits

EMAIL = "duke@test.com"


async def _lot_remaining(pool, user_id) -> int:
    value = await pool.fetchval(
        "SELECT COALESCE(SUM(remaining_units),0) FROM credit_wallet_lots "
        "WHERE user_id=$1 AND tag='grant'",
        user_id,
    )
    return int(value or 0)


async def main() -> None:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    set_db_pool(pool)
    try:
        user_id = await pool.fetchval("SELECT id FROM users WHERE lower(email)=lower($1)", EMAIL)
        if user_id is None:
            raise SystemExit(f"missing {EMAIL}")
        await pool.execute("DELETE FROM credit_wallet_lots WHERE user_id=$1", user_id)
        await pool.execute(
            "UPDATE credit_wallets SET balance=0, updated_at=NOW() WHERE user_id=$1", user_id
        )

        grants = get_v3_grant_service()
        repo = get_credit_repo()
        await grants.ensure_period_grant(user_id)
        start_lot = await _lot_remaining(pool, user_id)
        print(f"after grant lot={units_to_credits(start_lot)}")

        ref = str(uuid.uuid4())
        ok = await repo.atomic_deduct(
            user_id,
            credits_to_units(7.5),
            "v3_music",
            ref_id=ref,
            metadata={"billing": "wallet", "op": "music"},
        )
        assert ok, "deduct failed"
        lot_after = await _lot_remaining(pool, user_id)
        wallet_after = int(await pool.fetchval("SELECT balance FROM credit_wallets WHERE user_id=$1", user_id))
        print(f"after deduct lot={units_to_credits(lot_after)} wallet={units_to_credits(wallet_after)}")
        if lot_after != credits_to_units(42.5):
            raise SystemExit("LOT_NOT_DECREMENTED")

        await repo.refund(user_id, credits_to_units(7.5), "v3_refund_music", ref_id=ref)
        lot_refunded = await _lot_remaining(pool, user_id)
        wallet_refunded = int(await pool.fetchval("SELECT balance FROM credit_wallets WHERE user_id=$1", user_id))
        print(f"after refund lot={units_to_credits(lot_refunded)} wallet={units_to_credits(wallet_refunded)}")
        if lot_refunded != credits_to_units(50) or wallet_refunded != credits_to_units(50):
            raise SystemExit("REFUND_DID_NOT_RESTORE_LOT")
        print("LOT_FIFO_REFUND_OK")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
