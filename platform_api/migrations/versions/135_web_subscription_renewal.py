"""Add renewal-checkout columns to web_subscriptions (CutLuy is one-time).

Revision ID: 135_web_subscription_renewal
Revises: 134_streaming_upload_job_dedup
Create Date: 2026-10-06

"""
from alembic import op

revision = "135_web_subscription_renewal"
down_revision = "134_streaming_upload_job_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE web_subscriptions
            ADD COLUMN IF NOT EXISTS pending_renewal_payment_id VARCHAR(255)
        """
    )
    op.execute(
        """
        ALTER TABLE web_subscriptions
            ADD COLUMN IF NOT EXISTS renewal_reminder_sent_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_subscriptions_pending_renewal
            ON web_subscriptions(pending_renewal_payment_id)
            WHERE pending_renewal_payment_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_web_subscriptions_pending_renewal")
    op.execute(
        "ALTER TABLE web_subscriptions DROP COLUMN IF EXISTS pending_renewal_payment_id"
    )
    op.execute(
        "ALTER TABLE web_subscriptions DROP COLUMN IF EXISTS renewal_reminder_sent_at"
    )
