"""Seed admin-managed billing term discount settings."""

import json

from alembic import op

revision = "055_plan_term_discounts"
down_revision = "054_plan_kind_profile_addons"
branch_labels = None
depends_on = None

DEFAULT = {
    "semi_annual_discount_percent": 15,
    "annual_discount_percent": 25,
}


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES (
            'plan_term_discounts',
            'json',
            '{json.dumps(DEFAULT)}'::jsonb,
            NOW()
        )
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key = 'plan_term_discounts'")
