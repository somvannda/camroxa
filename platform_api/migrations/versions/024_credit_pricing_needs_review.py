"""Add needs_review flag to credit_pricing for draft auto-seeded rows.

Revision ID: 024_credit_pricing_needs_review
Revises: 023_add_billing_payments
"""

from alembic import op

revision = "024_credit_pricing_needs_review"
down_revision = "023_add_billing_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE credit_pricing
        ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT FALSE
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE credit_pricing
        DROP COLUMN IF EXISTS needs_review
    """)
