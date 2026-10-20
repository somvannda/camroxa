"""Case-insensitive uniqueness for user emails.

The original ``users.email`` UNIQUE constraint is case-sensitive, while every
lookup uses ``LOWER(email)``. That allowed near-duplicate rows if two writers
inserted ``A@x.com`` and ``a@x.com`` directly. Enforce one canonical row.

Revision ID: 137_users_email_lower_unique
Revises: 136_user_google_id
Create Date: 2026-10-20
"""

from alembic import op

revision = "137_users_email_lower_unique"
down_revision = "136_user_google_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
            ON users (LOWER(email))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_email_lower")
