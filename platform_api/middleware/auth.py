"""Authentication and authorization middleware for the Platform API.

Implements FastAPI dependency functions for JWT validation and the
authorization chain defined in Requirement 16:
  1. Token validity → 401 (AuthenticationError)
  2. Account suspension → 403 (ForbiddenError)
  3. License status → 403 (LicenseExpiredError) — generation endpoints only
  4. Credit balance → 402 (InsufficientCreditsError) — generation endpoints only

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from fastapi import Depends, Header, Request

from platform_api.exceptions import (
    AuthenticationError,
    ForbiddenError,
    InsufficientCreditsError,
    LicenseExpiredError,
)
from platform_api.ports.auth_port import TokenPayload
from platform_api.services.auth_service import AuthService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Repository Protocols (minimal interfaces needed by the middleware)
# ---------------------------------------------------------------------------


class UserLookupRepository(Protocol):
    """Minimal protocol for user status lookups in the auth middleware."""

    async def get_status(self, user_id: str) -> str | None:
        """Return the user's current status ('active', 'suspended', 'deleted') or None."""
        ...

    async def get_auth_state(self, user_id: str) -> dict[str, Any] | None:
        """Return auth-critical fields such as status and token version."""
        ...


class LicenseLookupRepository(Protocol):
    """Protocol for checking active license status."""

    async def has_active_license(self, user_id: str) -> bool:
        """Return True if the user has a non-expired, non-revoked license."""
        ...


class CreditLookupRepository(Protocol):
    """Protocol for checking credit balance."""

    async def get_balance(self, user_id: str) -> int:
        """Return the user's current credit wallet balance."""
        ...


class PlanQuotaLookupRepository(Protocol):
    """Protocol for subscription quota lookups in auth middleware."""

    async def get_user_active_subscription_context(self, user_id: UUID) -> Any | None:
        ...

    async def get_user_active_plan(self, user_id: UUID) -> Any | None:
        ...


class UsageQuotaLookupRepository(Protocol):
    """Protocol for usage_tracking reads in auth middleware."""

    async def get_monthly_count(
        self, user_id: UUID, operation_type: str, period_start: date
    ) -> int:
        ...


