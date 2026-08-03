from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.clients.suno_client import (
    extract_suno_wav_task_id,
    parse_suno_wav_poll,
)
from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.distrokid import _get_distrokid_service


def test_parse_suno_wav_response_states() -> None:
    assert extract_suno_wav_task_id({"code": 200, "data": {"taskId": "wav-1"}}) == "wav-1"
    success = parse_suno_wav_poll(
        {"code": 200, "data": {"successFlag": "SUCCESS", "response": {"audioWavUrl": "https://cdn/w.wav"}}}
    )
    assert success.state == "success"
    assert success.audio_wav_url.endswith("w.wav")
    assert parse_suno_wav_poll({"code": 200, "data": {"successFlag": "PENDING"}}).state == "pending"


@pytest.fixture
def app():
    service = AsyncMock()
    service.usage.return_value = {"used": 3, "limit": 600, "period_key": "2026-07"}
    service.convert.return_value = {"id": str(uuid4()), "status": "pending", "wav_task_id": "wav-1"}
    service.check_history.return_value = [{"track_title": "Existing"}]
    application = create_app()
    application.dependency_overrides[_get_distrokid_service] = lambda: service
    application.dependency_overrides[get_current_user] = lambda: AuthContext(
        user_id=str(uuid4()), email="user@example.com", role="user"
    )
    yield application, service
    application.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_distrokid_wav_endpoints(app) -> None:
    application, service = app
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        usage = await client.get("/api/v1/distrokid/wav/usage")
        convert = await client.post(
            "/api/v1/distrokid/wav/convert",
            json={"suno_task_id": "suno-1", "audio_id": "audio-1", "role": "primary"},
        )
        duplicate = await client.post(
            "/api/v1/distrokid/history/check",
            json={"album_name": "Album", "tracks": [{"title": "Existing", "wav_sha256": "abc"}]},
        )
    assert usage.json()["limit"] == 600
    assert convert.status_code == 200
    assert duplicate.json()["duplicate"] is True
    service.convert.assert_awaited_once()
