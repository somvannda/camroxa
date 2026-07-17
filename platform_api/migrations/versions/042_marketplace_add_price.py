"""Add price column to marketplace_items table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "042_marketplace_add_price"
down_revision = "041_add_marketplace_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "marketplace_items",
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False, server_default=sa.text("0.00")),
    )


def downgrade() -> None:
    op.drop_column("marketplace_items", "price")
