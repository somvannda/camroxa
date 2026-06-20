"""Authentication router endpoints.

Provides POST /login, POST /register, POST /refresh, POST /logout,
POST /send-verification, POST /verify-email endpoints.
"""

from __future__ import annotations

import random
import re
import string
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr, Field

from platform_api.exceptions import (
    AuthenticationError,
    DuplicateError,
    NotFoundError,
    ValidationError,
)
from platform_api.models.domain import User
from platform_api.models.enums import UserRole, UserStatus
from platform_api.models.schemas import LoginRequest, TokenResponse
from platform_api.services.auth_service import AuthService
from platform_api.services.lockout import AccountLockout

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas specific to this router
# ---------------------------------------------------------------------------


class RefreshRequest(BaseModel):
    """Body for the token refresh endpoint."""

    refresh_token: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    """Registration request — permissive model for multi-error collection."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=200)
    display_name: str = Field(..., min_length=1, max_length=200)


class UserResponse(BaseModel):
    """Response model for successful registration."""

    id: str
    email: str
    display_name: str


class SendVerificationRequest(BaseModel):
    """Request to send a verification code."""

    email: EmailStr


class VerifyEmailRequest(BaseModel):
    """Request to verify an email with a code."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class VerificationResponse(BaseModel):
    """Response for verification endpoints."""

    message: str
    email: str | None = None
    is_verified: bool = False


# ---------------------------------------------------------------------------
# Placeholder Dependency Stubs
# ---------------------------------------------------------------------------
# These will be replaced by real DI wiring in dependencies.py (task 19.1).
# For now, they allow the router to be imported and tested with overrides.


