"""One pack lot per purchase reference; retire the v2 grant trigger.

Settlement runs more than once for the same top-up: the payment webhook and the
client's status poll race, and a provider retry adds more. The credit grant was
already idempotent on ``(user, reason, ref)``, but the pack lot insert was not,
so the wallet was credited once while the lot ledger grew a duplicate for every
extra caller. Production held 17 duplicate lot pairs (42,300 credits, 14,942.92
still live) by 2026-11-10. The partial unique index below makes a second lot for
the same purchase reference impossible; ``insert_pack_lot_if_absent`` returns
the existing row instead.

Migration 091 also left ``trigger_grant_topup_credits`` firing on every
``pending -> completed`` update. It credited ``credits_purchased`` as *units*
(0.1 credit for a 1,000 pack) on top of the v3 pack grant — a second, wrong-unit
credit writer whose residue is why some wallets end in ``.10``. Nothing reads
the ``topup_purchase`` ledger rows it writes, so it is dropped here.

Existing rows are untouched (all current pack lots have a unique reference or
NULL), so this migration does not move any wallet balance.

Revision ID: 186
Revises: 185
"""

from __future__ import annotations

from alembic import op

revision = "186"
down_revision = "185"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_wallet_lots_pack_ref
        ON credit_wallet_lots (user_id, ref_id)
        WHERE tag = 'pack' AND ref_id IS NOT NULL
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trigger_grant_topup_credits ON topup_purchases")
    op.execute("DROP FUNCTION IF EXISTS grant_topup_credits()")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_credit_wallet_lots_pack_ref")
    # The trigger is deliberately not restored: it double-credited in the wrong
    # unit (credits written as units) and the v3 pack path already grants.
