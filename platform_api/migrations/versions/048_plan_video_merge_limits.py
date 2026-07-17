"""Add video + merge plan meters and seed Standard Monthly + list prices.

Video/merge are local (COGS $0). Daily caps are **account-wide** (not
per-channel) so 10 videos/day × 30 = 300/mo and 1 merge/day × 30 = 30/mo.
Song/draft/image keep daily_*_per_channel.
"""

from alembic import op

revision = "048_plan_video_merge_limits"
down_revision = "047_admin_pending_ops"
branch_labels = None
depends_on = None

# 3 display credits = 30_000 micro-units; 10 display = 100_000 (CREDIT_SCALE=10_000)
_VIDEO_UNITS = 30_000
_MERGE_UNITS = 100_000


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE plans
        ADD COLUMN IF NOT EXISTS monthly_video_limit INTEGER NULL
        """
    )
    op.execute(
        """
        ALTER TABLE plans
        ADD COLUMN IF NOT EXISTS monthly_merge_limit INTEGER NULL
        """
    )
    op.execute(
        """
        ALTER TABLE plans
        ADD COLUMN IF NOT EXISTS daily_video_limit INTEGER NOT NULL DEFAULT 10
        """
    )
    op.execute(
        """
        ALTER TABLE plans
        ADD COLUMN IF NOT EXISTS daily_merge_limit INTEGER NOT NULL DEFAULT 1
        """
    )

    # Standard Monthly: 300 videos / 30 merges / day 10 + 1 (account-wide).
    op.execute(
        """
        UPDATE plans
        SET monthly_video_limit = 300,
            monthly_merge_limit = 30,
            daily_video_limit = 10,
            daily_merge_limit = 1
        WHERE LOWER(name) = 'monthly'
        """
    )

    # List prices: video=3, video_merge=10 display credits; COGS $0 (local ffmpeg).
    op.execute(
        f"""
        INSERT INTO credit_pricing (
            id, ai_service, operation_type, sub_model,
            credits_per_operation, external_cost_cents, needs_review,
            created_at, updated_at
        )
        SELECT gen_random_uuid(), 'local', 'video', '',
               {_VIDEO_UNITS}, 0, false, NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = 'local' AND operation_type = 'video'
              AND COALESCE(sub_model, '') = ''
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO credit_pricing (
            id, ai_service, operation_type, sub_model,
            credits_per_operation, external_cost_cents, needs_review,
            created_at, updated_at
        )
        SELECT gen_random_uuid(), 'local', 'video_merge', '',
               {_MERGE_UNITS}, 0, false, NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = 'local' AND operation_type = 'video_merge'
              AND COALESCE(sub_model, '') = ''
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM credit_pricing
        WHERE ai_service = 'local'
          AND operation_type IN ('video', 'video_merge')
        """
    )
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS daily_merge_limit")
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS daily_video_limit")
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS monthly_merge_limit")
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS monthly_video_limit")
