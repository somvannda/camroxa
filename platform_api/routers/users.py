"""Users router endpoints.

Provides user profile management (GET/PATCH /users/me) and admin-only
user administration (listing, updating, suspending, reactivating, deleting).

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.http_paths import canonical_api_path
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.services.user_service import UserService
from platform_api.services.credit_units import units_to_credits
from platform_api.utils.upload_paths import resolve_upload_path, uploads_root, upload_path_exists

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

_PASSWORD_UPPER_RE = re.compile(r"[A-Z]")
_PASSWORD_LOWER_RE = re.compile(r"[a-z]")
_PASSWORD_DIGIT_RE = re.compile(r"\d")


class UserProfileResponse(BaseModel):
    """Public user profile information (never includes password_hash)."""

    id: str
    email: str
    email_confirmed: bool = False
    display_name: str
    avatar_url: str | None = None
    role: str
    status: str
    suspension_reason: str | None = None
    credit_balance: float = 0
    plan_name: str | None = None
    music_credits_remaining: int | None = None
    music_credits_limit: int | None = None
    credits_burned: float | None = None
    profile_allowance: int | None = None
    profile_addon_slots: int = 0
    profile_addon_pending: int = 0
    effective_profile_allowance: int | None = None
    effective_quota_channels: int | None = None
    channel_profile_count: int = 0
    onboarding_paid: bool = False
    desktop_access: bool = False
    products: list[str] = Field(default_factory=list)
    pending_verification_code: str | None = None
    verification_code_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ChannelProfileAdminSummary(BaseModel):
    id: str
    name: str
    folder_name: str | None = None
    run_prefix: str | None = None
    created_at: datetime | None = None
    logo_available: bool = False
    cover_count: int = 0
    output_resolution: str | None = None
    video_template_id: str | None = None
    reel_template_id: str | None = None
    video_template_name: str | None = None
    video_template_updated_at: datetime | None = None
    video_template_available: bool = False
    reel_template_name: str | None = None
    reel_template_updated_at: datetime | None = None
    reel_template_available: bool = False
    genre: str | None = None
    role: str | None = None
    description: str | None = None
    visibility: str | None = None
    publish_at: str | None = None
    made_for_kids: bool = False
    ai_use: bool = False
    category: str | None = None
    playlist: str | None = None
    title_template: str | None = None
    description_template: str | None = None
    keywords: list[str] = []
    tags: list[str] = []


class UserOwnedPromptSummary(BaseModel):
    id: str
    name: str
    content: str
    usage_count: int = 0
    created_at: datetime
    updated_at: datetime


class UserFullDetailResponse(BaseModel):
    """Comprehensive user detail for admin detail page."""

    # Basic info
    id: str
    email: str
    display_name: str
    role: str
    status: str
    suspension_reason: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    # Credits
    credit_balance: float = 0
    total_credits_spent: float = 0
    music_credits_remaining: int | None = None
    music_credits_limit: int | None = None
    credits_burned: float | None = None
    recent_transactions: list[dict] = []

    # Plan/License
    plan_name: str | None = None
    plan_id: str | None = None
    license_status: str | None = None
    license_activated_at: datetime | None = None
    license_expires_at: datetime | None = None

    # Profiles
    channel_profiles: list[ChannelProfileAdminSummary] = []

    # Usage stats
    total_songs_generated: int = 0
    total_images_generated: int = 0

    # Current billing-period quota snapshot (admin top-up surface)
    quota_period: dict[str, Any] | None = None

    # User-owned prompts
    custom_descriptions: list[UserOwnedPromptSummary] = []
    custom_structures: list[UserOwnedPromptSummary] = []

    # Music-web generation freeze (Redis TTL, not a DB status)
    generation_frozen: bool = False
    generation_frozen_reason: str | None = None
    generation_frozen_hours: int | None = None
    generation_frozen_retry_after: int = 0


class QuotaTopupRequest(BaseModel):
    """Admin request to bump a user's period quota limit."""

    quota_kind: str = Field(
        ...,
        description="draft | music | image | video | merge (aliases: drafts, songs, images, videos, merges)",
    )
    amount: int = Field(..., gt=0, description="Extra period units to add")
    reason: str = Field(..., min_length=1, max_length=500)


class QuotaKindStatusResponse(BaseModel):
    quota_kind: str
    base_limit: int | None = None
    topup_extra: int = 0
    effective_limit: int | None = None
    used: int = 0
    remaining: int | None = None


class AdminQuotaPeriodResponse(BaseModel):
    """Admin view of current billing-period quotas + top-ups."""

    user_id: str
    period_start: str | None = None
    period_end: str | None = None
    plan_name: str | None = None
    wallet_balance: float = 0
    kinds: dict[str, QuotaKindStatusResponse] = {}


class QuotaTopupResponse(BaseModel):
    id: str
    user_id: str
    quota_kind: str
    amount: int
    reason: str
    period_start: str
    period_end: str
    base_limit: int
    topup_extra: int
    effective_limit: int
    used: int
    remaining: int
    quota_period: AdminQuotaPeriodResponse | None = None


class PaginatedUsersResponse(BaseModel):
    """Paginated list of users for admin endpoints."""

    users: list[UserProfileResponse]
    total: int
    page: int
    page_size: int


