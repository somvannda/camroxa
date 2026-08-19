"""Allow pending status on web_subscriptions for checkout flow.

Revision ID: 097_web_subscriptions_pending_status
Revises: 096_web_music_playlists
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "097_web_subscriptions_pending_status"
down_revision = "096_web_music_playlists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE web_subscriptions
        DROP CONSTRAINT IF EXISTS web_subscriptions_status_check
        """
    )
    op.execute(
        """
        ALTER TABLE web_subscriptions
        ADD CONSTRAINT web_subscriptions_status_check
        CHECK (status IN ('pending', 'active', 'cancelled', 'expired', 'past_due'))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE web_subscriptions
        SET status = 'cancelled'
        WHERE status = 'pending'
        """
    )
    op.execute(
        """
        ALTER TABLE web_subscriptions
        DROP CONSTRAINT IF EXISTS web_subscriptions_status_check
        """
    )
    op.execute(
        """
        ALTER TABLE web_subscriptions
        ADD CONSTRAINT web_subscriptions_status_check
        CHECK (status IN ('active', 'cancelled', 'expired', 'past_due'))
        """
    )
