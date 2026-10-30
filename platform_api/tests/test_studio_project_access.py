"""Studio project ownership checks on the platform proxy.

Every `/web-music/studio/sessions/*` route writes to a real Suno project, so the
proxy must reject another user's project before it forwards the call.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import ForbiddenError
from platform_api.services.web_music_service import WebMusicService


def _service(pool: AsyncMock) -> WebMusicService:
    return WebMusicService(pool=pool, generation_service=AsyncMock(), redis=None)


@pytest.mark.asyncio
async def test_owner_passes() -> None:
    owner = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"user_id": owner})
    await _service(pool)._assert_studio_project_access(owner, "suno-project")


@pytest.mark.asyncio
async def test_other_user_is_forbidden() -> None:
    owner, intruder = uuid4(), uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"user_id": owner})
    with pytest.raises(ForbiddenError):
        await _service(pool)._assert_studio_project_access(intruder, "suno-project")


@pytest.mark.asyncio
async def test_unindexed_project_is_allowed() -> None:
    # Projects created before the index existed have no row; they must keep
    # working rather than locking their owners out.
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    await _service(pool)._assert_studio_project_access(uuid4(), "legacy-project")


@pytest.mark.asyncio
async def test_index_inserts_missing_project() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock()
    user_id = uuid4()
    await _service(pool)._ensure_studio_project_index(
        user_id, "suno-project", title="Drive tonight"
    )
    pool.execute.assert_awaited_once()
    args = pool.execute.await_args.args
    assert args[1] == user_id
    assert args[2] == "Drive tonight"
    assert args[3] == "suno-project"


@pytest.mark.asyncio
async def test_index_skips_known_project() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"user_id": uuid4()})
    pool.execute = AsyncMock()
    await _service(pool)._ensure_studio_project_index(uuid4(), "suno-project")
    pool.execute.assert_not_awaited()
