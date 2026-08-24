"""Sandbox leftover conversion DRY-RUN only. Never apply / mint / flip flag."""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import datetime, timezone

import asyncpg

from platform_api.config import get_settings
from platform_api.dependencies import get_v3_conversion_service, set_db_pool
from platform_api.services.credit_units import units_to_credits

SPEC_FIELDS = [
    "user_id",
    "email",
    "plan_id",
    "plan_name",
    "price_cents",
    "plan_song_limit",
    "addon_slots",
    "music_used",
    "leftover_packages",
    "credits_to_mint",
    "existing_wallet",
    "profile_count",
    "addon_pending",
    "next_grant",
    "next_price_cents",
    "bucket",
]


def _bucket(row: dict) -> str:
    name = str(row.get("plan_name") or "").lower()
    if "lifetime" in name:
        return "lifetime_skipped"
    expires = row.get("expires_at")
    now = datetime.now(timezone.utc)
    if expires is not None:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            return "expired"
    allowance = int(row.get("profile_allowance") or 0)
    cycle = int(row.get("billing_cycle_days") or 0)
    price = int(row.get("price_cents") or 0)
    if allowance == 2 and cycle == 30 and price == 7900:
        return "monthly_2ch_79"
    if allowance == 6:
        return "monthly_6ch" if cycle == 30 else f"prepaid_{cycle}d_6ch"
    if allowance == 10:
        return "monthly_10ch" if cycle == 30 else f"prepaid_{cycle}d_10ch"
    if cycle >= 365:
        return "prepaid_annual"
    if cycle == 180:
        return "prepaid_6mo"
    if not row.get("plan_id"):
        return "no_active_license"
    return "monthly"


async def main() -> None:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    set_db_pool(pool)
    try:
        flag = await pool.fetchval(
            "SELECT value FROM system_settings WHERE key = 'credits_only_v3_charge'"
        )
        print("FLAG_NOW", flag)
        print("APPLY_SKIPPED confirm=false mint=false flag_flip=false")

        conversion = get_v3_conversion_service()
        service_rows = await conversion.dry_run()
        print("=== service_dry_run_rows", len(service_rows), "===")

        licenses = await pool.fetch(
            """
            SELECT DISTINCT ON (l.user_id)
                   l.user_id,
                   u.email,
                   p.id AS plan_id,
                   p.name AS plan_name,
                   COALESCE(p.price_cents, 0) AS price_cents,
                   COALESCE(p.monthly_song_limit, 0) AS plan_song_limit,
                   COALESCE(l.profile_addon_slots, 0) AS addon_slots,
                   COALESCE(l.profile_addon_pending, 0) AS addon_pending,
                   COALESCE(p.monthly_credits, 0) AS next_grant,
                   COALESCE(p.price_cents, 0) AS next_price_cents,
                   COALESCE(p.profile_allowance, 0) AS profile_allowance,
                   COALESCE(p.billing_cycle_days, 0) AS billing_cycle_days,
                   l.expires_at,
                   l.status AS license_status,
                   l.activated_at
            FROM licenses l
            JOIN users u ON u.id = l.user_id
            LEFT JOIN plans p ON p.id = l.plan_id
            WHERE l.user_id IS NOT NULL
              AND COALESCE(p.plan_type, 'desktop_pro') = 'desktop_pro'
            ORDER BY l.user_id, l.activated_at DESC NULLS LAST
            """
        )

        usage_rows = await pool.fetch(
            """
            SELECT user_id, COALESCE(SUM(monthly_count), 0) AS music_used
            FROM usage_tracking
            WHERE operation_type = 'music'
            GROUP BY user_id
            """
        )
        usage_map = {str(r["user_id"]): int(r["music_used"] or 0) for r in usage_rows}

        wallet_rows = await pool.fetch("SELECT user_id, balance FROM credit_wallets")
        wallet_map = {str(r["user_id"]): units_to_credits(int(r["balance"] or 0)) for r in wallet_rows}

        profile_rows = await pool.fetch(
            "SELECT user_id, COUNT(*) AS profile_count FROM channel_profiles GROUP BY user_id"
        )
        profile_map = {str(r["user_id"]): int(r["profile_count"] or 0) for r in profile_rows}

        preview_map = {str(r.get("user_id")): r for r in service_rows}

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=SPEC_FIELDS, extrasaction="ignore")
        writer.writeheader()

        expired = 0
        unexpired = 0
        mintable = 0
        lifetime = 0

        for lic in licenses:
            user_id = str(lic["user_id"])
            preview = preview_map.get(user_id) or {}
            bucket = _bucket(dict(lic))
            if bucket == "lifetime_skipped":
                leftover = 0
                credits = 0
                music_used = int(preview.get("music_used") or usage_map.get(user_id) or 0)
                lifetime += 1
            elif bucket == "expired":
                leftover = 0
                credits = 0
                music_used = int(usage_map.get(user_id) or 0)
                expired += 1
            else:
                leftover = int(preview.get("leftover_packages") or 0)
                credits = int(preview.get("credits_to_mint") or 0)
                music_used = int(preview.get("music_used") or 0)
                unexpired += 1
                if credits > 0:
                    mintable += 1

            writer.writerow(
                {
                    "user_id": user_id,
                    "email": lic["email"] or "",
                    "plan_id": str(lic["plan_id"] or preview.get("plan_id") or ""),
                    "plan_name": lic["plan_name"] or preview.get("plan_name") or "",
                    "price_cents": int(lic["price_cents"] or 0),
                    "plan_song_limit": int(lic["plan_song_limit"] or 0),
                    "addon_slots": int(lic["addon_slots"] or 0),
                    "music_used": music_used,
                    "leftover_packages": leftover,
                    "credits_to_mint": credits,
                    "existing_wallet": wallet_map.get(user_id, 0),
                    "profile_count": profile_map.get(user_id, 0),
                    "addon_pending": int(lic["addon_pending"] or 0),
                    "next_grant": int(lic["next_grant"] or 0),
                    "next_price_cents": int(lic["next_price_cents"] or 0),
                    "bucket": bucket,
                }
            )

        print(
            "=== conversion_csv_counts",
            "rows",
            len(licenses),
            "expired",
            expired,
            "unexpired",
            unexpired,
            "mintable",
            mintable,
            "lifetime_skipped",
            lifetime,
            "===",
        )
        print("===CSV_BEGIN===")
        print(buf.getvalue(), end="")
        print("===CSV_END===")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

