"""Merge marketplace and streaming migration heads."""

from __future__ import annotations

revision = "044_merge_streaming_heads"
down_revision = ("042_marketplace_price", "043_streaming_catalog")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