class UpdateSelfRequest(BaseModel):
    """Request body for a user updating their own profile."""

    display_name: str | None = Field(default=None, min_length=2, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class AdminUpdateUserRequest(BaseModel):
    """Request body for an admin updating a user's record."""

    display_name: str | None = Field(default=None, min_length=2, max_length=50)
    role: str | None = Field(default=None, pattern=r"^(user|admin)$")


class SuspendRequest(BaseModel):
    """Request body for suspending a user."""

    reason: str = Field(..., min_length=1, max_length=500)


class FreezeGenerationRequest(BaseModel):
    """Admin timed freeze of music-web generation."""

    hours: int = Field(..., description="1, 6, 24, or 72")
    reason: str = Field(..., min_length=1, max_length=500)


class AdminSetPasswordRequest(BaseModel):
    """Admin sets a new password for a target user."""

    password: str = Field(..., min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Placeholder Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_user_service() -> UserService:
    """Placeholder dependency for UserService â€” override in tests or dependencies.py."""
    raise NotImplementedError(
        "UserService dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases for dependency injection
UserServiceDep = Annotated[UserService, Depends(_get_user_service)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]
AdminUserDep = Annotated[AuthContext, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _fetch_avatar_url(pool, user_id: UUID) -> str | None:
    row = await _fetch_optional_row(pool, "SELECT avatar_url FROM users WHERE id = $1", user_id)
    if not row:
        return None
    raw = str(row.get("avatar_url") or "").strip()
    if not raw:
        return None
    return canonical_api_path(f"media/users/{user_id}/avatar")




def _save_user_avatar(*, user_id: UUID, data: bytes, content_type: str) -> str:
    ext = ".jpg"
    lowered = str(content_type or "").lower()
    if "png" in lowered:
        ext = ".png"
    elif "webp" in lowered:
        ext = ".webp"
    avatar_dir = (uploads_root() / "avatars").resolve()
    avatar_dir.mkdir(parents=True, exist_ok=True)
    avatar_path = avatar_dir / f"{user_id}{ext}"
    avatar_path.write_bytes(data)
    return str(Path("uploads") / "avatars" / f"{user_id}{ext}")


MUSIC_WEB_PRODUCT = "music_web"


async def _fetch_optional_rows(pool, query: str, *args):
    """Fetch rows, treating a missing table/column as an empty result."""
    try:
        return await pool.fetch(query, *args)
    except Exception as exc:
        message = str(exc).lower()
        if "does not exist" in message or "undefined" in message:
            return []
        raise


async def _fetch_optional_row(pool, query: str, *args):
    """Fetch one row, treating a missing table/column as None."""
    try:
        return await pool.fetchrow(query, *args)
    except Exception as exc:
        message = str(exc).lower()
        if "does not exist" in message or "undefined" in message:
            return None
        raise


def _is_music_web_user(products: list[str] | None) -> bool:
    return MUSIC_WEB_PRODUCT in {str(item).strip() for item in (products or [])}


def _paid_music_credit_fields(
    music_row: dict[str, Any],
    purchased: int,
) -> tuple[int, int, float, str | None]:
    granted = int(music_row["granted"] or 0)
    used = int(music_row["used"] or 0)
    topup = int(music_row["topup"] or 0)
    monthly_remaining = max(0, granted - used)
    remaining = monthly_remaining + max(0, topup)
    limit = max(remaining, granted + max(topup, purchased), 1)
    burned = float(used + max(0, purchased - topup))
    plan_name = music_row.get("plan_name")
    return remaining, limit, burned, str(plan_name) if plan_name else None


def _studio_credits_burned(units: int | None) -> float:
    """Debit rows are stored as signed micro-units; never show negative burn."""
    return units_to_credits(abs(int(units or 0)))


def _user_to_response(
    user,
    credit_balance: int | float = 0,
    plan_name: str | None = None,
    avatar_url: str | None = None,
    profile_allowance: int | None = None,
    profile_addon_slots: int = 0,
    profile_addon_pending: int = 0,
    effective_profile_allowance: int | None = None,
    effective_quota_channels: int | None = None,
    channel_profile_count: int = 0,
    onboarding_paid: bool = False,
    desktop_access: bool = False,
    products: list[str] | None = None,
    music_credits_remaining: int | None = None,
    music_credits_limit: int | None = None,
    credits_burned: float | None = None,
    pending_verification_code: str | None = None,
    verification_code_expires_at: datetime | None = None,
) -> UserProfileResponse:
    """Convert a domain User object to the response model."""
    balance_display = (
        units_to_credits(int(credit_balance))
        if isinstance(credit_balance, int)
        else float(credit_balance)
    )
    return UserProfileResponse(
        id=str(user.id),
        email=user.email,
        email_confirmed=bool(getattr(user, "email_confirmed", False)),
        display_name=user.display_name,
        avatar_url=avatar_url,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        status=user.status.value if hasattr(user.status, "value") else str(user.status),
        suspension_reason=getattr(user, "suspension_reason", None),
        credit_balance=balance_display,
        plan_name=plan_name,
        music_credits_remaining=music_credits_remaining,
        music_credits_limit=music_credits_limit,
        credits_burned=credits_burned,
        profile_allowance=profile_allowance,
        profile_addon_slots=profile_addon_slots,
        profile_addon_pending=profile_addon_pending,
        effective_profile_allowance=effective_profile_allowance,
        effective_quota_channels=effective_quota_channels,
        channel_profile_count=channel_profile_count,
        onboarding_paid=onboarding_paid,
        desktop_access=desktop_access,
        products=list(products or getattr(user, "products", None) or []),
        pending_verification_code=pending_verification_code,
        verification_code_expires_at=verification_code_expires_at,
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
    )


# ---------------------------------------------------------------------------
# User Endpoints (authenticated user)
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=200,
    summary="Get current user profile",
)
async def get_me(
    ctx: CurrentUserDep,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Return the authenticated user's profile information.

    Requirement 3 context: Users can view their own account details.
    """
    user = await user_service.get_user(UUID(ctx.user_id))
    pool = get_db_pool()
    user_id = UUID(ctx.user_id)

    balance_row = await pool.fetchrow(
        "SELECT balance FROM credit_wallets WHERE user_id = $1",
        user_id,
    )
    credit_balance = int(balance_row["balance"] or 0) if balance_row else 0

    profile_allowance = None
    profile_addon_slots = 0
    profile_addon_pending = 0
    effective_quota_channels = None
    effective_profile_allowance = None

    profile_row = await pool.fetchrow(
        "SELECT COUNT(*)::int AS cnt FROM channel_profiles WHERE user_id = $1",
        user_id,
    )
    channel_profile_count = int(profile_row["cnt"] or 0) if profile_row else 0

    from platform_api.repositories.license_repo import LicenseRepository

    desktop_access = await LicenseRepository(pool=pool).has_paid_desktop_access(str(user_id))
    plan_name = "Pro" if desktop_access else "Free"
    onboarding_paid = desktop_access
    avatar_url = await _fetch_avatar_url(pool, user_id)

    return _user_to_response(
        user,
        credit_balance=credit_balance,
        plan_name=plan_name,
        avatar_url=avatar_url,
        profile_allowance=profile_allowance,
        profile_addon_slots=profile_addon_slots,
        profile_addon_pending=profile_addon_pending,
        effective_profile_allowance=effective_profile_allowance,
        effective_quota_channels=effective_quota_channels,
        channel_profile_count=channel_profile_count,
        onboarding_paid=onboarding_paid,
        desktop_access=desktop_access,
    )


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    status_code=200,
    summary="Update current user profile",
)
async def update_me(
    request: UpdateSelfRequest,
    ctx: CurrentUserDep,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Update the authenticated user's display_name or password.

    Requirement 2.6: When a User updates their display name or password,
    the Platform_API validates and persists the change.
    """
    from platform_api.exceptions import ValidationError

    fields: dict = {}

    if request.display_name is not None:
        fields["display_name"] = request.display_name

    if request.password is not None:
        _validate_password_complexity(request.password)
        from platform_api.services.auth_service import AuthService

        fields["password_hash"] = AuthService.hash_password(request.password)

    if not fields:
        raise ValidationError(
            message="No fields provided for update.",
            details={"allowed_fields": ["display_name", "password"]},
        )

    user_id = UUID(ctx.user_id)
    from platform_api.dependencies import get_user_repo

    user_repo = get_user_repo()
    user = await user_repo.update(user_id, **fields)
    if user is None:
        user = await user_service.get_user(user_id)

    if request.password is not None:
        from platform_api.dependencies import get_auth_service

        await get_auth_service().revoke_tokens(ctx.user_id)

    pool = get_db_pool()
    balance_row = await pool.fetchrow(
        "SELECT balance FROM credit_wallets WHERE user_id = $1",
        user_id,
    )
    credit_balance = int(balance_row["balance"] or 0) if balance_row else 0

    profile_allowance = None
    profile_addon_slots = 0
    profile_addon_pending = 0
    effective_quota_channels = None
    effective_profile_allowance = None

    profile_row = await pool.fetchrow(
        "SELECT COUNT(*)::int AS cnt FROM channel_profiles WHERE user_id = $1",
        user_id,
    )
    channel_profile_count = int(profile_row["cnt"] or 0) if profile_row else 0

    from platform_api.repositories.license_repo import LicenseRepository

    desktop_access = await LicenseRepository(pool=pool).has_paid_desktop_access(str(user_id))
    plan_name = "Pro" if desktop_access else "Free"
    onboarding_paid = desktop_access
    avatar_url = await _fetch_avatar_url(pool, user_id)
    return _user_to_response(
        user,
        credit_balance=credit_balance,
        plan_name=plan_name,
        avatar_url=avatar_url,
        profile_allowance=profile_allowance,
        profile_addon_slots=profile_addon_slots,
        profile_addon_pending=profile_addon_pending,
        effective_profile_allowance=effective_profile_allowance,
        effective_quota_channels=effective_quota_channels,
        channel_profile_count=channel_profile_count,
        onboarding_paid=onboarding_paid,
        desktop_access=desktop_access,
    )


@router.post(
    "/me/avatar",
    response_model=UserProfileResponse,
    status_code=200,
    summary="Upload current user profile photo",
)
async def upload_my_avatar(
    ctx: CurrentUserDep,
    user_service: UserServiceDep,
    file: UploadFile = File(...),
) -> UserProfileResponse:
    from platform_api.exceptions import ValidationError

    content_type = str(file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise ValidationError("Profile photo must be an image file.", details={"field": "file"})
    data = await file.read()
    if not data:
        raise ValidationError("Profile photo file is empty.", details={"field": "file"})
    if len(data) > 2 * 1024 * 1024:
        raise ValidationError("Profile photo must be 2 MB or smaller.", details={"field": "file"})

    user_id = UUID(ctx.user_id)
    stored_path = _save_user_avatar(user_id=user_id, data=data, content_type=content_type)
    pool = get_db_pool()
    await pool.execute(
        "UPDATE users SET avatar_url = $2, updated_at = NOW() WHERE id = $1",
        user_id,
        stored_path,
    )
    return await get_me(ctx, user_service)


# ---------------------------------------------------------------------------
# Admin Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=PaginatedUsersResponse,
    status_code=200,
    summary="List all users (Admin)",
)
async def list_users(
    ctx: AdminUserDep,
    user_service: UserServiceDep,
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=25, ge=1, le=100, description="Users per page"),
    status: str | None = Query(default=None, description="Filter by status"),
    role: str | None = Query(default=None, description="Filter by role (user/admin)"),
    email_confirmed: bool | None = Query(
        default=None, description="Filter by email confirmation state"
    ),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
        description="Search by email, display name, or user id",
    ),
    plan_name: str | None = Query(default=None, description="Filter by active plan name"),
    is_free: bool | None = Query(
        default=None, description="Only users without an active plan"
    ),
    date_from: datetime | None = Query(default=None, description="Registration date from"),
    date_to: datetime | None = Query(default=None, description="Registration date to"),
) -> PaginatedUsersResponse:
    """Return a paginated list of users with optional filters.

    Requirement 3.1: Paginated user list (default 25, max 100) with filtering
    by status, role, email confirmation, plan, search, and registration date.
    """
    users, total = await user_service.get_users(
        page=page,
        page_size=page_size,
        status=status,
        role=role,
        email_confirmed=email_confirmed,
        search=search,
        plan_name=plan_name,
        is_free=is_free,
        date_from=date_from,
        date_to=date_to,
    )

    # Enrich users with extra data (credit balances, plans, profile counts)
    user_ids = [u.id for u in users]
    if user_ids:
        pool = get_db_pool()

        # Batch fetch credit balances
        balance_rows = await pool.fetch(
            "SELECT user_id, balance FROM credit_wallets WHERE user_id = ANY($1)",
            user_ids,
        )
        balances = {str(row["user_id"]): row["balance"] for row in balance_rows}

        # Tier is derived from live pack lots (plans are retired).
        tier_rows = await pool.fetch(
            """
            SELECT w.user_id,
                   EXISTS (
                       SELECT 1 FROM credit_wallet_lots lot
                       WHERE lot.user_id = w.user_id
                         AND lot.tag = 'pack'
                         AND lot.remaining_units > 0
                         AND (lot.expires_at IS NULL OR lot.expires_at > NOW())
                   ) AS is_pro
            FROM credit_wallets w
            WHERE w.user_id = ANY($1)
            """,
            user_ids,
        )
        plans = {
            str(row["user_id"]): ("Pro" if row["is_pro"] else "Free")
            for row in tier_rows
        }
        web_plans: dict[str, str] = {}

        spent_rows = await pool.fetch(
            """
            SELECT user_id, COALESCE(SUM(amount), 0)::bigint AS total
            FROM credit_transactions
            WHERE user_id = ANY($1) AND direction = 'debit'
            GROUP BY user_id
            """,
            user_ids,
        )
        studio_spent = {str(row["user_id"]): int(row["total"] or 0) for row in spent_rows}

        product_rows = await _fetch_optional_rows(
            pool,
            """
            SELECT id, COALESCE(products, '{}'::text[]) AS products
            FROM users
            WHERE id = ANY($1)
            """,
            user_ids,
        )
        products_by_user = {
            str(row["id"]): [str(item) for item in (row["products"] or []) if str(item).strip()]
            for row in product_rows
        }

        # Batch fetch profile counts
        profile_rows = await pool.fetch(
            "SELECT user_id, COUNT(*)::int as cnt FROM channel_profiles WHERE user_id = ANY($1) GROUP BY user_id",
            user_ids,
        )
        profiles = {str(row["user_id"]): row["cnt"] for row in profile_rows}

        verification_rows = await pool.fetch(
            """
            SELECT DISTINCT ON (user_id) user_id, code, expires_at
            FROM email_verifications
            WHERE user_id = ANY($1)
              AND purpose = 'register'
              AND used = false
            ORDER BY user_id, created_at DESC
            """,
            user_ids,
        )
        verifications = {
            str(row["user_id"]): {
                "code": row["code"],
                "expires_at": row["expires_at"],
            }
            for row in verification_rows
        }
    else:
        balances = {}
        plans = {}
        web_plans = {}
        studio_spent = {}
        products_by_user = {}
        profiles = {}
        verifications = {}

    def _list_row(user):
        uid = str(user.id)
        plan_name = plans.get(uid) or web_plans.get(uid) or "Free"
        burned = _studio_credits_burned(studio_spent.get(uid, 0))
        return _user_to_response(
            user,
            credit_balance=balances.get(uid, 0),
            plan_name=plan_name,
            profile_allowance=None,
            channel_profile_count=profiles.get(uid, 0),
            pending_verification_code=verifications.get(uid, {}).get("code"),
            verification_code_expires_at=verifications.get(uid, {}).get("expires_at"),
            music_credits_remaining=None,
            music_credits_limit=None,
            credits_burned=burned,
            products=products_by_user.get(uid, []),
        )

    return PaginatedUsersResponse(
        users=[_list_row(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{user_id}/details",
    response_model=UserFullDetailResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden â€” non-admin access"},
        404: {"description": "User not found"},
    },
    summary="Get full user details (Admin)",
)
async def get_user_full_details(
    user_id: UUID,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> UserFullDetailResponse:
    """Return comprehensive user details for the admin detail page."""
    user = await user_service.get_user(str(user_id))
    if user is None:
        from platform_api.exceptions import NotFoundError

        raise NotFoundError(message="User not found.", details={"user_id": str(user_id)})

    pool = get_db_pool()

    # Credit balance
    balance_row = await pool.fetchrow(
        "SELECT balance FROM credit_wallets WHERE user_id = $1", user_id
    )
    credit_balance_units = int(balance_row["balance"] or 0) if balance_row else 0

    # Total credits spent (sum of debit transactions, stored as micro-units)
    spent_row = await pool.fetchrow(
        """
        SELECT COALESCE(SUM(amount), 0)::bigint as total
        FROM credit_transactions
        WHERE user_id = $1 AND direction = 'debit'
        """,
        user_id,
    )
    total_credits_spent = units_to_credits(int(spent_row["total"] or 0)) if spent_row else 0.0

    # Recent 10 transactions
    from platform_api.services.usage_transaction_labels import enrich_transaction_for_api

    tx_rows = await pool.fetch(
        """
        SELECT id, amount, direction, reason, ref_id, metadata, created_at
        FROM credit_transactions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 10
        """,
        user_id,
    )
    recent_transactions = []
    for row in tx_rows:
        enriched = enrich_transaction_for_api(
            {
                "id": row["id"],
                "user_id": user_id,
                "amount": row["amount"],
                "direction": row.get("direction", "debit"),
                "reason": row.get("reason", ""),
                "ref_id": row.get("ref_id"),
                "metadata": row.get("metadata"),
                "created_at": row["created_at"],
            }
        )
        recent_transactions.append(
            {
                "id": str(row["id"]),
                "amount": enriched["amount"],
                "amount_units": enriched["amount_units"],
                "direction": enriched["direction"],
                "reason": enriched["reason"],
                "purpose": enriched["purpose"],
                "provider": enriched.get("provider"),
                "model": enriched.get("model"),
                "operation": enriched.get("operation"),
                "line_items_summary": enriched.get("line_items_summary"),
                "ref_id": enriched.get("ref_id"),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )

    # Tier is derived from live pack lots (plans/licenses are retired).
    from platform_api.services.tier_service import is_pro as _is_pro

    user_is_pro = await _is_pro(pool, user_id)
    plan_name = "Pro" if user_is_pro else "Free"
    plan_id = None
    license_status = "active" if user_is_pro else None
    license_activated_at = None
    from platform_api.services.v3.store import V3BillingStore

    license_expires_at = await V3BillingStore(pool=pool).live_pack_expiry(user_id)

    product_row = await _fetch_optional_row(
        pool,
        "SELECT COALESCE(products, '{}'::text[]) AS products FROM users WHERE id = $1",
        user_id,
    )
    products = [
        str(item).strip()
        for item in ((product_row or {}).get("products") or [])
        if str(item).strip()
    ]

    music_credits_remaining: int | None = None
    music_credits_limit: int | None = None
    credits_burned: float | None = _studio_credits_burned(
        int(spent_row["total"] or 0) if spent_row else 0
    )

    # Channel profiles
    profile_rows = await pool.fetch(
        """
        SELECT
            id,
            name,
            folder_name,
            run_prefix,
            created_at,
            logo_path,
            video_template_id,
            reel_template_id,
            output_resolution,
            image_config,
            youtube_config
        FROM channel_profiles
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user_id,
    )

    def _as_dict(value) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value or "{}")
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _as_list(value) -> list:
        return value if isinstance(value, list) else []

    channel_profiles: list[ChannelProfileAdminSummary] = []
    template_rows = await pool.fetch(
        """
        SELECT id, name, updated_at
        FROM profile_video_templates
        WHERE user_id = $1
        """,
        user_id,
    )
    templates_by_id = {
        str(row["id"]): {
            "name": str(row["name"]),
            "updated_at": row["updated_at"],
        }
        for row in template_rows
    }

    for row in profile_rows:
        image_cfg = _as_dict(row.get("image_config"))
        youtube_cfg = _as_dict(row.get("youtube_config"))
        cover_paths = _as_list(image_cfg.get("cover_paths")) if isinstance(image_cfg, dict) else []
        keywords = _as_list(youtube_cfg.get("keywords")) if isinstance(youtube_cfg, dict) else []
        tags = _as_list(youtube_cfg.get("tags")) if isinstance(youtube_cfg, dict) else []
        video_template_id = str(row.get("video_template_id") or "").strip() or None
        reel_template_id = str(row.get("reel_template_id") or "").strip() or None
        video_meta = templates_by_id.get(video_template_id or "")
        reel_meta = templates_by_id.get(reel_template_id or "")
        channel_profiles.append(
            ChannelProfileAdminSummary(
                id=str(row["id"]),
                name=row["name"],
                folder_name=row.get("folder_name"),
                run_prefix=str(row.get("run_prefix") or "").strip() or None,
                created_at=row["created_at"],
                logo_available=upload_path_exists(row.get("logo_path")),
                cover_count=len([x for x in cover_paths if upload_path_exists(x)]),
                output_resolution=str(row.get("output_resolution") or "").strip() or None,
                video_template_id=video_template_id,
                reel_template_id=reel_template_id,
                video_template_name=video_meta["name"] if video_meta else None,
                video_template_updated_at=video_meta["updated_at"] if video_meta else None,
                video_template_available=bool(video_meta),
                reel_template_name=reel_meta["name"] if reel_meta else None,
                reel_template_updated_at=reel_meta["updated_at"] if reel_meta else None,
                reel_template_available=bool(reel_meta),
                genre=str(image_cfg.get("genre") or "").strip() or None,
                role=str(image_cfg.get("role") or "").strip() or None,
                description=str(youtube_cfg.get("description") or "").strip() or None,
                visibility=str(youtube_cfg.get("visibility") or "").strip() or None,
                publish_at=str(youtube_cfg.get("publish_at") or "").strip() or None,
                made_for_kids=bool(youtube_cfg.get("made_for_kids") or False),
                ai_use=bool(youtube_cfg.get("ai_use") or False),
                category=str(youtube_cfg.get("category") or "").strip() or None,
                playlist=str(youtube_cfg.get("playlist") or "").strip() or None,
                title_template=str(youtube_cfg.get("title_template") or "").strip()
                or None,
                description_template=str(
                    youtube_cfg.get("description_template") or ""
                ).strip()
                or None,
                keywords=[str(x).strip() for x in keywords if str(x).strip()],
                tags=[str(x).strip() for x in tags if str(x).strip()],
            )
        )

    # Usage stats â€” songs generated
    songs_row = await pool.fetchrow(
        "SELECT COUNT(*)::int as cnt FROM suno_tasks WHERE user_id = $1",
        user_id,
    )
    total_songs_generated = songs_row["cnt"] if songs_row else 0

    # Usage stats â€” images generated
    images_row = await pool.fetchrow(
        "SELECT COUNT(*)::int as cnt FROM image_jobs WHERE user_id = $1",
        user_id,
    )
    total_images_generated = images_row["cnt"] if images_row else 0

    custom_description_rows = await pool.fetch(
        """
        SELECT
            d.id,
            d.name,
            d.content,
            d.created_at,
            d.updated_at,
            COALESCE(usage.usage_count, 0)::int AS usage_count
        FROM music_descriptions d
        LEFT JOIN (
            SELECT description_id, COUNT(*)::int AS usage_count
            FROM songs
            WHERE description_id IS NOT NULL
            GROUP BY description_id
        ) usage ON usage.description_id = d.id
        WHERE d.user_id = $1
        ORDER BY d.name ASC
        """,
        user_id,
    )
    custom_structure_rows = await pool.fetch(
        """
        SELECT
            s.id,
            s.name,
            s.content,
            s.created_at,
            s.updated_at,
            COALESCE(usage.usage_count, 0)::int AS usage_count
        FROM music_structures s
        LEFT JOIN (
            SELECT structure_id, COUNT(*)::int AS usage_count
            FROM songs
            WHERE structure_id IS NOT NULL
            GROUP BY structure_id
        ) usage ON usage.structure_id = s.id
        WHERE s.user_id = $1
        ORDER BY s.name ASC
        """,
        user_id,
    )

    quota_snapshot = None

    freeze_info = {
        "generation_frozen": False,
        "generation_frozen_reason": None,
        "generation_frozen_hours": None,
        "generation_frozen_retry_after": 0,
    }
    try:
        from platform_api.services.generation_freeze import freeze_status

        freeze_info = await freeze_status(str(user_id))
    except Exception:
        pass

    return UserFullDetailResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        status=user.status.value if hasattr(user.status, "value") else str(user.status),
        suspension_reason=getattr(user, "suspension_reason", None),
        created_at=user.created_at,
        updated_at=getattr(user, "updated_at", None),
        credit_balance=units_to_credits(credit_balance_units),
        total_credits_spent=total_credits_spent,
        music_credits_remaining=music_credits_remaining,
        music_credits_limit=music_credits_limit,
        credits_burned=credits_burned,
        recent_transactions=recent_transactions,
        plan_name=plan_name,
        plan_id=plan_id,
        license_status=license_status,
        license_activated_at=license_activated_at,
        license_expires_at=license_expires_at,
        channel_profiles=channel_profiles,
        total_songs_generated=total_songs_generated,
        total_images_generated=total_images_generated,
        quota_period=quota_snapshot,
        custom_descriptions=[
            UserOwnedPromptSummary(
                id=str(row["id"]),
                name=row["name"],
                content=row["content"],
                usage_count=int(row["usage_count"] or 0),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in custom_description_rows
        ],
        custom_structures=[
            UserOwnedPromptSummary(
                id=str(row["id"]),
                name=row["name"],
                content=row["content"],
                usage_count=int(row["usage_count"] or 0),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in custom_structure_rows
        ],
        generation_frozen=bool(freeze_info.get("generation_frozen")),
        generation_frozen_reason=freeze_info.get("generation_frozen_reason"),
        generation_frozen_hours=freeze_info.get("generation_frozen_hours"),
        generation_frozen_retry_after=int(freeze_info.get("generation_frozen_retry_after") or 0),
    )


async def _admin_quota_period_response(
    user_id: UUID,
    *,
    wallet_balance: float | None = None,
) -> AdminQuotaPeriodResponse:
    if wallet_balance is None:
        pool = get_db_pool()
        balance_row = await pool.fetchrow(
            "SELECT balance FROM credit_wallets WHERE user_id = $1", user_id
        )
        credit_balance_units = int(balance_row["balance"] or 0) if balance_row else 0
        wallet_balance = units_to_credits(credit_balance_units)
    return AdminQuotaPeriodResponse(
        user_id=str(user_id),
        period_start=None,
        period_end=None,
        plan_name=None,
        wallet_balance=float(wallet_balance or 0),
        kinds={},
    )


@router.get(
    "/{user_id}/quota-status",
    response_model=AdminQuotaPeriodResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "User not found"},
    },
    summary="Get period quota status for a user (Admin)",
)
async def get_user_quota_status(
    user_id: UUID,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> AdminQuotaPeriodResponse:
    """Return current billing-period quotas including admin top-up extras."""
    del ctx
    user = await user_service.get_user(str(user_id))
    if user is None:
        from platform_api.exceptions import NotFoundError

        raise NotFoundError(message="User not found.", details={"user_id": str(user_id)})
    return await _admin_quota_period_response(user_id)


@router.post(
    "/{user_id}/quota-topups",
    response_model=QuotaTopupResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "User not found"},
        422: {"description": "Validation error"},
    },
    summary="Top up period plan quota for a user (Admin)",
)
async def create_user_quota_topup(
    user_id: UUID,
    body: QuotaTopupRequest,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> QuotaTopupResponse:
    """Add a period-scoped limit bump (expires at next billing period)."""
    user = await user_service.get_user(str(user_id))
    if user is None:
        from platform_api.exceptions import NotFoundError

        raise NotFoundError(message="User not found.", details={"user_id": str(user_id)})

    from platform_api.dependencies import get_audit_service, get_quota_topup_service

    topup_service = get_quota_topup_service()
    result = await topup_service.grant(
        user_id=user_id,
        quota_kind=body.quota_kind,
        amount=body.amount,
        reason=body.reason,
        admin_id=UUID(str(ctx.user_id)),
    )
    try:
        audit_service = get_audit_service()
        await audit_service.log_event(
            actor_id=str(ctx.user_id),
            action_type="quota.topup",
            target_resource=f"user:{user_id}",
            credit_impact=0,
            outcome="success",
            metadata={
                "user_id": str(user_id),
                "quota_kind": result["quota_kind"],
                "amount": result["amount"],
                "period_start": result["period_start"],
                "period_end": result["period_end"],
                "reason": result["reason"],
                "topup_id": result["id"],
                "effective_limit": result["effective_limit"],
            },
        )
    except Exception:
        pass

    period = await _admin_quota_period_response(user_id)
    return QuotaTopupResponse(
        id=result["id"],
        user_id=result["user_id"],
        quota_kind=result["quota_kind"],
        amount=result["amount"],
        reason=result["reason"],
        period_start=result["period_start"],
        period_end=result["period_end"],
        base_limit=result["base_limit"],
        topup_extra=result["topup_extra"],
        effective_limit=result["effective_limit"],
        used=result["used"],
        remaining=result["remaining"],
        quota_period=period,
    )


class FailAbsorbStatusResponse(BaseModel):
    """Admin payload for today's platform fail/retry absorb counter."""

    user_id: str
    usage_date: str
    fail_absorb_used: int
    fail_absorb_budget: int
    remaining: int | None = None
    blocked: bool = False
    redis_key: str
    fail_absorb_used_before: int | None = None


async def _get_usage_enforcement_service():
    """Placeholder — wired in wire_dependencies / dependencies."""
    raise NotImplementedError(
        "UsageEnforcementService dependency not configured. Wire via app.dependency_overrides."
    )


UsageEnforcementDep = Annotated[Any, Depends(_get_usage_enforcement_service)]


@router.get(
    "/{user_id}/fail-absorb",
    response_model=FailAbsorbStatusResponse,
    status_code=200,
    summary="Get today's fail/retry absorb status (Admin)",
)
async def get_user_fail_absorb(
    user_id: UUID,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
    enforcement: UsageEnforcementDep,
) -> FailAbsorbStatusResponse:
    """Return Redis fail-absorb used/budget for the billing day."""
    _ = ctx
    user = await user_service.get_user(str(user_id))
    if user is None:
        from platform_api.exceptions import NotFoundError

        raise NotFoundError(message="User not found.", details={"user_id": str(user_id)})
    used = await enforcement.get_fail_absorb_count(user_id)
    payload = await enforcement.fail_absorb_status(user_id, used=used)
    return FailAbsorbStatusResponse(**payload)


@router.post(
    "/{user_id}/fail-absorb/reset",
    response_model=FailAbsorbStatusResponse,
    status_code=200,
    summary="Reset today's fail/retry absorb counter (Admin)",
)
async def reset_user_fail_absorb(
    user_id: UUID,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
    enforcement: UsageEnforcementDep,
) -> FailAbsorbStatusResponse:
    """Clear today's absorb counter so the user can generate again."""
    _ = ctx
    user = await user_service.get_user(str(user_id))
    if user is None:
        from platform_api.exceptions import NotFoundError

        raise NotFoundError(message="User not found.", details={"user_id": str(user_id)})
    previous = await enforcement.reset_fail_absorb(user_id)
    used = await enforcement.get_fail_absorb_count(user_id)
    payload = await enforcement.fail_absorb_status(user_id, used=used)
    payload["fail_absorb_used_before"] = previous
    return FailAbsorbStatusResponse(**payload)


@router.get(
    "/{user_id}",
    response_model=UserProfileResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden â€” non-admin access"},
        404: {"description": "User not found"},
    },
    summary="Get a user by ID (Admin)",
)
async def get_user_by_id(
    user_id: UUID,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Return a single user's profile by ID."""
    user = await user_service.get_user(str(user_id))
    if user is None:
        from platform_api.exceptions import NotFoundError
        raise NotFoundError(message="User not found.", details={"user_id": str(user_id)})
    return _user_to_response(user)


@router.patch(
    "/{user_id}",
    response_model=UserProfileResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden â€” non-admin access"},
        404: {"description": "User not found"},
    },
    summary="Update a user (Admin)",
)
async def admin_update_user(
    user_id: UUID,
    request: AdminUpdateUserRequest,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Update a user's account details (display_name, role).

    Requirement 3.2: Admin can update user display name and role.
    Requirement 3.6: Returns 404 if user does not exist.
    """
    fields: dict = {}
    if request.display_name is not None:
        fields["display_name"] = request.display_name
    if request.role is not None:
        fields["role"] = request.role

    user = await user_service.update_user(user_id, **fields)
    return _user_to_response(user)


def _validate_password_complexity(password: str) -> None:
    from platform_api.exceptions import ValidationError

    errors: list[str] = []
    if not _PASSWORD_UPPER_RE.search(password):
        errors.append("Password must contain at least one uppercase letter.")
    if not _PASSWORD_LOWER_RE.search(password):
        errors.append("Password must contain at least one lowercase letter.")
    if not _PASSWORD_DIGIT_RE.search(password):
        errors.append("Password must contain at least one digit.")
    if errors:
        raise ValidationError(
            message="Password does not meet security requirements.",
            details={"password": errors},
        )


@router.post(
    "/{user_id}/set-password",
    response_model=UserProfileResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "User not found"},
        422: {"description": "Password validation failed"},
    },
    summary="Set a user's password (Admin)",
)
async def admin_set_user_password(
    user_id: UUID,
    request: AdminSetPasswordRequest,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Set a new password for any user and revoke their existing sessions."""
    from platform_api.dependencies import get_auth_service, get_user_repo
    from platform_api.exceptions import NotFoundError
    from platform_api.services.auth_service import AuthService

    _validate_password_complexity(request.password)

    existing = await user_service.get_user(str(user_id))
    if existing is None:
        raise NotFoundError(message="User not found.", details={"user_id": str(user_id)})

    password_hash = AuthService.hash_password(request.password)
    user_repo = get_user_repo()
    user = await user_repo.update(user_id, password_hash=password_hash)
    if user is None:
        raise NotFoundError(message="User not found.", details={"user_id": str(user_id)})

    await get_auth_service().revoke_tokens(str(user_id))
    return _user_to_response(user)


@router.post(
    "/{user_id}/suspend",
    response_model=UserProfileResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden â€” non-admin access"},
        404: {"description": "User not found"},
    },
    summary="Suspend a user (Admin)",
)
async def suspend_user(
    user_id: UUID,
    request: SuspendRequest,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Suspend a user account with a reason.

    Requirement 3.3: Revokes all active tokens, prevents new authentication,
    and records the suspension reason.
    """
    user = await user_service.suspend_user(user_id, request.reason)
    return _user_to_response(user)


class FreezeGenerationResponse(BaseModel):
    user_id: str
    generation_frozen: bool
    generation_frozen_reason: str | None = None
    generation_frozen_hours: int | None = None
    generation_frozen_retry_after: int = 0


@router.post(
    "/{user_id}/freeze-generation",
    response_model=FreezeGenerationResponse,
    summary="Temporarily freeze music-web generation (Admin)",
)
async def freeze_user_generation(
    user_id: UUID,
    request: FreezeGenerationRequest,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> FreezeGenerationResponse:
    from platform_api.exceptions import ValidationError
    from platform_api.services.generation_freeze import (
        ALLOWED_HOURS,
        freeze_generation,
        freeze_status,
    )

    await user_service.get_user(user_id)
    if request.hours not in ALLOWED_HOURS:
        raise ValidationError(
            "Freeze hours must be 1, 6, 24, or 72.",
            details={"field": "hours", "allowed": list(ALLOWED_HOURS)},
        )
    await freeze_generation(
        user_id=str(user_id),
        ip=None,
        hours=request.hours,
        reason=request.reason.strip(),
    )
    status = await freeze_status(str(user_id))
    return FreezeGenerationResponse(user_id=str(user_id), **status)


@router.post(
    "/{user_id}/unfreeze-generation",
    response_model=FreezeGenerationResponse,
    summary="Clear music-web generation freeze (Admin)",
)
async def unfreeze_user_generation(
    user_id: UUID,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> FreezeGenerationResponse:
    from platform_api.services.generation_freeze import freeze_status, unfreeze_generation

    await user_service.get_user(user_id)
    await unfreeze_generation(user_id=str(user_id))
    status = await freeze_status(str(user_id))
    return FreezeGenerationResponse(user_id=str(user_id), **status)


@router.post(
    "/{user_id}/reactivate",
    response_model=UserProfileResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden â€” non-admin access"},
        404: {"description": "User not found"},
    },
    summary="Reactivate a suspended user (Admin)",
)
async def reactivate_user(
    user_id: UUID,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> UserProfileResponse:
    """Reactivate a previously suspended user account.

    Requirement 3.3: Restores authentication access for the user.
    """
    user = await user_service.reactivate_user(user_id)
    return _user_to_response(user)


@router.delete(
    "/{user_id}",
    status_code=200,
    responses={
        403: {"description": "Forbidden â€” non-admin access"},
        404: {"description": "User not found"},
    },
    summary="Soft-delete a user (Admin)",
)
async def delete_user(
    user_id: UUID,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> dict[str, str]:
    """Soft-delete a user account.

    Requirement 3.4: Sets deleted_at timestamp, preserves audit history,
    and revokes all associated licenses.
    """
    await user_service.delete_user(user_id)
    return {"message": f"User {user_id} has been deleted."}


@router.delete(
    "/{user_id}/permanent",
    status_code=200,
    responses={
        403: {"description": "Forbidden â€” non-admin access"},
        404: {"description": "User not found"},
    },
    summary="Permanently delete a user (Admin)",
)
async def permanent_delete_user(
    user_id: UUID,
    ctx: AdminUserDep,
    user_service: UserServiceDep,
) -> dict[str, str]:
    """Permanently delete a user account and all associated data.

    WARNING: This action is irreversible. The user row will be permanently
    removed from the database.
    """
    await user_service.hard_delete_user(user_id)
    return {"message": f"User {user_id} has been permanently deleted."}


from platform_api.routers.admin_user_web_music import router as admin_web_music_router

router.include_router(admin_web_music_router)
