"""Canonicalise credit_pricing keys to lowercase provider/operation.

Pricing rows are matched by exact string. Mixed case or stray whitespace creates
an orphan row that never matches the routing key, so the service now normalises
and validates writes (W5). This migration fixes rows created before that guard.

Model ids keep their case: Suno music models are uppercase (V6) and are
normalised separately by ``normalize_suno_pricing_sub_model``.

Revision ID: 184
Revises: 183
"""

from __future__ import annotations

from alembic import op

revision = "184"
down_revision = "183"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Collapse case/whitespace duplicates first, keeping the newest row, so the
    # lowercase UPDATE cannot violate the unique key.
    op.execute(
        """
        DELETE FROM credit_pricing AS stale
        USING credit_pricing AS keeper
        WHERE stale.id <> keeper.id
          AND lower(btrim(stale.ai_service)) = lower(btrim(keeper.ai_service))
          AND lower(btrim(stale.operation_type)) = lower(btrim(keeper.operation_type))
          AND COALESCE(stale.sub_model, '') = COALESCE(keeper.sub_model, '')
          AND (keeper.updated_at, keeper.id) > (stale.updated_at, stale.id)
        """
    )
    op.execute(
        """
        UPDATE credit_pricing
        SET ai_service = lower(btrim(ai_service)),
            operation_type = lower(btrim(operation_type)),
            updated_at = NOW()
        WHERE ai_service <> lower(btrim(ai_service))
           OR operation_type <> lower(btrim(operation_type))
        """
    )


def downgrade() -> None:
    # Case information is not recoverable; the lowercase form is canonical.
    pass
