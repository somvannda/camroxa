"""Add music_moods catalog, songs.mood_id, and seed EDM/feeling moods."""

from __future__ import annotations

from alembic import op

revision = "069_music_moods"
down_revision = "068_video_export_telemetry"
branch_labels = None
depends_on = None

# System mood seeds: short writing briefs for album/title/lyric (not Suno style).
_MOOD_SEEDS: tuple[tuple[str, str], ...] = (
    (
        "Euphoric Peak-Time",
        "Euphoric festival EDM energy. Big-room lift, hands-up joy, cathartic release. "
        "Write bright, anthemic emotion. Avoid neon-city clichés, chrome, cyberpunk, and night-drive tropes.",
    ),
    (
        "Melodic Melancholy",
        "Melodic EDM sadness: bittersweet chords, quiet longing, beautiful ache. "
        "Intimate and reflective. Avoid party bravado, neon nightlife, and hyper-aggressive flex lines.",
    ),
    (
        "Bittersweet Love",
        "Romantic love with a soft sting — devotion mixed with distance. "
        "Specific tender images, honest vulnerability. Avoid neon, cars, chrome, and cyberpunk metaphors.",
    ),
    (
        "Heartbreak Afterglow",
        "Post-breakup heartbreak: empty rooms, leftover messages, quiet grief. "
        "Emotional and personal. Avoid nightlife flex, neon skylines, and racing/city-chase imagery.",
    ),
    (
        "Pure Joy",
        "Uncomplicated happiness and celebration. Warm smiles, light feet, sunlit energy. "
        "Keep language playful and clean. Avoid dark underground grit and neon noir tropes.",
    ),
    (
        "Dark & Aggressive",
        "Hard, confrontational EDM attitude: tension, edge, controlled rage. "
        "Sharp verbs and punchy lines. Still original — avoid neon cyberpunk and night-drive clichés.",
    ),
    (
        "Dreamy Ethereal",
        "Dream-pop / ethereal EDM haze: floating, weightless, half-asleep wonder. "
        "Soft surreal images. Avoid street racing, neon signage, and chrome-city catalogs.",
    ),
    (
        "Nostalgic Summer",
        "Warm nostalgia: late summer evenings, old friendships, fading light. "
        "Memory-forward and specific. Avoid futuristic neon, cyberpunk, and club-flex swagger.",
    ),
    (
        "Empowerment Anthem",
        "Self-worth and rising-up anthem. Strong but human — courage, boundaries, reclaiming voice. "
        "Avoid neon city tropes and empty tough-guy posturing.",
    ),
    (
        "Lonely Quiet Night",
        "Quiet loneliness without cyberpunk scenery. Empty apartment, unanswered calls, soft solitude. "
        "Emotional restraint. Explicitly avoid neon lights, chrome, and night-drive metaphors.",
    ),
    (
        "Romantic Intimacy",
        "Close, soft romance: breath, touch, whispered honesty. Slow emotional heat. "
        "Avoid festival mega-hooks, neon, and racing imagery.",
    ),
    (
        "Hopeful Sunrise",
        "Hope after hardship: morning reset, second chances, gentle resolve. "
        "Forward-looking warmth. Avoid dark neon noir and underground menace.",
    ),
    (
        "Anxious Tension",
        "Anxiety and restless anticipation — racing thoughts, tight chest, waiting for a drop. "
        "Psychological, not scenic. Avoid neon skyline lists and cyberpunk gadget imagery.",
    ),
    (
        "Playful Flirt",
        "Flirty, teasing chemistry with wink and charm. Light, witty, danceable. "
        "Keep it fun. Avoid tragic neon noir and heavy cyberpunk metaphors.",
    ),
    (
        "Grief & Loss",
        "Grief that sits heavy: absence, ritual, remembering. Respectful and specific. "
        "No party tropes. Avoid neon, chrome, and night-drive clichés entirely.",
    ),
    (
        "Rebellion Defiance",
        "Defiant independence — refusing a script, breaking a rule, owning the choice. "
        "Attitude with purpose. Avoid generic neon-city rebellion wallpaper.",
    ),
    (
        "Chillout Calm",
        "Calm downtempo mood: exhale, soft pulse, peaceful clarity. "
        "Sparse gentle language. Avoid hype festival energy and neon cyberpunk scenery.",
    ),
    (
        "Passionate Desire",
        "Hungry romantic desire — heat, pull, magnetic want. Sensual but tasteful. "
        "Avoid neon nightlife catalogs and car/chase metaphors.",
    ),
    (
        "Grateful Warmth",
        "Gratitude and soft appreciation: found family, quiet thanks, earned peace. "
        "Warm and grounded. Avoid dark neon noir and aggressive drop-culture bravado.",
    ),
    (
        "Mysterious Seduction",
        "Mysterious allure and slow seduction — secrets, half-smiles, charged silence. "
        "Elegant tension. Avoid neon-sign tourism and chrome cyberpunk filler.",
    ),
    (
        "Festival Hands-Up",
        "Mainstage festival togetherness: crowd as one heartbeat, shared lift, communal joy. "
        "Collective euphoria. Avoid lone neon night-drive loner tropes.",
    ),
    (
        "Underground Warehouse",
        "Raw underground warehouse feeling: sweat, concrete pulse, hypnotic groove. "
        "Physical and minimal. Avoid glossy neon cyberpunk tourism language.",
    ),
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS music_moods (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            content TEXT NOT NULL
                CHECK (char_length(content) >= 1 AND char_length(content) <= 5000),
            match_key VARCHAR(100),
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_music_moods_global_name
        ON music_moods (name)
        WHERE user_id IS NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_music_moods_user_active_name
        ON music_moods (user_id, name)
        WHERE user_id IS NOT NULL AND is_active = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_music_moods_user_active_name
        ON music_moods (user_id, is_active, name)
        """
    )
    op.execute(
        """
        ALTER TABLE songs
        ADD COLUMN IF NOT EXISTS mood_id UUID REFERENCES music_moods(id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_songs_mood_id
        ON songs (mood_id)
        """
    )

    for name, content in _MOOD_SEEDS:
        safe_name = name.replace("'", "''")
        safe_content = content.replace("'", "''")
        op.execute(
            f"""
            INSERT INTO music_moods (id, name, content, match_key, user_id, is_active, created_at, updated_at)
            SELECT gen_random_uuid(), '{safe_name}', '{safe_content}', NULL, NULL, TRUE, NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM music_moods
                WHERE user_id IS NULL AND name = '{safe_name}'
            )
            """
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_songs_mood_id")
    op.execute("ALTER TABLE songs DROP COLUMN IF EXISTS mood_id")
    op.execute("DROP INDEX IF EXISTS idx_music_moods_user_active_name")
    op.execute("DROP INDEX IF EXISTS ux_music_moods_user_active_name")
    op.execute("DROP INDEX IF EXISTS ux_music_moods_global_name")
    op.execute("DROP TABLE IF EXISTS music_moods")
