"""Project comments can be posted by the owner (S55 rail)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.services.web_music_service import WebMusicService

USER_ID = uuid4()
PROJECT_ID = uuid4()
PROJECT_ROW = {"id": PROJECT_ID, "user_id": USER_ID}
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class RecordingPool:
    def __init__(self, *, owned: bool = True, insert_row: dict | None = None) -> None:
        self.owned = owned
        self.insert_row = insert_row or {
            "id": uuid4(),
            "parent_id": None,
            "author_name": "somvannda",
            "body": "Tighten the low end",
            "created_at": NOW,
        }
        self.queries: list[str] = []
        self.args: list[tuple[object, ...]] = []

    @staticmethod
    def _sql(query: str) -> str:
        return " ".join(query.split())

    async def fetchrow(self, query: str, *args: object) -> dict | None:
        sql = self._sql(query)
        self.queries.append(sql)
        self.args.append(args)
        if sql.startswith("SELECT id FROM studio_projects"):
            return PROJECT_ROW if self.owned else None
        if sql.startswith("INSERT INTO studio_project_comments"):
            return self.insert_row
        raise AssertionError(f"unexpected fetchrow: {sql}")


def _service(pool: RecordingPool) -> WebMusicService:
    return WebMusicService(pool, AsyncMock())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_posts_a_comment_for_the_owner() -> None:
    pool = RecordingPool()
    payload = await _service(pool).add_studio_project_comment(
        USER_ID, PROJECT_ID, author_name="somvannda", body="Tighten the low end"
    )
    assert payload["body"] == "Tighten the low end"
    assert payload["author_name"] == "somvannda"
    assert any(query.startswith("INSERT INTO studio_project_comments") for query in pool.queries)


@pytest.mark.asyncio
async def test_rejects_a_project_the_user_does_not_own() -> None:
    with pytest.raises(NotFoundError):
        await _service(RecordingPool(owned=False)).add_studio_project_comment(
            USER_ID, PROJECT_ID, author_name="x", body="hello"
        )


@pytest.mark.asyncio
async def test_rejects_an_empty_body() -> None:
    with pytest.raises(ValidationError):
        await _service(RecordingPool()).add_studio_project_comment(
            USER_ID, PROJECT_ID, author_name="x", body="   "
        )


@pytest.mark.asyncio
async def test_posts_a_clip_scoped_comment() -> None:
    now = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    pool = RecordingPool(
        insert_row={
            "id": uuid4(),
            "clip_id": "clip-abc",
            "parent_id": None,
            "author_name": "You",
            "body": "Tighten the low end",
            "created_at": now,
        }
    )

    payload = await _service(pool).add_studio_project_comment(
        USER_ID,
        PROJECT_ID,
        author_name="You",
        body="Tighten the low end",
        clip_id="clip-abc",
    )

    assert payload["clip_id"] == "clip-abc"
    insert_args = next(
        args for query, args in zip(pool.queries, pool.args)
        if query.startswith("INSERT INTO studio_project_comments")
    )
    assert insert_args[-1] == "clip-abc"

