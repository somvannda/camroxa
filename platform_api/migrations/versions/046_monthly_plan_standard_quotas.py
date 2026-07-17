"""Align Monthly plan to dual-channel standard quotas.

Standard (account-wide monthly meters):
- Song packages: 300 Suno requests (= 600 Primary + Secondary tracks, ~300/channel)
- Drafts: 1260 (= 630/channel fair share)
- Images: 120 (= 60/channel fair share)
- Daily/channel: songs 10, drafts 21, images 2
"""

from alembic import op

revision = "046_monthly_plan_standard_quotas"
down_revision = "045_plan_draft_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE plans
        SET monthly_song_limit = 300,
            monthly_draft_limit = 1260,
            monthly_image_limit = 120,
            daily_song_limit_per_channel = 10,
            daily_draft_limit_per_channel = 21,
            daily_image_limit_per_channel = 2,
            updated_at = NOW()
        WHERE LOWER(name) = 'monthly'
        """
    )


def downgrade() -> None:
    # Best-effort prior migration defaults; not a perfect restore.
    op.execute(
        """
        UPDATE plans
        SET monthly_song_limit = 300,
            monthly_draft_limit = 900,
            monthly_image_limit = 60,
            daily_song_limit_per_channel = 100,
            daily_draft_limit_per_channel = 300,
            daily_image_limit_per_channel = 30,
            updated_at = NOW()
        WHERE LOWER(name) = 'monthly'
        """
    )
