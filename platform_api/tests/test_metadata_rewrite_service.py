"""Unit tests for batch album/title rewrite service methods."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.models.domain import Batch, Song
from platform_api.services.batch_service import BatchService


def _service() -> BatchService:
    batch_repo = AsyncMock()
    credit = AsyncMock()
    pricing = AsyncMock()
    generation = AsyncMock()
    profile = AsyncMock()
    routing = AsyncMock()
    prompts = AsyncMock()
    settings = AsyncMock()
    enforcement = AsyncMock()
    enforcement.check_and_deduct = AsyncMock(
        return_value=SimpleNamespace(charged_credit_units=1)
    )
    enforcement.refund_failed_operation = AsyncMock()
    service = BatchService(
        batch_repo=batch_repo,
        credit_service=credit,
        pricing_service=pricing,
        generation_service=generation,
        profile_repo=profile,
        ai_routing_service=routing,
        prompt_service=prompts,
        settings_service=settings,
        enforcement_service=enforcement,
    )
    service._resolve_draft_routing = AsyncMock(
        return_value=SimpleNamespace(
            title=SimpleNamespace(provider="deepseek", sub_model="chat"),
            album=SimpleNamespace(provider="deepseek", sub_model="chat"),
            lyric=SimpleNamespace(provider="deepseek", sub_model="chat"),
        )
    )
    service.resolve_lyric_rewrite_context = AsyncMock(
        return_value={"mood": "Euphoric Peak-Time", "structure": "", "title": "Old"}
    )
    return service


@pytest.mark.asyncio
async def test_rewrite_song_title_persists_without_status_change() -> None:
    service = _service()
    batch_id = uuid4()
    song_id = uuid4()
    user_id = uuid4()
    batch = Batch(id=batch_id, user_id=user_id, ok_profile_id=uuid4(), song_count=1)
    song = Song(
        id=song_id,
        batch_id=batch_id,
        batch_index=0,
        user_id=user_id,
        title="Old Title",
        album="Album",
        lyrics="lyrics",
        status="suno_success",
    )
    service._batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    service._batch_repo.get_songs_for_user_batch = AsyncMock(return_value=[song])
    service._generation_service.generate_text = AsyncMock(
        return_value='{"title": "Neon Glow Phantom"}'
    )

    result = await service.rewrite_song_title(
        batch_id=batch_id,
        song_id=song_id,
        user_id=str(user_id),
    )
    assert result["title"] == "Neon Glow Phantom"
    service._batch_repo.update_song_title_keep_status.assert_awaited_once_with(
        song_id, "Neon Glow Phantom"
    )


@pytest.mark.asyncio
async def test_rewrite_batch_album_ok_updates_songs() -> None:
    service = _service()
    batch_id = uuid4()
    user_id = uuid4()
    batch = Batch(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=uuid4(),
        alt_profile_id=uuid4(),
        ok_album="Old Album",
        alt_album="Alt Album",
        song_count=1,
    )
    song = Song(
        id=uuid4(),
        batch_id=batch_id,
        batch_index=0,
        user_id=user_id,
        title="Track",
        album="Old Album",
        lyrics="lyrics",
        status="suno_success",
    )
    service._batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    service._batch_repo.get_songs_for_user_batch = AsyncMock(return_value=[song])
    service._generation_service.generate_text = AsyncMock(
        return_value='{"album": "Neon Coastal Midnight"}'
    )

    result = await service.rewrite_batch_album(
        batch_id=batch_id,
        user_id=str(user_id),
        role="ok",
    )
    assert result["album"] == "Neon Coastal Midnight"
    service._batch_repo.update_batch_channel_albums.assert_awaited()
    service._batch_repo.update_batch_songs_album.assert_awaited_once_with(
        batch_id, "Neon Coastal Midnight"
    )


@pytest.mark.asyncio
async def test_rewrite_batch_album_alt_requires_secondary() -> None:
    service = _service()
    batch_id = uuid4()
    user_id = uuid4()
    batch = Batch(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=uuid4(),
        alt_profile_id=None,
        song_count=1,
    )
    service._batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    with pytest.raises(ValidationError):
        await service.rewrite_batch_album(
            batch_id=batch_id,
            user_id=str(user_id),
            role="alt",
        )
