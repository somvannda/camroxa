"""Allow $0 credit pricing and make local video export / merge free.

Local desktop operations (``video`` / ``video_manual`` / ``video_merge``) run on
the user's machine with FFmpeg (COGS $0). We no longer charge for them, so:

  - relax ``credit_pricing_credits_per_operation_check`` to allow 0
  - set the local video/merge pricing rows to 0 (sell + cost)
  - force ``plans.video_credits`` / ``merge_credits`` to 0 where set

Revision ID: 124_free_local_video_merge
Revises: 123_retire_web_music_free_daily_settings
Create Date: 2026-09-29
"""

from __future__ import annotations

from alembic import op

revision = "124_free_local_video_merge"
down_revision = "123_retire_web_music_free_daily_settings"
branch_labels = None
depends_on = None

SCALE = 10_000
MAX_UNITS = 10_000_000 * SCALE
LOCAL_OPS = ("video", "video_manual", "video_merge", "merge")


def upgrade() -> None:
    op.execute(
        "ALTER TABLE credit_pricing "
        "DROP CONSTRAINT IF EXISTS credit_pricing_credits_per_operation_check"
    )
    op.execute(
        "ALTER TABLE credit_pricing "
        "ADD CONSTRAINT credit_pricing_credits_per_operation_check "
        f"CHECK (credits_per_operation >= 0 AND credits_per_operation <= {MAX_UNITS})"
    )
    op.execute(
        "UPDATE credit_pricing "
        "SET credits_per_operation = 0, external_cost_cents = 0 "
        "WHERE ai_service = 'local' "
        "AND operation_type IN ('video', 'video_manual', 'video_merge', 'merge')"
    )
    op.execute(
        "UPDATE plans SET video_credits = 0, merge_credits = 0, updated_at = NOW() "
        "WHERE COALESCE(video_credits, 0) <> 0 OR COALESCE(merge_credits, 0) <> 0"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE credit_pricing SET credits_per_operation = "
        "CASE operation_type "
        "WHEN 'video' THEN 3 * 10000 "
        "WHEN 'video_manual' THEN 5 * 10000 "
        "WHEN 'video_merge' THEN 5 * 10000 "
        "ELSE credits_per_operation END "
        "WHERE ai_service = 'local' "
        "AND operation_type IN ('video', 'video_manual', 'video_merge')"
    )
    op.execute(
        "ALTER TABLE credit_pricing "
        "DROP CONSTRAINT IF EXISTS credit_pricing_credits_per_operation_check"
    )
    op.execute(
        "ALTER TABLE credit_pricing "
        "ADD CONSTRAINT credit_pricing_credits_per_operation_check "
        f"CHECK (credits_per_operation >= 1 AND credits_per_operation <= {MAX_UNITS})"
    )
