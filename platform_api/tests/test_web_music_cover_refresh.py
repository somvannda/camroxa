"""Cover art must not turn a cheap song read into a Suno poll.

``_ensure_cover_urls`` runs on every ``GET /generations/{id}``, and the Create
page polls every open song. It must only fetch art when none is stored; re-polling
an existing URL caused one Suno request per poll tick and drove the API into OOM.
Dead URLs are handled client-side by CoverImage (fallback on error).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services import web_music_service as svc_mod
from platform_api.services.web_music_service import WebMusicService


def _service(pool: AsyncMock) -> WebMusicService:
    return WebMusicService(pool=pool, generation_service=AsyncMock(), redis=None)


@pytest.mark.asyncio
async def test_missing_cover_is_backfilled(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value="UPDATE 1")
    pool.fetchrow = AsyncMock(return_value={"id": uuid4(), "image_url_ok": "https://cdn1.suno.ai/new.jpeg"})
    service = _service(pool)
    service._poll_suno_task_status = AsyncMock(return_value=SimpleNamespace(state="success"))
    monkeypatch.setattr(
        svc_mod,
        "urls_from_generate_poll",
        lambda _polled: SimpleNamespace(
            image_url_ok="https://cdn1.suno.ai/new.jpeg",
            image_url_alt="https://cdn1.suno.ai/new-alt.jpeg",
        ),
    )

    row = {
        "id": uuid4(),
        "status": "SUCCESS",
        "external_task_id": "suno-task-1",
        "image_url_ok": None,
        "image_url_alt": None,
    }

    await service._ensure_cover_urls(row)

    service._poll_suno_task_status.assert_awaited_once()
    assert "UPDATE suno_tasks" in pool.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_existing_suno_cover_is_never_repolled() -> None:
    pool = AsyncMock()
    pool.execute = AsyncMock()
    service = _service(pool)
    service._poll_suno_task_status = AsyncMock()

    row = {
        "id": uuid4(),
        "status": "SUCCESS",
        "external_task_id": "suno-task-1",
        "image_url_ok": "https://cdn1.suno.ai/stored.jpeg",
        "image_url_alt": None,
    }

    result = await service._ensure_cover_urls(row)

    service._poll_suno_task_status.assert_not_awaited()
    pool.execute.assert_not_awaited()
    assert result is row
