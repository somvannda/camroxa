"""Allow credit-pack top-ups without a web subscription.

Subscriptions stopped being sold on music.camxora.com (migration
``136_packs_only_billing``), so ``TopupService.purchase_topup`` links a purchase
to a subscription only when the buyer happens to be a grandfathered subscriber
and otherwise inserts ``NULL``.

Retail production still had ``topup_purchases.web_subscription_id NOT NULL``,
so every pack purchase by a non-subscriber failed inside the INSERT and the API
answered a generic 500 ("An unexpected error occurred."). No ``billing`` row was
ever written, which is why the failure left no trace in ``topup_purchases``.

The repository's original table definition (``091_topup_purchases``) is already
nullable, so this is a no-op on fresh databases and repairs drifted installs.

Revision ID: 146_topup_purchase_subscription_nullable
Revises: 145_web_music_preview_masters
Create Date: 2026-10-21
"""

from __future__ import annotations

from alembic import op

revision: str = "146_topup_purchase_subscription_nullable"
down_revision: str | None = "145_web_music_preview_masters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE topup_purchases
            ALTER COLUMN web_subscription_id DROP NOT NULL
        """
    )


def downgrade() -> None:
    # Re-tighten only what the original schema allowed. Existing NULL rows
    # (non-subscriber pack purchases) make this fail loudly rather than being
    # silently rewritten, which is the correct outcome for a downgrade.
    op.execute(
        """
        ALTER TABLE topup_purchases
            ALTER COLUMN web_subscription_id SET NOT NULL
        """
    )
