"""Cover art must survive Suno's expiring CDN URLs.

Stored covers are raw Suno CDN links. ``_ensure_cover_urls`` used to store them
once and never refresh, so an expired/hotlink-blocked URL stayed broken forever.
Rows whose cover is missing or still points at Suno are now re-polled.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services import web_music_service as svc_mod
from platform_api.services.web_music_service import (
    WebMusicService,
    _cover_url_looks_ephemeral,
)


@pytest.mark.parametrize(
    "value",
    ["", "   ", None, "https://cdn1.suno.ai/image_abc.jpeg", "https://cdn.suno.com/x.png"],
)
def test_ephemeral_covers_detected(value: object) -> None:
    assert _cover_url_looks_ephemeral(value) is True


@pytest.mark.parametrize(
    "value",
    ["https://storage.camxora.com/covers/x.jpeg", "https://b2.example.com/x.png"],
)
def test_durable_covers_kept(value: str) -> None:
    assert _cover_url_looks_ephemeral(value) is False


def _service(pool: AsyncMock) -> WebMusicService:
    return WebMusicService(pool=pool, generation_service=AsyncMock(), redis=None)


@pytest.mark.asyncio
async def test_expired_suno_cover_is_refreshed(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value="UPDATE 1")
    pool.fetchrow = AsyncMock(return_value={"id": uuid4(), "image_url_ok": "https://cdn1.suno.ai/new.jpeg"})
    service = _service(pool)
    polled = SimpleNamespace(state="success")
    service._poll_suno_task_status = AsyncMock(return_value=polled)
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
        "image_url_ok": "https://cdn1.suno.ai/stale.jpeg",
        "image_url_alt": None,
    }

    await service._ensure_cover_urls(row)

    service._poll_suno_task_status.assert_awaited_once()
    assert "UPDATE suno_tasks" in pool.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_durable_cover_is_not_repolled(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = AsyncMock()
    pool.execute = AsyncMock()
    service = _service(pool)
    service._poll_suno_task_status = AsyncMock()

    row = {
        "id": uuid4(),
        "status": "SUCCESS",
        "external_task_id": "suno-task-1",
        "image_url_ok": "https://storage.camxora.com/covers/ok.jpeg",
        "image_url_alt": "https://storage.camxora.com/covers/alt.jpeg",
    }

    result = await service._ensure_cover_urls(row)

    service._poll_suno_task_status.assert_not_awaited()
    pool.execute.assert_not_awaited()
    assert result is row
