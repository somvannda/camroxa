from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.repositories.image_sample_pack_repo import ImageSamplePackRecord
from platform_api.routers.admin_image_sample_packs import (
    _get_image_sample_pack_repo as admin_get_repo,
)
from platform_api.routers.image_sample_packs import _get_image_sample_pack_repo as user_get_repo


USER_CONTEXT = AuthContext(user_id=str(uuid4()), email="user@example.com", role="user")
ADMIN_CONTEXT = AuthContext(user_id=str(uuid4()), email="admin@example.com", role="admin")


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.list_for_user = AsyncMock(return_value=[])
    repo.list_all = AsyncMock(return_value=[])
    repo.create = AsyncMock(return_value=None)
    repo.update = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def app(mock_repo: AsyncMock):
    application = create_app()
    application.dependency_overrides[user_get_repo] = lambda: mock_repo
    application.dependency_overrides[admin_get_repo] = lambda: mock_repo
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_image_sample_packs_for_user(client: AsyncClient, app, mock_repo: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = lambda: USER_CONTEXT
    response = await client.get("/api/v1/image-sample-packs")
    assert response.status_code == 200
    mock_repo.list_for_user.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_crud_image_sample_packs(client: AsyncClient, app, mock_repo: AsyncMock) -> None:
    app.dependency_overrides[require_admin] = lambda: ADMIN_CONTEXT

    created = ImageSamplePackRecord(
        id=str(uuid4()),
        category="background",
        name="Default Pack",
        source_type="google_drive",
        source_value="file-id",
        is_active=True,
        sort_order=0,
    )
    mock_repo.create = AsyncMock(return_value=created)
    response = await client.post(
        "/api/v1/admin/image-sample-packs",
        json={
            "category": "background",
            "name": "Default Pack",
            "source_type": "google_drive",
            "source_value": "file-id",
            "is_active": True,
            "sort_order": 0,
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Default Pack"

    mock_repo.create = AsyncMock(return_value=created)
    response = await client.post(
        "/api/v1/admin/image-sample-packs",
        json={
            "category": "thumbnail",
            "name": "Upload Only Pack",
            "is_active": True,
            "sort_order": 1,
        },
    )
    assert response.status_code == 200
    mock_repo.create.assert_awaited()

    mock_repo.update = AsyncMock(return_value=created)
    response = await client.patch(
        f"/api/v1/admin/image-sample-packs/{created.id}",
        json={"notes": "updated"},
    )
    assert response.status_code == 200

    response = await client.delete(f"/api/v1/admin/image-sample-packs/{created.id}")
    assert response.status_code == 200
    assert response.json()["ok"] is True
