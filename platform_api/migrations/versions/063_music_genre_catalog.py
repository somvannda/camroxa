"""Migration: curated music genre catalog for prompt autocomplete."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from platform_api.data.music_genre_catalog import MUSIC_GENRE_CATALOG
from platform_api.services.streaming_slug import slugify

revision = "063_music_genre_catalog"
down_revision = "062_music_description_genres"
branch_labels = None
depends_on = None


def _seed_genres() -> None:
    bind = op.get_bind()
    rows = []
    for index, item in enumerate(MUSIC_GENRE_CATALOG):
        rows.append(
            {
                "name": item.name,
                "slug": slugify(item.name),
                "category": item.category,
                "aliases": list(item.aliases),
                "sort_order": index,
            }
        )
    if not rows:
        return
    table = sa.table(
        "music_genre_catalog",
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("category", sa.String),
        sa.column("aliases", postgresql.JSONB),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(table, rows)


def upgrade() -> None:
    op.create_table(
        "music_genre_catalog",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("aliases", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("uq_music_genre_catalog_name", "music_genre_catalog", ["name"], unique=True)
    op.create_index("uq_music_genre_catalog_slug", "music_genre_catalog", ["slug"], unique=True)
    op.create_index("idx_music_genre_catalog_category", "music_genre_catalog", ["category"])
    op.create_index("idx_music_genre_catalog_name_lower", "music_genre_catalog", [sa.text("LOWER(name)")])
    _seed_genres()


def downgrade() -> None:
    op.drop_index("idx_music_genre_catalog_name_lower", table_name="music_genre_catalog")
    op.drop_index("idx_music_genre_catalog_category", table_name="music_genre_catalog")
    op.drop_index("uq_music_genre_catalog_slug", table_name="music_genre_catalog")
    op.drop_index("uq_music_genre_catalog_name", table_name="music_genre_catalog")
    op.drop_table("music_genre_catalog")
