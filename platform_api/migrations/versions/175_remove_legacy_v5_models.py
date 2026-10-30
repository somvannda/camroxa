"""Remove the legacy V5 / V5_5 Suno models.

V6 / V6_MINI / V6_WILD are the only supported music models. V5 and V5_5 are
discontinued by the provider and are removed from pricing.

Revision ID: 175
Revises: 174
"""

from __future__ import annotations

from alembic import op

revision = "175"
down_revision = "174"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM credit_pricing
        WHERE ai_service = 'suno'
          AND operation_type = 'music'
          AND sub_model IN ('V5', 'V5_5')
        """
    )


def downgrade() -> None:
    # Pricing rows are configuration; restore from a backup if needed.
    pass
