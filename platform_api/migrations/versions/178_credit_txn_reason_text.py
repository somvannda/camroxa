"""credit_transactions.reason must hold the full admin adjustment reason.

``credit_transactions.reason`` was ``VARCHAR(100)`` from the initial schema, but
the admin adjust route accepts a reason up to 255 characters and
``CreditService.admin_adjust`` stores it prefixed with ``admin_adjustment: ``.
Any reason longer than ~81 characters therefore raised
``value too long for type character varying(100)`` inside ``add_credits`` --
after the balance check, so the operator saw a 500 and the adjustment did not
apply.

Widened to ``TEXT``, matching the sibling ledger tables that already hold a free
-text reason (``credit_grant_claims``, ``admin_pending_ops``). ``VARCHAR`` ->
``TEXT`` is a binary-compatible change in PostgreSQL and does not rewrite the
table.

Revision ID: 178
Revises: 177
"""

from __future__ import annotations

from alembic import op

revision = "178"
down_revision = "177"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE credit_transactions
        ALTER COLUMN reason TYPE TEXT
        """
    )


def downgrade() -> None:
    # ``left(reason, 100)`` keeps the downgrade runnable when an admin reason
    # longer than the old limit already exists.
    op.execute(
        """
        ALTER TABLE credit_transactions
        ALTER COLUMN reason TYPE VARCHAR(100) USING left(reason, 100)
        """
    )
