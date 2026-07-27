"""Tests for album image-job race remapping of thumbnail source_job_id."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from platform_api.models.domain import ImageJob
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.repositories.batch_repo import BatchRepository


class _FakePool:
    def __init__(self) -> None:
        self.insert_results: list[object | None] = []
        self.slot_jobs: dict[tuple, ImageJob] = {}
        self.by_id: dict = {}
        self.inserted: list[ImageJob] = []

    async def fetchrow(self, query: str, *args):
        sql = " ".join(query.split())
        if sql.startswith("INSERT INTO image_jobs"):
            result = self.insert_results.pop(0) if self.insert_results else SimpleNamespace(id=args[0])
            return result
        if "ORDER BY created_at ASC" in sql and "LIMIT 1" in sql:
            key = (args[0], args[1], args[2], args[3])
            job = self.slot_jobs.get(key)
            return job  # _row_to_image_job accepts mapping-like; we'll stub method
        if "WHERE id = $1 AND user_id = $2" in sql.replace("\n", " "):
            return self.by_id.get((args[0], args[1]))
        return None


@pytest.mark.asyncio
async def test_create_image_jobs_remaps_thumbnail_when_background_conflicts() -> None:
    pool = _FakePool()
    repo = BatchRepository(pool)  # type: ignore[arg-type]

    batch_id = uuid4()
    user_id = uuid4()
    profile_id = uuid4()
    existing_bg_id = uuid4()
    raced_bg_id = uuid4()
    thumb_id = uuid4()

    existing_bg = ImageJob(
        id=existing_bg_id,
        song_id=uuid4(),
        user_id=user_id,
        batch_id=batch_id,
        profile_id=profile_id,
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.ALT,
        status=TaskStatus.SUCCESS,
    )
    pool.slot_jobs[
        (batch_id, profile_id, ImageKind.BACKGROUND.value, ChannelRole.ALT.value)
    ] = existing_bg

    # BG insert conflicts (None); TH insert succeeds.
    pool.insert_results = [None, SimpleNamespace(id=thumb_id)]

    # Avoid needing real DB row conversion for slot lookup / by-id.
    async def _slot(**kwargs):
        return existing_bg

    async def _by_id(job_id, uid):
        return None

    repo.get_image_job_for_album_slot = _slot  # type: ignore[method-assign]
    repo.get_image_job_by_id = _by_id  # type: ignore[method-assign]

    bg = ImageJob(
        id=raced_bg_id,
        song_id=uuid4(),
        user_id=user_id,
        batch_id=batch_id,
        profile_id=profile_id,
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.ALT,
        status=TaskStatus.PENDING,
    )
    th = ImageJob(
        id=thumb_id,
        song_id=bg.song_id,
        user_id=user_id,
        batch_id=batch_id,
        profile_id=profile_id,
        kind=ImageKind.THUMBNAIL,
        channel_role=ChannelRole.ALT,
        source_job_id=raced_bg_id,
        status=TaskStatus.PENDING,
    )

    created = await repo.create_image_jobs([bg, th])
    assert len(created) == 1
    assert created[0].id == thumb_id
    assert created[0].source_job_id == existing_bg_id
