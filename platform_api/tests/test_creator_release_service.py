"""Tests for the creator release pipeline (Phase 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.creator_release_service import CreatorReleaseService


def _task(user_id=None):
    return {
        "id": uuid4(),
        "user_id": user_id or uuid4(),
        "song_id": None,
        "batch_id": None,
        "title": "Bassac Moon",
        "lyrics": "Khmer lyrics",
        "status": "success",
        "stream_ready_ok": True,
        "b2_storage_key_ok": "user/task/ok.mp3",
        "b2_full_storage_key_ok": None,
        "packaged_storage_key_ok": None,
        "duration_ok": 208.0,
        "image_url_ok": "https://img.example/cover.jpg",
        "audio_id_ok": "audio-1",
        "source_variant": "ok",
    }


def _release(user_id=None, status="draft", metadata=None):
    return {
        "id": uuid4(),
        "creator_id": user_id or uuid4(),
        "source_type": "web_music_generation",
        "source_task_id": uuid4(),
        "source_variant": "ok",
        "status": status,
        "metadata": metadata
        or {
            "title": "Bassac Moon",
            "genre": "Khmer Pop",
            "genres": ["Khmer Pop"],
            "language": "km",
            "release_type": "single",
            "rights_attested": True,
            "lyrics": "Khmer lyrics",
        },
        "ai_disclosure": "ai_assisted",
        "origin": "ai_assisted",
        "album_id": None,
        "track_id": None,
        "submitted_at": None,
        "sla_due_at": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "published_at": None,
        "takedown_reason": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.mark.asyncio
async def test_create_draft_requires_a_profile_and_owned_generation() -> None:
    user_id = uuid4()
    task = _task(user_id)
    release = _release(user_id, metadata={})
    service = CreatorReleaseService(AsyncMock())
    service._profiles = AsyncMock()
    service._profiles.get_by_user_id = AsyncMock(return_value={"user_id": user_id})
    service._pool = AsyncMock()
    service._pool.fetchrow = AsyncMock(side_effect=[task, None, release])

    result = await service.create_draft(
        str(user_id), source_task_id=str(task["id"]), variant="ok", metadata={"title": "Bassac Moon"}
    )

    assert result["status"] == "draft"
    assert service._pool.fetchrow.await_count == 3


@pytest.mark.asyncio
async def test_submit_rejects_unready_audio() -> None:
    user_id = uuid4()
    release = _release(user_id)
    task = _task(user_id)
    task["stream_ready_ok"] = False
    task["b2_storage_key_ok"] = None
    service = CreatorReleaseService(AsyncMock())
    service._pool = AsyncMock()
    service._pool.fetchrow = AsyncMock(side_effect=[release, task])

    with pytest.raises(ValidationError) as exc:
        await service.submit(str(user_id), str(release["id"]))

    assert "audio" in (exc.value.details or {}).get("fields", {})


@pytest.mark.asyncio
async def test_submit_requires_rights_attestation() -> None:
    user_id = uuid4()
    release = _release(user_id, metadata={"title": "Bassac Moon", "genre": "Khmer Pop", "language": "km"})
    task = _task(user_id)
    service = CreatorReleaseService(AsyncMock())
    service._pool = AsyncMock()
    service._pool.fetchrow = AsyncMock(side_effect=[release, task])

    with pytest.raises(ValidationError) as exc:
        await service.submit(str(user_id), str(release["id"]))

    assert "rights_attested" in (exc.value.details or {}).get("fields", {})


@pytest.mark.asyncio
async def test_approving_a_release_publishes_to_the_catalog() -> None:
    user_id = uuid4()
    task = _task(user_id)
    release = _release(user_id, status="submitted")
    release["source_task_id"] = task["id"]
    published = {**release, "status": "published", "album_id": uuid4(), "track_id": uuid4()}
    service = CreatorReleaseService(AsyncMock())
    service._pool = AsyncMock()
    service._pool.fetchrow = AsyncMock(side_effect=[release, task, published])
    service._streaming = AsyncMock()
    service._streaming.get_or_create_album = AsyncMock(return_value=published["album_id"])
    service._streaming.upsert_track = AsyncMock(return_value=published["track_id"])

    result = await service.decide(
        str(release["id"]), decision="approve", reviewer_id=str(uuid4())
    )

    assert result["release"]["status"] == "published"
    service._streaming.get_or_create_album.assert_awaited_once()
    service._streaming.upsert_track.assert_awaited_once()
    assert service._pool.execute.await_count == 2


@pytest.mark.asyncio
async def test_unpublish_hides_the_catalog_rows() -> None:
    user_id = uuid4()
    release = _release(user_id, status="published")
    release["album_id"] = uuid4()
    release["track_id"] = uuid4()
    taken_down = {**release, "status": "taken_down"}
    service = CreatorReleaseService(AsyncMock())
    service._pool = AsyncMock()
    service._pool.fetchrow = AsyncMock(side_effect=[release, taken_down])
    service._streaming = AsyncMock()
    service._streaming.set_track_publish_status = AsyncMock(return_value=True)
    service._streaming.set_album_publish_status = AsyncMock(return_value=True)

    result = await service.unpublish(str(user_id), str(release["id"]))

    assert result["status"] == "taken_down"
    service._streaming.set_track_publish_status.assert_awaited_once()
    service._streaming.set_album_publish_status.assert_awaited_once()
