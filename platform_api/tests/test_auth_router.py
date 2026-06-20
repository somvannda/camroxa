"""Tests for the auth router endpoints (platform_api.routers.auth)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.exceptions import AuthenticationError, AccountLockedError
from platform_api.main import create_app
from platform_api.models.domain import User
from platform_api.models.enums import UserRole, UserStatus
from platform_api.ports.auth_port import TokenPair, TokenPayload
from platform_api.routers.auth import _get_auth_service, _get_lockout, _get_current_user_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_auth_service() -> AsyncMock:
    """Create a mock auth service with common defaults."""
    service = AsyncMock()
    service._user_repo = AsyncMock()
    service._user_repo.get_by_email = AsyncMock(return_value=None)
    service.authenticate = AsyncMock(
        return_value=TokenPair(
            access_token="access.token.here",
            refresh_token="refresh.token.here",
            expires_in=1800,
        )
    )
    service.refresh_token = AsyncMock(
        return_value=TokenPair(
            access_token="new.access.token",
            refresh_token="new.refresh.token",
            expires_in=1800,
        )
    )
    service.revoke_tokens = AsyncMock(return_value=None)
    service.hash_password = lambda pwd: f"hashed_{pwd}"
    return service


@pytest.fixture
def mock_lockout() -> AsyncMock:
    """Create a mock lockout service."""
    lockout = AsyncMock()
    lockout.check_lockout = AsyncMock(return_value=None)
    lockout.record_failed_attempt = AsyncMock(return_value=None)
    lockout.reset_failures = AsyncMock(return_value=None)
    return lockout


@pytest.fixture
def app(mock_auth_service: AsyncMock, mock_lockout: AsyncMock):
    """Create a test app with dependency overrides."""
    application = create_app()
    application.dependency_overrides[_get_auth_service] = lambda: mock_auth_service
    application.dependency_overrides[_get_lockout] = lambda: mock_lockout
    application.dependency_overrides[_get_current_user_id] = lambda: "user-123"
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    async def test_login_success(
        self, client: AsyncClient, mock_auth_service: AsyncMock, mock_lockout: AsyncMock
    ) -> None:
        """Successful login returns token pair."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "ValidPass1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "access.token.here"
        assert data["refresh_token"] == "refresh.token.here"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 1800

        # Verify lockout integration
        mock_lockout.check_lockout.assert_awaited_once_with("user@example.com")
        mock_lockout.reset_failures.assert_awaited_once_with("user@example.com")

    async def test_login_invalid_credentials(
        self, client: AsyncClient, mock_auth_service: AsyncMock, mock_lockout: AsyncMock
    ) -> None:
        """Invalid credentials returns 401 and records failed attempt."""
        mock_auth_service.authenticate.side_effect = AuthenticationError("Invalid credentials.")

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "WrongPass1"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"

        # Verify failed attempt was recorded
        mock_lockout.record_failed_attempt.assert_awaited_once_with("user@example.com")
        mock_lockout.reset_failures.assert_not_awaited()

    async def test_login_account_locked(
        self, client: AsyncClient, mock_lockout: AsyncMock
    ) -> None:
        """Locked account returns 403."""
        mock_lockout.check_lockout.side_effect = AccountLockedError()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "locked@example.com", "password": "ValidPass1"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ACCOUNT_LOCKED"


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    async def test_register_success(
        self, client: AsyncClient, mock_auth_service: AsyncMock
    ) -> None:
        """Valid registration returns 201 with user info."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "ValidPass1",
                "display_name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["display_name"] == "New User"
        assert "id" in data

    async def test_register_duplicate_email(
        self, client: AsyncClient, mock_auth_service: AsyncMock
    ) -> None:
        """Duplicate email returns 409."""
        mock_auth_service._user_repo.get_by_email.return_value = User(
            email="existing@example.com"
        )

        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "existing@example.com",
                "password": "ValidPass1",
                "display_name": "Existing User",
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "DUPLICATE_ERROR"

    async def test_register_password_too_short(self, client: AsyncClient) -> None:
        """Password below 8 chars returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "Short1",
                "display_name": "User",
            },
        )
        assert response.status_code == 422

    async def test_register_password_missing_uppercase(self, client: AsyncClient) -> None:
        """Password without uppercase returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "lowercase1",
                "display_name": "User Name",
            },
        )
        assert response.status_code == 422

    async def test_register_password_missing_lowercase(self, client: AsyncClient) -> None:
        """Password without lowercase returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "UPPERCASE1",
                "display_name": "User Name",
            },
        )
        assert response.status_code == 422

    async def test_register_password_missing_digit(self, client: AsyncClient) -> None:
        """Password without digit returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "NoDigitHere",
                "display_name": "User Name",
            },
        )
        assert response.status_code == 422

    async def test_register_returns_all_errors(self, client: AsyncClient) -> None:
        """Multiple validation failures should all be returned at once (Property 4)."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "nouppercase",  # missing uppercase + digit
                "display_name": "X",  # too short
            },
        )
        assert response.status_code == 422
        data = response.json()
        details = data["error"]["details"]
        fields_with_errors = [e["field"] for e in details["fields"]]
        # Both password and display_name should have errors
        assert "password" in fields_with_errors
        assert "display_name" in fields_with_errors

    async def test_register_display_name_too_short(self, client: AsyncClient) -> None:
        """Display name below 2 chars returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "ValidPass1",
                "display_name": "X",
            },
        )
        assert response.status_code == 422

    async def test_register_display_name_too_long(self, client: AsyncClient) -> None:
        """Display name above 50 chars returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "ValidPass1",
                "display_name": "A" * 51,
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    """Tests for POST /api/v1/auth/refresh."""

    async def test_refresh_success(
        self, client: AsyncClient, mock_auth_service: AsyncMock
    ) -> None:
        """Valid refresh token returns new token pair."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "valid.refresh.token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new.access.token"
        assert data["refresh_token"] == "new.refresh.token"
        assert data["expires_in"] == 1800

    async def test_refresh_invalid_token(
        self, client: AsyncClient, mock_auth_service: AsyncMock
    ) -> None:
        """Invalid refresh token returns 401."""
        mock_auth_service.refresh_token.side_effect = AuthenticationError(
            "Refresh token has expired."
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "expired.token"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    async def test_logout_success(
        self, client: AsyncClient, mock_auth_service: AsyncMock
    ) -> None:
        """Logout revokes tokens and returns 200."""
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer valid.token"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out."
        mock_auth_service.revoke_tokens.assert_awaited_once_with("user-123")
