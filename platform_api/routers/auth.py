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

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, EmailStr, Field

from platform_api.config import get_settings
from platform_api.exceptions import (
    AuthenticationError,
    DuplicateError,
    NotFoundError,
    ValidationError,
)
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.models.domain import User
from platform_api.models.enums import UserRole, UserStatus
from platform_api.models.products import PRODUCT_MUSIC_WEB, normalize_signup_product
from platform_api.models.schemas import LoginRequest, TokenResponse
from platform_api.services.auth_service import AuthService
from platform_api.services.invitation_code_service import InvitationCodeService
from platform_api.services.lockout import AccountLockout
from platform_api.services.shared.turnstile_service import TurnstileService

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["auth"])
USER_ACCESS_TOKEN_COOKIE_NAME = "camxora_access_token"
USER_REFRESH_TOKEN_COOKIE_NAME = "camxora_refresh_token"
ADMIN_ACCESS_TOKEN_COOKIE_NAME = "camxora_admin_access_token"
ADMIN_REFRESH_TOKEN_COOKIE_NAME = "camxora_admin_refresh_token"


# ---------------------------------------------------------------------------
# Request / Response schemas specific to this router
# ---------------------------------------------------------------------------


class RefreshRequest(BaseModel):
    """Body for the token refresh endpoint."""

    refresh_token: str | None = Field(default=None, min_length=1)


