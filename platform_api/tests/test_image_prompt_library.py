from __future__ import annotations

from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.repositories.image_prompt_repo import ImagePromptStyleRecord
from platform_api.services.image_prompt_library import ImagePromptLibraryService


class _Repo:
    def __init__(self, styles):
        self._styles = styles
        self.used: dict[str, list[str]] = {"background": [], "thumbnail": []}
        self.calls: list[dict] = []

    async def list_active(self, *, kind, text_mode=None):
        return [style for style in self._styles if style.kind == kind]

    async def count_active(self):
        return {
            "background": len([s for s in self._styles if s.kind == "background"]),
            "thumbnail": len([s for s in self._styles if s.kind == "thumbnail"]),
        }

    async def pick_rotating_style(
        self,
        *,
        user_id,
        kind,
        active_ids,
        exclude_ids=None,
        batch_id=None,
    ):
        self.calls.append(
            {
                "user_id": user_id,
                "kind": kind,
                "active_ids": list(active_ids),
                "exclude_ids": list(exclude_ids or []),
                "batch_id": batch_id,
            }
        )
        used = self.used.setdefault(kind, [])
        exclude = set(exclude_ids or [])
        unused = [value for value in active_ids if value not in used]
        candidates = [value for value in unused if value not in exclude]
        if not candidates:
            used.clear()
            candidates = [value for value in active_ids if value not in exclude] or list(active_ids)
        chosen = candidates[0]
        used.append(chosen)
        return chosen


@pytest.mark.asyncio
async def test_empty_library_raises_clear_error() -> None:
    service = ImagePromptLibraryService(repo=_Repo([]))
    with pytest.raises(ValidationError, match="No active admin prompt styles"):
        await service.pick_style(user_id=uuid4(), kind="background", batch_id=uuid4())


@pytest.mark.asyncio
async def test_pick_style_avoids_ids_used_in_same_batch() -> None:
    styles = [
        ImagePromptStyleRecord(id=str(uuid4()), kind="background", name="A", prompt_text="a"),
        ImagePromptStyleRecord(id=str(uuid4()), kind="background", name="B", prompt_text="b"),
    ]
    repo = _Repo(styles)
    service = ImagePromptLibraryService(repo=repo)
    batch_id = uuid4()
    user_id = uuid4()

    first = await service.pick_style(
        user_id=user_id, kind="background", batch_id=batch_id
    )
    second = await service.pick_style(
        user_id=user_id,
        kind="background",
        batch_id=batch_id,
        exclude_ids=[first.id],
    )
    third = await service.pick_style(
        user_id=user_id, kind="background", batch_id=batch_id
    )

    assert first.id != second.id
    assert third.id in {first.id, second.id}
    assert repo.calls[0]["user_id"] == user_id
    assert repo.calls[0]["active_ids"] == [first.id, second.id]


def test_resolve_text_template_tokens_and_fallback() -> None:
    style = ImagePromptStyleRecord(
        id=str(uuid4()),
        kind="thumbnail",
        name="TH",
        prompt_text="style",
        text_template="{album}",
    )
    assert (
        ImagePromptLibraryService.resolve_text_template(
            style, title="Storm Run", album="Night Shift", channel="Primary"
        )
        == "Night Shift"
    )

    title_style = ImagePromptStyleRecord(
        id=str(uuid4()),
        kind="thumbnail",
        name="TH",
        prompt_text="style",
        text_template="{title}",
    )
    assert (
        ImagePromptLibraryService.resolve_text_template(
            title_style, title="", album="", channel=""
        )
        == "NEW MUSIC"
    )
