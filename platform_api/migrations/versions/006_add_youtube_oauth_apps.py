"""Add admin-managed YouTube OAuth app storage.

Revision ID: 006_add_youtube_oauth_apps
Revises: 005_add_batch_planned_date_range
Create Date: 2026-06-25 00:00:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "006_add_youtube_oauth_apps"
down_revision: Union[str, None] = "005_add_batch_planned_date_range"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE youtube_oauth_apps (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(120) NOT NULL UNIQUE,
            client_id TEXT NOT NULL,
            encrypted_client_secret BYTEA NOT NULL,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_youtube_oauth_apps_single_default
            ON youtube_oauth_apps ((is_default))
            WHERE is_default = TRUE
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_youtube_oauth_apps_single_default")
    op.execute("DROP TABLE IF EXISTS youtube_oauth_apps CASCADE")
