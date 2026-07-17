"""Store credits as micro-units (1 credit = 10_000 units) for fractional billing."""

from alembic import op

revision = "028_micro_credits"
down_revision = "027_model_cost_usd_precision"
branch_labels = None
depends_on = None

SCALE = 10_000
MAX_UNITS = 10_000_000 * SCALE


def upgrade() -> None:
    # ─── credit_wallets ───────────────────────────────────────────────────
    op.execute("""
        ALTER TABLE credit_wallets
        DROP CONSTRAINT IF EXISTS credit_wallets_balance_check
    """)
    op.execute(f"""
        ALTER TABLE credit_wallets
        ALTER COLUMN balance TYPE BIGINT
        USING balance::bigint * {SCALE}
    """)
    op.execute(f"""
        ALTER TABLE credit_wallets
        ADD CONSTRAINT credit_wallets_balance_check
        CHECK (balance >= 0 AND balance <= {MAX_UNITS})
    """)

    # ─── credit_transactions ────────────────────────────────────────────────
    op.execute(f"""
        ALTER TABLE credit_transactions
        ALTER COLUMN amount TYPE BIGINT
        USING amount::bigint * {SCALE}
    """)

    # ─── credit_pricing ─────────────────────────────────────────────────────
    op.execute("""
        ALTER TABLE credit_pricing
        DROP CONSTRAINT IF EXISTS credit_pricing_credits_per_operation_check
    """)
    op.execute(f"""
        ALTER TABLE credit_pricing
        ALTER COLUMN credits_per_operation TYPE BIGINT
        USING credits_per_operation::bigint * {SCALE}
    """)
    op.execute(f"""
        UPDATE credit_pricing
        SET external_cost_cents = external_cost_cents * {SCALE}
        WHERE external_cost_cents IS NOT NULL
    """)
    op.execute(f"""
        ALTER TABLE credit_pricing
        ALTER COLUMN external_cost_cents TYPE BIGINT
        USING external_cost_cents::bigint
    """)
    op.execute(f"""
        ALTER TABLE credit_pricing
        ADD CONSTRAINT credit_pricing_credits_per_operation_check
        CHECK (
            credits_per_operation >= 1
            AND credits_per_operation <= {MAX_UNITS}
        )
    """)

    # ─── credit_packs ───────────────────────────────────────────────────────
    op.execute(f"""
        ALTER TABLE credit_packs
        ALTER COLUMN song_credits TYPE BIGINT
        USING song_credits::bigint * {SCALE}
    """)

    # Default GCV to $0.01 (1 credit = 1 cent) when not yet configured.
    op.execute("""
        INSERT INTO system_settings (key, value, value_type, updated_at)
        VALUES ('global_credit_value', '0.01', 'number', NOW())
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE credit_packs
        ALTER COLUMN song_credits TYPE INTEGER
        USING (song_credits / 10000)::integer
    """)

    op.execute("""
        ALTER TABLE credit_pricing
        DROP CONSTRAINT IF EXISTS credit_pricing_credits_per_operation_check
    """)
    op.execute("""
        ALTER TABLE credit_pricing
        ALTER COLUMN credits_per_operation TYPE INTEGER
        USING (credits_per_operation / 10000)::integer
    """)
    op.execute("""
        UPDATE credit_pricing
        SET external_cost_cents = (external_cost_cents / 10000)::integer
        WHERE external_cost_cents IS NOT NULL
    """)
    op.execute("""
        ALTER TABLE credit_pricing
        ALTER COLUMN external_cost_cents TYPE INTEGER
        USING external_cost_cents::integer
    """)
    op.execute("""
        ALTER TABLE credit_pricing
        ADD CONSTRAINT credit_pricing_credits_per_operation_check
        CHECK (credits_per_operation >= 1 AND credits_per_operation <= 10000)
    """)

    op.execute("""
        ALTER TABLE credit_transactions
        ALTER COLUMN amount TYPE INTEGER
        USING (amount / 10000)::integer
    """)

    op.execute("""
        ALTER TABLE credit_wallets
        DROP CONSTRAINT IF EXISTS credit_wallets_balance_check
    """)
    op.execute("""
        ALTER TABLE credit_wallets
        ALTER COLUMN balance TYPE INTEGER
        USING (balance / 10000)::integer
    """)
    op.execute("""
        ALTER TABLE credit_wallets
        ADD CONSTRAINT credit_wallets_balance_check
        CHECK (balance >= 0 AND balance <= 10000000)
    """)
