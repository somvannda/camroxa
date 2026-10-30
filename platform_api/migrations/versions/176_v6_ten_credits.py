"""Set the V6 music models to 10 credits (100,000 micro-units).

All three V6 models cost the same: V6 Pro, V6 Mini, V6 Wild.
V5 / V5_5 were removed in migration 175.

Revision ID: 176
Revises: 175
"""

from __future__ import annotations

from alembic import op

revision = "176"
down_revision = "175"
branch_labels = None
depends_on = None

TEN_CREDITS_UNITS = 100_000


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE credit_pricing
        SET credits_per_operation = {TEN_CREDITS_UNITS},
            updated_at = NOW()
        WHERE ai_service = 'suno'
          AND operation_type = 'music'
          AND (
              sub_model IN ('V6', 'V6_MINI', 'V6_WILD')
              OR sub_model IS NULL
              OR sub_model = ''
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE credit_pricing
        SET credits_per_operation = 150000,
            updated_at = NOW()
        WHERE ai_service = 'suno'
          AND operation_type = 'music'
          AND (
              sub_model IN ('V6', 'V6_MINI', 'V6_WILD')
              OR sub_model IS NULL
              OR sub_model = ''
          )
        """
    )
