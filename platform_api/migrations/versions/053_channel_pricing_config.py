"""Seed default linear channel pricing configuration."""

import json

from alembic import op

revision = "053_channel_pricing_config"
down_revision = "052_profile_addon_pending"
branch_labels = None
depends_on = None

DEFAULT_CONFIG = {
    "two_channel_block_cents": 7900,
    "addon_bundle_cents": {"2": 7900, "4": 15800, "6": 23700, "8": 31600},
    "semi_annual_discount_percent": 15,
    "annual_discount_percent": 25,
}


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES (
            'channel_pricing_config',
            'json',
            '{json.dumps(DEFAULT_CONFIG)}'::jsonb,
            NOW()
        )
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key = 'channel_pricing_config'")
