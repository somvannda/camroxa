"""Web Music credit management API v2.

Handles credit balance queries and transaction history.
Credit consumption is service-internal only (not exposed via HTTP).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.services.v2.credit_service import CreditService

router = APIRouter(prefix="/credits", tags=["credits-v2"])


def _iso(value: object | None) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    text = str(value).strip()
    return text or None

CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


async def _get_credit_service() -> CreditService:
    raise NotImplementedError("CreditService dependency not configured.")


CreditServiceDep = Annotated[CreditService, Depends(_get_credit_service)]


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class CreditBalanceResponse(BaseModel):
    total_credits: int
    monthly_credits: int
    monthly_credits_used: int
    topup_credits: int
    daily_free_credits: int
    daily_free_limit: int
    daily_free_used: int
    has_subscription: bool
    current_period_end: str | None = None
    reset_at: str | None = None
    breakdown: dict


class CreditTransactionResponse(BaseModel):
    id: str
    wallet_id: str
    amount: int
    transaction_type: str
    description: str
    reference_id: str | None
    balance_after: int
    created_at: str


class CreditHistoryResponse(BaseModel):
    transactions: list[CreditTransactionResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/balance", response_model=CreditBalanceResponse)
async def get_balance(
    ctx: CurrentUserDep,
    service: CreditServiceDep
) -> CreditBalanceResponse:
    """Get the current user's credit balance.
    
    Returns:
    - total_credits: Total available credits (monthly + topup)
    - monthly_credits: Credits from current subscription period
    - monthly_credits_used: Credits already used this period
    - topup_credits: Credits from top-up purchases
    - breakdown: Detailed breakdown by source
    """
    import logging
    _log = logging.getLogger("platform_api.routers.v2_credits.get_balance")
    
    try:
        _log.info(f"Fetching credit balance for user: {ctx.user_id}")
        
        balance = await service.get_detailed_balance(ctx.user_id)
        _log.info(f"Balance query result: {balance}")

        _log.info(
            "Returning balance: total=%s monthly=%s topup=%s daily=%s",
            balance.total_available,
            balance.monthly_remaining,
            balance.topup_balance,
            balance.daily_free_remaining,
        )
        return CreditBalanceResponse(
            total_credits=balance.total_available,
            monthly_credits=balance.monthly_remaining,
            monthly_credits_used=balance.monthly_used,
            topup_credits=balance.topup_balance,
            daily_free_credits=balance.daily_free_remaining,
            daily_free_limit=balance.daily_free_limit,
            daily_free_used=balance.daily_free_used,
            has_subscription=balance.has_subscription,
            current_period_end=_iso(balance.current_period_end),
            reset_at=_iso(balance.reset_at),
            breakdown={
                "monthly": balance.monthly_remaining,
                "topup": balance.topup_balance,
                "daily_free": balance.daily_free_remaining,
            },
        )
    except Exception as e:
        _log.error(f"Error fetching credit balance for user {ctx.user_id}: {type(e).__name__}: {e}", exc_info=True)
        raise


@router.get("/history", response_model=CreditHistoryResponse)
async def get_history(
    ctx: CurrentUserDep,
    service: CreditServiceDep,
    limit: int = 50,
    offset: int = 0
) -> CreditHistoryResponse:
    """Get the current user's credit transaction history.
    
    Query params:
    - limit: Number of transactions to return (max 100)
    - offset: Number of transactions to skip
    """
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0
    
    transactions = await service.get_transaction_history(
        user_id=str(ctx.user_id),
        limit=limit,
        offset=offset
    )
    total = await service.get_transaction_count(str(ctx.user_id))

    return CreditHistoryResponse(
        transactions=[
            CreditTransactionResponse(
                id=str(tx.id),
                wallet_id=str(ctx.user_id),
                amount=abs(tx.amount),
                transaction_type="consume" if tx.direction == "debit" else tx.reason,
                description=tx.reason,
                reference_id=str(tx.ref_id) if tx.ref_id else None,
                balance_after=0,
                created_at=tx.created_at.isoformat()
            )
            for tx in transactions
        ],
        total=total,
        limit=limit,
        offset=offset
    )
