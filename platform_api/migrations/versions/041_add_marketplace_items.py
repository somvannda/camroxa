"""Add marketplace_items table for template marketplace feature."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "041_add_marketplace_items"
down_revision = "040_add_blog_posts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("tags", ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'enabled'")),
        sa.Column("zip_path", sa.String(length=500), nullable=False),
        sa.Column("preview_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("name", "version", name="uq_marketplace_items_name_version"),
        sa.CheckConstraint("kind IN ('video', 'reel')", name="ck_marketplace_items_kind"),
        sa.CheckConstraint("status IN ('enabled', 'disabled')", name="ck_marketplace_items_status"),
    )

    op.create_index("idx_marketplace_items_status", "marketplace_items", ["status"])
    op.create_index("idx_marketplace_items_kind", "marketplace_items", ["kind"])
    op.create_index("idx_marketplace_items_created", "marketplace_items", [sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("idx_marketplace_items_created", table_name="marketplace_items")
    op.drop_index("idx_marketplace_items_kind", table_name="marketplace_items")
    op.drop_index("idx_marketplace_items_status", table_name="marketplace_items")
    op.drop_table("marketplace_items")
