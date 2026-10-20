"""Add users.google_id for Google sign-in on music web.

Revision ID: 137_user_google_id
Revises: 136_packs_only_billing
Create Date: 2026-10-20
"""

from alembic import op

revision = "137_user_google_id"
down_revision = "136_packs_only_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS google_id VARCHAR(255)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_users_google_id
            ON users (google_id)
            WHERE google_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_google_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS google_id")
