"""Admin-managed thumbnail text selection with per-user rotation."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from platform_api.exceptions import ValidationError
from platform_api.repositories.image_thumbnail_text_repo import ThumbnailTextRecord


class ThumbnailTextRepositoryProtocol(Protocol):
    async def list_active(self) -> list[ThumbnailTextRecord]: ...

    async def count_active(self) -> int: ...

    async def pick_rotating_text(
        self,
        *,
        user_id: UUID,
        active_ids: list[str],
        exclude_ids: list[str] | None = None,
        batch_id: UUID | None = None,
    ) -> str | None: ...


def empty_thumbnail_text_message() -> str:
    return (
        "No active admin thumbnail texts are available. Add them in "
        "Admin → Thumbnail Texts."
    )


class ThumbnailTextLibraryService:
    """Pick a thumbnail text preset from the user's current rotation cycle."""

    def __init__(self, *, repo: ThumbnailTextRepositoryProtocol) -> None:
        self._repo = repo

    async def pick_text(
        self,
        *,
        user_id: UUID,
        batch_id: UUID,
        exclude_ids: list[str] | None = None,
    ) -> ThumbnailTextRecord:
        active = await self._repo.list_active()
        if not active:
            raise ValidationError(
                empty_thumbnail_text_message(),
                details={"source": "thumbnail_texts"},
            )
        chosen_id = await self._repo.pick_rotating_text(
            user_id=user_id,
            active_ids=[item.id for item in active],
            exclude_ids=exclude_ids,
            batch_id=batch_id,
        )
        if chosen_id:
            for item in active:
                if item.id == str(chosen_id):
                    return item
        return active[0]

    async def active_count(self) -> int:
        return await self._repo.count_active()