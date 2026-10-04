"""Correct web-music economics: real GCV, recalibrated COGS, profitable music price.

At the real value of a music.camxora.com credit (GCV $0.005), the old 7.5-credit
music price was a loss against the ~$0.06 Suno cost. This migration:

1. Sets ``global_credit_value`` to 0.005 (the $5 / 1,000-credit entry rate).
2. Recalibrates every Cost Credits value to ``cost_usd / GCV`` so the Credits
   page shows real cost/profit.
3. Keeps the Suno music COGS at $0.06 but charges 15 credits ($0.075) per
   generation -> a 20% margin, and seeds the V6-series music rows.

Revision ID: 129_web_music_real_economics
Revises: 128_camxora_music_api_pricing
Create Date: 2026-10-04
"""

from __future__ import annotations

from alembic import op

revision = "129_web_music_real_economics"
down_revision = "128_camxora_music_api_pricing"
branch_labels = None
depends_on = None

_GCV = "0.005"
_MUSIC_PRICE_UNITS = 150_000  # 15 display credits
_MUSIC_COST_UNITS = 120_000  # 12 display credits = $0.06 at GCV $0.005
_MUSIC_MODELS = ("V6", "V6_MINI", "V6_WILD")


def _set_gcv(value: str) -> None:
    op.execute(
        f"""
        INSERT INTO system_settings (key, value, value_type, updated_at)
        VALUES ('global_credit_value', '{value}', 'number', NOW())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """
    )


def _recalibrate_cost_credits(gcv: str) -> None:
    op.execute(
        f"""
        UPDATE credit_pricing cp
        SET external_cost_cents = ROUND(amc.cost_usd / {gcv} * 10000),
            updated_at = NOW()
        FROM ai_model_costs amc
        WHERE cp.ai_service = amc.ai_service
          AND COALESCE(cp.sub_model, '') = COALESCE(amc.sub_model, '')
          AND cp.operation_type = amc.operation_type
          AND amc.cost_usd > 0
        """
    )


def upgrade() -> None:
    _set_gcv(_GCV)
    _recalibrate_cost_credits(_GCV)

    op.execute(
        """
        UPDATE ai_model_costs
        SET cost_usd = 0.06, updated_at = NOW()
        WHERE ai_service = 'suno' AND operation_type IN ('music', 'music_generation')
        """
    )

    for model in _MUSIC_MODELS:
        op.execute(
            f"""
            INSERT INTO credit_pricing (
                id, ai_service, operation_type, sub_model,
                credits_per_operation, external_cost_cents, needs_review,
                created_at, updated_at
            )
            SELECT gen_random_uuid(), 'suno', 'music', '{model}',
                   {_MUSIC_PRICE_UNITS}, {_MUSIC_COST_UNITS}, false, NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM credit_pricing
                WHERE ai_service = 'suno' AND operation_type = 'music'
                  AND COALESCE(sub_model, '') = '{model}'
            )
            """
        )

    op.execute(
        f"""
        UPDATE credit_pricing
        SET credits_per_operation = {_MUSIC_PRICE_UNITS},
            external_cost_cents = {_MUSIC_COST_UNITS},
            updated_at = NOW()
        WHERE ai_service = 'suno'
          AND operation_type IN ('music', 'music_generation')
        """
    )


def downgrade() -> None:
    _set_gcv("0.01")
    op.execute(
        """
        UPDATE credit_pricing
        SET credits_per_operation = 75000, external_cost_cents = 60000, updated_at = NOW()
        WHERE ai_service = 'suno'
          AND operation_type IN ('music', 'music_generation')
        """
    )
    _recalibrate_cost_credits("0.01")
