"""User delete for failed / non-audio batches."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.models.domain import Batch, Song
from platform_api.services.batch_service import (
    SONG_STATUS_DRAFT_FAILED,
    SONG_STATUS_DRAFT_READY,
    SONG_STATUS_PENDING,
    SONG_STATUS_SUNO_FAILED,
    SONG_STATUS_SUNO_PENDING,
    SONG_STATUS_SUNO_SUCCESS,
    BatchService,
    batch_songs_are_user_deletable,
)


def _song(status: str) -> Song:
    now = datetime.now(timezone.utc)
    return Song(
        id=uuid4(),
        batch_id=uuid4(),
        batch_index=0,
        user_id=uuid4(),
        title=None,
        album=None,
        lyrics=None,
        description_id=None,
        structure_id=None,
        status=status,
        created_at=now,
        updated_at=now,
    )


def test_batch_songs_are_user_deletable_allows_failed_and_ready() -> None:
    ok, reason = batch_songs_are_user_deletable(
        [
            _song(SONG_STATUS_PENDING),
            _song(SONG_STATUS_DRAFT_FAILED),
            _song(SONG_STATUS_DRAFT_READY),
            _song(SONG_STATUS_SUNO_FAILED),
        ]
    )
    assert ok is True
    assert reason is None


def test_batch_songs_are_user_deletable_blocks_suno_success() -> None:
    ok, reason = batch_songs_are_user_deletable([_song(SONG_STATUS_SUNO_SUCCESS)])
    assert ok is False
    assert reason is not None


def test_batch_songs_are_user_deletable_blocks_suno_pending() -> None:
    ok, reason = batch_songs_are_user_deletable([_song(SONG_STATUS_SUNO_PENDING)])
    assert ok is False
    assert reason is not None


@pytest.mark.asyncio
async def test_delete_failed_batch_releases_draft_leak_and_deletes() -> None:
    user_id = uuid4()
    batch_id = uuid4()
    ok_profile_id = uuid4()
    now = datetime.now(timezone.utc)
    batch = Batch(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=ok_profile_id,
        alt_profile_id=uuid4(),
        song_count=2,
        language="en",
        status="failed",
        created_at=now,
        updated_at=now,
    )
    songs = [
        Song(
            id=uuid4(),
            batch_id=batch_id,
            batch_index=0,
            user_id=user_id,
            title=None,
            album=None,
            lyrics=None,
            description_id=None,
            structure_id=None,
            status=SONG_STATUS_DRAFT_FAILED,
            created_at=now,
            updated_at=now,
        ),
        Song(
            id=uuid4(),
            batch_id=batch_id,
            batch_index=1,
            user_id=user_id,
            title=None,
            album=None,
            lyrics=None,
            description_id=None,
            structure_id=None,
            status=SONG_STATUS_DRAFT_FAILED,
            created_at=now,
            updated_at=now,
        ),
    ]

    batch_repo = AsyncMock()
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.get_songs_for_user_batch = AsyncMock(return_value=songs)
    batch_repo.delete_batch_cascade = AsyncMock(return_value=True)

    enforcement = AsyncMock()
    enforcement.release_operation_quota = AsyncMock()

    service = BatchService(
        batch_repo=batch_repo,
        credit_service=AsyncMock(),
        pricing_service=AsyncMock(),
        generation_service=AsyncMock(),
        profile_repo=AsyncMock(),
        ai_routing_service=None,
        enforcement_service=enforcement,
    )

    result = await service.delete_failed_batch(batch_id=batch_id, user_id=str(user_id))

    assert result["deleted"] is True
    assert result["songs_deleted"] == 2
    assert result["draft_quota_released"] == 4
    enforcement.release_operation_quota.assert_awaited_once()
    assert enforcement.release_operation_quota.await_args.kwargs["count"] == 4
    batch_repo.delete_batch_cascade.assert_awaited_once_with(batch_id, user_id)


@pytest.mark.asyncio
async def test_delete_failed_batch_rejects_suno_success() -> None:
    user_id = uuid4()
    batch_id = uuid4()
    now = datetime.now(timezone.utc)
    batch = SimpleNamespace(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=uuid4(),
    )
    songs = [
        Song(
            id=uuid4(),
            batch_id=batch_id,
            batch_index=0,
            user_id=user_id,
            title="ok",
            album=None,
            lyrics="x",
            description_id=None,
            structure_id=None,
            status=SONG_STATUS_SUNO_SUCCESS,
            created_at=now,
            updated_at=now,
        )
    ]
    batch_repo = AsyncMock()
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.get_songs_for_user_batch = AsyncMock(return_value=songs)
    batch_repo.delete_batch_cascade = AsyncMock()

    service = BatchService(
        batch_repo=batch_repo,
        credit_service=AsyncMock(),
        pricing_service=AsyncMock(),
        generation_service=AsyncMock(),
        profile_repo=AsyncMock(),
        ai_routing_service=None,
    )

    with pytest.raises(ValidationError):
        await service.delete_failed_batch(batch_id=batch_id, user_id=str(user_id))
    batch_repo.delete_batch_cascade.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_failed_batch_not_found() -> None:
    batch_repo = AsyncMock()
    batch_repo.get_batch_for_user = AsyncMock(return_value=None)
    service = BatchService(
        batch_repo=batch_repo,
        credit_service=AsyncMock(),
        pricing_service=AsyncMock(),
        generation_service=AsyncMock(),
        profile_repo=AsyncMock(),
        ai_routing_service=None,
    )
    with pytest.raises(NotFoundError):
        await service.delete_failed_batch(batch_id=uuid4(), user_id=str(uuid4()))
