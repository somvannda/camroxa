"""credits-only two-tier model

Removes plans, licenses, subscriptions, plan quotas and profile add-ons.

Approved cutover (2026-10-30):

  Pro until original expiry, keep wallet:
    sophay@camxora.com            2026-11-01   8,658.95
    mr.zhiwei@gmail.com           2026-11-01   5,009.85
    edmbass1@gmail.com            2026-11-03   2,676.43
    tepchanpanharith@gmail.com    2026-11-06       0.11
    iamduke1987@gmail.com         2026-11-05     886.00
    mr.limeang.018@gmail.com      2026-11-12     520.00

  Free with 50 credits (plan/sub already expired):
    pich.sou11@gmail.com           expired 2026-10-03
    teangchunpanhavorn@gmail.com   expired 2026-10-06

  Other live pack buyers stay Pro until their pack expiry.
  Everyone else keeps their existing signup credits as one grant lot.

No invented expiry dates: converted pack lots use the source expiry exactly.

This migration is destructive. Originals are copied to *_archive tables first.

Revision ID: 174
Revises: 173
"""

from __future__ import annotations

from alembic import op

revision = "174"
down_revision = "173"
branch_labels = None
depends_on = None

ARCHIVE_TABLES = (
    "plans",
    "licenses",
    "plan_offers",
    "plan_usage",
    "web_subscriptions",
    "user_period_quota_topups",
    "daily_quota_bank",
)

