"""Set 12-track Studio stems to 60 Camxora credits.

Revision ID: 151_studio_stems_12_price_60
Revises: 150_studio_operation_charges
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op

revision: str = "151_studio_stems_12_price_60"
down_revision: str | None = "150_studio_operation_charges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE credit_pricing
        SET credits_per_operation = 600000,
            updated_at = now()
        WHERE ai_service = 'suno'
          AND operation_type = 'studio_stems_12'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE credit_pricing
        SET credits_per_operation = 520000,
            updated_at = now()
        WHERE ai_service = 'suno'
          AND operation_type = 'studio_stems_12'
        """
    )
