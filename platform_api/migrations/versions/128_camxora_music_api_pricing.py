"""Seed Camxora Music API model costs and credit pricing.

The platform can now charge music generations that are fulfilled through the
Camxora Music API (musicapi.camxora.com) as a distinct provider alongside
``suno``. Only the current V6 series is offered:

    v6, v6-wild, v6-mini

Costs mirror exactly what musicapi.camxora.com charges today: its live pricing
table has ``music`` at 10 credits per generation, so each V6 model is priced at
10 credits. ``cost_usd`` is the provider COGS estimate and
``credits_per_operation`` / ``external_cost_cents`` are stored as micro-units
(1 display credit = 10,000 units).

Rows are sourced ``manual`` so a later "Seed from registry" run does not prune
them (the registry does not model this provider).

Revision ID: 128_camxora_music_api_pricing
Revises: 127_web_music_plans_v2
Create Date: 2026-10-04
"""

from __future__ import annotations

from alembic import op

revision = "128_camxora_music_api_pricing"
down_revision = "127_web_music_plans_v2"
branch_labels = None
depends_on = None

_AI_SERVICE = "camxora_music_api"
_COST_USD = 0.03
_CREDIT_UNITS = 100_000  # 10 display credits (matches live musicapi pricing)
_MODELS = ("v6", "v6-wild", "v6-mini")


def upgrade() -> None:
    for model in _MODELS:
        op.execute(
            f"""
            INSERT INTO ai_model_costs (
                id, ai_service, sub_model, operation_type, cost_usd,
                notes, source, created_at, updated_at
            )
            SELECT gen_random_uuid(), '{_AI_SERVICE}', '{model}', 'music',
                   {_COST_USD},
                   'Camxora Music API: 10 credits per generation (matches live musicapi pricing)',
                   'manual', NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM ai_model_costs
                WHERE ai_service = '{_AI_SERVICE}'
                  AND COALESCE(sub_model, '') = '{model}'
                  AND operation_type = 'music'
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
            SELECT gen_random_uuid(), '{_AI_SERVICE}', 'music', '{model}',
                   {_CREDIT_UNITS}, {_CREDIT_UNITS}, false, NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM credit_pricing
                WHERE ai_service = '{_AI_SERVICE}'
                  AND operation_type = 'music'
                  AND COALESCE(sub_model, '') = '{model}'
            )
            """
        )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM credit_pricing
        WHERE ai_service = '{_AI_SERVICE}'
          AND operation_type = 'music'
          AND COALESCE(sub_model, '') IN ('v6', 'v6-wild', 'v6-mini')
        """
    )
    op.execute(
        f"""
        DELETE FROM ai_model_costs
        WHERE ai_service = '{_AI_SERVICE}'
          AND operation_type = 'music'
          AND COALESCE(sub_model, '') IN ('v6', 'v6-wild', 'v6-mini')
        """
    )
