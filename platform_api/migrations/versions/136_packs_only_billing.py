"""Packs-only billing: raise web-music packs to the plan credit ladder.

Revision ID: 136_packs_only_billing
Revises: 135_web_subscription_renewal
Create Date: 2026-10-15

Subscriptions are no longer sold on music.camxora.com; credit packs are the only
product. So a pack must now be worth what the matching monthly plan used to be --
same price, same credit allowance:

    $5  -> 1,000 credits   (small)   was   700
    $10 -> 2,300 credits   (medium)  was 1,840
    $20 -> 5,500 credits   (pro)     new tier -- the plan ladder had no $20 pack
    $30 -> 8,800 credits   (large)   was 7,920

Pack credits expire 30 days from purchase; that rule lives in code
(``PACK_CREDIT_VALIDITY`` in ``services/v3/wallet_sync.py``) and deliberately does
not touch here, so existing lots keep whatever expiry they already had.

Idempotent: re-running is a no-op.
"""

from __future__ import annotations

from alembic import op

revision = "136_packs_only_billing"
down_revision = "135_web_subscription_renewal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Raise the three existing tiers to the plan allowance at the same price.
    op.execute(
        """
        UPDATE credit_packs
        SET name = 'Small Pack',
            pack_type = 'web_music',
            total_credits = 1000,
            song_credits = 100,
            request_count = 100,
            display_order = 1,
            is_active = true,
            updated_at = NOW()
        WHERE slug = 'small' AND pack_type = 'web_music'
        """
    )
    op.execute(
        """
        UPDATE credit_packs
        SET name = 'Medium Pack',
            pack_type = 'web_music',
            total_credits = 2300,
            song_credits = 230,
            request_count = 230,
            display_order = 2,
            is_active = true,
            updated_at = NOW()
        WHERE slug = 'medium' AND pack_type = 'web_music'
        """
    )
    op.execute(
        """
        UPDATE credit_packs
        SET name = 'Large Pack',
            pack_type = 'web_music',
            total_credits = 8800,
            song_credits = 880,
            request_count = 880,
            display_order = 4,
            is_active = true,
            updated_at = NOW()
        WHERE slug = 'large' AND pack_type = 'web_music'
        """
    )

    # 2. The $20 plan tier had no matching pack; add it so the ladder is complete.
    op.execute(
        """
        INSERT INTO credit_packs (
            slug, name, pack_type, total_credits, price_cents,
            song_credits, request_count, display_order, is_active
        ) VALUES
            ('pro', 'Pro Pack', 'web_music', 5500, 2000, 550, 550, 3, true)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            pack_type = 'web_music',
            total_credits = EXCLUDED.total_credits,
            price_cents = EXCLUDED.price_cents,
            song_credits = EXCLUDED.song_credits,
            request_count = EXCLUDED.request_count,
            display_order = EXCLUDED.display_order,
            is_active = true,
            updated_at = NOW()
        """
    )

    # 3. Retire the old fourth tier; it no longer fits the ladder.
    op.execute(
        """
        UPDATE credit_packs
        SET is_active = false, updated_at = NOW()
        WHERE slug = 'mega' AND pack_type = 'web_music'
        """
    )


def downgrade() -> None:
    # Restore the pre-136 pack prices/credits.
    op.execute(
        """
        UPDATE credit_packs
        SET total_credits = 700, song_credits = 70, request_count = 70,
            display_order = 1, updated_at = NOW()
        WHERE slug = 'small' AND pack_type = 'web_music'
        """
    )
    op.execute(
        """
        UPDATE credit_packs
        SET total_credits = 1840, song_credits = 184, request_count = 184,
            display_order = 2, updated_at = NOW()
        WHERE slug = 'medium' AND pack_type = 'web_music'
        """
    )
    op.execute(
        """
        UPDATE credit_packs
        SET total_credits = 7920, song_credits = 792, request_count = 792,
            display_order = 3, updated_at = NOW()
        WHERE slug = 'large' AND pack_type = 'web_music'
        """
    )
    op.execute("DELETE FROM credit_packs WHERE slug = 'pro' AND pack_type = 'web_music'")
    op.execute(
        """
        UPDATE credit_packs
        SET is_active = false, updated_at = NOW()
        WHERE slug = 'mega' AND pack_type = 'web_music'
        """
    )
