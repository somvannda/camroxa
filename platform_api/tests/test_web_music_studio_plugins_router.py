"""Web routes for the Suno agent plugin authoring proxy (S45)."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.web_music import _get_web_music_service


@pytest.fixture
def service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(service: AsyncMock) -> AsyncClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthContext(
        user_id=str(uuid4()), email="designer@example.com", role="user"
    )
    app.dependency_overrides[_get_web_music_service] = lambda: service
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_author_route_forwards_the_prompt(client: AsyncClient, service: AsyncMock) -> None:
    service.author_studio_plugin = AsyncMock(return_value={"job_id": "job-1", "status": "pending"})
    project_id = uuid4()

    async with client:
        response = await client.post(
            f"/api/v3/web-music/studio/projects/{project_id}/plugins/author",
            json={
                "instruction": "a warm tape saturation with a low cut",
                "required_controls": ["Drive", "Low Cut"],
            },
        )

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-1"
    call = service.author_studio_plugin.await_args
    assert call.args[1] == project_id
    assert call.kwargs["instruction"] == "a warm tape saturation with a low cut"
    assert call.kwargs["required_controls"] == ["Drive", "Low Cut"]


@pytest.mark.asyncio
async def test_author_route_rejects_an_empty_prompt(client: AsyncClient, service: AsyncMock) -> None:
    service.author_studio_plugin = AsyncMock()
    async with client:
        response = await client.post(
            f"/api/v3/web-music/studio/projects/{uuid4()}/plugins/author",
            json={"instruction": ""},
        )
    assert response.status_code == 422
    service.author_studio_plugin.assert_not_awaited()


@pytest.mark.asyncio
async def test_job_route_forwards_the_job_id(client: AsyncClient, service: AsyncMock) -> None:
    service.studio_plugin_authoring_job = AsyncMock(
        return_value={"job_id": "job-1", "status": "ready", "plugin_id": "p1"}
    )
    project_id = uuid4()

    async with client:
        response = await client.get(
            f"/api/v3/web-music/studio/projects/{project_id}/plugins/author/job-1"
        )

    assert response.status_code == 200
    assert response.json()["plugin_id"] == "p1"
    call = service.studio_plugin_authoring_job.await_args
    assert call.args[1] == project_id
    assert call.args[2] == "job-1"
