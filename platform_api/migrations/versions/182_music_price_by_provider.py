"""Price music generation by routed provider: sunoapi.org 15, musicapi 10.

Decision (2026-11-05): the price follows the provider AI Routing picked.

  * ``suno``            -> sunoapi.org reseller, 15 credits per generation
  * ``camxora_music_api`` -> Camxora's own musicapi, 10 credits per generation

This supersedes migration 176 (which set 10 for Suno) because the reseller's
cost is higher and must not be sold at the musicapi price. The two ids are
served by the same Suno-compatible client; only the upstream host and the price
row differ.

Because the price differs per provider, a runtime failover must charge the
provider that actually executed. Quotes already follow AI Routing
(``_music_fallbacks`` prefers the routed provider's row), so a manual switch is
price-correct. Automatic failover needs the hold/settle pattern (see
docs/ai-routing-credit-audit-2026-11-05.md, W8) before it is enabled.

Revision ID: 182
Revises: 181
"""

from __future__ import annotations

from alembic import op

revision = "182"
down_revision = "181"
branch_labels = None
depends_on = None

_MUSIC_OPS = ("music", "music_generation", "suno")
_MUSIC_OPS_SQL = ", ".join(f"'{o}'" for o in _MUSIC_OPS)

# provider -> sell price in credit micro-units (1 display credit = 10_000).
_RESELLER_UNITS = 150_000  # sunoapi.org, 15 display credits
_MUSICAPI_UNITS = 100_000  # our musicapi, 10 display credits


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE credit_pricing
        SET credits_per_operation = {_RESELLER_UNITS},
            updated_at = NOW()
        WHERE ai_service = 'suno'
          AND operation_type IN ({_MUSIC_OPS_SQL})
        """
    )
    op.execute(
        f"""
        UPDATE credit_pricing
        SET credits_per_operation = {_MUSICAPI_UNITS},
            updated_at = NOW()
        WHERE ai_service = 'camxora_music_api'
          AND operation_type IN ({_MUSIC_OPS_SQL})
        """
    )


def downgrade() -> None:
    # 176 set suno music to 10; 131 set camxora music to 10. Both were 10, so a
    # single statement restores the pre-182 state.
    op.execute(
        f"""
        UPDATE credit_pricing
        SET credits_per_operation = {_MUSICAPI_UNITS},
            updated_at = NOW()
        WHERE ai_service IN ('suno', 'camxora_music_api')
          AND operation_type IN ({_MUSIC_OPS_SQL})
        """
    )