class RegisterRequest(BaseModel):
    """Registration request — permissive model for multi-error collection."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=200)
    display_name: str = Field(..., min_length=1, max_length=200)
    invitation_code: str | None = Field(default=None, min_length=1, max_length=64)
    product: str | None = Field(default=None, max_length=32)
    cf_turnstile_response: str | None = Field(default=None, description="Cloudflare Turnstile token")


class SignupModeResponse(BaseModel):
    mode: str


class ValidateInvitationRequest(BaseModel):
    invitation_code: str = Field(..., min_length=1, max_length=64)


class ValidateInvitationResponse(BaseModel):
    ok: bool = True
    code_hint: str | None = None
    label: str | None = None


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


async def _get_invitation_code_service() -> InvitationCodeService:
    """Placeholder dependency for InvitationCodeService."""
    raise NotImplementedError(
        "InvitationCodeService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_turnstile_service() -> TurnstileService:
    """Placeholder dependency for TurnstileService."""
    raise NotImplementedError(
        "TurnstileService dependency not configured. Wire via app.dependency_overrides."
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


def _resolve_cookie_names(request: Request | None) -> tuple[str, str]:
    portal_context = (
        request.headers.get("X-Portal-Context", "").strip().lower()
        if request is not None
        else ""
    )
    if portal_context == "admin":
        return ADMIN_ACCESS_TOKEN_COOKIE_NAME, ADMIN_REFRESH_TOKEN_COOKIE_NAME
    return USER_ACCESS_TOKEN_COOKIE_NAME, USER_REFRESH_TOKEN_COOKIE_NAME


def _set_auth_cookies(
    response: Response,
    token_response: TokenResponse,
    request: Request | None = None,
) -> None:
    settings = get_settings()
    secure = not settings.debug
    access_cookie_name, refresh_cookie_name = _resolve_cookie_names(request)
    response.set_cookie(
        access_cookie_name,
        token_response.access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=token_response.expires_in,
        path="/",
    )
    response.set_cookie(
        refresh_cookie_name,
        token_response.refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response, request: Request | None = None) -> None:
    settings = get_settings()
    secure = not settings.debug
    access_cookie_name, refresh_cookie_name = _resolve_cookie_names(request)
    response.delete_cookie(access_cookie_name, path="/", httponly=True, secure=secure, samesite="lax")
    response.delete_cookie(refresh_cookie_name, path="/", httponly=True, secure=secure, samesite="lax")


async def _set_session_for_user(
    auth_service: AuthService,
    user: User,
    response: Response,
    http_request: Request,
) -> None:
    """Issue auth cookies for a user who just registered or re-registered."""
    token_pair = await auth_service.issue_token_pair_for_user(user)
    token_response = TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )
    _set_auth_cookies(response, token_response, http_request)


# Type aliases for dependency injection
AuthServiceDep = Annotated[AuthService, Depends(_get_auth_service)]
LockoutDep = Annotated[AccountLockout, Depends(_get_lockout)]
InvitationCodeServiceDep = Annotated[
    InvitationCodeService, Depends(_get_invitation_code_service)
]
TurnstileServiceDep = Annotated[TurnstileService, Depends(_get_turnstile_service)]
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
    turnstile: TurnstileServiceDep,
    response: Response,
    http_request: Request,
) -> TokenResponse:
    """Authenticate a user and return a JWT token pair.

    Integrates with account lockout:
    - Checks lockout status before attempting authentication.
    - Records failed attempt on authentication failure.
    - Resets failure counter on successful authentication.
    - Verifies Cloudflare Turnstile token to prevent bots.
    """
    import logging
    _log = logging.getLogger("platform_api.routers.auth.login")
    
    try:
        _log.info(f"Login attempt: email={request.email}, has_turnstile={bool(request.cf_turnstile_response)}")
        
        # Verify Cloudflare Turnstile token (if provided from web clients)
        if request.cf_turnstile_response:
            _log.info("Verifying Turnstile token...")
            _log.info(f"Turnstile token (first 20 chars): {request.cf_turnstile_response[:20] if request.cf_turnstile_response else 'None'}")
            _log.info(f"Client IP: {http_request.client.host if http_request.client else 'None'}")
            
            # Get expected hostnames from settings
            settings = get_settings()
            expected_hostnames = set(
                h.strip() for h in settings.cloudflare_turnstile_hostnames.split(",") if h.strip()
            )
            _log.info(f"Expected hostnames: {expected_hostnames}")
            
            try:
                result = await turnstile.verify(
                    request.cf_turnstile_response,
                    remote_ip=http_request.client.host if http_request.client else None
                )
                _log.info(f"Turnstile verification result: {result}")
                
                # Canonical validation: success, action, and hostname
                if not result.get("success"):
                    error_codes = result.get("error-codes", [])
                    _log.error(f"Turnstile failed: success=False, error_codes={error_codes}")
                    raise ValidationError(
                        message=f"Bot verification failed: {', '.join(error_codes) if error_codes else 'unknown error'}",
                        details={"field": "cf_turnstile_response", "cloudflare_errors": error_codes}
                    )
                
                if result.get("action") != "login":
                    _log.error(f"Turnstile action mismatch: expected='login', got='{result.get('action')}'")
                    raise ValidationError(
                        message="Bot verification failed: invalid action",
                        details={"field": "cf_turnstile_response"}
                    )
                
                if expected_hostnames and result.get("hostname") not in expected_hostnames:
                    _log.error(f"Turnstile hostname mismatch: got='{result.get('hostname')}', expected one of {expected_hostnames}")
                    raise ValidationError(
                        message="Bot verification failed: invalid hostname",
                        details={"field": "cf_turnstile_response"}
                    )
                
                _log.info("Turnstile verification passed all checks")
            except ValidationError:
                raise
            except Exception as e:
                _log.error(f"Turnstile verification error: {type(e).__name__}: {e}", exc_info=True)
                raise
        
        # Check if account is locked (raises AccountLockedError if locked)
        _log.info("Checking account lockout status...")
        await lockout.check_lockout(request.email)

        _log.info("Authenticating user...")
        try:
            token_pair = await auth_service.authenticate(request.email, request.password)
        except AuthenticationError as auth_err:
            _log.warning(f"Authentication failed for {request.email}: {auth_err}")
            # Record the failed attempt (may trigger lockout)
            await lockout.record_failed_attempt(request.email)
            raise

        # Success — reset failure counter
        _log.info("Authentication successful, resetting failure counter...")
        await lockout.reset_failures(request.email)

        token_response = TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="bearer",
            expires_in=token_pair.expires_in,
        )
        _log.info("Setting auth cookies...")
        _set_auth_cookies(response, token_response, http_request)
        _log.info("Login successful")
        return token_response
        
    except (AuthenticationError, ValidationError, AccountLockedError):
        # These are expected errors, just re-raise
        raise
    except Exception as e:
        _log.error(f"Unexpected login error: {type(e).__name__}: {e}", exc_info=True)
        raise


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
    invitation_code_service: InvitationCodeServiceDep,
    turnstile: TurnstileServiceDep,
    response: Response,
    http_request: Request,
) -> UserResponse:
    """Register a new user account.

    Validates all fields and returns ALL validation errors at once (not just
    the first failure), per Property 4. Checks email uniqueness. On success,
    returns the created user's id, email, and display_name.
    Verifies Cloudflare Turnstile token to prevent bot registrations.
    """
    import logging
    _log = logging.getLogger("platform_api.routers.auth.register")
    _log.warning("Register called: email=%s display_name=%s password_len=%d",
                 request.email, request.display_name, len(request.password))

    # Verify Cloudflare Turnstile token (if provided from web clients)
    if request.cf_turnstile_response:
        settings = get_settings()
        expected_hostnames = set(
            h.strip() for h in settings.cloudflare_turnstile_hostnames.split(",") if h.strip()
        )
        
        result = await turnstile.verify(
            request.cf_turnstile_response,
            remote_ip=http_request.client.host if http_request.client else None
        )
        
        # Canonical validation: success, action, and hostname
        if not result.get("success"):
            error_codes = result.get("error-codes", [])
            raise ValidationError(
                message=f"Bot verification failed: {', '.join(error_codes) if error_codes else 'unknown error'}",
                details={"field": "cf_turnstile_response", "cloudflare_errors": error_codes}
            )
        
        if result.get("action") != "register":
            raise ValidationError(
                message="Bot verification failed: invalid action",
                details={"field": "cf_turnstile_response"}
            )
        
        if expected_hostnames and result.get("hostname") not in expected_hostnames:
            raise ValidationError(
                message="Bot verification failed: invalid hostname",
                details={"field": "cf_turnstile_response"}
            )

    # Validate all fields — collect all errors
    errors = _validate_registration(request)

    if errors:
        raise ValidationError(
            message="Validation failed.",
            details={"fields": errors},
        )

    header_product = http_request.headers.get("X-Signup-Product")
    signup_product = normalize_signup_product(request.product or header_product)

    signup_mode = await invitation_code_service.get_signup_mode()
    normalized_invitation_code = (
        request.invitation_code.strip().upper()
        if isinstance(request.invitation_code, str) and request.invitation_code.strip()
        else None
    )

    if (
        signup_product != PRODUCT_MUSIC_WEB
        and signup_mode == "invite_only"
        and not normalized_invitation_code
    ):
        raise ValidationError(
            message="Invitation code is required.",
            details={"fields": [{"field": "invitation_code", "message": "Invitation code is required."}]},
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
        settings = get_settings()
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
        refreshed_user = await auth_service._user_repo.get_by_email(request.email)
        add_product = getattr(auth_service._user_repo, "add_product", None)
        if callable(add_product):
            await add_product(existing_user.id, signup_product)
        if refreshed_user is not None:
            await _set_session_for_user(auth_service, refreshed_user, response, http_request)
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
        products=[signup_product],
    )

    from platform_api.dependencies import get_db_pool

    needs_invite_consume = (
        signup_product != PRODUCT_MUSIC_WEB
        and signup_mode == "invite_only"
        and bool(normalized_invitation_code)
    )
    if needs_invite_consume:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                created_user = await auth_service._user_repo.create(user, conn=conn)
                await invitation_code_service.consume_invitation_code(
                    conn=conn,
                    code=normalized_invitation_code,
                    user_id=created_user.id,
                )
    else:
        created_user = await auth_service._user_repo.create(user)

    # Send email verification code for new users (web music flow)
    if signup_product == PRODUCT_MUSIC_WEB:
        from platform_api.services.email_service import send_verification_email
        pool = get_db_pool()
        code = _generate_code()
        settings = get_settings()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.email_verification_expire_minutes)
        
        await pool.execute(
            """INSERT INTO email_verifications (user_id, code, purpose, expires_at)
               VALUES ($1, $2, 'register', $3)""",
            created_user.id, code, expires_at,
        )
        
        send_verification_email(
            to_email=created_user.email,
            code=code,
            display_name=created_user.display_name or "there",
        )

    await _set_session_for_user(auth_service, created_user, response, http_request)
    return UserResponse(
        id=str(created_user.id),
        email=created_user.email,
        display_name=created_user.display_name,
    )


@router.get(
    "/signup-mode",
    response_model=SignupModeResponse,
    status_code=200,
    summary="Get current signup access mode",
)
async def get_signup_mode(
    invitation_code_service: InvitationCodeServiceDep,
) -> SignupModeResponse:
    return SignupModeResponse(mode=await invitation_code_service.get_signup_mode())


@router.post(
    "/validate-invitation",
    response_model=ValidateInvitationResponse,
    status_code=200,
    summary="Validate invitation code for invite-only signup",
)
async def validate_invitation(
    request: ValidateInvitationRequest,
    invitation_code_service: InvitationCodeServiceDep,
) -> ValidateInvitationResponse:
    result = await invitation_code_service.validate_invitation_code(request.invitation_code)
    return ValidateInvitationResponse(
        ok=True,
        code_hint=result.get("code_hint"),
        label=result.get("label"),
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
    request: RefreshRequest | None,
    http_request: Request,
    auth_service: AuthServiceDep,
    response: Response,
) -> TokenResponse:
    """Issue a new token pair using a valid refresh token.

    The old refresh token is revoked (rotated). If the refresh token is
    invalid or expired, returns 401.
    """
    refresh_token = request.refresh_token if request and request.refresh_token else None
    if not refresh_token:
        _, refresh_cookie_name = _resolve_cookie_names(http_request)
        refresh_token = http_request.cookies.get(refresh_cookie_name)
    if not refresh_token:
        raise AuthenticationError("Refresh token is required.")

    token_pair = await auth_service.refresh_token(refresh_token)

    token_response = TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )
    _set_auth_cookies(response, token_response, http_request)
    return token_response


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
    ctx: Annotated[AuthContext, Depends(get_current_user)],
    response: Response,
    request: Request,
) -> dict[str, str]:
    """Revoke all refresh tokens for the authenticated user.

    Accepts Bearer token or user auth cookies (same as other authenticated routes).
    """
    await auth_service.revoke_tokens(ctx.user_id)
    _clear_auth_cookies(response, request)
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
        "SELECT id, display_name, email_confirmed FROM users WHERE LOWER(email) = LOWER($1)",
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
    if bool(user_row["email_confirmed"]):
        return VerificationResponse(
            message="Email already verified.",
            email=request.email,
            is_verified=True,
        )

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

    # Mark email as confirmed — payment is required before onboarding AI access.
    await pool.execute(
        "UPDATE users SET email_confirmed = true WHERE id = $1",
        user_id,
    )

    return VerificationResponse(
        message="Email verified successfully. Choose a plan and complete payment to continue.",
        email=request.email,
        is_verified=True,
    )
