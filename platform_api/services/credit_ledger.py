"""Single typed entry point for credit movements.

Wraps :class:`CreditRepository` so grant/deduct/refund all flow through one named,
typed API. Grant reasons that come from an entitlement use :class:`GrantType`;
dynamic/admin reasons may still be passed as a plain string. The underlying
``CreditRepository`` remains the low-level writer and now requires an idempotency
claim for grants with a stable ``ref_id`` (see migration 133).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID


class GrantType(StrEnum):
    """Known entitlement grant reasons."""

    PERIOD = "v3_period_grant"
    DAILY = "v3_daily_grant"
    PACK = "v3_pack"
    QUOTA_CONVERSION = "v3_quota_conversion"
    WEB_REMAINING = "v3_web_remaining"
    PLAN_PURCHASE = "plan_purchase"
    REDEEM = "redeem_code_credit"
    ADMIN = "admin_adjustment"


class _CreditRepo(Protocol):
    async def add_credits(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
        pack_id: UUID | None = None,
        payment_ref: str | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        idempotent: bool = True,
    ) -> int: ...

    async def atomic_deduct(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool: ...

    async def refund(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int: ...


def _reason(grant_type: GrantType | str) -> str:
    return grant_type.value if isinstance(grant_type, GrantType) else str(grant_type)


class CreditLedger:
    """The one place credits are granted, deducted, or refunded."""

    def __init__(self, repo: _CreditRepo) -> None:
        self._repo = repo

    async def grant(
        self,
        user_id: UUID,
        amount_units: int,
        *,
        grant_type: GrantType | str,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        pack_id: UUID | None = None,
        payment_ref: str | None = None,
        idempotent: bool = True,
    ) -> int:
        """Grant credits for an entitlement. Idempotent per (user, reason, ref)."""
        return await self._repo.add_credits(
            user_id,
            amount_units,
            _reason(grant_type),
            ref_id=ref_id,
            pack_id=pack_id,
            payment_ref=payment_ref,
            metadata=metadata,
            idempotent=idempotent,
        )

    async def deduct(
        self,
        user_id: UUID,
        amount_units: int,
        *,
        reason: str,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Spend credits (atomic; False when the balance is insufficient)."""
        return await self._repo.atomic_deduct(
            user_id, amount_units, reason, ref_id=ref_id, metadata=metadata
        )

    async def refund(
        self,
        user_id: UUID,
        amount_units: int,
        *,
        reason: str,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Reverse a specific debit (idempotent per refund key)."""
        return await self._repo.refund(
            user_id, amount_units, reason, ref_id=ref_id, metadata=metadata
        )
