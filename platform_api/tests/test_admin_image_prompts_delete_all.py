from __future__ import annotations

import pytest
from fastapi import HTTPException

from platform_api.routers.admin_image_prompts import delete_all_image_prompts


class _Repo:
    def __init__(self, deleted: int = 0) -> None:
        self.deleted = deleted
        self.kind: str | None = None

    async def delete_all(self, *, kind: str) -> int:
        self.kind = kind
        return self.deleted


@pytest.mark.asyncio
async def test_delete_all_normalizes_kind_and_returns_count() -> None:
    repo = _Repo(deleted=4)

    result = await delete_all_image_prompts(None, repo, " Background ")

    assert result.deleted == 4
    assert result.kind == "background"
    assert repo.kind == "background"


@pytest.mark.asyncio
async def test_delete_all_rejects_unknown_kind() -> None:
    repo = _Repo(deleted=1)

    with pytest.raises(HTTPException) as exc:
        await delete_all_image_prompts(None, repo, "cover")

    assert exc.value.status_code == 422
    assert repo.kind is None
