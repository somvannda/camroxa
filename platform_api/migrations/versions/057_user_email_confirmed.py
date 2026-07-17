"""Add users.email_confirmed for registration confirmation flow."""

from alembic import op

revision = "057_user_email_confirmed"
down_revision = "056_license_pending_plan_change"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS email_confirmed BOOLEAN NOT NULL DEFAULT false
        """
    )
    op.execute(
        """
        UPDATE users SET email_confirmed = true WHERE email_confirmed = false
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE users DROP COLUMN IF EXISTS email_confirmed
        """
    )