# ---------------------------------------------------------------------------
# AuthContext — carries authenticated user info through the request lifecycle
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Authenticated user context passed through the request lifecycle.

    Attributes:
        user_id: UUID string of the authenticated user.
        email: User's email address from the JWT claims.
        role: User's role ('user' or 'admin').
    """

    user_id: str
    email: str
    role: str

    @property
    def is_admin(self) -> bool:
        """Return True if the user has admin privileges."""
        return self.role == "admin"


# ---------------------------------------------------------------------------
# Dependency injection placeholders
#
# These module-level variables act as placeholder injection points.
# They are set during application startup (in dependencies.py or main.py)
# via `configure_auth_dependencies()`.
# ---------------------------------------------------------------------------

_auth_service: AuthService | None = None
_user_repo: UserLookupRepository | None = None
_license_repo: LicenseLookupRepository | None = None
_credit_repo: CreditLookupRepository | None = None
_plan_repo: PlanQuotaLookupRepository | None = None
_usage_repo: UsageQuotaLookupRepository | None = None
USER_ACCESS_TOKEN_COOKIE_NAME = "camxora_access_token"
ADMIN_ACCESS_TOKEN_COOKIE_NAME = "camxora_admin_access_token"

# Unconfirmed users may only read profile/routing status and refresh/logout.
# Play and download require a confirmed email.
_UNCONFIRMED_ALLOWED_PATHS = {
    ("GET", "/api/v1/users/me"),
    ("GET", "/users/me"),
    ("GET", "/api/v1/profiles"),
    ("GET", "/profiles"),
    ("GET", "/api/v1/channel-setup/profiles-status"),
    ("GET", "/channel-setup/profiles-status"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/auth/logout"),
    ("POST", "/api/v1/auth/refresh"),
    ("POST", "/auth/refresh"),
}


def _normalize_request_path(path: str) -> str:
    if not path or path == "/":
        return path or "/"
    return path.rstrip("/")


def _is_unconfirmed_path_allowed(method: str, path: str) -> bool:
    return (method.upper(), _normalize_request_path(path)) in _UNCONFIRMED_ALLOWED_PATHS


def _resolve_access_cookie_name(request: Request | None) -> str:
    if request is None:
        return USER_ACCESS_TOKEN_COOKIE_NAME

    portal_context = request.headers.get("X-Portal-Context", "").strip().lower()
    if portal_context == "admin" or "/api/v1/admin" in str(request.url.path):
        return ADMIN_ACCESS_TOKEN_COOKIE_NAME
    return USER_ACCESS_TOKEN_COOKIE_NAME


def configure_auth_dependencies(
    *,
    auth_service: AuthService,
    user_repo: UserLookupRepository,
    license_repo: LicenseLookupRepository | None = None,
    credit_repo: CreditLookupRepository | None = None,
    plan_repo: PlanQuotaLookupRepository | None = None,
    usage_repo: UsageQuotaLookupRepository | None = None,
) -> None:
    """Configure the auth middleware with service/repository instances.

    Call this once during application startup to wire the dependencies.

    Args:
        auth_service: AuthService instance for token validation.
        user_repo: Repository for user status lookups.
        license_repo: Repository for license checks (optional, for generation endpoints).
        credit_repo: Repository for credit balance checks (optional, for generation endpoints).
        plan_repo: Repository for subscription quota checks (optional, quota-only subscribers).
        usage_repo: Repository for usage_tracking reads (optional, quota-only subscribers).
    """
    global _auth_service, _user_repo, _license_repo, _credit_repo, _plan_repo, _usage_repo
    _auth_service = auth_service
    _user_repo = user_repo
    _license_repo = license_repo
    _credit_repo = credit_repo
    _plan_repo = plan_repo
    _usage_repo = usage_repo


def _get_auth_service() -> AuthService:
    """Return the configured AuthService or raise if not configured."""
    if _auth_service is None:
        raise RuntimeError(
            "Auth middleware not configured. Call configure_auth_dependencies() at startup."
        )
    return _auth_service


def _get_user_repo() -> UserLookupRepository:
    """Return the configured user repository or raise if not configured."""
    if _user_repo is None:
        raise RuntimeError(
            "Auth middleware not configured. Call configure_auth_dependencies() at startup."
        )
    return _user_repo


# ---------------------------------------------------------------------------
# Core dependency: get_current_user
# Validates the JWT and checks account suspension (steps 1-2 of the chain).
# ---------------------------------------------------------------------------


def _extract_bearer_token(authorization: str) -> str:
    """Extract the token from a 'Bearer <token>' header value.

    Raises:
        AuthenticationError: If the header format is invalid.
    """
    if not authorization:
        raise AuthenticationError("Missing authorization header.")

    parts = authorization.split(" ", maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid authorization header format. Expected 'Bearer <token>'.")

    token = parts[1].strip()
    if not token:
        raise AuthenticationError("Empty bearer token.")

    return token


def _bind_auth_context_to_request(request: Request | None, context: AuthContext) -> None:
    """Expose the authenticated user to later middleware such as audit logging."""
    if request is None:
        return
    request.state.auth_context = context
    request.state.user_id = context.user_id


async def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    request: Request = None,
) -> AuthContext:
    """FastAPI dependency that validates the JWT and enforces steps 1-2 of the authorization chain.

    Authorization chain enforced here:
      1. Token validity → raises AuthenticationError (401)
      2. Account suspension → raises ForbiddenError (403)

    Usage:
        @router.get("/resource")
        async def get_resource(ctx: AuthContext = Depends(get_current_user)):
            ...

    Returns:
        AuthContext with the authenticated user's identity and role.

    Raises:
        AuthenticationError: If the token is missing, malformed, or invalid (401).
        ForbiddenError: If the user's account is suspended (403).
    """
    # Step 1: Token validity → 401
    token: str | None = None
    if authorization:
        token = _extract_bearer_token(authorization)
    else:
        cookie_name = _resolve_access_cookie_name(request)
        token = request.cookies.get(cookie_name) if request is not None else None
        if not token:
            raise AuthenticationError("Missing authorization credentials.")

    auth_service = _get_auth_service()

    payload: TokenPayload = await auth_service.validate_token(token)

    # Step 2: Account suspension → 403
    user_repo = _get_user_repo()
    auth_state = await user_repo.get_auth_state(payload.user_id)

    if auth_state is None:
        raise AuthenticationError("User not found.")

    status = str(auth_state.get("status") or "")
    token_version = int(auth_state.get("token_version") or 0)

    if payload.token_version != token_version:
        raise AuthenticationError("Session has been revoked. Please sign in again.")

    if status == "suspended":
        raise ForbiddenError("Account suspended")

    email_confirmed = bool(auth_state.get("email_confirmed", True))
    if not email_confirmed:
        method = request.method if request is not None else ""
        path = str(request.url.path) if request is not None else ""
        if not _is_unconfirmed_path_allowed(method, path):
            raise ForbiddenError("Confirm your email before using Camxora.")

    context = AuthContext(
        user_id=payload.user_id,
        email=payload.email,
        role=payload.role,
    )
    _bind_auth_context_to_request(request, context)
    return context


# ---------------------------------------------------------------------------
# Role enforcement: require_admin
# ---------------------------------------------------------------------------


async def require_admin(
    context: AuthContext = Depends(get_current_user),
) -> AuthContext:
    """FastAPI dependency that requires admin role.

    Must be used after get_current_user (which it depends on via Depends).

    Usage:
        @router.get("/admin/resource")
        async def admin_resource(ctx: AuthContext = Depends(require_admin)):
            ...

    Returns:
        AuthContext (guaranteed to have role == 'admin').

    Raises:
        ForbiddenError: If the user does not have admin role (403).
    """
    if not context.is_admin:
        raise ForbiddenError("You do not have permission to perform this action.")
    return context


# ---------------------------------------------------------------------------
# Generation endpoint dependencies (steps 3-4 of the authorization chain)
# These are separate so they only apply to generation routes.
# ---------------------------------------------------------------------------


async def require_active_license(
    context: AuthContext = Depends(get_current_user),
) -> AuthContext:
    """FastAPI dependency that checks the user has an active license (step 3).

    Use this on generation endpoints that require a valid license.

    Authorization chain step 3: License status → 403 (LicenseExpiredError)

    Usage:
        @router.post("/generation/suno")
        async def submit_suno(ctx: AuthContext = Depends(require_active_license)):
            ...

    Returns:
        AuthContext (guaranteed to have an active license).

    Raises:
        LicenseExpiredError: If no active license exists (403).
        RuntimeError: If the license repository is not configured.
    """
    if _license_repo is None:
        raise RuntimeError(
            "License repository not configured. Call configure_auth_dependencies() with license_repo."
        )

    has_license = await _license_repo.has_active_license(context.user_id)
    if not has_license:
        raise LicenseExpiredError()

    return context


async def require_sufficient_credits(
    context: AuthContext = Depends(get_current_user),
    required_credits: int = 1,
) -> AuthContext:
    """FastAPI dependency that checks the user has sufficient credits (step 4).

    Use this on generation endpoints that consume credits.

    Authorization chain step 4: Credit balance → 402 (InsufficientCreditsError)

    Note: The `required_credits` parameter defaults to 1. For endpoints with
    variable costs, create a custom dependency that calculates the cost and
    calls `check_credit_balance()` directly.

    Usage:
        @router.post("/generation/suno")
        async def submit_suno(ctx: AuthContext = Depends(require_sufficient_credits)):
            ...

    Returns:
        AuthContext (guaranteed to have sufficient credits).

    Raises:
        InsufficientCreditsError: If the balance is below the required amount (402).
        RuntimeError: If the credit repository is not configured.
    """
    if _credit_repo is None:
        raise RuntimeError(
            "Credit repository not configured. Call configure_auth_dependencies() with credit_repo."
        )

    balance = await _credit_repo.get_balance(context.user_id)
    if balance < required_credits:
        raise InsufficientCreditsError(
            details={"balance": balance, "required": required_credits},
        )

    return context


async def check_credit_balance(user_id: str, required_credits: int) -> None:
    """Utility function to check credit balance outside of the Depends chain.

    Useful when the required credit amount is determined dynamically
    (e.g., based on the request body or model selection).

    Args:
        user_id: The user's UUID string.
        required_credits: The minimum credits required for the operation.

    Raises:
        InsufficientCreditsError: If the balance is below the required amount (402).
        RuntimeError: If the credit repository is not configured.
    """
    if _credit_repo is None:
        raise RuntimeError(
            "Credit repository not configured. Call configure_auth_dependencies() with credit_repo."
        )

    balance = await _credit_repo.get_balance(user_id)
    if balance < required_credits:
        raise InsufficientCreditsError(
            details={"balance": balance, "required": required_credits},
        )


# ---------------------------------------------------------------------------
# Composite dependency: full generation authorization chain (all 4 steps)
# ---------------------------------------------------------------------------


async def require_generation_access(
    authorization: str = Header(..., alias="Authorization"),
    request: Request = None,
) -> AuthContext:
    """FastAPI dependency combining all 4 authorization chain steps for generation endpoints.

    Enforces the full chain in strict order per Requirement 16.7:
      1. Token validity → 401 (AuthenticationError)
      2. Account suspension → 403 (ForbiddenError)
      3. License status → 403 (LicenseExpiredError)
      4. Credit balance → 402 (InsufficientCreditsError)

    Usage:
        @router.post("/generation/suno")
        async def submit_suno(ctx: AuthContext = Depends(require_generation_access)):
            ...

    Returns:
        AuthContext (passed all 4 checks).
    """
    # Steps 1-2: Token + suspension (via get_current_user)
    context = await get_current_user(authorization=authorization, request=request)

    # Step 3: License check
    if _license_repo is None:
        raise RuntimeError(
            "License repository not configured. Call configure_auth_dependencies() with license_repo."
        )
    has_license = await _license_repo.has_active_license(context.user_id)
    if not has_license:
        raise LicenseExpiredError()

    # Step 4: Credit balance or subscription quota
    if _credit_repo is None:
        raise RuntimeError(
            "Credit repository not configured. Call configure_auth_dependencies() with credit_repo."
        )
    balance = await _credit_repo.get_balance(context.user_id)
    if balance >= 1:
        return context

    if _plan_repo is not None and _usage_repo is not None:
        from platform_api.services.quota_display_service import user_has_generation_capacity

        has_capacity = await user_has_generation_capacity(
            user_id=UUID(context.user_id),
            credit_repo=_credit_repo,
            plan_repo=_plan_repo,
            usage_repo=_usage_repo,
            min_credits=1,
        )
        if has_capacity:
            return context

    raise InsufficientCreditsError(
        details={"balance": balance, "required": 1},
    )
