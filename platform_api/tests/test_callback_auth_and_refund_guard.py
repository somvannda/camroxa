"""Focused Phase 0 tests for Suno callback auth and SUCCESS→FAILED refund guard."""

from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.config import get_settings
from platform_api.models.enums import TaskStatus
from platform_api.routers.callbacks import (
    _get_batch_service,
    _get_image_job_service,
    _get_notification_port,
    _get_suno_task_repo,
    _validate_callback_request,
)
from platform_api.services.batch_service import (
    SONG_STATUS_SUNO_FAILED,
    SONG_STATUS_SUNO_PENDING,
    SONG_STATUS_SUNO_SUCCESS,
    BatchService,
)


HMAC_SECRET = "phase0-callback-hmac-secret"


def _sign(body: bytes, secret: str = HMAC_SECRET) -> str:
    return hmac.HMAC(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture
def ids() -> dict[str, str]:
    return {
        "user_id": str(uuid4()),
        "batch_id": str(uuid4()),
        "song_id": str(uuid4()),
        "task_id": str(uuid4()),
        "external_task_id": "ext-task-auth",
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
            "status": TaskStatus.PENDING.value,
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
    svc.get_batch_for_user = AsyncMock(return_value=SimpleNamespace(auto_gen_image=False))
    return svc


@pytest.fixture
def mock_image_job_service() -> AsyncMock:
    svc = AsyncMock()
    svc.run_pending_jobs = AsyncMock(return_value=0)
    return svc


@pytest.fixture
def hmac_app(
    monkeypatch: pytest.MonkeyPatch,
    mock_task_repo: AsyncMock,
    mock_notification: AsyncMock,
    mock_batch_service: AsyncMock,
    mock_image_job_service: AsyncMock,
):
    monkeypatch.setenv("PLATFORM_DEBUG", "false")
    monkeypatch.setenv("PLATFORM_SUNO_CALLBACK_HMAC_SECRET", HMAC_SECRET)
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
async def hmac_client(hmac_app) -> AsyncClient:
    transport = ASGITransport(app=hmac_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_ip_allowlist_accepts_callbacks_despite_invalid_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_DEBUG", "false")
    monkeypatch.setenv("PLATFORM_SUNO_CALLBACK_HMAC_SECRET", HMAC_SECRET)
    monkeypatch.setenv("PLATFORM_SUNO_CALLBACK_ALLOWED_IPS", "1.2.3.4")
    get_settings.cache_clear()
    body = b'{"task_id":"x","status":"SUCCESS"}'
    try:
        # Unsigned callbacks are authorized by the provider-IP allowlist only.
        assert _validate_callback_request("1.2.3.4", body, signature=None) is True
        assert _validate_callback_request("9.9.9.9", body, signature=None) is False
        assert _validate_callback_request("1.2.3.4", body, signature="deadbeef") is True
        assert _validate_callback_request("9.9.9.9", body, signature="deadbeef") is False
    finally:
        get_settings.cache_clear()


def test_hmac_accepts_valid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_DEBUG", "false")
    monkeypatch.setenv("PLATFORM_SUNO_CALLBACK_HMAC_SECRET", HMAC_SECRET)
    get_settings.cache_clear()
    body = b'{"task_id":"x","status":"SUCCESS"}'
    try:
        assert _validate_callback_request("9.9.9.9", body, signature=_sign(body)) is True
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_callback_rejects_unsigned_provider_without_allowlist(
    hmac_client: AsyncClient,
    ids: dict[str, str],
    mock_batch_service: AsyncMock,
    mock_task_repo: AsyncMock,
) -> None:
    # With a secret configured and no provider-IP allowlist, an unsigned
    # callback is unauthenticated and must be rejected.
    response = await hmac_client.post(
        "/api/v1/callbacks/suno",
        json={
            "task_id": ids["external_task_id"],
            "status": "SUCCESS",
            "audio_url_ok": "https://cdn.example.com/ok.mp3",
        },
    )
    assert response.status_code == 403
    mock_task_repo.update_status.assert_not_awaited()
    mock_batch_service.handle_suno_task_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_rejects_invalid_hmac_signature(
    hmac_client: AsyncClient,
    ids: dict[str, str],
    mock_batch_service: AsyncMock,
) -> None:
    payload = {"task_id": ids["external_task_id"], "status": "SUCCESS"}
    body = json.dumps(payload).encode("utf-8")
    response = await hmac_client.post(
        "/api/v1/callbacks/suno",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": "deadbeef",
        },
    )
    assert response.status_code == 403
    mock_batch_service.handle_suno_task_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_accepts_valid_hmac(
    hmac_client: AsyncClient,
    ids: dict[str, str],
    mock_batch_service: AsyncMock,
    mock_task_repo: AsyncMock,
) -> None:
    payload = {
        "task_id": ids["external_task_id"],
        "status": "SUCCESS",
        "audio_url_ok": "https://cdn.example.com/ok.mp3",
    }
    body = json.dumps(payload).encode("utf-8")
    response = await hmac_client.post(
        "/api/v1/callbacks/suno",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": _sign(body),
        },
    )
    assert response.status_code == 200
    mock_task_repo.update_status.assert_awaited()
    mock_batch_service.handle_suno_task_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_ignores_success_to_failed_downgrade(
    hmac_client: AsyncClient,
    ids: dict[str, str],
    mock_batch_service: AsyncMock,
    mock_task_repo: AsyncMock,
) -> None:
    mock_task_repo.find_by_external_id = AsyncMock(
        return_value={
            "id": ids["task_id"],
            "user_id": ids["user_id"],
            "song_id": ids["song_id"],
            "batch_id": ids["batch_id"],
            "status": TaskStatus.SUCCESS.value,
        }
    )
    payload = {"task_id": ids["external_task_id"], "status": "FAILED"}
    body = json.dumps(payload).encode("utf-8")
    response = await hmac_client.post(
        "/api/v1/callbacks/suno",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": _sign(body),
        },
    )
    assert response.status_code == 200
    mock_task_repo.update_status.assert_not_awaited()
    mock_batch_service.handle_suno_task_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_suno_task_update_skips_refund_after_success() -> None:
    song_id = uuid4()
    batch_id = uuid4()
    user_id = uuid4()

    batch_repo = AsyncMock()
    batch_repo.get_song_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=song_id,
            user_id=user_id,
            status=SONG_STATUS_SUNO_SUCCESS,
            title="Already Done",
            batch_index=0,
        )
    )
    batch_repo.get_batch_by_id = AsyncMock()
    batch_repo.update_song_status = AsyncMock()

    enforcement = AsyncMock()
    enforcement.refund_failed_operation = AsyncMock()
    enforcement.pop_operation_charge = AsyncMock(return_value=10)

    service = BatchService(
        batch_repo=batch_repo,
        credit_service=AsyncMock(),
        pricing_service=AsyncMock(),
        generation_service=AsyncMock(),
        profile_repo=AsyncMock(),
        ai_routing_service=AsyncMock(),
        enforcement_service=enforcement,
    )

    result = await service.handle_suno_task_update(
        song_id=song_id,
        batch_id=batch_id,
        status=TaskStatus.FAILED,
    )

    assert result == []
    enforcement.refund_failed_operation.assert_not_awaited()
    batch_repo.update_song_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_suno_task_update_skips_duplicate_failed_refund() -> None:
    song_id = uuid4()
    batch_id = uuid4()
    user_id = uuid4()

    batch_repo = AsyncMock()
    batch_repo.get_song_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=song_id,
            user_id=user_id,
            status=SONG_STATUS_SUNO_FAILED,
            title="Already Failed",
            batch_index=0,
        )
    )
    batch_repo.get_batch_by_id = AsyncMock(
        return_value=SimpleNamespace(
            user_id=user_id, ok_profile_id=None, alt_profile_id=None, auto_gsuno=True, auto_gen_image=False
        )
    )
    batch_repo.get_batch_status_counters = AsyncMock(
        return_value={
            "total_songs": 1,
            "drafts_completed": 1,
            "drafts_failed": 0,
            "suno_submitted": 1,
            "suno_completed": 0,
            "suno_failed": 1,
        }
    )
    batch_repo.update_song_status = AsyncMock()
    batch_repo.update_batch_status = AsyncMock()

    enforcement = AsyncMock()
    enforcement.refund_failed_operation = AsyncMock()
    enforcement.pop_operation_charge = AsyncMock(return_value=10)

    service = BatchService(
        batch_repo=batch_repo,
        credit_service=AsyncMock(),
        pricing_service=AsyncMock(),
        generation_service=AsyncMock(),
        profile_repo=AsyncMock(),
        ai_routing_service=AsyncMock(),
        enforcement_service=enforcement,
    )

    await service.handle_suno_task_update(
        song_id=song_id,
        batch_id=batch_id,
        status=TaskStatus.FAILED,
    )

    enforcement.refund_failed_operation.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_suno_task_update_refunds_pending_failure() -> None:
    song_id = uuid4()
    batch_id = uuid4()
    user_id = uuid4()

    batch_repo = AsyncMock()
    batch_repo.get_song_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=song_id,
            user_id=user_id,
            status=SONG_STATUS_SUNO_PENDING,
            title="Pending Song",
            batch_index=0,
        )
    )
    batch_repo.get_batch_by_id = AsyncMock(
        return_value=SimpleNamespace(
            user_id=user_id, ok_profile_id=None, alt_profile_id=None, auto_gsuno=True, auto_gen_image=False
        )
    )
    batch_repo.get_batch_status_counters = AsyncMock(
        return_value={
            "total_songs": 1,
            "drafts_completed": 1,
            "drafts_failed": 0,
            "suno_submitted": 1,
            "suno_completed": 0,
            "suno_failed": 1,
        }
    )
    batch_repo.update_song_status = AsyncMock()
    batch_repo.update_batch_status = AsyncMock()

    enforcement = AsyncMock()
    enforcement.refund_failed_operation = AsyncMock()
    enforcement.pop_operation_charge = AsyncMock(return_value=7)

    service = BatchService(
        batch_repo=batch_repo,
        credit_service=AsyncMock(),
        pricing_service=AsyncMock(),
        generation_service=AsyncMock(),
        profile_repo=AsyncMock(),
        ai_routing_service=AsyncMock(),
        enforcement_service=enforcement,
    )

    await service.handle_suno_task_update(
        song_id=song_id,
        batch_id=batch_id,
        status=TaskStatus.FAILED,
    )

    enforcement.refund_failed_operation.assert_awaited_once()
