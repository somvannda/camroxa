"""A quota/cap rejection while retrying Suno must not fail the song.

Before this, ``retry_song_suno`` caught every exception, marked the song
``suno_failed`` and re-raised. The daily music cap is enforced inside the
charge, so retries that were never submitted still looked like generation
failures, hid the real reason and stayed in the retry loop.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import QuotaExceededError
from platform_api.services import batch_service as batch_service_module
from platform_api.services.batch_service import BatchService


def _service(*, submit_error: Exception) -> BatchService:
    service = BatchService.__new__(BatchService)
    song = SimpleNamespace(
        id=uuid4(),
        batch_index=0,
        title="Scarlet Ember Calling",
        album="Album",
        lyrics="La la la",
    )
    batch = SimpleNamespace(id=uuid4(), user_id=uuid4(), ok_profile_id=None)
    service._batch_repo = SimpleNamespace(
        get_batch_for_user=AsyncMock(return_value=batch),
        get_songs_for_user_batch=AsyncMock(return_value=[song]),
    )
    service._assert_song_allows_suno_retry = AsyncMock()
    service._resolve_suno_model = AsyncMock(return_value="V6")
    service._submit_song_to_suno = AsyncMock(side_effect=submit_error)
    service.update_song_to_suno_failed = AsyncMock()
    service._log_suno_failure_metric = lambda **_: None
    service.refresh_batch_status = AsyncMock()
    service._song = song
    return service


@pytest.mark.asyncio
async def test_quota_rejection_keeps_song_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "log_suno_submit_started",
        "log_suno_submitted",
        "log_suno_submit_failed",
    ):
        monkeypatch.setattr(batch_service_module.draft_log, name, lambda **_: None)

    service = _service(
        submit_error=QuotaExceededError(
            "Daily music limit reached (500 credits). It resets at midnight.",
            details={"code": "music_daily_cap"},
        )
    )

    with pytest.raises(QuotaExceededError):
        await service.retry_song_suno(
            batch_id=uuid4(),
            song_id=service._song.id,
            user_id=str(uuid4()),
        )

    service.update_song_to_suno_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_submit_failure_still_marks_song_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "log_suno_submit_started",
        "log_suno_submitted",
        "log_suno_submit_failed",
    ):
        monkeypatch.setattr(batch_service_module.draft_log, name, lambda **_: None)

    service = _service(submit_error=RuntimeError("provider exploded"))

    with pytest.raises(RuntimeError):
        await service.retry_song_suno(
            batch_id=uuid4(),
            song_id=service._song.id,
            user_id=str(uuid4()),
        )

    service.update_song_to_suno_failed.assert_awaited_once()
