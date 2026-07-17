from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.batch import _get_batch_service

USER_CONTEXT = AuthContext(user_id=str(uuid4()), email="user@example.com", role="user")


@pytest.fixture
def mock_batch_service() -> AsyncMock:
    service = AsyncMock()
    service.create_batch = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid4(),
            status="pending",
            song_count=4,
            planned_from_date=date(2026, 6, 25),
            planned_to_date=date(2026, 6, 25),
            ok_run_dir=r"D:\Music\Primary\2026-06-25",
            alt_run_dir=r"D:\Music\Secondary\2026-06-25",
        )
    )
    service.execute_batch = AsyncMock(return_value=None)
    service.get_batch_status = AsyncMock(
        return_value={
            "batch_id": str(uuid4()),
            "status": "processing",
            "total_songs": 4,
            "drafts_completed": 2,
            "drafts_failed": 0,
            "suno_submitted": 0,
            "suno_completed": 0,
            "suno_failed": 0,
            "audio_downloaded": 0,
            "images_completed": 0,
        }
    )
    return service


@pytest.fixture
def app(mock_batch_service: AsyncMock):
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: USER_CONTEXT
    application.dependency_overrides[_get_batch_service] = lambda: mock_batch_service
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_batch_schedules_background_execution(
    client: AsyncClient,
    mock_batch_service: AsyncMock,
) -> None:
    response = await client.post(
        "/api/v1/batches",
        json={
            "ok_profile_id": str(uuid4()),
            "alt_profile_id": str(uuid4()),
            "song_count": 4,
            "language": "en",
            "creativity_level": 55,
            "pairing_mode": "match_key",
            "auto_gen_image": False,
            "auto_gsuno": True,
            "from_date": "2026-06-25",
            "to_date": "2026-06-25",
            "ok_run_dir": r"D:\Music\Primary\2026-06-25",
            "alt_run_dir": r"D:\Music\Secondary\2026-06-25",
        },
    )

    assert response.status_code == 201
    assert response.json()["ok_run_dir"] == r"D:\Music\Primary\2026-06-25"
    assert response.json()["alt_run_dir"] == r"D:\Music\Secondary\2026-06-25"
    mock_batch_service.create_batch.assert_awaited_once()
    mock_batch_service.execute_batch.assert_awaited_once()
