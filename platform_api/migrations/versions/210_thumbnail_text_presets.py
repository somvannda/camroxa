"""Admin thumbnail text presets, per-user rotation, and clean text-lockup styles.

Revision ID: 210
Revises: 209
Create Date: 2026-11-18

The legacy thumbnail prompt styles embed literal typography words. This
migration adds a separate text table so the words can be maintained and
rotated independently, plus a small set of text-free typography styles.
"""

from __future__ import annotations

from alembic import op

revision = "210"
down_revision = "209"
branch_labels = None
depends_on = None

_LOCKUP_STYLES = (
    (
        "Lockup Chrome Blue",
        "Bold condensed uppercase 3D lettering with polished chrome surfaces, "
        "electric-blue rim light, sharp angular edges, subtle extrusion, and high "
        "contrast. Premium EDM YouTube thumbnail finish.",
    ),
    (
        "Lockup Neon Gold",
        "Bold italic 3D lettering with metallic gold gradients, warm orange rim "
        "light, glowing edges, and a luxury automotive finish. High contrast and "
        "crisp, readable letterforms.",
    ),
    (
        "Lockup Fire Red",
        "Aggressive 3D lettering with molten red and orange gradients, fiery rim "
        "light, dark shadows, and distressed metallic edges. High-energy bass "
        "thumbnail styling.",
    ),
    (
        "Lockup Emerald",
        "Bold 3D lettering with fluorescent green and metallic silver gradients, "
        "electric-green glow, sharp bevels, and a futuristic underground club look.",
    ),
    (
        "Lockup Purple Haze",
        "Bold 3D lettering with violet and magenta gradients, soft neon glow, "
        "chrome highlights, and a premium nightclub aesthetic.",
    ),
    (
        "Lockup Ice White",
        "Clean bold 3D lettering with pearl-white and ice-blue gradients, crisp "
        "cyan rim light, and polished metallic edges. Bright and highly readable.",
    ),
    (
        "Lockup Molten Orange",
        "Bold 3D lettering with orange and copper gradients, glowing ember edges, "
        "dark metallic shadows, and a high-impact bass aesthetic.",
    ),
    (
        "Lockup Cyber Cyan",
        "Bold futuristic lettering with cyan and teal gradients, neon outlines, "
        "subtle circuit-like highlights, and a sleek cyber aesthetic.",
    ),
    (
        "Lockup Crimson Steel",
        "Bold 3D lettering with crimson and gunmetal gradients, sharp steel bevels, "
        "red rim light, and a heavy aggressive finish.",
    ),
    (
        "Lockup Gold Luxe",
        "Elegant bold 3D lettering with champagne-gold gradients, soft white "
        "highlights, and a premium luxury finish.",
    ),
    (
        "Lockup Toxic Green",
        "Bold 3D lettering with acid-green and black gradients, intense green glow, "
        "and a raw underground EDM finish.",
    ),
    (
        "Lockup Monochrome",
        "Bold 3D lettering with silver, white, and black gradients, crisp metallic "
        "edges, and a clean high-contrast finish.",
    ),
)


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE image_prompt_styles
            ADD COLUMN IF NOT EXISTS text_mode TEXT NOT NULL DEFAULT 'legacy'
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS image_thumbnail_texts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title TEXT NOT NULL,
            subtitle TEXT,
            subline TEXT,
            placement TEXT NOT NULL DEFAULT 'top_center',
            alignment TEXT NOT NULL DEFAULT 'center',
            style_hint TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS image_thumbnail_text_rotation (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            text_id UUID NOT NULL REFERENCES image_thumbnail_texts(id) ON DELETE CASCADE,
            cycle_number INTEGER NOT NULL,
            batch_id UUID,
            used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, text_id, cycle_number)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_thumbnail_text_rotation_user_cycle
        ON image_thumbnail_text_rotation(user_id, cycle_number)
        """
    )
    op.execute(
        """
        ALTER TABLE image_jobs
            ADD COLUMN IF NOT EXISTS thumbnail_text_id UUID
            REFERENCES image_thumbnail_texts(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_jobs_thumbnail_text_id
        ON image_jobs(thumbnail_text_id)
        """
    )

    # Seed a few usable text presets; admins can edit or delete them.
    op.execute(
        """
        INSERT INTO image_thumbnail_texts
            (title, subtitle, subline, placement, alignment, sort_order)
        VALUES
            ('BASS', 'CAR MUSIC', '2026', 'top_center', 'center', 0),
            ('EDM', 'BASS BOOSTED', '2026', 'top_center', 'center', 1),
            ('HIDDEN FIRE', 'COASTAL SIGNAL', '2026', 'bottom_center', 'center', 2)
        ON CONFLICT DO NOTHING
        """
    )

    rows = []
    for index, (name, prompt) in enumerate(_LOCKUP_STYLES):
        rows.append(
            f"('thumbnail', {_sql_literal(name)}, {_sql_literal(prompt)}, "
            f"'lockup', {index})"
        )
    op.execute(
        "INSERT INTO image_prompt_styles "
        "(kind, name, prompt_text, text_mode, sort_order) VALUES "
        + ", ".join(rows)
    )


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM image_prompt_styles
        WHERE kind = 'thumbnail' AND text_mode = 'lockup'
        """
    )
    op.execute(
        """
        DELETE FROM image_thumbnail_text_rotation
        """
    )
    op.execute("DROP TABLE IF EXISTS image_thumbnail_text_rotation")
    op.execute("DROP TABLE IF EXISTS image_thumbnail_texts")
    op.execute(
        """
        ALTER TABLE image_jobs DROP COLUMN IF EXISTS thumbnail_text_id
        """
    )
    op.execute(
        """
        ALTER TABLE image_prompt_styles DROP COLUMN IF EXISTS text_mode
        """
    )
