"""Indexes for the Telegram report windows.

`/stats` and the 22:00 report filter `users`, `suno_tasks` and
`credit_transactions` by `created_at`, and the platform-revenue line filters
`billing_payments` by `fulfilled_at`. The old SQL cast the column
(`(created_at AT TIME ZONE …)::date`), which made every report a sequential
scan; the queries now use range predicates, so these indexes can serve them.

The tables are small today (suno_tasks ~10k rows, credit_transactions ~55k), so
a plain CREATE INDEX is fast enough inside alembic's transaction. Use
CONCURRENTLY manually if the tables grow large before this runs.

Revision ID: 140_telegram_report_indexes
Revises: 139_referral_program
Create Date: 2026-10-20
"""

from alembic import op

revision = "140_telegram_report_indexes"
down_revision = "139_referral_program"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_suno_tasks_created_at "
        "ON suno_tasks (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_credit_txn_created_at "
        "ON credit_transactions (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_billing_payments_fulfilled_at "
        "ON billing_payments (fulfilled_at) "
        "WHERE status = 'paid' AND fulfilled_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_billing_payments_fulfilled_at")
    op.execute("DROP INDEX IF EXISTS idx_credit_txn_created_at")
    op.execute("DROP INDEX IF EXISTS idx_suno_tasks_created_at")
    op.execute("DROP INDEX IF EXISTS idx_users_created_at")