async def _get_auth_service() -> AuthService:
    """Placeholder dependency for AuthService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "AuthService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_lockout() -> AccountLockout:
    """Placeholder dependency for AccountLockout — override in tests or dependencies.py."""
    raise NotImplementedError(
        "AccountLockout dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_current_user_id(authorization: Annotated[str, Header()]) -> str:
    """Extract user_id from Bearer token in Authorization header.

    Placeholder: real implementation will call auth_service.validate_token.
    This is wired properly once middleware/auth.py is complete (task 2.4).
    """
    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Missing or invalid Authorization header.")
    token = authorization[len("Bearer "):]
    # We need the auth service to validate — get it from the placeholder
    # In production this will be wired through proper DI
    raise NotImplementedError(
        "Token validation dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases for dependency injection
AuthServiceDep = Annotated[AuthService, Depends(_get_auth_service)]
LockoutDep = Annotated[AccountLockout, Depends(_get_lockout)]
CurrentUserIdDep = Annotated[str, Depends(_get_current_user_id)]


# ---------------------------------------------------------------------------
# Registration Validation Helpers
# ---------------------------------------------------------------------------

_PASSWORD_UPPER_RE = re.compile(r"[A-Z]")
_PASSWORD_LOWER_RE = re.compile(r"[a-z]")
_PASSWORD_DIGIT_RE = re.compile(r"\d")


def _validate_registration(request: RegisterRequest) -> list[dict[str, str]]:
    """Validate all registration fields and return ALL errors at once.

    Returns a list of error dicts with 'field' and 'message' keys.
    Per Property 4 (Registration validation completeness): every invalid field
    must be reported in a single response.
    """
    errors: list[dict[str, str]] = []

    # Password length (Pydantic handles min/max but we double-check for clarity)
    password = request.password
    if len(password) < 8:
        errors.append({
            "field": "password",
            "message": "Password must be at least 8 characters.",
        })
    elif len(password) > 128:
        errors.append({
            "field": "password",
            "message": "Password must be at most 128 characters.",
        })
    else:
        # Complexity checks
        if not _PASSWORD_UPPER_RE.search(password):
            errors.append({
                "field": "password",
                "message": "Password must contain at least one uppercase letter.",
            })
        if not _PASSWORD_LOWER_RE.search(password):
            errors.append({
                "field": "password",
                "message": "Password must contain at least one lowercase letter.",
            })
        if not _PASSWORD_DIGIT_RE.search(password):
            errors.append({
                "field": "password",
                "message": "Password must contain at least one digit.",
            })

    # Display name length
    display_name = request.display_name
    if len(display_name) < 2:
        errors.append({
            "field": "display_name",
            "message": "Display name must be at least 2 characters.",
        })
    elif len(display_name) > 50:
        errors.append({
            "field": "display_name",
            "message": "Display name must be at most 50 characters.",
        })

    return errors


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=200,
    responses={
        401: {"description": "Invalid credentials"},
        403: {"description": "Account locked"},
    },
    summary="Authenticate with email and password",
)
async def login(
    request: LoginRequest,
    auth_service: AuthServiceDep,
    lockout: LockoutDep,
) -> TokenResponse:
    """Authenticate a user and return a JWT token pair.

    Integrates with account lockout:
    - Checks lockout status before attempting authentication.
    - Records failed attempt on authentication failure.
    - Resets failure counter on successful authentication.
    """
    # Check if account is locked (raises AccountLockedError if locked)
    await lockout.check_lockout(request.email)

    try:
        token_pair = await auth_service.authenticate(request.email, request.password)
    except AuthenticationError:
        # Record the failed attempt (may trigger lockout)
        await lockout.record_failed_attempt(request.email)
        raise

    # Success — reset failure counter
    await lockout.reset_failures(request.email)

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    responses={
        409: {"description": "Email already registered"},
        422: {"description": "Validation errors"},
    },
    summary="Register a new user account",
)
async def register(
    request: RegisterRequest,
    auth_service: AuthServiceDep,
) -> UserResponse:
    """Register a new user account.

    Validates all fields and returns ALL validation errors at once (not just
    the first failure), per Property 4. Checks email uniqueness. On success,
    returns the created user's id, email, and display_name.
    """
    import logging
    _log = logging.getLogger("platform_api.routers.auth.register")
    _log.warning("Register called: email=%s display_name=%s password_len=%d",
                 request.email, request.display_name, len(request.password))

    # Validate all fields — collect all errors
    errors = _validate_registration(request)

    if errors:
        raise ValidationError(
            message="Validation failed.",
            details={"fields": errors},
        )

    # Check email uniqueness via the auth service's user repository
    existing_user = await auth_service._user_repo.get_by_email(request.email)
    if existing_user is not None:
        if existing_user.email_confirmed:
            raise DuplicateError(
                message="A user with this email address already exists.",
                details={"field": "email"},
            )
        # Email exists but not confirmed — update password, display_name, and re-send code
        from platform_api.services.email_service import send_verification_email
        from platform_api.dependencies import get_db_pool
        import random, string

        new_hash = AuthService.hash_password(request.password)
        await auth_service._user_repo.update(
            existing_user.id,
            password_hash=new_hash,
            display_name=request.display_name,
        )

        # Invalidate old codes and send new one
        pool = get_db_pool()
        await pool.execute(
            """UPDATE email_verifications SET used = true
               WHERE user_id = $1 AND purpose = 'register' AND used = false""",
            existing_user.id,
        )
        code = "".join(random.choices(string.digits, k=6))
        from datetime import datetime, timezone, timedelta
        settings = __import__("platform_api.config", fromlist=["get_settings"]).get_settings()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.email_verification_expire_minutes)
        await pool.execute(
            """INSERT INTO email_verifications (user_id, code, purpose, expires_at)
               VALUES ($1, $2, 'register', $3)""",
            existing_user.id, code, expires_at,
        )
        send_verification_email(
            to_email=request.email,
            code=code,
            display_name=request.display_name or "there",
        )
        return UserResponse(
            id=str(existing_user.id),
            email=existing_user.email,
            display_name=existing_user.display_name,
        )

    # Hash password and create user
    password_hash = AuthService.hash_password(request.password)
    user = User(
        email=request.email,
        password_hash=password_hash,
        display_name=request.display_name,
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )

    # Persist the user via the user repository
    created_user = await auth_service._user_repo.create(user)

    return UserResponse(
        id=str(created_user.id),
        email=created_user.email,
        display_name=created_user.display_name,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=200,
    responses={
        401: {"description": "Invalid or expired refresh token"},
    },
    summary="Refresh an access token",
)
async def refresh(
    request: RefreshRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Issue a new token pair using a valid refresh token.

    The old refresh token is revoked (rotated). If the refresh token is
    invalid or expired, returns 401.
    """
    token_pair = await auth_service.refresh_token(request.refresh_token)

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )


@router.post(
    "/logout",
    status_code=200,
    responses={
        401: {"description": "Invalid or missing authorization token"},
    },
    summary="Logout and revoke refresh tokens",
)
async def logout(
    auth_service: AuthServiceDep,
    current_user_id: CurrentUserIdDep,
) -> dict[str, str]:
    """Revoke all refresh tokens for the authenticated user.

    Requires a valid Bearer token in the Authorization header.
    """
    await auth_service.revoke_tokens(current_user_id)
    return {"message": "Successfully logged out."}


# ---------------------------------------------------------------------------
# Email Verification Endpoints
# ---------------------------------------------------------------------------


def _generate_code() -> str:
    """Generate a 6-digit verification code."""
    return "".join(random.choices(string.digits, k=6))


