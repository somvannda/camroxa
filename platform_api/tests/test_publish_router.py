"""Router tests for the publishing endpoints and webhook authentication."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.repositories.publish_repo import PublishJobRecord
from platform_api.routers.publish import (
    _get_job_queue_repo,
    _get_publish_repo,
    _get_publish_service,
)


USER_ID = str(uuid4())
AUTH = AuthContext(user_id=USER_ID, email="boss@example.com", role="user")


def _job() -> PublishJobRecord:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return PublishJobRecord(
        id=str(uuid4()),
        user_id=USER_ID,
        song_id=None,
        job_uid="job-1",
        batch_id=None,
        profile_id=str(uuid4()),
        role="OK",
        file_path=None,
        title="Song",
        description=None,
        tags=None,
        privacy_status="private",
        youtube_video_id=None,
        youtube_url=None,
        status="processing",
        attempt_count=0,
        error_message=None,
        provider="postforme",
        platform="youtube",
        social_account_id="spc_1",
        postforme_post_id="post_1",
        postforme_result_id=None,
        media_url="https://cdn.example/v.mp4",
        upload_url=None,
        upload_expires_at=None,
        file_size_bytes=None,
        file_checksum=None,
        thumbnail_path=None,
        thumbnail_media_url=None,
        profile_config={},
        credits_charged_units=50_000,
        credit_ref_id="job-1",
        error_code=None,
        scheduled_at=None,
        result_payload={},
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def app():
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: AUTH
    return application


@pytest.fixture
def service() -> AsyncMock:
    mock = AsyncMock()
    mock.list_accounts = AsyncMock(return_value=[])
    mock.latest_connect_session = AsyncMock(return_value=None)
    mock.quote = AsyncMock(
        return_value={
            "op": "publish",
            "credits_per_upload": 5.0,
            "amount_units": 50_000,
            "balance": 20.0,
            "available": True,
            "platforms": ["youtube"],
        }
    )
    mock.get_job = AsyncMock(
        return_value={
            "job_uid": "job-1",
            "status": "processing",
            "platform": "youtube",
            "provider": "postforme",
            "batch_id": None,
            "profile_id": None,
            "role": "OK",
            "title": "Song",
            "description": None,
            "privacy_status": "private",
            "scheduled_at": None,
            "youtube_video_id": None,
            "youtube_url": None,
            "postforme_post_id": "post_1",
            "credits_charged": 5.0,
            "error_code": None,
            "error_message": None,
            "attempt_count": 0,
            "created_at": None,
            "updated_at": None,
        }
    )
    mock.list_jobs = AsyncMock(return_value=[])
    mock.verify_webhook_secret = lambda value: value == "secret"
    return mock


@pytest.fixture
def repo() -> AsyncMock:
    mock = AsyncMock()
    mock.insert_webhook_event = AsyncMock(return_value="event-1")
    mock.get_job_by_post_id = AsyncMock(return_value=_job())
    return mock


@pytest.fixture
def queue() -> AsyncMock:
    mock = AsyncMock()
    mock.enqueue_if_absent = AsyncMock(return_value=(AsyncMock(), True))
    return mock


async def _client(app, service, repo, queue) -> AsyncClient:
    app.dependency_overrides[_get_publish_service] = lambda: service
    app.dependency_overrides[_get_publish_repo] = lambda: repo
    app.dependency_overrides[_get_job_queue_repo] = lambda: queue
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_quote_returns_five_credits(app, service, repo, queue) -> None:
    async with await _client(app, service, repo, queue) as client:
        response = await client.get("/api/v3/publish/quote")
    assert response.status_code == 200
    assert response.json()["credits_per_upload"] == 5.0


@pytest.mark.asyncio
async def test_get_job_contract(app, service, repo, queue) -> None:
    async with await _client(app, service, repo, queue) as client:
        response = await client.get("/api/v3/publish/jobs/job-1")
    assert response.status_code == 200
    body = response.json()
    assert body["job_uid"] == "job-1"
    assert body["credits_charged"] == 5.0


@pytest.mark.asyncio
async def test_webhook_rejects_bad_secret(app, service, repo, queue) -> None:
    async with await _client(app, service, repo, queue) as client:
        response = await client.post(
            "/api/v3/publish/webhooks/postforme",
            headers={"Post-For-Me-Webhook-Secret": "wrong"},
            json={"event": "social.post.result.created", "data": {"post_id": "post_1"}},
        )
    assert response.status_code == 401
    repo.insert_webhook_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_accepts_secret_and_enqueues_sync(app, service, repo, queue) -> None:
    async with await _client(app, service, repo, queue) as client:
        response = await client.post(
            "/api/v3/publish/webhooks/postforme",
            headers={"Post-For-Me-Webhook-Secret": "secret"},
            json={"event": "social.post.result.created", "data": {"post_id": "post_1"}},
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    repo.insert_webhook_event.assert_awaited_once()
    queue.enqueue_if_absent.assert_awaited_once()
    assert queue.enqueue_if_absent.await_args.kwargs["payload"]["post_id"] == "post_1"
