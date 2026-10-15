"""CutLuy fulfill → shared credit_wallets (period grant + pack lots)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from platform_api.services.credit_ledger import CreditLedger, GrantType
from platform_api.services.credit_units import credits_to_units, units_to_credits

logger = logging.getLogger(__name__)

# A pack's credits are valid for this long from the moment of purchase. Buying
# another pack re-stamps the whole live balance to ``now + PACK_CREDIT_VALIDITY``
# (one shared expiry date per wallet -- see ``V3BillingStore.restamp_live_lots``).
PACK_CREDIT_VALIDITY = timedelta(days=30)


def pack_ref_id(topup_id: str) -> str:
    return f"v3_pack:{topup_id}"


class WalletSyncService:
    def __init__(self, *, grant: Any, store: Any, credit_repo: Any) -> None:
        self._grant = grant
        self._store = store
        self._credit_repo = credit_repo

    async def after_subscription_fulfill(self, user_id: UUID) -> dict[str, Any]:
        result = await self._grant.ensure_period_grant(user_id)
        if result.get("granted") or result.get("reason") == "already_granted":
            await self._store.zero_web_monthly_remaining(user_id)
        return result

    async def after_topup_fulfill(
        self,
        user_id: UUID,
        credits: int,
        *,
        topup_id: str,
    ) -> dict[str, Any]:
        amount = max(0, int(credits or 0))
        ref_id = pack_ref_id(topup_id)
        if amount <= 0:
            return {
                "minted": False,
                "reason": "zero_credits",
                "user_id": str(user_id),
                "ref_id": ref_id,
            }
        if await self._store.has_transaction_ref(ref_id):
            return {
                "minted": False,
                "reason": "already_minted",
                "user_id": str(user_id),
                "credits": amount,
                "ref_id": ref_id,
            }
        units = credits_to_units(amount)
        await CreditLedger(self._credit_repo).grant(
            user_id,
            units,
            grant_type=GrantType.PACK,
            ref_id=ref_id,
        )
        # Packs are no longer immortal. A purchase is valid for 30 days, and it
        # resets the wallet's single shared expiry date so older packs plus any
        # leftover subscription allowance age forward with it (Option B). The
        # per-op credit is already granted above; stamping the lot only decides
        # when the balance burns.
        expires_at = datetime.now(timezone.utc) + PACK_CREDIT_VALIDITY
        lot = await self._store.insert_lot(
            user_id=user_id,
            tag="pack",
            amount_units=units,
            expires_at=expires_at,
            period_start=None,
        )
        restamped_lots = await self._store.restamp_live_lots(user_id, expires_at)
        await self._store.subtract_web_topup(user_id, amount)
        return {
            "minted": True,
            "user_id": str(user_id),
            "credits": amount,
            "amount_units": units,
            "ref_id": ref_id,
            "lot_id": str(lot["id"]),
            "expires_at": expires_at.isoformat(),
            "restamped_lots": restamped_lots,
            "balance_credits": units_to_credits(int(await self._credit_repo.get_balance(user_id))),
        }


def try_wallet_sync() -> WalletSyncService | None:
    try:
        from platform_api.dependencies import get_credit_repo, get_v3_grant_service, get_v3_store

        return WalletSyncService(
            grant=get_v3_grant_service(),
            store=get_v3_store(),
            credit_repo=get_credit_repo(),
        )
    except Exception:
        logger.exception("v3 wallet sync is unavailable")
        return None


async def sync_subscription_grant(user_id: UUID) -> dict[str, Any] | None:
    sync = try_wallet_sync()
    if sync is None:
        return None
    try:
        return await sync.after_subscription_fulfill(user_id)
    except Exception:
        logger.exception("v3 period grant after CutLuy subscribe failed user=%s", user_id)
        return None


async def sync_topup_pack(user_id: UUID, credits: int, *, topup_id: str) -> dict[str, Any] | None:
    sync = try_wallet_sync()
    if sync is None:
        return None
    try:
        return await sync.after_topup_fulfill(user_id, credits, topup_id=topup_id)
    except Exception:
        logger.exception("v3 pack mint after CutLuy top-up failed user=%s topup=%s", user_id, topup_id)
        return None