# 50 display credits
RESET_BALANCE_UNITS = 500_000


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 0. DistroKid entitlements live on licenses; preserve them on users.
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS distrokid_enabled boolean NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS distrokid_expires_at timestamptz"
    )
    op.execute(
        """
        UPDATE users u
        SET distrokid_enabled = src.distrokid_enabled,
            distrokid_expires_at = src.distrokid_expires_at
        FROM (
            SELECT DISTINCT ON (l.user_id)
                   l.user_id,
                   COALESCE(l.distrokid_enabled, false) AS distrokid_enabled,
                   l.distrokid_expires_at
            FROM licenses l
            WHERE l.status = 'active'
              AND (l.expires_at IS NULL OR l.expires_at > now())
              AND (l.distrokid_enabled OR l.distrokid_expires_at IS NOT NULL)
            ORDER BY l.user_id, l.activated_at DESC NULLS LAST
        ) src
        WHERE src.user_id = u.id
        """
    )

    # ------------------------------------------------------------------
    # 1. Archive everything we are about to delete.
    # ------------------------------------------------------------------
    for table in ARCHIVE_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}_archive")
        op.execute(f"CREATE TABLE {table}_archive AS TABLE {table}")

    op.execute("DROP TABLE IF EXISTS credit_wallet_lots_archive")
    op.execute("CREATE TABLE credit_wallet_lots_archive AS TABLE credit_wallet_lots")

    # ------------------------------------------------------------------
    # 2. Rebuild lots so balance == SUM(live lots) and tier is derivable.
    #
    #   active_legacy : active license or active web subscription
    #                   -> pack lot = wallet, expiry = ORIGINAL expiry
    #   expired_reset : quota_conversion user with no active plan/sub
    #                   -> wallet reset to 50, one grant lot
    #   pack_u        : any other user with a live pack lot
    #                   -> pack lot = wallet, expiry = original pack expiry
    #   everyone else : grant lot = wallet (signup credits), no expiry
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE TEMP TABLE _tier_rebuild ON COMMIT DROP AS
        WITH active_legacy AS (
            SELECT user_id, MAX(exp) AS exp
            FROM (
                SELECT l.user_id, l.expires_at AS exp
                FROM licenses l
                WHERE l.status = 'active'
                  AND (l.expires_at IS NULL OR l.expires_at > now())
                UNION ALL
                SELECT ws.user_id, ws.current_period_end AS exp
                FROM web_subscriptions ws
                WHERE ws.status = 'active'
                  AND ws.current_period_end > now()
            ) src
            GROUP BY user_id
        ),
        expired_reset AS (
            SELECT DISTINCT lot.user_id
            FROM credit_wallet_lots lot
            WHERE lot.tag = 'quota_conversion'
            EXCEPT
            SELECT user_id FROM active_legacy
        ),
        pack_u AS (
            SELECT lot.user_id, MAX(lot.expires_at) AS exp
            FROM credit_wallet_lots lot
            WHERE lot.tag = 'pack'
              AND lot.remaining_units > 0
              AND (lot.expires_at IS NULL OR lot.expires_at > now())
              AND lot.user_id NOT IN (SELECT user_id FROM expired_reset)
            GROUP BY lot.user_id
        )
        SELECT
            w.user_id,
            CASE
                WHEN er.user_id IS NOT NULL THEN {RESET_BALANCE_UNITS}
                ELSE w.balance
            END AS balance,
            CASE
                WHEN er.user_id IS NOT NULL THEN 'grant'
                WHEN al.user_id IS NOT NULL OR pu.user_id IS NOT NULL THEN 'pack'
                ELSE 'grant'
            END AS tag,
            CASE
                WHEN er.user_id IS NOT NULL THEN NULL
                WHEN al.user_id IS NOT NULL THEN al.exp
                WHEN pu.user_id IS NOT NULL THEN pu.exp
                ELSE NULL
            END AS expires_at,
            (er.user_id IS NOT NULL) AS reset
        FROM credit_wallets w
        LEFT JOIN active_legacy al ON al.user_id = w.user_id
        LEFT JOIN expired_reset er ON er.user_id = w.user_id
        LEFT JOIN pack_u pu ON pu.user_id = w.user_id
        """
    )

    # Reset balances for the two expired users; everyone else keeps theirs.
    op.execute(
        """
        UPDATE credit_wallets w
        SET balance = r.balance
        FROM _tier_rebuild r
        WHERE r.user_id = w.user_id
          AND w.balance <> r.balance
        """
    )

    op.execute(
        """
        UPDATE credit_wallet_lots l
        SET remaining_units = 0
        WHERE l.user_id IN (SELECT user_id FROM _tier_rebuild)
        """
    )
    op.execute(
        """
        INSERT INTO credit_wallet_lots
            (id, user_id, tag, amount_units, remaining_units, expires_at, period_start, created_at, ref_id)
        SELECT gen_random_uuid(), user_id, tag, balance, balance, expires_at, NULL, now(),
               CASE WHEN tag = 'pack' THEN 'legacy_conversion_2026_10_30' ELSE NULL END
        FROM _tier_rebuild
        WHERE balance > 0
        """
    )

    # ------------------------------------------------------------------
    # 3. Retire licenses and web subscriptions (archived above).
    # ------------------------------------------------------------------
    op.execute(
        "UPDATE licenses SET status = 'revoked', revoked_at = now() WHERE status = 'active'"
    )
    op.execute(
        "UPDATE web_subscriptions SET status = 'cancelled' WHERE status = 'active'"
    )

    # ------------------------------------------------------------------
    # 4. Drop foreign keys that point at plan tables.
    #
    # The columns themselves are kept as nullable legacy audit fields so
    # billing history survives; a follow-up migration drops them once the
    # code no longer writes them. `billing_payments.plan_id` is NOT NULL
    # today, so it must be relaxed before pack checkout can pass NULL.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN
                SELECT tc.table_name, tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND ccu.table_name IN ('plans', 'licenses', 'web_subscriptions', 'plan_offers')
            LOOP
                EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', r.table_name, r.constraint_name);
            END LOOP;
        END $$;
        """
    )
    op.execute("ALTER TABLE billing_payments ALTER COLUMN plan_id DROP NOT NULL")
    op.execute("ALTER TABLE billing_payments ALTER COLUMN offer_id DROP NOT NULL")

    # ------------------------------------------------------------------
    # 5. Drop the plan tables.
    # ------------------------------------------------------------------
    for table in (
        "plan_usage",
        "user_period_quota_topups",
        "plan_offers",
        "licenses",
        "web_subscriptions",
        "plans",
        "daily_quota_bank",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")

    # ------------------------------------------------------------------
    # 6. Remove plan-only settings.
    # ------------------------------------------------------------------
    op.execute("DELETE FROM system_settings WHERE key = 'plan_term_discounts'")


def downgrade() -> None:
    """Best-effort restore: rename the archive tables back.

    Dropped FK columns (billing_payments.plan_id, etc.) and the rebuilt credit
    lots are not restored. Restore from a DB backup for a full rollback.
    """
    for table in reversed(ARCHIVE_TABLES):
        op.execute(f"ALTER TABLE IF EXISTS {table}_archive RENAME TO {table}")
