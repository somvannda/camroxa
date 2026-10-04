"""Tests for the admin key-pool router host-switching contract.

Covers the request/response surface added for reversible provider switching:
per-key ``base_url`` on add, and the provider config's active host (``base_url``
/ ``clear_base_url``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.models.domain import ApiKeyEntry, KeyPoolConfig
from platform_api.models.enums import KeyStatus, SelectionStrategy
from platform_api.routers.key_pool import _get_key_pool_service

ADMIN = AuthContext(user_id=str(uuid4()), email="admin@example.com", role="admin")
NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def _fake_service() -> MagicMock:
    service = MagicMock()
    service.add_key = AsyncMock(return_value=uuid4())
    service.update_key = AsyncMock()
    service.configure_provider = AsyncMock()

    entry = ApiKeyEntry(
        id=uuid4(),
        provider="suno",
        label="musicapi-1",
        encrypted_key_value=b"enc::mk_x",
        priority=10,
        status=KeyStatus.ACTIVE,
        base_url="https://musicapi.camxora.com",
        created_at=NOW,
    )
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=entry)
    repo.get_provider_config = AsyncMock(
        return_value=KeyPoolConfig(
            provider="suno",
            selection_strategy=SelectionStrategy.PRIORITY,
            cooldown_seconds=60,
            base_url="https://musicapi.camxora.com",
        )
    )
    service._repo = repo

    encryption = MagicMock()
    encryption.decrypt = MagicMock(return_value="mk_secret_value_1234")
    service._encryption = encryption
    return service


@pytest.fixture
def app():
    application = create_app()
    service = _fake_service()
    application.dependency_overrides[require_admin] = lambda: ADMIN
    application.dependency_overrides[_get_key_pool_service] = lambda: service
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_add_key_accepts_and_returns_base_url(client: AsyncClient, app) -> None:
    service = app.dependency_overrides[_get_key_pool_service]()

    resp = await client.post(
        "/api/v3/admin/key-pool/suno/keys",
        json={
            "key_value": "mk_x",
            "label": "musicapi-1",
            "priority": 10,
            "base_url": "https://musicapi.camxora.com",
        },
    )

    assert resp.status_code == 201
    assert resp.json()["base_url"] == "https://musicapi.camxora.com"
    assert service.add_key.call_args.kwargs["base_url"] == "https://musicapi.camxora.com"


@pytest.mark.asyncio
async def test_update_provider_config_sets_active_host(client: AsyncClient, app) -> None:
    service = app.dependency_overrides[_get_key_pool_service]()

    resp = await client.put(
        "/api/v3/admin/key-pool/suno/config",
        json={
            "selection_strategy": "priority",
            "cooldown_seconds": 60,
            "base_url": "https://musicapi.camxora.com",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["base_url"] == "https://musicapi.camxora.com"
    kwargs = service.configure_provider.call_args.kwargs
    assert kwargs["base_url"] == "https://musicapi.camxora.com"
    assert kwargs["clear_base_url"] is False


@pytest.mark.asyncio
async def test_update_provider_config_clears_active_host(client: AsyncClient, app) -> None:
    service = app.dependency_overrides[_get_key_pool_service]()

    resp = await client.put(
        "/api/v3/admin/key-pool/suno/config",
        json={
            "selection_strategy": "priority",
            "cooldown_seconds": 60,
            "clear_base_url": True,
        },
    )

    assert resp.status_code == 200
    assert resp.json()["base_url"] is None
    assert service.configure_provider.call_args.kwargs["clear_base_url"] is True


@pytest.mark.asyncio
async def test_get_provider_config_returns_active_host(client: AsyncClient) -> None:
    resp = await client.get("/api/v3/admin/key-pool/suno/config")

    assert resp.status_code == 200
    assert resp.json()["base_url"] == "https://musicapi.camxora.com"
