"""Add the endpoint-wide ``camxora_music_api`` music price.

AI Routing can now select ``camxora_music_api`` as the music provider (Suno
compatible, ``musicapi.camxora.com``). The billing lookup for the ``music``
operation has no sub-model, so it needs a provider-wide row; migration
``128_camxora_music_api_pricing`` only seeded per-model rows (v6 / v6-wild /
v6-mini). This inserts the missing provider-wide row at the same 10-credit price
and mirrors it into ``ai_model_costs`` for the admin cost view.

Idempotent: re-running is a no-op.

Revision ID: 131_camxora_music_api_music_default
Revises: 130_web_music_free_plan
Create Date: 2026-10-05
"""

from __future__ import annotations

from alembic import op

revision = "131_camxora_music_api_music_default"
down_revision = "130_web_music_free_plan"
branch_labels = None
depends_on = None

_AI_SERVICE = "camxora_music_api"
_COST_USD = 0.05  # value of 10 musicapi credits at its entry ($5 / 1,000) rate
_CREDIT_UNITS = 100_000  # 10 display credits (matches live musicapi pricing)


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO credit_pricing (
            id, ai_service, operation_type, sub_model,
            credits_per_operation, external_cost_cents, needs_review,
            created_at, updated_at
        )
        SELECT gen_random_uuid(), '{_AI_SERVICE}', 'music', '',
               {_CREDIT_UNITS}, {_CREDIT_UNITS}, false, NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = '{_AI_SERVICE}'
              AND operation_type = 'music'
              AND COALESCE(sub_model, '') = ''
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO ai_model_costs (
            id, ai_service, sub_model, operation_type, cost_usd,
            notes, source, created_at, updated_at
        )
        SELECT gen_random_uuid(), '{_AI_SERVICE}', '', 'music',
               {_COST_USD},
               'Camxora Music API: 10 credits per generation (provider-wide)',
               'manual', NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM ai_model_costs
            WHERE ai_service = '{_AI_SERVICE}'
              AND operation_type = 'music'
              AND COALESCE(sub_model, '') = ''
        )
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM credit_pricing
        WHERE ai_service = '{_AI_SERVICE}'
          AND operation_type = 'music'
          AND COALESCE(sub_model, '') = ''
        """
    )
    op.execute(
        f"""
        DELETE FROM ai_model_costs
        WHERE ai_service = '{_AI_SERVICE}'
          AND operation_type = 'music'
          AND COALESCE(sub_model, '') = ''
        """
    )
