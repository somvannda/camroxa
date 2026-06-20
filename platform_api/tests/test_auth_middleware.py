"""Tests for the auth middleware (platform_api.middleware.auth).

Validates the authorization chain, role enforcement, and dependency injection
for JWT-based authentication.

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from platform_api.exceptions import (
    AuthenticationError,
    ForbiddenError,
    InsufficientCreditsError,
    LicenseExpiredError,
)
from platform_api.middleware.auth import (
    AuthContext,
    _extract_bearer_token,
    check_credit_balance,
    configure_auth_dependencies,
    get_current_user,
    require_active_license,
    require_admin,
    require_generation_access,
    require_sufficient_credits,
)
from platform_api.ports.auth_port import TokenPayload


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_auth_service():
    """Return a mock AuthService with validate_token configured."""
    service = AsyncMock()
    service.validate_token = AsyncMock(
        return_value=TokenPayload(
            user_id="user-123",
            email="test@example.com",
            role="user",
            exp=9999999999,
        )
    )
    return service


@pytest.fixture
def mock_user_repo():
    """Return a mock user repository that returns 'active' status."""
    repo = AsyncMock()
    repo.get_status = AsyncMock(return_value="active")
    return repo


@pytest.fixture
def mock_license_repo():
    """Return a mock license repository that reports active license."""
    repo = AsyncMock()
    repo.has_active_license = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_credit_repo():
    """Return a mock credit repository that returns 100 credits."""
    repo = AsyncMock()
    repo.get_balance = AsyncMock(return_value=100)
    return repo


@pytest.fixture(autouse=True)
def configure_deps(mock_auth_service, mock_user_repo, mock_license_repo, mock_credit_repo):
    """Configure auth dependencies for all tests in this module."""
    configure_auth_dependencies(
        auth_service=mock_auth_service,
        user_repo=mock_user_repo,
        license_repo=mock_license_repo,
        credit_repo=mock_credit_repo,
    )
    yield
    # Reset to None after tests
    configure_auth_dependencies(
        auth_service=mock_auth_service,
        user_repo=mock_user_repo,
        license_repo=None,
        credit_repo=None,
    )


# ---------------------------------------------------------------------------
# AuthContext tests
# ---------------------------------------------------------------------------


class TestAuthContext:
    """Tests for the AuthContext dataclass."""

    def test_create_user_context(self) -> None:
        ctx = AuthContext(user_id="u1", email="a@b.com", role="user")
        assert ctx.user_id == "u1"
        assert ctx.email == "a@b.com"
        assert ctx.role == "user"
        assert ctx.is_admin is False

    def test_create_admin_context(self) -> None:
        ctx = AuthContext(user_id="a1", email="admin@b.com", role="admin")
        assert ctx.is_admin is True

    def test_frozen_dataclass(self) -> None:
        ctx = AuthContext(user_id="u1", email="a@b.com", role="user")
        with pytest.raises(Exception):  # FrozenInstanceError
            ctx.user_id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Bearer token extraction tests
# ---------------------------------------------------------------------------


class TestExtractBearerToken:
    """Tests for _extract_bearer_token helper."""

    def test_valid_bearer_token(self) -> None:
        token = _extract_bearer_token("Bearer abc123")
        assert token == "abc123"

    def test_valid_bearer_token_case_insensitive(self) -> None:
        token = _extract_bearer_token("bearer abc123")
        assert token == "abc123"

    def test_missing_header_raises(self) -> None:
        with pytest.raises(AuthenticationError, match="Missing authorization header"):
            _extract_bearer_token("")

    def test_no_bearer_prefix_raises(self) -> None:
        with pytest.raises(AuthenticationError, match="Invalid authorization header format"):
            _extract_bearer_token("Token abc123")

    def test_only_bearer_no_token_raises(self) -> None:
        with pytest.raises(AuthenticationError, match="Empty bearer token"):
            _extract_bearer_token("Bearer ")

    def test_basic_auth_raises(self) -> None:
        with pytest.raises(AuthenticationError, match="Invalid authorization header format"):
            _extract_bearer_token("Basic dXNlcjpwYXNz")


# ---------------------------------------------------------------------------
# get_current_user tests (Steps 1-2)
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""

    async def test_valid_token_active_user(self, mock_auth_service, mock_user_repo) -> None:
        ctx = await get_current_user("Bearer valid-token")
        assert ctx.user_id == "user-123"
        assert ctx.email == "test@example.com"
        assert ctx.role == "user"
        mock_auth_service.validate_token.assert_awaited_once_with("valid-token")
        mock_user_repo.get_status.assert_awaited_once_with("user-123")

    async def test_invalid_token_raises_401(self, mock_auth_service) -> None:
        mock_auth_service.validate_token.side_effect = AuthenticationError("Invalid token.")
        with pytest.raises(AuthenticationError):
            await get_current_user("Bearer bad-token")

    async def test_expired_token_raises_401(self, mock_auth_service) -> None:
        mock_auth_service.validate_token.side_effect = AuthenticationError("Token has expired.")
        with pytest.raises(AuthenticationError, match="Token has expired"):
            await get_current_user("Bearer expired-token")

    async def test_missing_header_raises_401(self) -> None:
        with pytest.raises(AuthenticationError):
            await get_current_user("")

    async def test_suspended_user_raises_403(self, mock_user_repo) -> None:
        mock_user_repo.get_status.return_value = "suspended"
        with pytest.raises(ForbiddenError, match="Account suspended"):
            await get_current_user("Bearer valid-token")

    async def test_deleted_user_is_not_suspended(self, mock_user_repo) -> None:
        # Deleted users are not found — treated as auth error
        mock_user_repo.get_status.return_value = None
        with pytest.raises(AuthenticationError, match="User not found"):
            await get_current_user("Bearer valid-token")

    async def test_user_not_found_raises_401(self, mock_user_repo) -> None:
        mock_user_repo.get_status.return_value = None
        with pytest.raises(AuthenticationError):
            await get_current_user("Bearer valid-token")


# ---------------------------------------------------------------------------
# require_admin tests
# ---------------------------------------------------------------------------


class TestRequireAdmin:
    """Tests for the require_admin dependency."""

    async def test_admin_user_passes(self) -> None:
        admin_ctx = AuthContext(user_id="a1", email="admin@b.com", role="admin")
        result = await require_admin(admin_ctx)
        assert result is admin_ctx

    async def test_regular_user_raises_403(self) -> None:
        user_ctx = AuthContext(user_id="u1", email="user@b.com", role="user")
        with pytest.raises(ForbiddenError, match="permission"):
            await require_admin(user_ctx)


# ---------------------------------------------------------------------------
# require_active_license tests (Step 3)
# ---------------------------------------------------------------------------


class TestRequireActiveLicense:
    """Tests for the require_active_license dependency."""

    async def test_active_license_passes(self, mock_license_repo) -> None:
        ctx = AuthContext(user_id="u1", email="a@b.com", role="user")
        result = await require_active_license(ctx)
        assert result is ctx
        mock_license_repo.has_active_license.assert_awaited_once_with("u1")

    async def test_expired_license_raises_403(self, mock_license_repo) -> None:
        mock_license_repo.has_active_license.return_value = False
        ctx = AuthContext(user_id="u1", email="a@b.com", role="user")
        with pytest.raises(LicenseExpiredError):
            await require_active_license(ctx)


# ---------------------------------------------------------------------------
# require_sufficient_credits tests (Step 4)
# ---------------------------------------------------------------------------


class TestRequireSufficientCredits:
    """Tests for the require_sufficient_credits dependency."""

    async def test_sufficient_credits_passes(self, mock_credit_repo) -> None:
        ctx = AuthContext(user_id="u1", email="a@b.com", role="user")
        result = await require_sufficient_credits(ctx, required_credits=10)
        assert result is ctx
        mock_credit_repo.get_balance.assert_awaited_once_with("u1")

    async def test_insufficient_credits_raises_402(self, mock_credit_repo) -> None:
        mock_credit_repo.get_balance.return_value = 5
        ctx = AuthContext(user_id="u1", email="a@b.com", role="user")
        with pytest.raises(InsufficientCreditsError):
            await require_sufficient_credits(ctx, required_credits=10)

    async def test_zero_balance_raises_402(self, mock_credit_repo) -> None:
        mock_credit_repo.get_balance.return_value = 0
        ctx = AuthContext(user_id="u1", email="a@b.com", role="user")
        with pytest.raises(InsufficientCreditsError):
            await require_sufficient_credits(ctx, required_credits=1)


# ---------------------------------------------------------------------------
# check_credit_balance utility tests
# ---------------------------------------------------------------------------


class TestCheckCreditBalance:
    """Tests for the check_credit_balance utility function."""

    async def test_sufficient_balance_no_error(self, mock_credit_repo) -> None:
        await check_credit_balance("u1", required_credits=50)
        mock_credit_repo.get_balance.assert_awaited_once_with("u1")

    async def test_insufficient_balance_raises_402(self, mock_credit_repo) -> None:
        mock_credit_repo.get_balance.return_value = 3
        with pytest.raises(InsufficientCreditsError) as exc_info:
            await check_credit_balance("u1", required_credits=10)
        assert exc_info.value.details["balance"] == 3
        assert exc_info.value.details["required"] == 10


# ---------------------------------------------------------------------------
# require_generation_access composite tests (Steps 1-4)
# ---------------------------------------------------------------------------


class TestRequireGenerationAccess:
    """Tests for the full generation authorization chain."""

    async def test_all_checks_pass(self, mock_auth_service, mock_user_repo, mock_license_repo, mock_credit_repo) -> None:
        ctx = await require_generation_access("Bearer valid-token")
        assert ctx.user_id == "user-123"
        assert ctx.role == "user"
        mock_auth_service.validate_token.assert_awaited_once()
        mock_user_repo.get_status.assert_awaited_once()
        mock_license_repo.has_active_license.assert_awaited_once()
        mock_credit_repo.get_balance.assert_awaited_once()

    async def test_step1_invalid_token_raises_401(self, mock_auth_service) -> None:
        """Step 1: Token validity check fails first."""
        mock_auth_service.validate_token.side_effect = AuthenticationError("Invalid token.")
        with pytest.raises(AuthenticationError):
            await require_generation_access("Bearer bad")

    async def test_step2_suspended_raises_403_before_license_check(
        self, mock_user_repo, mock_license_repo
    ) -> None:
        """Step 2: Suspension check fails before license is checked (Req 16.4)."""
        mock_user_repo.get_status.return_value = "suspended"
        with pytest.raises(ForbiddenError, match="Account suspended"):
            await require_generation_access("Bearer valid-token")
        # License should NOT be checked since suspension fails first
        mock_license_repo.has_active_license.assert_not_awaited()

    async def test_step3_expired_license_raises_403_before_credit_check(
        self, mock_license_repo, mock_credit_repo
    ) -> None:
        """Step 3: License check fails before credit check (Req 16.7 order)."""
        mock_license_repo.has_active_license.return_value = False
        with pytest.raises(LicenseExpiredError):
            await require_generation_access("Bearer valid-token")
        # Credit should NOT be checked since license fails first
        mock_credit_repo.get_balance.assert_not_awaited()

    async def test_step4_insufficient_credits_raises_402(self, mock_credit_repo) -> None:
        """Step 4: Credit balance check fails last."""
        mock_credit_repo.get_balance.return_value = 0
        with pytest.raises(InsufficientCreditsError):
            await require_generation_access("Bearer valid-token")

    async def test_authorization_order_is_strict(
        self, mock_auth_service, mock_user_repo, mock_license_repo, mock_credit_repo
    ) -> None:
        """All checks should fail in order: 401 → 403(suspension) → 403(license) → 402."""
        # When token is invalid, nothing else is checked
        mock_auth_service.validate_token.side_effect = AuthenticationError("Bad")
        mock_user_repo.get_status.return_value = "suspended"
        mock_license_repo.has_active_license.return_value = False
        mock_credit_repo.get_balance.return_value = 0

        with pytest.raises(AuthenticationError):
            await require_generation_access("Bearer bad")
        mock_user_repo.get_status.assert_not_awaited()
        mock_license_repo.has_active_license.assert_not_awaited()
        mock_credit_repo.get_balance.assert_not_awaited()
