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
async def get_balance(ctx: CurrentUserDep) -> CreditBalanceResponse:
    """Credits-only wallet balance (legacy v2 shape)."""
    from uuid import UUID

    from platform_api.dependencies import get_v3_billing_service

    view = await get_v3_billing_service().wallet_view(UUID(ctx.user_id))
    total = int(round(float(view.get("balance_credits") or 0)))
    is_pro = bool(view.get("is_pro"))
    return CreditBalanceResponse(
        total_credits=total,
        monthly_credits=0,
        monthly_credits_used=0,
        topup_credits=total,
        daily_free_credits=0,
        daily_free_limit=0,
        daily_free_used=0,
        has_subscription=is_pro,
        current_period_end=view.get("pack_expires_at"),
        reset_at=None,
        breakdown={"monthly": 0, "topup": total, "daily_free": 0},
    )


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
