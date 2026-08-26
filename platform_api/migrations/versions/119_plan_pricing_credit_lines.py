"""Add per-plan credit-block captions for public pricing cards.

Revision ID: 119
Revises: 118
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "119_plan_pricing_credit_lines"
down_revision: Union[str, None] = "118_plan_pricing_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE plans
            ADD COLUMN IF NOT EXISTS pricing_credit_lines TEXT[] NOT NULL DEFAULT '{}'::text[]
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS pricing_credit_lines")
