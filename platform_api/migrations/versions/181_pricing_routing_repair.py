"""Repair credit_pricing keys and negative margins for AI routing.

Two independent problems this migration fixes, both discovered by the
2026-11-05 AI routing x credit audit (docs/ai-routing-credit-audit-2026-11-05.md):

1. ``AIRoutingService.resolve()`` normalises text model aliases before returning
   them (``resolve_text_model_id``), so the biller asks for
   ``deepseek-v4-flash`` while the pricing rows are keyed ``deepseek-chat``
   (the retired alias). Exact-model lookups therefore miss, ``get_price``
   raises, and batch cost estimation fails with
   "Draft generation pricing is not configured". Re-key the alias rows to the
   canonical registry id.

2. A pricing row may be sold below its recorded provider cost
   (``external_cost_cents`` is stored in credit micro-units, despite the name).
   ``_validate_pricing_economics`` rejects ``cost > sell`` on create/update, but
   ``sync_from_routing_config`` and older seeds bypassed that guard, so rows
   with a negative margin can exist. Raise the sell price to the documented
   target margin rather than deleting the row (deleting would take the
   operation offline).

The migration is data-agnostic: it is safe on an install that has not yet run
175/176, and it is idempotent (a second run updates zero rows).

Revision ID: 181
Revises: 180
"""

from __future__ import annotations

from alembic import op

revision = "181"
down_revision = "180"
branch_labels = None
depends_on = None

# Canonical registry id for the retired ``deepseek-chat`` alias
# (see platform_api/ai/registry.py: DEEPSEEK_TEXT_MODELS).
_ALIAS_PROVIDER = "deepseek"
_ALIAS_MODEL = "deepseek-chat"
_CANONICAL_MODEL = "deepseek-v4-flash"

# Documented target margin used by the pricing generator / Credits page.
# 20% matches the music cost basis note in credit_pricing_service.py and
# docs/credits-only-plan-unification.md. Change here (and only here) to use a
# different floor; the SQL below derives sell from the stored cost.
_TARGET_MARGIN_PERCENT = 20


def upgrade() -> None:
    # 1. Re-key retired alias rows to the model id the biller actually receives.
    #    The NOT EXISTS guard keeps the unique
    #    (ai_service, operation_type, sub_model) key intact when both rows exist.
    op.execute(
        f"""
        UPDATE credit_pricing AS target
        SET sub_model = '{_CANONICAL_MODEL}',
            updated_at = NOW()
        WHERE target.ai_service = '{_ALIAS_PROVIDER}'
          AND target.sub_model = '{_ALIAS_MODEL}'
          AND NOT EXISTS (
              SELECT 1
              FROM credit_pricing AS existing
              WHERE existing.ai_service = target.ai_service
                AND existing.operation_type = target.operation_type
                AND existing.sub_model = '{_CANONICAL_MODEL}'
          )
        """
    )

    # Drop alias duplicates left behind when the canonical row already existed.
    op.execute(
        f"""
        DELETE FROM credit_pricing AS alias
        WHERE alias.ai_service = '{_ALIAS_PROVIDER}'
          AND alias.sub_model = '{_ALIAS_MODEL}'
          AND EXISTS (
              SELECT 1
              FROM credit_pricing AS canonical
              WHERE canonical.ai_service = alias.ai_service
                AND canonical.operation_type = alias.operation_type
                AND canonical.sub_model = '{_CANONICAL_MODEL}'
          )
        """
    )

    # 2. Raise any still-negative-margin row to the target margin.
    #    ``external_cost_cents`` holds credit micro-units (1 display credit =
    #    10_000 units); sell must be >= cost, with margin on revenue:
    #    sell = ceil(cost / (1 - margin)).
    #
    #    Music is excluded on purpose:
    #      * migration 176 owns the music sell price (10 credits), and
    #      * the stored music cost basis is inflated 2x (provider credit count
    #        entered as display credits: suno 120_000 vs the documented
    #        60_000 in ``MIN_MUSIC_COST_UNITS``, camxora 100_000 vs 50_000).
    #    Running the generic rule over music would silently undo 176 and set
    #    the price to 15. The music cost basis needs its own reviewed fix.
    divisor = 1 - (_TARGET_MARGIN_PERCENT / 100.0)
    op.execute(
        f"""
        UPDATE credit_pricing
        SET credits_per_operation = GREATEST(
                credits_per_operation,
                CEIL(external_cost_cents::numeric / {divisor})::bigint
            ),
            updated_at = NOW()
        WHERE external_cost_cents IS NOT NULL
          AND external_cost_cents > 0
          AND credits_per_operation < external_cost_cents
          AND lower(btrim(operation_type)) NOT IN ('music', 'music_generation', 'suno')
        """
    )


def downgrade() -> None:
    # Pricing rows are configuration, and both repairs are one-way:
    # re-keying to a retired alias would re-break exact lookups, and lowering a
    # sell price back below its cost would re-introduce negative margin.
    # Restore the previous values from a backup if a rollback is required.
    pass
