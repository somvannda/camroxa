"""Add email_verifications table for registration confirm codes."""

from alembic import op

revision = "058_email_verifications"
down_revision = "057_user_email_confirmed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS email_verifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            code VARCHAR(6) NOT NULL,
            purpose VARCHAR(20) NOT NULL DEFAULT 'register',
            expires_at TIMESTAMPTZ NOT NULL,
            used BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_email_verifications_user
            ON email_verifications(user_id, purpose)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_verifications")
