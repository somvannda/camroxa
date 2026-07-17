"""Store per-user onboarding draft payloads for portal resume."""

from alembic import op

revision = "032_onboarding_drafts"
down_revision = "031_credit_transaction_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_drafts (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_onboarding_drafts_updated_at
        ON onboarding_drafts (updated_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS onboarding_drafts")
