"""S04 routes: restore is scoped to the caller's own projects."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.exceptions import NotFoundError
from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.web_music import _get_web_music_service

USER_ID = uuid4()


@pytest.fixture
def service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(service: AsyncMock) -> AsyncClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthContext(
        user_id=str(USER_ID), email="designer@example.com", role="user"
    )
    app.dependency_overrides[_get_web_music_service] = lambda: service
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_restore_route_returns_the_restored_card(
    client: AsyncClient, service: AsyncMock
) -> None:
    project_id = uuid4()
    service.restore_studio_project = AsyncMock(
        return_value={"id": str(project_id), "title": "Back", "deleted_at": None}
    )

    async with client:
        response = await client.post(
            f"/api/v3/web-music/studio/projects/{project_id}/restore"
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(project_id)
    call = service.restore_studio_project.await_args
    # Ownership comes from the token, never from the URL or body.
    assert call.args == (UUID(str(USER_ID)), project_id)


@pytest.mark.asyncio
async def test_restore_route_is_a_404_for_someone_elses_project(
    client: AsyncClient, service: AsyncMock
) -> None:
    service.restore_studio_project = AsyncMock(
        side_effect=NotFoundError("Deleted Studio project not found.")
    )

    async with client:
        response = await client.post(
            f"/api/v3/web-music/studio/projects/{uuid4()}/restore"
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_route_soft_deletes_without_a_body(
    client: AsyncClient, service: AsyncMock
) -> None:
    project_id = uuid4()
    service.delete_studio_project = AsyncMock(return_value=None)

    async with client:
        response = await client.delete(
            f"/api/v3/web-music/studio/projects/{project_id}"
        )

    assert response.status_code == 204
    assert response.content == b""
    assert service.delete_studio_project.await_args.args == (
        UUID(str(USER_ID)),
        project_id,
    )
