from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.image_jobs import (
    _get_batch_service,
    _get_image_job_service,
    _get_job_queue_repo,
)
from platform_api.services.job_types import JOB_RUN_IMAGE_JOBS

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
def mock_job_queue() -> AsyncMock:
    queue = AsyncMock()
    queue.enqueue_if_absent = AsyncMock(return_value=(SimpleNamespace(id=uuid4()), True))
    return queue


@pytest.fixture
def app(
    mock_image_job_service: AsyncMock,
    mock_batch_service: AsyncMock,
    mock_job_queue: AsyncMock,
):
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: USER_CONTEXT
    application.dependency_overrides[_get_image_job_service] = lambda: mock_image_job_service
    application.dependency_overrides[_get_batch_service] = lambda: mock_batch_service
    application.dependency_overrides[_get_job_queue_repo] = lambda: mock_job_queue
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
async def test_run_image_jobs_enqueues_worker_job(
    client: AsyncClient,
    mock_job_queue: AsyncMock,
) -> None:
    response = await client.post(
        "/api/v1/image-jobs/run",
        json={"batch_id": "00000000-0000-0000-0000-000000000123", "limit": 2},
    )
    assert response.status_code == 202
    mock_job_queue.enqueue_if_absent.assert_awaited_once()
    kwargs = mock_job_queue.enqueue_if_absent.await_args.kwargs
    assert kwargs["job_type"] == JOB_RUN_IMAGE_JOBS
    assert kwargs["payload"]["batch_id"] == "00000000-0000-0000-0000-000000000123"


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
    mock_job_queue: AsyncMock,
) -> None:
    mock_image_job_service.retry_jobs = AsyncMock(return_value=2)
    response = await client.post(
        "/api/v1/image-jobs/retry",
        json={"batch_id": "00000000-0000-0000-0000-000000000123"},
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 2
    mock_batch_service.refresh_image_job_prompts_for_retry.assert_awaited_once()
    mock_image_job_service.retry_jobs.assert_awaited_once()
    mock_job_queue.enqueue_if_absent.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_image_jobs_by_job_ids(
    client: AsyncClient,
    mock_image_job_service: AsyncMock,
    mock_batch_service: AsyncMock,
    mock_job_queue: AsyncMock,
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
    response = await client.post(
        "/api/v1/image-jobs/retry",
        json={"job_ids": ["00000000-0000-0000-0000-000000000456"]},
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 1
    mock_batch_service.refresh_image_job_prompts_for_retry.assert_awaited_once()
    mock_image_job_service.retry_jobs.assert_awaited_once()
    mock_job_queue.enqueue_if_absent.assert_awaited_once()
