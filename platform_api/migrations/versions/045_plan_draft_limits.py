"""Add draft allowance meters to plans (lyric/title/album pool)."""

from alembic import op

revision = "045_plan_draft_limits"
down_revision = "044_merge_streaming_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE plans
        ADD COLUMN IF NOT EXISTS monthly_draft_limit INTEGER NULL
        """
    )
    op.execute(
        """
        ALTER TABLE plans
        ADD COLUMN IF NOT EXISTS daily_draft_limit_per_channel INTEGER NOT NULL DEFAULT 300
        """
    )
    # Dual-channel draft pool: (lyric+title)×2 channels + ~2 albums/day×30
    # = song_packages * 4 + 60  (e.g. 300 → 1260).
    op.execute(
        """
        UPDATE plans
        SET monthly_draft_limit = monthly_song_limit * 4 + 60
        WHERE monthly_draft_limit IS NULL
          AND monthly_song_limit IS NOT NULL
        """
    )
    # Daily draft ≈ (lyric+title+album) for fair share of one channel day,
    # or 2× that if channel can run a full package day: use packages×2+1.
    op.execute(
        """
        UPDATE plans
        SET daily_draft_limit_per_channel = GREATEST(daily_song_limit_per_channel * 2 + 1, 21)
        WHERE daily_song_limit_per_channel IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS daily_draft_limit_per_channel")
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS monthly_draft_limit")
