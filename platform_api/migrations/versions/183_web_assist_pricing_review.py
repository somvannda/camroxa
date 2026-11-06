"""Review the web AI-assist pricing rows: 5 credits + a real cost basis.

The four ``web_music_*`` rows were seeded as drafts (``needs_review = true``)
with a zero cost basis. They are now reached deterministically by the v3 text
quote (W5b), so they must be a decided price rather than an auto-seeded draft.

Decision (2026-11-05): AI assist costs **5 credits**, matching
docs/credits-only-plan-unification.md. Cost basis is the registry estimate at
~900 tokens (lyrics) / ~400 tokens (style):

  * deepseek-v4-flash ~$0.0014/1K -> 0.126 cr lyrics, 0.056 cr style
  * gpt-4o-mini       ~$0.0006/1K -> 0.054 cr lyrics, 0.024 cr style

Cost only affects margin reporting and the create/update guard; it does not
change what users pay.

Revision ID: 183
Revises: 182
"""

from __future__ import annotations

from alembic import op

revision = "183"
down_revision = "182"
branch_labels = None
depends_on = None

_FIVE_CREDITS = 50_000

# (provider, operation) -> (sell_units, cost_units)
_REVIEWED = {
    ("deepseek", "web_music_lyrics"): (_FIVE_CREDITS, 1_260),
    ("deepseek", "web_music_style"): (_FIVE_CREDITS, 560),
    ("openai", "web_music_lyrics"): (_FIVE_CREDITS, 540),
    ("openai", "web_music_style"): (_FIVE_CREDITS, 240),
}

# Pre-183 state (auto-seeded drafts).
_ORIGINAL = {
    ("deepseek", "web_music_lyrics"): 20_000,
    ("deepseek", "web_music_style"): 20_000,
    ("openai", "web_music_lyrics"): 30_000,
    ("openai", "web_music_style"): 20_000,
}


def upgrade() -> None:
    for (service, operation), (sell, cost) in _REVIEWED.items():
        op.execute(
            f"""
            UPDATE credit_pricing
            SET credits_per_operation = {sell},
                external_cost_cents = {cost},
                needs_review = FALSE,
                updated_at = NOW()
            WHERE ai_service = '{service}'
              AND operation_type = '{operation}'
            """
        )


def downgrade() -> None:
    for (service, operation), sell in _ORIGINAL.items():
        op.execute(
            f"""
            UPDATE credit_pricing
            SET credits_per_operation = {sell},
                external_cost_cents = 0,
                needs_review = TRUE,
                updated_at = NOW()
            WHERE ai_service = '{service}'
              AND operation_type = '{operation}'
            """
        )
