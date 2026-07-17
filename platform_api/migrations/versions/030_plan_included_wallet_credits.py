"""Add included_wallet_credits to plans for lifetime purchase grants."""

from alembic import op

revision = "030_plan_included_wallet_credits"
down_revision = "029_onboarding_ai_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE plans
        ADD COLUMN IF NOT EXISTS included_wallet_credits INTEGER NOT NULL DEFAULT 0
    """)
    op.execute("""
        UPDATE plans
        SET included_wallet_credits = 10000
        WHERE LOWER(name) = 'lifetime'
          AND included_wallet_credits = 0
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS included_wallet_credits")
