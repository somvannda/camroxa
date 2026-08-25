"""Integration tests for platform API login."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from shared.models.auth import ProfileResponse, TokenResponse, UserMeResponse
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
        plan_name="Pro",
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
