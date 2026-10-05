"""Credits-only API v3 — same billing tables as /api/v1, new charge model."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from platform_api.dependencies import (
    get_v3_billing_service,
    get_v3_conversion_service,
    get_v3_grant_service,
    get_v3_store,
    get_v3_web_ledger_service,
)
from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.services.plan_credits import validate_credit_cadence
from platform_api.services.pricing_display import normalize_pricing_features
from platform_api.services.v3.ops import PATCHABLE_PLAN_FIELDS, SUPPORTED_OPS

router = APIRouter(tags=["credits-only-v3"])
docs_router = APIRouter(tags=["credits-only-v3"])

AdminDep = Annotated[AuthContext, Depends(require_admin)]
UserDep = Annotated[AuthContext, Depends(get_current_user)]
BillingDep = Annotated[Any, Depends(get_v3_billing_service)]
GrantDep = Annotated[Any, Depends(get_v3_grant_service)]
ConversionDep = Annotated[Any, Depends(get_v3_conversion_service)]
WebLedgerDep = Annotated[Any, Depends(get_v3_web_ledger_service)]
StoreDep = Annotated[Any, Depends(get_v3_store)]


class QuoteRequest(BaseModel):
    op: str
    user_id: UUID | None = None
    plan_id: UUID | None = None
    waive: bool = False


class ChargeRequest(BaseModel):
    op: str
    user_id: UUID | None = None
    plan_id: UUID | None = None
    ref_id: str | None = None
    waive: bool = False


class RefundRequest(BaseModel):
    op: str
    user_id: UUID | None = None
    amount_credits: float | None = None
    ref_id: str | None = None
    absorb: bool = False


class PlanPatchRequest(BaseModel):
    monthly_credits: int | None = Field(default=None, ge=0)
    daily_credits: int | None = Field(default=None, ge=0)
    is_public: bool | None = None
    is_active: bool | None = None
    pricing_features: list[str] | None = None
    pricing_credit_lines: list[str] | None = None
    lyric_credits: int | None = Field(default=None, ge=0)
    title_credits: int | None = Field(default=None, ge=0)
    album_credits: int | None = Field(default=None, ge=0)
    music_credits: int | None = Field(default=None, ge=0)
    style_credits: int | None = Field(default=None, ge=0)
    image_credits: int | None = Field(default=None, ge=0)
    video_credits: int | None = Field(default=None, ge=0)
    merge_credits: int | None = Field(default=None, ge=0)


class ConversionRequest(BaseModel):
    user_ids: list[UUID] | None = None
    confirm: bool = False


@docs_router.get("/docs", include_in_schema=False)
async def v3_docs() -> HTMLResponse:
    return get_swagger_ui_html(openapi_url="/api/v3/openapi.json", title="Credits-only API v3")


@router.get("/plans", summary="Admin list of the same plans v1 uses")
async def list_plans(ctx: AdminDep, store: StoreDep) -> list[dict[str, Any]]:
    return await store.list_plans()


@router.get("/plans/public", summary="Active and public plans only")
async def list_public_plans(store: StoreDep, billing: BillingDep) -> list[dict[str, Any]]:
    op_credits = await billing.op_list_credits()
    rate = await billing.music_credits_per_generate()
    plans = await store.list_public_plans(credits_per_generate=rate)
    return [billing.apply_list_prices(plan, op_credits, overlay_ops=True) for plan in plans]


@router.get("/admin/plans", summary="List all plans including v3 grant / per-op fields")
async def list_admin_plans(ctx: AdminDep, store: StoreDep) -> list[dict[str, Any]]:
    return await store.list_plans()


@router.get("/admin/plans/{plan_id}", summary="Get one plan including v3 grant fields")
async def get_admin_plan(plan_id: UUID, ctx: AdminDep, store: StoreDep) -> dict[str, Any]:
    plan = await store.get_plan(plan_id)
    if plan is None:
        raise NotFoundError("Plan not found.", details={"plan_id": str(plan_id)})
    return plan


@router.patch("/admin/plans/{plan_id}", summary="Set monthly credits / per-op / public on an existing plan")
async def patch_admin_plan(
    plan_id: UUID,
    body: PlanPatchRequest,
    ctx: AdminDep,
    store: StoreDep,
) -> dict[str, Any]:
    fields = body.model_dump(exclude_unset=True)
    unknown = set(fields) - PATCHABLE_PLAN_FIELDS
    if unknown:
        raise ValidationError("Unsupported plan fields.", details={"fields": sorted(unknown)})
    current = await store.get_plan(plan_id)
    if current is None:
        raise NotFoundError("Plan not found.", details={"plan_id": str(plan_id)})
    if "pricing_features" in fields:
        fields["pricing_features"] = normalize_pricing_features(fields.get("pricing_features"))
    if "pricing_credit_lines" in fields:
        fields["pricing_credit_lines"] = normalize_pricing_features(fields.get("pricing_credit_lines"))
    validate_credit_cadence(
        monthly_credits=fields.get("monthly_credits", current.get("monthly_credits")),
        daily_credits=fields.get("daily_credits", current.get("daily_credits")),
    )
    plan = await store.patch_plan(plan_id, fields)
    if plan is None:
        raise NotFoundError("Plan not found.", details={"plan_id": str(plan_id)})
    return plan


@router.get("/credits/pricing", summary="Read-through of Admin Credits page pricing")
async def list_pricing(ctx: AdminDep, billing: BillingDep) -> list[dict[str, Any]]:
    return await billing.list_pricing()


@router.get("/me/credits", summary="Current user wallet (same credit_wallets as v1)")
async def me_credits(ctx: UserDep, billing: BillingDep) -> dict[str, Any]:
    # Read-only: grant minting runs on billing events + the grant-maintenance
    # scheduler, never on a GET.
    user_id = UUID(ctx.user_id)
    return await billing.wallet_view(user_id)


@router.get("/users/{user_id}/credits", summary="Admin view of a user wallet")
async def user_credits(user_id: UUID, ctx: AdminDep, billing: BillingDep, grants: GrantDep) -> dict[str, Any]:
    await grants.expire_unused_grants(user_id)
    return await billing.wallet_view(user_id)


@router.post("/billing/quote", summary="Credits for an op from the Credits page list price")
async def quote(body: QuoteRequest, ctx: UserDep, billing: BillingDep) -> dict[str, Any]:
    target = body.user_id
    if ctx.role != "admin" or target is None:
        target = UUID(ctx.user_id)
    result = await billing.quote(
        op=body.op,
        user_id=target,
        plan_id=body.plan_id,
        waive=body.waive,
    )
    return result.to_dict()


@router.post("/billing/charge", summary="Debit the shared wallet")
async def charge(body: ChargeRequest, ctx: UserDep, billing: BillingDep) -> dict[str, Any]:
    target = body.user_id
    if ctx.role != "admin" or target is None:
        target = UUID(ctx.user_id)
    return await billing.charge(
        user_id=target,
        op=body.op,
        ref_id=body.ref_id,
        waive=body.waive,
        plan_id=body.plan_id,
    )


@router.post("/billing/refund", summary="Refund the shared wallet; optional fail-absorb")
async def refund(body: RefundRequest, ctx: AdminDep, billing: BillingDep) -> dict[str, Any]:
    # Refunding credits is an operator action: a non-admin could otherwise mint
    # arbitrary amounts. User-facing failed-operation refunds go through the
    # operation-specific endpoints, which derive the amount from the charge.
    target = body.user_id or UUID(ctx.user_id)
    return await billing.refund(
        user_id=target,
        op=body.op,
        amount_credits=body.amount_credits,
        ref_id=body.ref_id,
        absorb=body.absorb,
    )


@router.post("/admin/billing/grant-period", summary="Issue this period's plan grant if missing")
async def grant_period(ctx: AdminDep, grants: GrantDep, user_id: UUID) -> dict[str, Any]:
    return await grants.ensure_period_grant(user_id)


@router.post("/admin/billing/conversion/dry-run", summary="Preview leftover packages x 10")
async def conversion_dry_run(
    ctx: AdminDep,
    conversion: ConversionDep,
    body: ConversionRequest | None = None,
) -> dict[str, Any]:
    rows = await conversion.dry_run(body.user_ids if body else None)
    return {"rows": rows, "ops": list(SUPPORTED_OPS)}


@router.post("/admin/billing/conversion/apply", summary="Mint leftover credits (confirm required)")
async def conversion_apply(
    ctx: AdminDep,
    conversion: ConversionDep,
    body: ConversionRequest,
) -> dict[str, Any]:
    rows = await conversion.apply(body.user_ids, confirm=body.confirm)
    return {"rows": rows}


@router.post("/admin/billing/web-ledger/dry-run", summary="Preview leftover CutLuy web credits")
async def web_ledger_dry_run(
    ctx: AdminDep,
    ledger: WebLedgerDep,
    body: ConversionRequest | None = None,
) -> dict[str, Any]:
    rows = await ledger.dry_run(body.user_ids if body else None)
    return {"rows": rows}


@router.post("/admin/billing/web-ledger/apply", summary="Mint leftover CutLuy web credits (confirm required)")
async def web_ledger_apply(
    ctx: AdminDep,
    ledger: WebLedgerDep,
    body: ConversionRequest,
) -> dict[str, Any]:
    rows = await ledger.apply(body.user_ids, confirm=body.confirm)
    return {"rows": rows}
