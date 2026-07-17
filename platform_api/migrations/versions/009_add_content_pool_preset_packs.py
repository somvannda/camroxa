"""Add shared content-pool tables and preset-pack storage."""

from alembic import op

revision = "009_content_pool_preset_packs"
down_revision = "008_youtube_code_verifier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS title_pool (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            norm TEXT NOT NULL,
            used_count INTEGER NOT NULL DEFAULT 0,
            used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_title_pool_norm
            ON title_pool(norm)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_title_pool_used
            ON title_pool(used_count, id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS album_pool (
            id SERIAL PRIMARY KEY,
            album TEXT NOT NULL,
            norm TEXT NOT NULL,
            used_count INTEGER NOT NULL DEFAULT 0,
            used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_album_pool_norm
            ON album_pool(norm)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_album_pool_used
            ON album_pool(used_count, id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS opening_pairs (
            id SERIAL PRIMARY KEY,
            line1 TEXT NOT NULL,
            line2 TEXT NOT NULL,
            norm TEXT NOT NULL,
            used_count INTEGER NOT NULL DEFAULT 0,
            used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_opening_pairs_norm
            ON opening_pairs(norm)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opening_pairs_used
            ON opening_pairs(used_count, id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS content_pool_preset_packs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kind VARCHAR(16) NOT NULL,
            name TEXT NOT NULL,
            name_norm TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            config JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_content_pool_preset_pack_kind
                CHECK (kind IN ('titles', 'albums', 'openings')),
            CONSTRAINT uq_content_pool_preset_pack_kind_name
                UNIQUE (kind, name_norm)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_content_pool_preset_packs_kind_active
            ON content_pool_preset_packs(kind, is_active, updated_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_content_pool_preset_packs_kind_active")
    op.execute("DROP TABLE IF EXISTS content_pool_preset_packs CASCADE")
