"""Seed default SLAI image provider configuration in system_settings."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "036_slai_image_provider_config"
down_revision = "035_image_random_history"
branch_labels = None
depends_on = None

_DEFAULT_CONFIG = (
    '{"min_interval_seconds":5.0,"max_concurrent":1,"provider_retries":5,'
    '"retry_base_delay_seconds":5.0,"retry_max_delay_seconds":45.0,'
    '"fallback_provider_retries":1}'
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO system_settings (key, value_type, value, updated_at)
            VALUES ('slai_image_provider_config', 'json', :config, NOW())
            ON CONFLICT (key) DO NOTHING
            """
        ),
        {"config": _DEFAULT_CONFIG},
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM system_settings WHERE key = 'slai_image_provider_config'"
    )
