"""Redeem code admin and user endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.exceptions import NotFoundError
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.middleware.rate_limit import get_rate_limiter
from platform_api.services.redeem_code_service import (
    create_redeem_code,
    delete_redeem_code,
    get_redeem_code_row_by_id,
    list_redeem_codes,
    list_redeem_code_redemptions,
    list_user_redeem_code_redemptions,
    preview_redeem_code,
    redeem_credit_code,
    update_redeem_code,
)

router = APIRouter(prefix="/redeem-codes", tags=["redeem-codes"])

PoolDep = Annotated[Any, Depends(get_db_pool)]
UserDep = Annotated[AuthContext, Depends(get_current_user)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


class RedeemCodeResponse(BaseModel):
    id: str
    code: str
    description: str | None = None
    reward_type: str
    discount_amount_cents: int | None = None
    discount_percent: int | None = None
    credit_amount: int | None = None
    applicable_plan_id: str | None = None
    applicable_plan_name: str | None = None
    max_redemptions: int | None = None
    current_redemptions: int
    remaining_redemptions: int | None = None
    per_user_limit: int
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateRedeemCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    reward_type: str
    discount_amount_cents: int | None = Field(default=None, ge=1)
    discount_percent: int | None = Field(default=None, ge=1, le=100)
    credit_amount: int | None = Field(default=None, ge=1)
    applicable_plan_id: str | None = None
    max_redemptions: int | None = Field(default=None, ge=1)
    per_user_limit: int = Field(default=1, ge=1)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool = True


class UpdateRedeemCodeRequest(CreateRedeemCodeRequest):
    pass


class PreviewRedeemCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    plan_id: UUID | None = None


class RedeemCodePreviewResponse(BaseModel):
    id: str
    code: str
    description: str | None = None
    reward_type: str
    discount_amount_cents: int | None = None
    discount_percent: int | None = None
    credit_amount: int | None = None
    applicable_plan_id: str | None = None
    applicable_plan_name: str | None = None
    max_redemptions: int | None = None
    current_redemptions: int
    remaining_redemptions: int | None = None
    per_user_limit: int
    user_redemptions: int
    is_active: bool
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    applied_discount: bool
    base_amount_cents: int | None = None
    best_public_amount_cents: int | None = None
    final_amount_cents: int | None = None
    savings_cents: int | None = None
    message: str | None = None
    new_balance: int | None = None


class RedeemCodeRedeemRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)


class RedeemCodeRedemptionResponse(BaseModel):
    id: str
    redeem_code_id: str
    code: str
    description: str | None = None
    reward_type: str
    user_id: str
    user_email: str | None = None
    user_display_name: str | None = None
    billing_payment_id: str | None = None
    plan_id: str | None = None
    plan_name: str | None = None
    status: str
    amount_cents: int | None = None
    credit_amount: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class RedeemCodeRedemptionListResponse(BaseModel):
    items: list[RedeemCodeRedemptionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


def _to_response(row: Any) -> RedeemCodeResponse:
    remaining = (
        None
        if row["max_redemptions"] is None
        else max(0, int(row["max_redemptions"]) - int(row["current_redemptions"] or 0))
    )
    return RedeemCodeResponse(
        id=str(row["id"]),
        code=str(row["code"]),
        description=row["description"],
        reward_type=str(row["reward_type"]),
        discount_amount_cents=row["discount_amount_cents"],
        discount_percent=row["discount_percent"],
        credit_amount=row["credit_amount"],
        applicable_plan_id=str(row["applicable_plan_id"]) if row["applicable_plan_id"] else None,
        applicable_plan_name=None,
        max_redemptions=row["max_redemptions"],
        current_redemptions=int(row["current_redemptions"] or 0),
        remaining_redemptions=remaining,
        per_user_limit=int(row["per_user_limit"] or 1),
        starts_at=row["starts_at"],
        expires_at=row["expires_at"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_redemption_response(row: Any) -> RedeemCodeRedemptionResponse:
    metadata = row["metadata"] or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    return RedeemCodeRedemptionResponse(
        id=str(row["id"]),
        redeem_code_id=str(row["redeem_code_id"]),
        code=str(row["code"]),
        description=row["description"],
        reward_type=str(row["reward_type"]),
        user_id=str(row["user_id"]),
        user_email=row["user_email"],
        user_display_name=row["user_display_name"],
        billing_payment_id=str(row["billing_payment_id"]) if row["billing_payment_id"] else None,
        plan_id=str(row["plan_id"]) if row["plan_id"] else None,
        plan_name=None,
        status=str(row["status"]),
        amount_cents=row["amount_cents"],
        credit_amount=row["credit_amount"],
        metadata=metadata if isinstance(metadata, dict) else {},
        created_at=row["created_at"],
    )


@router.get("", response_model=list[RedeemCodeResponse], status_code=200, summary="List redeem codes (Admin)")
async def list_redeem_codes_admin(_: AdminDep, pool: PoolDep) -> list[RedeemCodeResponse]:
    rows = await list_redeem_codes(pool)
    return [_to_response(row) for row in rows]


@router.post("", response_model=RedeemCodeResponse, status_code=201, summary="Create redeem code (Admin)")
async def create_redeem_code_admin(
    request: CreateRedeemCodeRequest,
    ctx: AdminDep,
    pool: PoolDep,
) -> RedeemCodeResponse:
    row = await create_redeem_code(pool, request.model_dump(), created_by=UUID(ctx.user_id))
    return _to_response(row)


@router.put(
    "/{redeem_code_id}",
    response_model=RedeemCodeResponse,
    status_code=200,
    summary="Update redeem code (Admin)",
)
async def update_redeem_code_admin(
    redeem_code_id: UUID,
    request: UpdateRedeemCodeRequest,
    _: AdminDep,
    pool: PoolDep,
) -> RedeemCodeResponse:
    row = await update_redeem_code(pool, redeem_code_id, request.model_dump())
    return _to_response(row)


@router.delete(
    "/{redeem_code_id}",
    status_code=204,
    summary="Delete redeem code (Admin)",
)
async def delete_redeem_code_admin(redeem_code_id: UUID, _: AdminDep, pool: PoolDep) -> Response:
    await delete_redeem_code(pool, redeem_code_id)
    return Response(status_code=204)


@router.post(
    "/preview",
    response_model=RedeemCodePreviewResponse,
    status_code=200,
    summary="Preview a redeem code for pricing or wallet behavior",
)
async def preview_code(
    request: Request,
    body: PreviewRedeemCodeRequest,
    pool: PoolDep,
) -> RedeemCodePreviewResponse:
    client_ip = request.client.host if request.client else "anonymous"
    await get_rate_limiter().check_for_endpoint(f"ip:{client_ip}", "redeem_preview")

    # Plans are retired; plan-specific codes no longer resolve a plan.
    plan_id = None
    plan_row = None
    preview = await preview_redeem_code(
        pool,
        code=body.code,
        plan_id=plan_id,
        plan_price_cents=int(plan_row["price_cents"]) if plan_row is not None else None,
        public_offer_price_cents=(
            int(plan_row["offer_price_cents"])
            if plan_row is not None and plan_row["offer_price_cents"] is not None
            else None
        ),
        user_id=None,
    )
    preview["description"] = None
    preview["applicable_plan_id"] = None
    preview["applicable_plan_name"] = None
    preview["max_redemptions"] = None
    preview["current_redemptions"] = 0
    preview["remaining_redemptions"] = None
    preview["per_user_limit"] = 1
    preview["user_redemptions"] = 0
    return RedeemCodePreviewResponse(**preview)


@router.post(
    "/redeem",
    response_model=RedeemCodePreviewResponse,
    status_code=200,
    summary="Redeem a credit-grant code (User)",
)
async def redeem_code_for_user(
    request: RedeemCodeRedeemRequest,
    ctx: UserDep,
    pool: PoolDep,
) -> RedeemCodePreviewResponse:
    result = await redeem_credit_code(pool, code=request.code, user_id=UUID(ctx.user_id))
    from platform_api.services.abuse_alert_service import maybe_note_redeem

    await maybe_note_redeem(user_id=ctx.user_id)
    return RedeemCodePreviewResponse(**result)


@router.get(
    "/redemptions",
    response_model=RedeemCodeRedemptionListResponse,
    status_code=200,
    summary="List redeem-code redemptions (Admin)",
)
async def list_redeem_code_redemptions_admin(
    _: AdminDep,
    pool: PoolDep,
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=25, ge=1, le=100, description="Entries per page"),
    code: str | None = Query(default=None, description="Filter by redeem code"),
    reward_type: str | None = Query(default=None, description="Filter by reward type"),
    status: str | None = Query(default=None, description="Filter by redemption status"),
) -> RedeemCodeRedemptionListResponse:
    rows, total = await list_redeem_code_redemptions(
        pool,
        page=page,
        page_size=page_size,
        code=code,
        reward_type=reward_type,
        status=status,
    )
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    return RedeemCodeRedemptionListResponse(
        items=[_to_redemption_response(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/my-redemptions",
    response_model=list[RedeemCodeRedemptionResponse],
    status_code=200,
    summary="List my recent redeem-code history (User)",
)
async def list_my_redeem_code_redemptions(
    ctx: UserDep,
    pool: PoolDep,
    limit: int = Query(default=10, ge=1, le=50, description="Number of recent items to return"),
) -> list[RedeemCodeRedemptionResponse]:
    rows = await list_user_redeem_code_redemptions(pool, user_id=UUID(ctx.user_id), limit=limit)
    return [_to_redemption_response(row) for row in rows]


@router.get(
    "/{redeem_code_id}",
    response_model=RedeemCodeResponse,
    status_code=200,
    summary="Get redeem code (Admin)",
)
async def get_redeem_code_admin(redeem_code_id: UUID, _: AdminDep, pool: PoolDep) -> RedeemCodeResponse:
    row = await get_redeem_code_row_by_id(pool, redeem_code_id)
    if row is None:
        raise NotFoundError("Redeem code not found.", details={"redeem_code_id": str(redeem_code_id)})
    return _to_response(row)
