"""Delivery log for the ops Telegram channel.

A bot cannot read back its own messages, and the only evidence of delivery used
to be scattered journal lines across nine systemd units. This table records
every post attempt (kind, text, status, HTTP code) so ops can answer "what did
we report, when, and did it land?" with SQL.

Revision ID: 141_telegram_ops_messages
Revises: 140_telegram_report_indexes
Create Date: 2026-10-20
"""

from alembic import op

revision = "141_telegram_ops_messages"
down_revision = "140_telegram_report_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_ops_messages (
            id BIGSERIAL PRIMARY KEY,
            kind VARCHAR(32) NOT NULL DEFAULT 'message',
            chat_id VARCHAR(64),
            text TEXT NOT NULL,
            status VARCHAR(16) NOT NULL,
            http_status INTEGER NULL,
            error TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_telegram_ops_messages_created "
        "ON telegram_ops_messages (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_telegram_ops_messages_kind_created "
        "ON telegram_ops_messages (kind, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS telegram_ops_messages")
