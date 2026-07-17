"""Hard-delete all non-admin users and remove the Trial plan.

Usage:
    PYTHONPATH=. python platform_api/scripts/reset_non_admin_users.py --dry-run
    PYTHONPATH=. python platform_api/scripts/reset_non_admin_users.py --confirm
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from uuid import UUID

import asyncpg

from platform_api.config import get_settings
from platform_api.dependencies import get_user_service, set_db_pool

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "admin@mgfaceless.com"
TRIAL_PLAN_NAMES = ("Trial", "trial")


async def _connect_pool() -> asyncpg.Pool:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.create_pool(dsn)


async def _list_users_to_delete(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT id, email, role, status
        FROM users
        WHERE LOWER(email) <> LOWER($1)
        ORDER BY created_at
        """,
        ADMIN_EMAIL,
    )


async def _trial_plan(pool: asyncpg.Pool) -> asyncpg.Record | None:
    for name in TRIAL_PLAN_NAMES:
        row = await pool.fetchrow(
            "SELECT id, name FROM plans WHERE LOWER(name) = LOWER($1)",
            name,
        )
        if row is not None:
            return row
    return None


async def _delete_trial_plan(pool: asyncpg.Pool, *, dry_run: bool) -> None:
    trial = await _trial_plan(pool)
    if trial is None:
        print("Trial plan: not found (nothing to delete)")
        return

    plan_id = trial["id"]
    license_count = await pool.fetchval(
        "SELECT COUNT(*) FROM licenses WHERE plan_id = $1",
        plan_id,
    )
    offer_count = await pool.fetchval(
        "SELECT COUNT(*) FROM plan_offers WHERE plan_id = $1",
        plan_id,
    )
    print(
        f"Trial plan: {trial['name']} ({plan_id}) — "
        f"{license_count} license row(s), {offer_count} offer row(s)"
    )
    if dry_run:
        return

    await pool.execute("DELETE FROM plan_offers WHERE plan_id = $1", plan_id)
    await pool.execute("DELETE FROM licenses WHERE plan_id = $1", plan_id)
    await pool.execute("DELETE FROM plans WHERE id = $1", plan_id)
    print(f"Deleted Trial plan {trial['name']}")


async def run(*, dry_run: bool) -> None:
    pool = await _connect_pool()
    set_db_pool(pool)
    try:
        admin = await pool.fetchrow(
            "SELECT id, email FROM users WHERE LOWER(email) = LOWER($1)",
            ADMIN_EMAIL,
        )
        if admin is None:
            raise SystemExit(f"Admin account not found: {ADMIN_EMAIL}")

        users = await _list_users_to_delete(pool)
        print(f"KEEP admin: {admin['email']} ({admin['id']})")
        print(f"Users to hard-delete: {len(users)}")
        for row in users:
            print(f"  - {row['email']} ({row['role']}, {row['status']})")

        if dry_run:
            print("\n[DRY RUN] No changes made.")
            await _delete_trial_plan(pool, dry_run=True)
            return

        user_service = get_user_service()

        deleted = 0
        for row in users:
            user_id = row["id"]
            await user_service.hard_delete_user(UUID(str(user_id)))
            deleted += 1
            print(f"Hard-deleted {row['email']}")

        remaining = await pool.fetchval(
            "SELECT COUNT(*) FROM users WHERE LOWER(email) <> LOWER($1)",
            ADMIN_EMAIL,
        )
        print(f"\nDone. Hard-deleted {deleted} user(s). Remaining non-admin users: {remaining}")

        await _delete_trial_plan(pool, dry_run=False)

        plans = await pool.fetch("SELECT name FROM plans ORDER BY name")
        print("Plans remaining:", ", ".join(r["name"] for r in plans) or "(none)")
    finally:
        await pool.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Hard-delete non-admin users and Trial plan")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without changing the database",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Execute the reset (required for destructive run)",
    )
    args = parser.parse_args()
    if not args.dry_run and not args.confirm:
        parser.error("Pass --dry-run to preview or --confirm to execute")
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
