"""Retire the legacy web-music free-daily system settings.

``web_music_free_daily_limit`` (084) and ``web_music_free_daily_credits`` (095)
were superseded by the Free plan row's ``daily_credits`` during the credits-only
unification, so the setting rows are dropped to keep a single source of truth.

Revision ID: 123_retire_web_music_free_daily_settings
Revises: 122_suno_v6_pricing
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op

revision = "123_retire_web_music_free_daily_settings"
down_revision = "122_suno_v6_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM system_settings
        WHERE key IN ('web_music_free_daily_limit', 'web_music_free_daily_credits')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES ('web_music_free_daily_limit', 'int', '5', NOW())
        ON CONFLICT (key) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES ('web_music_free_daily_credits', 'int', '50', NOW())
        ON CONFLICT (key) DO NOTHING
        """
    )
