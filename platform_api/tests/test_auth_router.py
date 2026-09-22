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
from platform_api.routers.auth import (
    _get_auth_service,
    _get_invitation_code_service,
    _get_license_repo,
    _get_lockout,
    _get_current_user_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_auth_service() -> AsyncMock:
    """Create a mock auth service with common defaults."""
    service = AsyncMock()
    service._user_repo = AsyncMock()
    service._user_repo.get_by_email = AsyncMock(return_value=None)
    service._user_repo.create = AsyncMock(
        return_value=User(
            id=uuid4(),
            email="new@example.com",
            display_name="New User",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
    )
    service._user_repo.add_product = AsyncMock(return_value=None)
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
    service.issue_token_pair_for_user = AsyncMock(
        return_value=TokenPair(
            access_token="access.token.here",
            refresh_token="refresh.token.here",
            expires_in=1800,
        )
    )
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
def mock_invitation() -> AsyncMock:
    service = AsyncMock()
    service.get_signup_mode = AsyncMock(return_value="open")
    service.consume_invitation_code = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_license_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.has_paid_desktop_access = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def app(
    mock_auth_service: AsyncMock,
    mock_lockout: AsyncMock,
    mock_invitation: AsyncMock,
    mock_license_repo: AsyncMock,
):
    """Create a test app with dependency overrides."""
    from platform_api.middleware.auth import AuthContext, get_current_user

    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: AuthContext(
        user_id="user-123", email="user@example.com", role="user"
    )
    application.dependency_overrides[_get_auth_service] = lambda: mock_auth_service
    application.dependency_overrides[_get_lockout] = lambda: mock_lockout
    application.dependency_overrides[_get_invitation_code_service] = lambda: mock_invitation
    application.dependency_overrides[_get_license_repo] = lambda: mock_license_repo
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

    async def test_desktop_login_blocks_free_user(
        self,
        client: AsyncClient,
        mock_auth_service: AsyncMock,
        mock_license_repo: AsyncMock,
    ) -> None:
        user_id = uuid4()
        mock_auth_service._user_repo.get_by_email = AsyncMock(
            return_value=User(
                id=user_id,
                email="free@example.com",
                display_name="Free User",
                role=UserRole.USER,
                status=UserStatus.ACTIVE,
            )
        )
        mock_license_repo.has_paid_desktop_access = AsyncMock(return_value=False)

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "free@example.com", "password": "ValidPass1"},
            headers={"X-Camxora-Client": "desktop"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DESKTOP_PLAN_REQUIRED"
        mock_license_repo.has_paid_desktop_access.assert_awaited_once_with(str(user_id))

    async def test_desktop_login_allows_paid_user(
        self,
        client: AsyncClient,
        mock_auth_service: AsyncMock,
        mock_license_repo: AsyncMock,
    ) -> None:
        user_id = uuid4()
        mock_auth_service._user_repo.get_by_email = AsyncMock(
            return_value=User(
                id=user_id,
                email="paid@example.com",
                display_name="Paid User",
                role=UserRole.USER,
                status=UserStatus.ACTIVE,
            )
        )
        mock_license_repo.has_paid_desktop_access = AsyncMock(return_value=True)

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "paid@example.com", "password": "ValidPass1"},
            headers={"X-Camxora-Client": "desktop"},
        )
        assert response.status_code == 200
        mock_license_repo.has_paid_desktop_access.assert_awaited_once_with(str(user_id))

    async def test_web_login_allows_free_user(
        self,
        client: AsyncClient,
        mock_license_repo: AsyncMock,
    ) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "free@example.com", "password": "ValidPass1"},
        )
        assert response.status_code == 200
        mock_license_repo.has_paid_desktop_access.assert_not_awaited()


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
        created_user = mock_auth_service._user_repo.create.await_args.args[0]
        assert created_user.products == ["studio"]

    async def test_register_music_web_skips_invite(
        self,
        client: AsyncClient,
        mock_auth_service: AsyncMock,
        mock_invitation: AsyncMock,
    ) -> None:
        from unittest.mock import patch

        mock_invitation.get_signup_mode = AsyncMock(return_value="invite_only")
        mock_pool = AsyncMock()
        mock_pool.execute = AsyncMock()
        with patch("platform_api.dependencies.get_db_pool", return_value=mock_pool), patch(
            "platform_api.services.email_service.send_verification_email"
        ):
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "listener@example.com",
                    "password": "ValidPass1",
                    "display_name": "Listener",
                    "product": "music_web",
                },
            )
        assert response.status_code == 201
        mock_invitation.consume_invitation_code.assert_not_awaited()
        created_user = mock_auth_service._user_repo.create.await_args.args[0]
        assert created_user.products == ["music_web"]

    async def test_register_music_web_requires_turnstile_when_configured(
        self,
        client: AsyncClient,
        mock_invitation: AsyncMock,
    ) -> None:
        from unittest.mock import patch

        mock_invitation.get_signup_mode = AsyncMock(return_value="invite_only")
        with patch("platform_api.routers.auth.get_settings") as mock_settings:
            mock_settings.return_value.cloudflare_turnstile_secret_key = "test-secret"
            mock_settings.return_value.cloudflare_turnstile_hostnames = ""
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "listener@example.com",
                    "password": "ValidPass1",
                    "display_name": "Listener",
                    "product": "music_web",
                },
            )
        assert response.status_code == 422

    async def test_register_studio_invite_only_requires_code(
        self,
        client: AsyncClient,
        mock_invitation: AsyncMock,
    ) -> None:
        mock_invitation.get_signup_mode = AsyncMock(return_value="invite_only")
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "studio@example.com",
                "password": "ValidPass1",
                "display_name": "Studio User",
            },
        )
        assert response.status_code == 422

    async def test_register_duplicate_email(
        self, client: AsyncClient, mock_auth_service: AsyncMock
    ) -> None:
        """Duplicate email returns 409."""
        mock_auth_service._user_repo.get_by_email.return_value = User(
            email="existing@example.com",
            display_name="Existing User",
            email_confirmed=True,
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

    async def test_register_rejects_special_char_email(self, client: AsyncClient) -> None:
        """Email whose local part uses characters no provider accepts (e.g. '*') is rejected.

        EmailStr accepts '******hheng@gmail.com' because '*' is legal RFC 5322
        atext — the pragmatic whitelist must catch it.
        """
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "******hheng@gmail.com",
                "password": "ValidPass1",
                "display_name": "Borey",
            },
        )
        assert response.status_code == 422
        data = response.json()
        details = data["error"]["details"]
        fields_with_errors = [e["field"] for e in details["fields"]]
        assert "email" in fields_with_errors

    async def test_register_accepts_plus_alias_and_dots(self, client: AsyncClient) -> None:
        """Common provider-style emails (plus alias, dotted, hyphen domain) still pass."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "borey.hheng+studio@gmail.com",
                "password": "ValidPass1",
                "display_name": "Borey",
            },
        )
        assert response.status_code == 201
        data = response.json()
        # The mocked user repo returns a fixed user, so the response echoes it.
        assert data["email"] == "new@example.com"


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


# ---------------------------------------------------------------------------
# POST /auth/verify-email
# ---------------------------------------------------------------------------


class TestVerifyEmail:
    """Tests for POST /api/v1/auth/verify-email (same handler as /api/v3)."""

    async def test_verify_email_issues_session_cookies(
        self, client: AsyncClient, mock_auth_service: AsyncMock
    ) -> None:
        from unittest.mock import patch

        user_id = uuid4()
        code_id = uuid4()
        mock_auth_service._user_repo.get_by_email = AsyncMock(
            return_value=User(
                id=user_id,
                email="new@example.com",
                display_name="New User",
                email_confirmed=True,
            )
        )

        class FakePool:
            async def fetchrow(self, query: str, *args: object):
                text = str(query)
                if "FROM users" in text:
                    return {"id": user_id, "email_confirmed": False}
                if "FROM email_verifications" in text:
                    return {"id": code_id}
                return None

            async def execute(self, *args: object, **kwargs: object):
                return None

        with patch("platform_api.dependencies.get_db_pool", return_value=FakePool()):
            response = await client.post(
                "/api/v1/auth/verify-email",
                json={"email": "new@example.com", "code": "123456"},
            )

        assert response.status_code == 200
        assert response.json()["is_verified"] is True
        assert "camxora_access_token" in response.cookies
        mock_auth_service.issue_token_pair_for_user.assert_awaited()

    async def test_verify_email_already_confirmed_without_code(
        self, client: AsyncClient, mock_auth_service: AsyncMock
    ) -> None:
        from unittest.mock import patch

        user_id = uuid4()

        class FakePool:
            async def fetchrow(self, query: str, *args: object):
                text = str(query)
                if "FROM users" in text:
                    return {"id": user_id, "email_confirmed": True}
                return None

            async def execute(self, *args: object, **kwargs: object):
                return None

        with patch("platform_api.dependencies.get_db_pool", return_value=FakePool()):
            response = await client.post(
                "/api/v1/auth/verify-email",
                json={"email": "duke@test.com", "code": "000000"},
            )

        assert response.status_code == 200
        assert response.json()["is_verified"] is True
        mock_auth_service.issue_token_pair_for_user.assert_not_called()
