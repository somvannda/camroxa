from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.config import get_settings
from platform_api.routers.callbacks import (
    _get_batch_service,
    _get_image_job_service,
    _get_notification_port,
    _get_suno_task_repo,
)


@pytest.fixture
def ids() -> dict[str, str]:
    return {
        "user_id": str(uuid4()),
        "batch_id": str(uuid4()),
        "song_id": str(uuid4()),
        "task_id": str(uuid4()),
        "external_task_id": "ext-task-123",
    }


@pytest.fixture
def mock_task_repo(ids: dict[str, str]) -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_external_id = AsyncMock(
        return_value={
            "id": ids["task_id"],
            "user_id": ids["user_id"],
            "song_id": ids["song_id"],
            "batch_id": ids["batch_id"],
        }
    )
    repo.update_status = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_notification() -> AsyncMock:
    port = AsyncMock()
    port.push = AsyncMock(return_value=None)
    port.queue = AsyncMock(return_value=None)
    return port


@pytest.fixture
def mock_batch_service() -> AsyncMock:
    svc = AsyncMock()
    svc.handle_suno_task_update = AsyncMock(return_value=[])
    svc.get_batch_for_user = AsyncMock(return_value=SimpleNamespace(auto_gen_image=True))
    return svc


@pytest.fixture
def mock_image_job_service() -> AsyncMock:
    svc = AsyncMock()
    svc.run_pending_jobs = AsyncMock(return_value=0)
    return svc


@pytest.fixture
def app(
    monkeypatch: pytest.MonkeyPatch,
    mock_task_repo: AsyncMock,
    mock_notification: AsyncMock,
    mock_batch_service: AsyncMock,
    mock_image_job_service: AsyncMock,
):
    monkeypatch.setenv("PLATFORM_DEBUG", "false")
    get_settings.cache_clear()
    from platform_api.main import create_app

    application = create_app()
    application.dependency_overrides[_get_suno_task_repo] = lambda: mock_task_repo
    application.dependency_overrides[_get_notification_port] = lambda: mock_notification
    application.dependency_overrides[_get_batch_service] = lambda: mock_batch_service
    application.dependency_overrides[_get_image_job_service] = lambda: mock_image_job_service
    yield application
    application.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_suno_callback_auto_runs_image_jobs_when_enabled(
    client: AsyncClient,
    ids: dict[str, str],
    mock_image_job_service: AsyncMock,
    mock_batch_service: AsyncMock,
) -> None:
    response = await client.post(
        "/api/v1/callbacks/suno",
        json={"task_id": ids["external_task_id"], "status": "SUCCESS"},
    )
    assert response.status_code == 403

    mock_batch_service.get_batch_for_user.assert_not_awaited()
    mock_image_job_service.run_pending_jobs.assert_not_awaited()


@pytest.mark.asyncio
async def test_suno_callback_does_not_auto_run_when_disabled(
    client: AsyncClient,
    ids: dict[str, str],
    mock_image_job_service: AsyncMock,
    mock_batch_service: AsyncMock,
) -> None:
    mock_batch_service.get_batch_for_user = AsyncMock(return_value=SimpleNamespace(auto_gen_image=False))

    response = await client.post(
        "/api/v1/callbacks/suno",
        json={"task_id": ids["external_task_id"], "status": "SUCCESS"},
    )
    assert response.status_code == 403
    mock_image_job_service.run_pending_jobs.assert_not_awaited()
