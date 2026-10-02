"""Production subscription/license transfer (probe/apply). Runs on the VPS.

MODE=probe (default): read-only — snapshot both accounts and the active
license that would be moved.
MODE=apply: revoke the source account's active license, issue an equivalent
active license to the target account (same plan + same activated/expires
dates so the paid period carries over), and revoke the source account's
sessions.

Used by run_subscription_transfer_production.py. Does not choose a host.
"""

from __future__ import annotations

import asyncio
import os
import secrets

import asyncpg

from platform_api.config import get_settings

MODE = os.environ.get("MODE", "probe")  # probe | apply
SOURCE_EMAIL = "chanpanharithtep168@gmail.com"
TARGET_EMAIL = "tepchanpanharith@gmail.com"


async def _print_license_row(conn, label: str, row) -> None:
    if row is None:
        print(f"{label} NONE")
        return
    print(label)
    for key in (
        "id",
        "license_key",
        "plan_id",
        "user_id",
        "status",
        "activated_at",
        "expires_at",
        "profile_addon_slots",
        "profile_addon_pending",
        "pending_plan_id",
        "pending_plan_effective_at",
    ):
        print(f"  {key}={row.get(key)}")


async def _user_id_by_email(conn, email: str):
    row = await conn.fetchrow(
        "SELECT id FROM users WHERE LOWER(email) = LOWER($1)", email
    )
    return row["id"] if row else None


async def probe(conn) -> None:
    print("LICENSE_COLUMNS")
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'licenses' ORDER BY ordinal_position"
    )
    print(", ".join(r["column_name"] for r in rows))

    source_id = await _user_id_by_email(conn, SOURCE_EMAIL)
    target_id = await _user_id_by_email(conn, TARGET_EMAIL)
    print(f"SOURCE id={source_id} email={SOURCE_EMAIL}")
    print(f"TARGET id={target_id} email={TARGET_EMAIL}")

    if source_id is None or target_id is None:
        print("PROBE_FAILED_USER_MISSING")
        return

    source_license = await conn.fetchrow(
        """
        SELECT * FROM licenses
        WHERE user_id = $1 AND status = 'active'
          AND (expires_at IS NULL OR expires_at > NOW())
        ORDER BY activated_at DESC
        LIMIT 1
        """,
        source_id,
    )
    await _print_license_row(conn, "SOURCE_ACTIVE_LICENSE", source_license)

    if source_license is not None:
        plan_row = await conn.fetchrow(
            "SELECT id, name, billing_cycle_days, profile_allowance, plan_kind "
            "FROM plans WHERE id = $1",
            source_license["plan_id"],
        )
        print("SOURCE_LICENSE_PLAN", dict(plan_row) if plan_row else None)

    target_license = await conn.fetchrow(
        """
        SELECT * FROM licenses
        WHERE user_id = $1 AND status = 'active'
          AND (expires_at IS NULL OR expires_at > NOW())
        ORDER BY activated_at DESC
        LIMIT 1
        """,
        target_id,
    )
    await _print_license_row(conn, "TARGET_ACTIVE_LICENSE", target_license)

    for label, uid in (("SOURCE", source_id), ("TARGET", target_id)):
        sub = await conn.fetchrow(
            "SELECT plan_id, status, current_period_end FROM web_subscriptions "
            "WHERE user_id = $1 AND status = 'active' AND current_period_end > NOW()",
            uid,
        )
        payments = await conn.fetchval(
            "SELECT COUNT(*)::int FROM billing_payments WHERE user_id = $1", uid
        )
        print(f"{label}_WEB_SUBSCRIPTION", dict(sub) if sub else None)
        print(f"{label}_BILLING_PAYMENTS", payments or 0)

    print("PROBE_DONE")


async def apply(conn) -> None:
    source_id = await _user_id_by_email(conn, SOURCE_EMAIL)
    target_id = await _user_id_by_email(conn, TARGET_EMAIL)
    if source_id is None or target_id is None:
        print("APPLY_ABORTED_USER_MISSING")
        return

    async with conn.transaction():
        # 1) Revoke the source account's active license (mirrors
        #    LicenseRepository.revoke_all_for_user).
        revoked = await conn.fetchrow(
            """
            UPDATE licenses
            SET status = 'revoked',
                revoked_at = NOW()
            WHERE user_id = $1 AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            RETURNING *
            """,
            source_id,
        )
        if revoked is None:
            print("APPLY_ABORTED_NO_ACTIVE_LICENSE")
            return
        print("REVOKED_SOURCE_LICENSE")
        print(f"  id={revoked['id']} plan_id={revoked['plan_id']}")

        # 2) Guard: target must not already hold an active license.
        existing = await conn.fetchrow(
            """
            SELECT id FROM licenses
            WHERE user_id = $1 AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
            """,
            target_id,
        )
        if existing is not None:
            print(f"APPLY_ABORTED_TARGET_HAS_LICENSE id={existing['id']}")
            return

        # 3) Issue an equivalent active license to the target, carrying the
        #    same paid period (activated_at/expires_at) and addon state.
        new_key = secrets.token_hex(32)
        created = await conn.fetchrow(
            """
            INSERT INTO licenses (
                license_key, plan_id, user_id, status,
                activated_at, expires_at,
                profile_addon_slots, profile_addon_pending,
                pending_plan_id, pending_plan_effective_at,
                distrokid_enabled, distrokid_expires_at,
                created_at
            )
            VALUES ($1, $2, $3, 'active', $4, $5, $6, $7, $8, $9, $10, $11, NOW())
            RETURNING id, license_key, plan_id, user_id, status,
                      activated_at, expires_at,
                      profile_addon_slots, profile_addon_pending,
                      distrokid_enabled, distrokid_expires_at
            """,
            new_key,
            revoked["plan_id"],
            target_id,
            revoked["activated_at"],
            revoked["expires_at"],
            int(revoked.get("profile_addon_slots") or 0),
            int(revoked.get("profile_addon_pending") or 0),
            revoked.get("pending_plan_id"),
            revoked.get("pending_plan_effective_at"),
            bool(revoked.get("distrokid_enabled") or False),
            revoked.get("distrokid_expires_at"),
        )
        print("CREATED_TARGET_LICENSE")
        print(
            f"  id={created['id']} plan_id={created['plan_id']} "
            f"activated_at={created['activated_at']} expires_at={created['expires_at']} "
            f"addon_slots={created['profile_addon_slots']} "
            f"addon_pending={created['profile_addon_pending']} "
            f"distrokid_enabled={created['distrokid_enabled']}"
        )

        # 4) Revoke the source account's sessions so they stop using the plan.
        await conn.execute(
            "UPDATE refresh_tokens SET revoked_at = NOW() "
            "WHERE user_id = $1 AND revoked_at IS NULL",
            source_id,
        )
        await conn.execute(
            "UPDATE users SET token_version = token_version + 1, updated_at = NOW() "
            "WHERE id = $1",
            source_id,
        )
        print("REVOKED_SOURCE_SESSIONS")

    # 5) Post-flight verification
    await probe(conn)
    print("APPLY_DONE")


async def main() -> None:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            if MODE == "apply":
                await apply(conn)
            else:
                await probe(conn)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
