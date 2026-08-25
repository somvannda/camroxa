"""Integration tests for platform API login."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from shared.models.auth import AuthTokens, ProfileResponse, TokenResponse, UserMeResponse
from shared.services.platform_client import PlatformApiError
from shared.services.secure_storage import SecureStorage
from shared.services.session_service import BootstrapDestination, SessionService


@pytest.fixture
def temp_storage(tmp_path) -> SecureStorage:
    path = tmp_path / "store.json"
    return SecureStorage(store_path=path)


def test_login_success_routes_to_app_home(temp_storage: SecureStorage) -> None:
    session = SessionService(storage=temp_storage)
    mock_api = MagicMock()
    mock_api.login.return_value = TokenResponse(
        access_token="access",
        refresh_token="refresh",
        token_type="bearer",
        expires_in=3600,
    )
    mock_api.get_me.return_value = UserMeResponse(
        id="u1",
        email="user@test.com",
        email_confirmed=True,
        display_name="User",
        credit_balance=100,
        plan_name="starter_monthly",
        onboarding_paid=True,
        profile_allowance=5,
        channel_profile_count=1,
    )
    mock_api.list_profiles.return_value = [
        ProfileResponse(id="p1", user_id="u1", name="Main"),
    ]
    session._api = mock_api  # noqa: SLF001

    result = session.login("user@test.com", "password123")

    assert result.destination == BootstrapDestination.APP_HOME
    assert session.get_tokens() is not None
    mock_api.login.assert_called_once_with("user@test.com", "password123")


def test_login_free_plan_stays_on_login_with_upgrade_message(temp_storage: SecureStorage) -> None:
    from shared.lib.desktop_entitlement import DESKTOP_REQUIRES_PAID_PLAN_MESSAGE

    session = SessionService(storage=temp_storage)
    mock_api = MagicMock()
    mock_api.login.return_value = TokenResponse(
        access_token="access",
        refresh_token="refresh",
        token_type="bearer",
        expires_in=3600,
    )
    mock_api.get_me.return_value = UserMeResponse(
        id="u1",
        email="user@test.com",
        email_confirmed=True,
        display_name="User",
        credit_balance=50,
        plan_name="Free",
        onboarding_paid=False,
        profile_allowance=1,
        channel_profile_count=0,
    )
    session._api = mock_api  # noqa: SLF001

    result = session.login("user@test.com", "password123")

    assert result.destination == BootstrapDestination.LOGIN
    assert result.message == DESKTOP_REQUIRES_PAID_PLAN_MESSAGE
    assert session.get_tokens() is None


def test_login_v3_403_desktop_plan_required(temp_storage: SecureStorage) -> None:
    from shared.lib.desktop_entitlement import DESKTOP_REQUIRES_PAID_PLAN_MESSAGE

    session = SessionService(storage=temp_storage)
    mock_api = MagicMock()
    mock_api.login.side_effect = PlatformApiError(
        403,
        "Desktop studio requires a paid plan. Choose Starter, Creator, or Studio on the web.",
        payload={"error": {"code": "DESKTOP_PLAN_REQUIRED"}},
    )
    session._api = mock_api  # noqa: SLF001

    with pytest.raises(PlatformApiError, match="paid plan"):
        session.login("user@test.com", "password123")

    assert session.get_tokens() is None
    # AuthWorker maps this exception to LOGIN + the popup message.
    assert "DESKTOP_PLAN_REQUIRED" not in DESKTOP_REQUIRES_PAID_PLAN_MESSAGE


def test_bootstrap_get_me_403_opens_login_with_plan_message(temp_storage: SecureStorage) -> None:
    from shared.lib.desktop_entitlement import DESKTOP_REQUIRES_PAID_PLAN_MESSAGE

    session = SessionService(storage=temp_storage)
    mock_api = MagicMock()
    mock_api.get_me.side_effect = PlatformApiError(
        403,
        "Desktop studio requires a paid plan. Choose Starter, Creator, or Studio on the web.",
        payload={"error": {"code": "DESKTOP_PLAN_REQUIRED"}},
    )
    session._api = mock_api  # noqa: SLF001
    session.set_tokens(
        AuthTokens(
            accessToken="access",
            refreshToken="refresh",
            tokenType="bearer",
            expiresAt=9_999_999_999_000,
        )
    )

    result = session.run_bootstrap()

    assert result.destination == BootstrapDestination.LOGIN
    assert result.message == DESKTOP_REQUIRES_PAID_PLAN_MESSAGE
    assert session.get_tokens() is None


def test_login_invalid_credentials(temp_storage: SecureStorage) -> None:
    session = SessionService(storage=temp_storage)
    mock_api = MagicMock()
    mock_api.login.side_effect = PlatformApiError(401, "Invalid email or password.")
    session._api = mock_api  # noqa: SLF001

    with pytest.raises(PlatformApiError, match="Invalid email or password"):
        session.login("user@test.com", "wrongpass1")


def test_api_health_url() -> None:
    from shared.services.api_health import health_url_for_api_base

    assert health_url_for_api_base("http://localhost:8000/api/v3") == "http://localhost:8000/health"
