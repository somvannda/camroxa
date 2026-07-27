"""Add DistroKid add-on entitlement columns on licenses."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "075_distrokid_addon"
down_revision = "074_suno_audio_ids"
branch_labels = None
depends_on = None

# 1 display credit list (CREDIT_SCALE=10_000).
_WAV_LIST_UNITS = 10_000


def upgrade() -> None:
    op.add_column(
        "licenses",
        sa.Column(
            "distrokid_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "licenses",
        sa.Column("distrokid_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        f"""
        INSERT INTO credit_pricing (
            id, ai_service, operation_type, sub_model,
            credits_per_operation, external_cost_cents, needs_review,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'suno',
            'wav',
            '',
            {_WAV_LIST_UNITS},
            0,
            false,
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = 'suno' AND operation_type = 'wav'
              AND COALESCE(sub_model, '') = ''
        )
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'credit_pricing' AND column_name = 'model_cost_usd'
            ) THEN
                UPDATE credit_pricing
                SET model_cost_usd = 0.002
                WHERE ai_service = 'suno' AND operation_type = 'wav'
                  AND COALESCE(sub_model, '') = '';
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'credit_pricing' AND column_name = 'notes'
            ) THEN
                UPDATE credit_pricing
                SET notes = 'DistroKid WAV: ~0.4 Suno API credits ≈ $0.002 COGS'
                WHERE ai_service = 'suno' AND operation_type = 'wav'
                  AND COALESCE(sub_model, '') = '';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM credit_pricing WHERE ai_service = 'suno' AND operation_type = 'wav'"
    )
    op.drop_column("licenses", "distrokid_expires_at")
    op.drop_column("licenses", "distrokid_enabled")
