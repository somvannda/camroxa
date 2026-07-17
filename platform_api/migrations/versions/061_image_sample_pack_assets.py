"""VPS-hosted image sample pack assets extracted from admin ZIP uploads."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "061_image_sample_pack_assets"
down_revision = "060_ai_structure_and_streaming_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("image_sample_packs", sa.Column("storage_path", sa.Text(), nullable=True))
    op.add_column(
        "image_sample_packs",
        sa.Column("asset_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "image_sample_pack_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "pack_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("image_sample_packs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("absolute_path", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("pack_id", "relative_path", name="uq_image_sample_pack_assets_pack_path"),
    )
    op.create_index(
        "idx_image_sample_pack_assets_pack_id",
        "image_sample_pack_assets",
        ["pack_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_image_sample_pack_assets_pack_id", table_name="image_sample_pack_assets")
    op.drop_table("image_sample_pack_assets")
    op.drop_column("image_sample_packs", "asset_count")
    op.drop_column("image_sample_packs", "storage_path")
