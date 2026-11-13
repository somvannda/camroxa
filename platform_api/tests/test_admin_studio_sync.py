"""Admin proxy for the Studio mirror health payload."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from platform_api.routers import admin_studio_sync


def _settings(token: str = "t", base: str = "http://mirror") -> SimpleNamespace:
    return SimpleNamespace(studio_internal_token=token, suno_api_base_url=base)


@pytest.mark.asyncio
async def test_health_reports_unconfigured_without_a_token(monkeypatch) -> None:
    monkeypatch.setattr(admin_studio_sync, "get_settings", lambda: _settings(token=""))

    result = await admin_studio_sync.studio_sync_health(None)

    assert result == {"configured": False, "ok": False}


@pytest.mark.asyncio
async def test_health_forwards_the_mirror_payload(monkeypatch) -> None:
    monkeypatch.setattr(admin_studio_sync, "get_settings", lambda: _settings())
    response = MagicMock(status_code=200)
    response.json = MagicMock(
        return_value={"projects": {"synced": 2}, "outbox": {"due": 0, "total": 0}}
    )
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(admin_studio_sync.httpx, "AsyncClient", lambda **_: context)

    result = await admin_studio_sync.studio_sync_health(None)

    assert result["configured"] is True
    assert result["ok"] is True
    assert result["projects"] == {"synced": 2}


@pytest.mark.asyncio
async def test_health_survives_an_unreachable_mirror(monkeypatch) -> None:
    monkeypatch.setattr(admin_studio_sync, "get_settings", lambda: _settings())
    context = MagicMock()
    context.__aenter__ = AsyncMock(side_effect=RuntimeError("connection refused"))
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(admin_studio_sync.httpx, "AsyncClient", lambda **_: context)

    result = await admin_studio_sync.studio_sync_health(None)

    assert result == {"configured": True, "ok": False}
