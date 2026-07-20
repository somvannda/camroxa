"""Tests for the public desktop release endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.services.desktop_notification_admin_service import SoftwareUpdateConfig


@pytest.fixture
def app():
    application = create_app()
    yield application


class TestPublicDesktopRelease:
    async def test_returns_published_release(self, app) -> None:
        published = SoftwareUpdateConfig(
            version="2.5.0",
            download_url="https://cdn.example.com/CamxoraSetup-2.5.0.exe",
            mandatory=True,
            release_notes="Bug fixes and performance improvements.",
            published_at="2026-07-19T03:00:00+00:00",
        )
        with patch("platform_api.routers.public_desktop.get_db_pool", return_value=object()), patch(
            "platform_api.routers.public_desktop.get_published_desktop_release",
            new=AsyncMock(return_value=published),
        ), patch(
            "platform_api.routers.public_desktop.get_download_count_for_version",
            new=AsyncMock(return_value=7),
        ), patch(
            "platform_api.routers.public_desktop.get_total_downloads",
            new=AsyncMock(return_value=42),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/public/desktop-release")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload == {
            "version": "2.5.0",
            "download_url": "https://cdn.example.com/CamxoraSetup-2.5.0.exe",
            "release_notes": "Bug fixes and performance improvements.",
            "mandatory": True,
            "published_at": "2026-07-19T03:00:00+00:00",
            "download_count": 7,
            "total_downloads": 42,
        }

    async def test_returns_404_when_not_published(self, app) -> None:
        with patch("platform_api.routers.public_desktop.get_db_pool", return_value=object()), patch(
            "platform_api.routers.public_desktop.get_published_desktop_release",
            new=AsyncMock(return_value=None),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/public/desktop-release")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "No published desktop release is available."
