"""Track capped onboarding AI usage per user (payment-gated, no wallet credits)."""

from alembic import op

revision = "029_onboarding_ai_usage"
down_revision = "028_micro_credits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_ai_usage (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            operation_type TEXT NOT NULL,
            usage_count INTEGER NOT NULL DEFAULT 0 CHECK (usage_count >= 0),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, operation_type)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_onboarding_ai_usage_user_id
        ON onboarding_ai_usage (user_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS onboarding_ai_usage")
