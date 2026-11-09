"""Desktop Google sign-in hands off through the registered production callback.

The desktop studio reuses the exact same Google OAuth client and redirect URI as
music.camxora.com, so nothing has to be registered in Google Cloud Console for
the app. ``GET /auth/google/url?desktop_port=…`` keeps the https redirect and
puts the loopback port inside the signed state; the web callback page forwards
the browser to ``http://127.0.0.1:<port>/google/callback`` and only the desktop
exchanges the code (with the client secret, server-side).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.config import get_settings
from platform_api.main import create_app
from platform_api.services.email_link_tokens import (
    oauth_state_desktop_port,
    sign_oauth_state,
    verify_oauth_state,
)


@pytest.fixture
def google_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    monkeypatch.setenv("PLATFORM_GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv(
        "PLATFORM_GOOGLE_REDIRECT_URIS",
        "https://music.camxora.com/auth/callback",
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestOauthState:
    def test_desktop_port_round_trips(self) -> None:
        state = sign_oauth_state("https://music.camxora.com/auth/callback", desktop_port=41580)

        assert verify_oauth_state(state) == "https://music.camxora.com/auth/callback"
        assert oauth_state_desktop_port(state) == 41580

    def test_browser_state_has_no_desktop_port(self) -> None:
        state = sign_oauth_state("https://music.camxora.com/auth/callback")

        assert oauth_state_desktop_port(state) is None

    def test_out_of_range_port_is_ignored(self) -> None:
        assert oauth_state_desktop_port(sign_oauth_state("https://x/auth/callback", desktop_port=0)) is None
        assert (
            oauth_state_desktop_port(sign_oauth_state("https://x/auth/callback", desktop_port=70000)) is None
        )


class TestGoogleAuthUrlEndpoint:
    async def test_desktop_port_keeps_the_registered_https_redirect(
        self, client: AsyncClient, google_env: None
    ) -> None:
        response = await client.get("/api/v1/auth/google/url", params={"desktop_port": 41580})

        assert response.status_code == 200
        payload = response.json()
        assert "redirect_uri=https%3A%2F%2Fmusic.camxora.com%2Fauth%2Fcallback" in payload["url"]
        assert "127.0.0.1" not in payload["url"]
        assert oauth_state_desktop_port(payload["state"]) == 41580

    async def test_browser_signin_unchanged(self, client: AsyncClient, google_env: None) -> None:
        response = await client.get("/api/v1/auth/google/url")

        assert response.status_code == 200
        payload = response.json()
        assert "redirect_uri=https%3A%2F%2Fmusic.camxora.com%2Fauth%2Fcallback" in payload["url"]
        assert oauth_state_desktop_port(payload["state"]) is None

    @pytest.mark.parametrize("port", [0, 70000])
    async def test_invalid_port_is_rejected(
        self, client: AsyncClient, google_env: None, port: int
    ) -> None:
        response = await client.get("/api/v1/auth/google/url", params={"desktop_port": port})

        assert response.status_code == 422

    async def test_loopback_redirect_is_still_rejected(
        self, client: AsyncClient, google_env: None
    ) -> None:
        response = await client.get(
            "/api/v1/auth/google/url",
            params={"redirect_uri": "http://127.0.0.1:41580/google/callback"},
        )

        assert response.status_code == 422

    async def test_unconfigured_google_returns_503(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLATFORM_GOOGLE_CLIENT_ID", "")
        monkeypatch.setenv("PLATFORM_GOOGLE_CLIENT_SECRET", "")
        get_settings.cache_clear()
        try:
            response = await client.get("/api/v1/auth/google/url")
        finally:
            get_settings.cache_clear()

        assert response.status_code == 503
