"""Studio operation charge tracking and +2 credit pricing.

Revision ID: 150_studio_operation_charges
Revises: 149_studio_operations
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op

revision: str = "150_studio_operation_charges"
down_revision: str | None = "149_studio_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE studio_operations
            ADD COLUMN IF NOT EXISTS charge_path TEXT NULL,
            ADD COLUMN IF NOT EXISTS charge_op TEXT NULL,
            ADD COLUMN IF NOT EXISTS charge_ref TEXT NULL,
            ADD COLUMN IF NOT EXISTS refunded_at TIMESTAMPTZ NULL
        """
    )
    # Suno charges 10 credits for a normal Studio edit, 10 for 2-track stems,
    # and 50 for 12-track stems. Camxora adds 2 credits on top of each.
    op.execute(
        """
        INSERT INTO credit_pricing
            (ai_service, operation_type, sub_model, credits_per_operation)
        SELECT 'suno', 'studio_edit', '', 120000
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = 'suno' AND operation_type = 'studio_edit'
        )
        """
    )
    op.execute(
        """
        INSERT INTO credit_pricing
            (ai_service, operation_type, sub_model, credits_per_operation)
        SELECT 'suno', 'studio_stems_2', '', 120000
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = 'suno' AND operation_type = 'studio_stems_2'
        )
        """
    )
    op.execute(
        """
        INSERT INTO credit_pricing
            (ai_service, operation_type, sub_model, credits_per_operation)
        SELECT 'suno', 'studio_stems_12', '', 520000
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = 'suno' AND operation_type = 'studio_stems_12'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM credit_pricing
        WHERE ai_service = 'suno'
          AND operation_type IN ('studio_edit', 'studio_stems_2', 'studio_stems_12')
        """
    )
    op.execute(
        """
        ALTER TABLE studio_operations
            DROP COLUMN IF EXISTS charge_path,
            DROP COLUMN IF EXISTS charge_op,
            DROP COLUMN IF EXISTS charge_ref,
            DROP COLUMN IF EXISTS refunded_at
        """
    )
