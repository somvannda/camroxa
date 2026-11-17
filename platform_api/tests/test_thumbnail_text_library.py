from __future__ import annotations

from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.repositories.image_thumbnail_text_repo import ThumbnailTextRecord
from platform_api.services.thumbnail_text_library import ThumbnailTextLibraryService


class _Repo:
    def __init__(self, records):
        self._records = records
        self.picked: list[str] = []

    async def list_active(self):
        return [record for record in self._records if record.is_active]

    async def count_active(self):
        return len([record for record in self._records if record.is_active])

    async def pick_rotating_text(self, *, user_id, active_ids, exclude_ids=None, batch_id=None):
        used = set(self.picked)
        exclude = set(exclude_ids or [])
        candidates = [value for value in active_ids if value not in used and value not in exclude]
        if not candidates:
            candidates = [value for value in active_ids if value not in exclude] or list(active_ids)
        chosen = candidates[0]
        self.picked.append(chosen)
        return chosen


@pytest.mark.asyncio
async def test_empty_text_library_raises_clear_error() -> None:
    service = ThumbnailTextLibraryService(repo=_Repo([]))
    with pytest.raises(ValidationError, match="No active admin thumbnail texts"):
        await service.pick_text(user_id=uuid4(), batch_id=uuid4())


@pytest.mark.asyncio
async def test_pick_text_avoids_excluded_and_rotates() -> None:
    records = [
        ThumbnailTextRecord(id=str(uuid4()), title="A"),
        ThumbnailTextRecord(id=str(uuid4()), title="B"),
        ThumbnailTextRecord(id=str(uuid4()), title="C"),
    ]
    repo = _Repo(records)
    service = ThumbnailTextLibraryService(repo=repo)
    user_id = uuid4()
    batch_id = uuid4()

    first = await service.pick_text(user_id=user_id, batch_id=batch_id)
    second = await service.pick_text(
        user_id=user_id, batch_id=batch_id, exclude_ids=[first.id]
    )
    third = await service.pick_text(
        user_id=user_id, batch_id=batch_id, exclude_ids=[first.id, second.id]
    )

    assert len({first.id, second.id, third.id}) == 3
    assert await service.active_count() == 3
