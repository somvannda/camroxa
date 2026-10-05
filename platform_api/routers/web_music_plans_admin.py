"""Admin endpoints for web music subscription plans and top-up packs."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.repositories.credit_repo import CreditRepository
from platform_api.repositories.license_repo import PlanRepository
from platform_api.services.plan_credits import validate_credit_cadence
from platform_api.services.pricing_display import credits_to_songs

router = APIRouter(prefix="/web-music", tags=["web-music-plans-admin"])

AdminDep = Annotated[AuthContext, Depends(require_admin)]


async def _get_plan_repo() -> PlanRepository:
    raise NotImplementedError("PlanRepository dependency not configured.")


async def _get_credit_repo() -> CreditRepository:
    raise NotImplementedError("CreditRepository dependency not configured.")


PlanRepoDep = Annotated[PlanRepository, Depends(_get_plan_repo)]
CreditRepoDep = Annotated[CreditRepository, Depends(_get_credit_repo)]


class WebMusicPlanFeatures(BaseModel):
    music: bool = True
    images: bool = False
    topup: bool = True


class WebMusicPlanResponse(BaseModel):
    id: str
    name: str
    price_cents: int
    billing_cycle_days: int
    monthly_credits: int
    features: WebMusicPlanFeatures
    is_public: bool
    display_order: int
    is_active: bool
    subscriber_count: int = 0
    can_delete: bool = False
    created_at: str
    updated_at: str


class CreateWebMusicPlanRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    price_cents: int = Field(..., ge=0)
    billing_cycle_days: int = Field(..., ge=1, description="30 = monthly, 365 = yearly")
    monthly_credits: int = Field(..., ge=1, le=1_000_000)
    features: WebMusicPlanFeatures = Field(default_factory=WebMusicPlanFeatures)
    is_public: bool = True
    display_order: int = Field(default=0, ge=0, le=100)


class UpdateWebMusicPlanRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    price_cents: int | None = Field(default=None, ge=0)
    billing_cycle_days: int | None = Field(default=None, ge=1)
    monthly_credits: int | None = Field(default=None, ge=1, le=1_000_000)
    features: WebMusicPlanFeatures | None = None
    is_public: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


class WebMusicTopupPackResponse(BaseModel):
    id: str
    slug: str
    name: str
    total_credits: int
    price_cents: int
    display_order: int
    is_active: bool
    songs_equivalent: int
    created_at: str
    updated_at: str


class CreateWebMusicTopupPackRequest(BaseModel):
    slug: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    total_credits: int = Field(..., ge=10, le=1_000_000)
    price_cents: int = Field(..., ge=0)
    display_order: int = Field(default=0, ge=0, le=100)
    is_active: bool = True


class UpdateWebMusicTopupPackRequest(BaseModel):
    slug: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    total_credits: int | None = Field(default=None, ge=10, le=1_000_000)
    price_cents: int | None = Field(default=None, ge=0)
    display_order: int | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,48}[a-z0-9]$")


def _features_from_plan(plan: Any) -> WebMusicPlanFeatures:
    raw = getattr(plan, "features", None) or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return WebMusicPlanFeatures(
        music=bool(raw.get("music", True)),
        images=bool(raw.get("images", False)),
        topup=bool(raw.get("topup", True)),
    )


def _plan_to_response(plan: Any, *, subscriber_count: int = 0) -> WebMusicPlanResponse:
    return WebMusicPlanResponse(
        id=str(plan.id),
        name=plan.name,
        price_cents=plan.price_cents,
        billing_cycle_days=int(plan.billing_cycle_days or 30),
        monthly_credits=int(plan.monthly_credits or 0),
        features=_features_from_plan(plan),
        is_public=bool(getattr(plan, "is_public", False)),
        display_order=int(getattr(plan, "display_order", 0) or 0),
        is_active=plan.is_active,
        subscriber_count=subscriber_count,
        can_delete=subscriber_count == 0,
        created_at=plan.created_at.isoformat(),
        updated_at=plan.updated_at.isoformat(),
    )


def _pack_to_response(row: dict[str, Any]) -> WebMusicTopupPackResponse:
    credits = int(row.get("total_credits") or 0)
    return WebMusicTopupPackResponse(
        id=str(row["id"]),
        slug=str(row.get("slug") or ""),
        name=str(row["name"]),
        total_credits=credits,
        price_cents=int(row["price_cents"]),
        display_order=int(row.get("display_order") or 0),
        is_active=bool(row.get("is_active")),
        songs_equivalent=credits_to_songs(credits),
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


def _validate_slug(slug: str) -> str:
    normalized = slug.strip().lower()
    if not _SLUG_RE.match(normalized):
        raise ValidationError(
            message="Slug must be 2-50 lowercase letters, numbers, hyphens, or underscores.",
            details={"slug": slug},
        )
    return normalized


async def _get_web_music_plan(plan_repo: PlanRepository, plan_id: UUID) -> Any:
    plan = await plan_repo.get_by_id(plan_id)
    if plan is None or str(getattr(plan, "plan_type", "desktop_pro")) != "web_music":
        raise NotFoundError(message="Web music plan not found.", details={"plan_id": str(plan_id)})
    return plan


@router.get(
    "/plans",
    response_model=list[WebMusicPlanResponse],
    summary="List web music subscription plans (Admin)",
)
async def list_web_music_plans(
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> list[WebMusicPlanResponse]:
    plans = await plan_repo.get_by_plan_type("web_music")
    counts = await plan_repo.get_web_music_subscriber_counts([p.id for p in plans])
    return [
        _plan_to_response(plan, subscriber_count=counts.get(plan.id, 0))
        for plan in plans
    ]


@router.post(
    "/plans",
    response_model=WebMusicPlanResponse,
    status_code=201,
    summary="Create web music subscription plan (Admin)",
)
async def create_web_music_plan(
    request: CreateWebMusicPlanRequest,
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> WebMusicPlanResponse:
    existing = await plan_repo.get_by_name(request.name.strip())
    if existing is not None:
        raise ValidationError(
            message="A plan with this name already exists.",
            details={"name": request.name},
        )
    validate_credit_cadence(monthly_credits=request.monthly_credits, daily_credits=0)

    plan = await plan_repo.create_web_music(
        name=request.name.strip(),
        price_cents=request.price_cents,
        billing_cycle_days=request.billing_cycle_days,
        monthly_credits=request.monthly_credits,
        features=request.features.model_dump(),
        is_public=request.is_public,
        display_order=request.display_order,
    )
    return _plan_to_response(plan, subscriber_count=0)


@router.patch(
    "/plans/{plan_id}",
    response_model=WebMusicPlanResponse,
    summary="Update web music subscription plan (Admin)",
)
async def update_web_music_plan(
    plan_id: UUID,
    request: UpdateWebMusicPlanRequest,
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> WebMusicPlanResponse:
    existing = await _get_web_music_plan(plan_repo, plan_id)

    fields: dict[str, Any] = {}
    if request.name is not None:
        fields["name"] = request.name.strip()
    if request.price_cents is not None:
        fields["price_cents"] = request.price_cents
    if request.billing_cycle_days is not None:
        fields["billing_cycle_days"] = request.billing_cycle_days
    if request.monthly_credits is not None:
        fields["monthly_credits"] = request.monthly_credits
    validate_credit_cadence(
        monthly_credits=(
            request.monthly_credits
            if request.monthly_credits is not None
            else getattr(existing, "monthly_credits", 0)
        ),
        daily_credits=getattr(existing, "daily_credits", 0),
    )
    if request.features is not None:
        fields["features"] = json.dumps(request.features.model_dump())
    if request.is_public is not None:
        fields["is_public"] = request.is_public
    if request.display_order is not None:
        fields["display_order"] = request.display_order
    if request.is_active is not None:
        fields["is_active"] = request.is_active

    if not fields:
        raise ValidationError(message="No fields provided for update.")

    updated = await plan_repo.update(plan_id, **fields)
    if updated is None:
        raise NotFoundError(message="Web music plan not found.", details={"plan_id": str(plan_id)})

    counts = await plan_repo.get_web_music_subscriber_counts([plan_id])
    return _plan_to_response(updated, subscriber_count=counts.get(plan_id, 0))


@router.delete(
    "/plans/{plan_id}",
    status_code=204,
    summary="Delete web music subscription plan (Admin)",
)
async def delete_web_music_plan(
    plan_id: UUID,
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> Response:
    deleted = await plan_repo.delete_web_music_if_no_subscribers(plan_id)
    if not deleted:
        raise NotFoundError(message="Web music plan not found.", details={"plan_id": str(plan_id)})
    return Response(status_code=204)


@router.get(
    "/topups",
    response_model=list[WebMusicTopupPackResponse],
    summary="List web music top-up packs (Admin)",
)
async def list_web_music_topups(
    ctx: AdminDep,
    credit_repo: CreditRepoDep,
) -> list[WebMusicTopupPackResponse]:
    rows = await credit_repo.get_packs_by_type("web_music", include_inactive=True)
    return [_pack_to_response(row) for row in rows]


@router.post(
    "/topups",
    response_model=WebMusicTopupPackResponse,
    status_code=201,
    summary="Create web music top-up pack (Admin)",
)
async def create_web_music_topup(
    request: CreateWebMusicTopupPackRequest,
    ctx: AdminDep,
    credit_repo: CreditRepoDep,
) -> WebMusicTopupPackResponse:
    slug = _validate_slug(request.slug)
    row = await credit_repo.create_web_music_pack(
        slug=slug,
        name=request.name.strip(),
        total_credits=request.total_credits,
        price_cents=request.price_cents,
        display_order=request.display_order,
        is_active=request.is_active,
    )
    return _pack_to_response(row)


@router.patch(
    "/topups/{pack_id}",
    response_model=WebMusicTopupPackResponse,
    summary="Update web music top-up pack (Admin)",
)
async def update_web_music_topup(
    pack_id: UUID,
    request: UpdateWebMusicTopupPackRequest,
    ctx: AdminDep,
    credit_repo: CreditRepoDep,
) -> WebMusicTopupPackResponse:
    slug = _validate_slug(request.slug) if request.slug is not None else None
    row = await credit_repo.update_web_music_pack(
        pack_id,
        slug=slug,
        name=request.name.strip() if request.name is not None else None,
        total_credits=request.total_credits,
        price_cents=request.price_cents,
        display_order=request.display_order,
        is_active=request.is_active,
    )
    if row is None:
        raise NotFoundError(message="Web music top-up pack not found.", details={"pack_id": str(pack_id)})
    return _pack_to_response(row)


@router.delete(
    "/topups/{pack_id}",
    status_code=204,
    summary="Delete web music top-up pack (Admin)",
)
async def delete_web_music_topup(
    pack_id: UUID,
    ctx: AdminDep,
    credit_repo: CreditRepoDep,
) -> Response:
    deleted = await credit_repo.delete_web_music_pack(pack_id)
    if not deleted:
        raise NotFoundError(message="Web music top-up pack not found.", details={"pack_id": str(pack_id)})
    return Response(status_code=204)
