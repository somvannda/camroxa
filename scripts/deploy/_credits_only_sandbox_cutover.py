"""Run on sandbox only. Dry-run leftover conversion; apply/flag only when env says so."""

from __future__ import annotations

import asyncio
import csv
import io
import os

import asyncpg

from platform_api.config import get_settings
from platform_api.dependencies import get_v3_conversion_service, set_db_pool


APPLY = os.environ.get("APPLY", "0") == "1"
FLAG_ON = os.environ.get("FLAG_ON", "0") == "1"


async def main() -> None:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    set_db_pool(pool)
    try:
        conversion = get_v3_conversion_service()
        rows = await conversion.apply(None, confirm=True) if APPLY else await conversion.dry_run()
        emails = {str(row["id"]): row["email"] for row in await pool.fetch("SELECT id, email FROM users")}
        fieldnames = [
            "status",
            "bucket",
            "email",
            "user_id",
            "plan_name",
            "price_cents",
            "plan_song_limit",
            "song_topup",
            "music_used",
            "leftover_packages",
            "credits_to_mint",
            "already_applied",
            "skipped",
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        mint_total = 0
        flagged = 0
        for row in rows:
            leftover = int(row.get("leftover_packages") or 0)
            limit = int(row.get("plan_song_limit") or 0)
            if leftover > limit and limit > 0:
                flagged += 1
            mint_total += int(row.get("credits_to_mint") or 0)
            writer.writerow(
                {
                    **row,
                    "email": emails.get(row["user_id"], ""),
                    "status": row.get("status", "dry_run"),
                }
            )
        print(
            "=== conversion rows",
            len(rows),
            "credits_to_mint_sum",
            mint_total,
            "leftover_gt_limit",
            flagged,
            "===",
        )
        print(buf.getvalue(), end="")
        if FLAG_ON:
            await pool.execute(
                """
                INSERT INTO system_settings (key, value, value_type, updated_at)
                VALUES ('credits_only_v3_charge', 'true', 'boolean', NOW())
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    value_type = EXCLUDED.value_type,
                    updated_at = NOW()
                """
            )
            print("FLAG credits_only_v3_charge=true")
        setting = await pool.fetchval(
            "SELECT value FROM system_settings WHERE key = 'credits_only_v3_charge'"
        )
        print("FLAG_NOW", setting)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
