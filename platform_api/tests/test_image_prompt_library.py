from __future__ import annotations

from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.repositories.image_prompt_repo import ImagePromptStyleRecord
from platform_api.services.image_prompt_library import ImagePromptLibraryService


class _Repo:
    def __init__(self, styles):
        self._styles = styles

    async def list_active(self, *, kind):
        return [style for style in self._styles if style.kind == kind]

    async def count_active(self):
        return {
            "background": len([s for s in self._styles if s.kind == "background"]),
            "thumbnail": len([s for s in self._styles if s.kind == "thumbnail"]),
        }


class _History:
    def __init__(self):
        self.seen: list[str] = []

    async def pick_least_used_value(
        self,
        *,
        kind,
        values,
        exclude=None,
        batch_id=None,
        previous_batch_id=None,
    ):
        excluded = set(exclude or [])
        candidates = [value for value in values if value not in excluded] or list(values)
        chosen = candidates[0]
        self.seen.append(chosen)
        return chosen


@pytest.mark.asyncio
async def test_empty_library_raises_clear_error() -> None:
    service = ImagePromptLibraryService(repo=_Repo([]), history=_History())
    with pytest.raises(ValidationError, match="No active admin prompt styles"):
        await service.pick_style(kind="background", batch_id=uuid4())


@pytest.mark.asyncio
async def test_pick_style_avoids_ids_used_in_same_batch() -> None:
    styles = [
        ImagePromptStyleRecord(id=str(uuid4()), kind="background", name="A", prompt_text="a"),
        ImagePromptStyleRecord(id=str(uuid4()), kind="background", name="B", prompt_text="b"),
    ]
    history = _History()
    service = ImagePromptLibraryService(repo=_Repo(styles), history=history)
    batch_id = uuid4()

    first = await service.pick_style(kind="background", batch_id=batch_id)
    second = await service.pick_style(
        kind="background",
        batch_id=batch_id,
        exclude_ids=[first.id],
    )

    assert first.id != second.id
    assert history.seen == [first.id, second.id]


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
