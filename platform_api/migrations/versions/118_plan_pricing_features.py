"""Add per-plan pricing feature lines for public cards.

Revision ID: 118
Revises: 117
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "118_plan_pricing_features"
down_revision: Union[str, None] = "117_daily_grant_lot_tag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE plans
            ADD COLUMN IF NOT EXISTS pricing_features TEXT[] NOT NULL DEFAULT '{}'::text[]
        """
    )
    op.execute(
        """
        UPDATE plans
        SET pricing_features = ARRAY['Web Create', 'Daily credit reset', 'Top-up packs']::text[]
        WHERE cardinality(pricing_features) = 0
          AND (
            lower(name) LIKE '%free%'
            OR (COALESCE(price_cents, 0) <= 0 AND COALESCE(daily_credits, 0) > 0)
          )
        """
    )
    op.execute(
        """
        UPDATE plans
        SET pricing_features = ARRAY['Web Create', 'Desktop studio', 'Dual channels', 'Top-up packs']::text[]
        WHERE cardinality(pricing_features) = 0
          AND COALESCE(price_cents, 0) > 0
          AND COALESCE(is_public, false) = true
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS pricing_features")