@router.post(
    "/send-verification",
    response_model=VerificationResponse,
    status_code=200,
    summary="Send email verification code",
)
async def send_verification(
    request: SendVerificationRequest,
) -> VerificationResponse:
    """Send a 6-digit verification code to the user's email.

    The code is stored in the email_verifications table with a 15-minute expiry.
    Uses MailHog in dev mode (localhost:1025).
    """
    from platform_api.dependencies import get_db_pool
    from platform_api.services.email_service import send_verification_email

    pool = get_db_pool()

    # Look up user by email
    user_row = await pool.fetchrow(
        "SELECT id, display_name FROM users WHERE LOWER(email) = LOWER($1)",
        request.email,
    )
    if user_row is None:
        # Don't reveal whether email exists — return success anyway
        return VerificationResponse(
            message="If an account with that email exists, a verification code has been sent.",
            email=request.email,
        )

    user_id = user_row["id"]
    display_name = user_row["display_name"] or "there"
    code = _generate_code()
    settings = __import__("platform_api.config", fromlist=["get_settings"]).get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.email_verification_expire_minutes)

    # Invalidate any existing unused codes for this user
    await pool.execute(
        """UPDATE email_verifications SET used = true
           WHERE user_id = $1 AND purpose = 'register' AND used = false""",
        user_id,
    )

    # Store the new code
    await pool.execute(
        """INSERT INTO email_verifications (user_id, code, purpose, expires_at)
           VALUES ($1, $2, 'register', $3)""",
        user_id, code, expires_at,
    )

    # Send the email (best-effort — don't fail the request if email fails)
    send_verification_email(
        to_email=request.email,
        code=code,
        display_name=display_name,
    )

    return VerificationResponse(
        message="Verification code sent.",
        email=request.email,
    )


@router.post(
    "/verify-email",
    response_model=VerificationResponse,
    status_code=200,
    responses={
        400: {"description": "Invalid or expired code"},
    },
    summary="Verify email with code",
)
async def verify_email(
    request: VerifyEmailRequest,
) -> VerificationResponse:
    """Verify a 6-digit code sent to the user's email.

    On success, marks the user's email as verified and returns tokens.
    """
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()

    # Look up user
    user_row = await pool.fetchrow(
        "SELECT id FROM users WHERE LOWER(email) = LOWER($1)",
        request.email,
    )
    if user_row is None:
        raise NotFoundError(message="User not found.")

    user_id = user_row["id"]

    # Find a valid, unused code
    code_row = await pool.fetchrow(
        """SELECT id FROM email_verifications
           WHERE user_id = $1 AND code = $2 AND purpose = 'register'
             AND used = false AND expires_at > NOW()
           ORDER BY created_at DESC LIMIT 1""",
        user_id, request.code,
    )
    if code_row is None:
        raise ValidationError(
            message="Invalid or expired verification code.",
            details={"field": "code"},
        )

    # Mark code as used
    await pool.execute(
        "UPDATE email_verifications SET used = true WHERE id = $1",
        code_row["id"],
    )

    # Mark email as confirmed
    await pool.execute(
        "UPDATE users SET email_confirmed = true WHERE id = $1",
        user_id,
    )

    # Grant 50 trial credits on first email verification
    wallet = await pool.fetchrow(
        "SELECT balance FROM credit_wallets WHERE user_id = $1",
        user_id,
    )
    if wallet is not None and int(wallet["balance"]) == 0:
        await pool.execute(
            """UPDATE credit_wallets SET balance = balance + 50 WHERE user_id = $1""",
            user_id,
        )
        await pool.execute(
            """INSERT INTO credit_transactions (user_id, amount, direction, reason)
               VALUES ($1, 50, 'credit', 'onboarding_trial')""",
            user_id,
        )

    # Assign a Trial license if user doesn't already have one
    existing_license = await pool.fetchrow(
        "SELECT id FROM licenses WHERE user_id = $1 AND status = 'active'",
        user_id,
    )
    if existing_license is None:
        # Find the Trial plan (auto-created if missing)
        trial_plan = await pool.fetchrow(
            "SELECT id FROM plans WHERE LOWER(name) = 'trial' AND is_active = true",
        )
        if trial_plan is None:
            # Create a Trial plan: free, no expiry, 2 profiles, 10 songs/month
            import uuid as _uuid
            trial_plan_id = _uuid.uuid4()
            await pool.execute(
                """INSERT INTO plans (id, name, price_cents, billing_cycle_days, profile_allowance, monthly_song_quota, daily_song_limit_per_channel)
                   VALUES ($1, 'Trial', 0, NULL, 2, 10, 3)""",
                trial_plan_id,
            )
        else:
            trial_plan_id = trial_plan["id"]

        # Create and assign a trial license
        import uuid as _uuid
        import secrets
        license_id = _uuid.uuid4()
        license_key = f"TRIAL-{secrets.token_hex(12).upper()}"
        await pool.execute(
            """INSERT INTO licenses (id, license_key, plan_id, user_id, status, activated_at)
               VALUES ($1, $2, $3, $4, 'active', NOW())""",
            license_id, license_key, trial_plan_id, user_id,
        )

    return VerificationResponse(
        message="Email verified successfully. 50 trial credits added!",
        email=request.email,
        is_verified=True,
    )
