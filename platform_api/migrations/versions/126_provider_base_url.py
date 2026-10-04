"""Per-key and per-provider upstream host for reversible provider switching.

Adds ``api_key_entries.base_url`` (which upstream a key belongs to) and
``key_pool_configs.base_url`` (the active upstream for the provider). When a
provider's config ``base_url`` is set, only keys tagged with that same host are
eligible, so sunoapi.org keys and Camxora musicapi keys can coexist in one pool
and the active host can be switched — or rolled back — from the admin console
without a redeploy.

Both columns are nullable: ``NULL`` preserves the legacy behaviour of using the
environment default (``PLATFORM_SUNO_API_BASE_URL``) and every active key.

Revision ID: 126_provider_base_url
Revises: 125_slai_image_model_cx_gpt_image_2_5
Create Date: 2026-10-04
"""

from __future__ import annotations

from alembic import op

revision = "126_provider_base_url"
down_revision = "125_slai_image_model_cx_gpt_image_2_5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE api_key_entries ADD COLUMN IF NOT EXISTS base_url TEXT"
    )
    op.execute(
        "ALTER TABLE key_pool_configs ADD COLUMN IF NOT EXISTS base_url TEXT"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE key_pool_configs DROP COLUMN IF EXISTS base_url")
    op.execute("ALTER TABLE api_key_entries DROP COLUMN IF EXISTS base_url")
