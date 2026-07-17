from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.image_jobs import _get_batch_service, _get_image_job_service

USER_CONTEXT = AuthContext(user_id=str(uuid4()), email="user@example.com", role="user")


@pytest.fixture
def mock_image_job_service() -> AsyncMock:
    service = AsyncMock()
    service.list_jobs = AsyncMock(return_value=[])
    service.run_pending_jobs = AsyncMock(return_value=0)
    service.retry_jobs = AsyncMock(return_value=0)
    service.clear_jobs = AsyncMock(return_value=0)
    return service


@pytest.fixture
def mock_batch_service() -> AsyncMock:
    service = AsyncMock()
    service.enqueue_image_jobs_for_batches = AsyncMock(return_value=3)
    service.sync_manual_assets_for_batch = AsyncMock(return_value=4)
    service.refresh_image_job_prompts_for_retry = AsyncMock(return_value=1)
    return service


@pytest.fixture
def app(mock_image_job_service: AsyncMock, mock_batch_service: AsyncMock):
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: USER_CONTEXT
    application.dependency_overrides[_get_image_job_service] = lambda: mock_image_job_service
    application.dependency_overrides[_get_batch_service] = lambda: mock_batch_service
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_image_jobs(client: AsyncClient, mock_image_job_service: AsyncMock) -> None:
    response = await client.get("/api/v1/image-jobs?limit=5")
    assert response.status_code == 200
    mock_image_job_service.list_jobs.assert_awaited_once()


@pytest.mark.asyncio
async def test_enqueue_image_jobs(client: AsyncClient, mock_batch_service: AsyncMock) -> None:
    response = await client.post(
        "/api/v1/image-jobs/enqueue",
        json={"batch_ids": ["00000000-0000-0000-0000-000000000123"]},
    )
    assert response.status_code == 200
    assert response.json()["created"] == 3
    mock_batch_service.enqueue_image_jobs_for_batches.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_image_jobs_schedules_background_task(
    client: AsyncClient,
) -> None:
    with patch(
        "platform_api.routers.image_jobs._run_image_jobs_with_logging",
        new_callable=AsyncMock,
    ) as runner:
        response = await client.post(
            "/api/v1/image-jobs/run",
            json={"batch_id": "00000000-0000-0000-0000-000000000123", "limit": 2},
        )
        assert response.status_code == 202
        await asyncio.sleep(0)
        runner.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_manual_image_jobs(client: AsyncClient, mock_batch_service: AsyncMock) -> None:
    response = await client.post(
        "/api/v1/image-jobs/sync-manual",
        json={"batch_id": "00000000-0000-0000-0000-000000000123"},
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 4
    mock_batch_service.sync_manual_assets_for_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_image_jobs_by_batch(
    client: AsyncClient,
    mock_image_job_service: AsyncMock,
    mock_batch_service: AsyncMock,
) -> None:
    mock_image_job_service.retry_jobs = AsyncMock(return_value=2)
    with patch(
        "platform_api.routers.image_jobs._run_image_jobs_with_logging",
        new_callable=AsyncMock,
    ) as runner:
        response = await client.post(
            "/api/v1/image-jobs/retry",
            json={"batch_id": "00000000-0000-0000-0000-000000000123"},
        )
        assert response.status_code == 200
        assert response.json()["updated"] == 2
        mock_batch_service.refresh_image_job_prompts_for_retry.assert_awaited_once()
        mock_image_job_service.retry_jobs.assert_awaited_once()
        await asyncio.sleep(0)
        runner.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_image_jobs_by_job_ids(
    client: AsyncClient,
    mock_image_job_service: AsyncMock,
    mock_batch_service: AsyncMock,
) -> None:
    mock_image_job_service.retry_jobs = AsyncMock(return_value=1)
    mock_image_job_service.list_jobs = AsyncMock(
        return_value=[
            SimpleNamespace(
                id="00000000-0000-0000-0000-000000000456",
                batch_id="00000000-0000-0000-0000-000000000123",
            )
        ]
    )
    with patch(
        "platform_api.routers.image_jobs._run_image_jobs_with_logging",
        new_callable=AsyncMock,
    ) as runner:
        response = await client.post(
            "/api/v1/image-jobs/retry",
            json={"job_ids": ["00000000-0000-0000-0000-000000000456"]},
        )
        assert response.status_code == 200
        assert response.json()["updated"] == 1
        mock_batch_service.refresh_image_job_prompts_for_retry.assert_awaited_once()
        mock_image_job_service.retry_jobs.assert_awaited_once()
        await asyncio.sleep(0)
        runner.assert_awaited_once()
