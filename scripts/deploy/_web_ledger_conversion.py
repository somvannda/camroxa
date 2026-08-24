"""Dry-run or apply leftover CutLuy web credits onto credit_wallets.

Used by sandbox and (later) production wrappers. Does not choose a host.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os

import asyncpg

from platform_api.config import get_settings
from platform_api.dependencies import get_v3_web_ledger_service, set_db_pool

APPLY = os.environ.get("APPLY", "0") == "1"


async def main() -> None:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    set_db_pool(pool)
    try:
        service = get_v3_web_ledger_service()
        rows = await service.apply(None, confirm=True) if APPLY else await service.dry_run()
        emails = {str(row["id"]): row["email"] for row in await pool.fetch("SELECT id, email FROM users")}
        fieldnames = [
            "status",
            "bucket",
            "email",
            "user_id",
            "plan_name",
            "price_cents",
            "monthly_remaining",
            "topup_remaining",
            "credits_to_mint",
            "already_applied",
            "skipped",
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        mint_total = 0
        applied = 0
        for row in rows:
            mint_total += int(row.get("credits_to_mint") or 0)
            if row.get("status") == "applied":
                applied += 1
            writer.writerow(
                {
                    **row,
                    "email": emails.get(row["user_id"], ""),
                    "status": row.get("status", "dry_run"),
                }
            )
        print(
            "=== web ledger rows",
            len(rows),
            "credits_to_mint_sum",
            mint_total,
            "applied",
            applied,
            "APPLY",
            int(APPLY),
            "===",
        )
        print(buf.getvalue(), end="")
        print("WEB_LEDGER_CONVERSION_DONE")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
