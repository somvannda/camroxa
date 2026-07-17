"""Audit user-related row counts before a bulk reset (read-only)."""
from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from platform_api.config import get_settings

ADMIN_EMAIL = "admin@mgfaceless.com"

# Tables with user_id column (user-owned data).
USER_ID_TABLES = [
    "invitation_code_redemptions",
    "redeem_code_redemptions",
    "billing_payments",
    "onboarding_drafts",
    "onboarding_ai_usage",
    "client_log_batches",
    "profile_video_templates",
    "youtube_connect_sessions",
    "youtube_connected_accounts",
    "youtube_upload_jobs",
    "usage_tracking",
    "image_jobs",
    "suno_tasks",
    "batch_channel_assets",
    "batch_channel_albums",
    "songs",
    "batches",
    "channel_profiles",
    "music_descriptions",
    "music_structures",
    "credit_transactions",
    "credit_wallets",
    "refresh_tokens",
    "email_verifications",
    "licenses",
    "user_settings",
    "notification_queue",
    "plan_usage",
    "content_pool_reservations",
]

ACTOR_ID_TABLES = [
    "audit_logs",
]

# System/catalog tables — listed for visibility, not reset.
SYSTEM_TABLES = [
    "plans",
    "plan_offers",
    "credit_packs",
    "credit_pricing",
    "ai_model_costs",
    "system_settings",
    "rate_limit_config",
    "youtube_oauth_apps",
    "image_sample_packs",
    "content_pool_items",
    "content_pool_presets",
    "invitation_codes",
    "redeem_codes",
    "music_languages",
    "blog_posts",
    "api_key_pool",
]


async def _table_exists(conn: asyncpg.Connection, table: str) -> bool:
    val = await conn.fetchval("SELECT to_regclass($1)", f"public.{table}")
    return val is not None


async def _count(
    conn: asyncpg.Connection,
    table: str,
    *,
    where: str = "",
    args: tuple[Any, ...] = (),
) -> int | None:
    if not await _table_exists(conn, table):
        return None
    clause = f" WHERE {where}" if where else ""
    return int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}{clause}", *args))


async def main() -> None:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        admin = await conn.fetchrow(
            "SELECT id, email, role, status FROM users WHERE LOWER(email) = LOWER($1)",
            ADMIN_EMAIL,
        )
        print(f"=== KEEP: {ADMIN_EMAIL} ===")
        if admin:
            print(f"  id={admin['id']} role={admin['role']} status={admin['status']}")
        else:
            print("  WARNING: admin account not found")

        users = await conn.fetch(
            """
            SELECT id, email, role, status, deleted_at IS NOT NULL AS is_deleted
            FROM users
            ORDER BY created_at
            """
        )
        print(f"\n=== USERS ({len(users)} total) ===")
        delete_users = [u for u in users if admin is None or u["id"] != admin["id"]]
        for u in users:
            marker = "KEEP" if admin and u["id"] == admin["id"] else "DELETE"
            deleted = " [soft-deleted]" if u["is_deleted"] else ""
            print(f"  [{marker}] {u['email']} ({u['role']}){deleted}")
        print(f"\nUsers to delete: {len(delete_users)}")

        admin_id = admin["id"] if admin else None

        print("\n=== USER-OWNED DATA (rows for users to delete) ===")
        total_user_rows = 0
        for table in USER_ID_TABLES:
            if admin_id is not None:
                n = await _count(conn, table, where="user_id <> $1", args=(admin_id,))
            else:
                n = await _count(conn, table)
            if n is None:
                continue
            if n > 0:
                print(f"  {table}: {n}")
                total_user_rows += n
            else:
                print(f"  {table}: 0")

        # User-owned prompts (user_id not null) — music_descriptions/structures may mix admin+user
        for table in ("music_descriptions", "music_structures"):
            if not await _table_exists(conn, table):
                continue
            cols = await conn.fetch(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = $1 AND column_name = 'user_id'
                """,
                table,
            )
            if not cols:
                continue
            if admin_id is not None:
                n = await _count(
                    conn,
                    table,
                    where="user_id IS NOT NULL AND user_id <> $1",
                    args=(admin_id,),
                )
            else:
                n = await _count(conn, table, where="user_id IS NOT NULL")
            if n and n > 0:
                print(f"  {table} (user-owned only): {n}")

        print("\n=== ACTOR DATA (audit logs by deleted users) ===")
        for table in ACTOR_ID_TABLES:
            if admin_id is not None:
                n = await _count(conn, table, where="actor_id IS NOT NULL AND actor_id <> $1", args=(admin_id,))
            else:
                n = await _count(conn, table, where="actor_id IS NOT NULL")
            if n is not None:
                print(f"  {table}: {n or 0}")

        if admin_id is not None:
            print(f"\n=== ADMIN DATA KEPT ({ADMIN_EMAIL}) ===")
            for table in USER_ID_TABLES:
                n = await _count(conn, table, where="user_id = $1", args=(admin_id,))
                if n is not None and n > 0:
                    print(f"  {table}: {n}")

        print("\n=== SYSTEM DATA (unchanged) ===")
        for table in SYSTEM_TABLES:
            n = await _count(conn, table)
            if n is None:
                continue
            print(f"  {table}: {n}")

        # Admin prompts (user_id IS NULL)
        for table in ("music_descriptions", "music_structures"):
            if await _table_exists(conn, table):
                cols = await conn.fetch(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = $1 AND column_name = 'user_id'
                    """,
                    table,
                )
                if cols:
                    n = await _count(conn, table, where="user_id IS NULL")
                    print(f"  {table} (system/admin prompts): {n or 0}")

        print(f"\nApprox. user-owned rows to remove: {total_user_rows}+ (excludes users row itself)")
        print(f"User accounts to remove: {len(delete_users)}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
