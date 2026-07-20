"""Tests for Suno sanitize follow-up features."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.models.domain import Song
from platform_api.models.enums import TaskStatus
from platform_api.routers import suno_blocklist_admin
from platform_api.services.batch_service import SONG_STATUS_SUNO_PENDING, BatchService
from platform_api.services.suno_status_messages import classify_suno_failure_type
from platform_api.tests.test_batch_service import make_service


@pytest.mark.asyncio
async def test_reconcile_stuck_suno_pending_songs() -> None:
    batch_repo = AsyncMock()
    credit_service = AsyncMock()
    pricing_service = AsyncMock()
    generation_service = AsyncMock()
    profile_repo = AsyncMock()
    ai_routing_service = AsyncMock()

    song_id = uuid4()
    batch_id = uuid4()
    batch_repo.list_stuck_suno_pending_songs = AsyncMock(
        return_value=[
            {
                "song_id": song_id,
                "batch_id": batch_id,
                "suno_status": "failed",
                "error_message": "producer tag lowlight",
            }
        ]
    )

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )
    service.update_song_to_suno_failed = AsyncMock()
    service.refresh_batch_status = AsyncMock()

    fixed = await service._reconcile_stuck_suno_pending_songs(
        user_id=str(uuid4()),
        limit=10,
    )

    assert fixed == 1
    service.update_song_to_suno_failed.assert_awaited_once_with(song_id)
    service.refresh_batch_status.assert_awaited_once_with(batch_id)


@pytest.mark.asyncio
async def test_handle_suno_task_update_auto_retries_sensitive_failure() -> None:
    batch_repo = AsyncMock()
    credit_service = AsyncMock()
    pricing_service = AsyncMock()
    generation_service = AsyncMock()
    profile_repo = AsyncMock()
    ai_routing_service = AsyncMock()

    song_id = uuid4()
    batch_id = uuid4()
    user_id = uuid4()
    song = Song(
        id=song_id,
        batch_id=batch_id,
        user_id=user_id,
        title="Neon lowlight",
        album="Album",
        lyrics="Pressure in the lowlight",
        batch_index=0,
        status=SONG_STATUS_SUNO_PENDING,
    )

    batch_repo.get_song_by_id = AsyncMock(return_value=song)
    batch_repo.get_latest_suno_task_for_song = AsyncMock(return_value=None)

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )
    service._promote_suno_blocked_terms = AsyncMock()
    service._try_auto_retry_suno_after_failure = AsyncMock(return_value=True)
    service.update_song_to_suno_failed = AsyncMock()
    service.refresh_batch_status = AsyncMock()

    result = await service.handle_suno_task_update(
        song_id=song_id,
        batch_id=batch_id,
        status=TaskStatus.FAILED,
        error_message="Your lyrics contain producer tag lowlight",
    )

    assert result == []
    service._promote_suno_blocked_terms.assert_awaited_once()
    service._try_auto_retry_suno_after_failure.assert_awaited_once()
    service.update_song_to_suno_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_suno_failure_metrics_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.middleware.auth import AuthContext

    batch_repo = AsyncMock()
    batch_repo.list_suno_failure_metrics_rows = AsyncMock(
        return_value=[
            {
                "error_message": "producer tag lowlight",
                "submit_order": 1,
            },
            {
                "error_message": "SENSITIVE_WORD_ERROR",
                "submit_order": 2,
            },
        ]
    )
    monkeypatch.setattr(
        "platform_api.dependencies.get_db_pool",
        lambda: object(),
    )
    monkeypatch.setattr(
        "platform_api.repositories.batch_repo.BatchRepository",
        lambda _pool: batch_repo,
    )

    admin_ctx = AuthContext(user_id=str(uuid4()), email="admin@example.com", role="admin")
    result = await suno_blocklist_admin.get_suno_failure_metrics(admin_ctx, days=30)

    assert result.total == 2
    assert any(
        bucket.failure_type == "producer_tag" and bucket.submit_kind == "first_submit"
        for bucket in result.buckets
    )
    assert classify_suno_failure_type(error_message="SENSITIVE_WORD_ERROR") == "SENSITIVE_WORD_ERROR"


@pytest.mark.asyncio
async def test_polish_lyrics_auto_fixes_remaining_block_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.services.suno_blocklist_service import SunoBlocklistService
    from platform_api.tests.test_generation_service import (
        FakeCreditService,
        FakeFalClient,
        FakeLlmClient,
        FakePricingRepo,
        FakeSlaiClient,
        FakeSunoClient,
        FakeTaskRepo,
        _attach_fake_pools,
    )
    from platform_api.tests.test_suno_blocklist_service import FakeSunoBlocklistRepo

    blocklist_service = SunoBlocklistService(FakeSunoBlocklistRepo())
    monkeypatch.setattr(
        "platform_api.dependencies.get_suno_blocklist_service",
        lambda: blocklist_service,
    )

    from platform_api.services.generation_service import GenerationService

    service = GenerationService(
        credit_service=FakeCreditService(),
        pricing_repo=FakePricingRepo(),
        task_repo=FakeTaskRepo(),
        llm_client=FakeLlmClient(),
        suno_client=FakeSunoClient(),
        fal_client=FakeFalClient(),
        slai_client=FakeSlaiClient(),
    )
    _attach_fake_pools(service)
    service.generate_text = AsyncMock(return_value="Shadows in the lowlight fade")

    polished = await service.polish_lyrics_text(
        user_id=str(uuid4()),
        lyrics="Shadows in the lowlight fade",
        strength=50,
        provider="deepseek",
        model_id="deepseek-chat",
    )

    assert "lowlight" not in polished.lower()
    assert "afterglow" in polished.lower()


def test_classify_suno_failure_type_rejects_as_sensitive() -> None:
    assert classify_suno_failure_type(status="REJECTED") == "SENSITIVE_WORD_ERROR"
    assert (
        classify_suno_failure_type(status="FAILED", error_message="content policy reject")
        == "SENSITIVE_WORD_ERROR"
    )
