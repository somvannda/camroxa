"""Read-path Suno poll coalescing.

Production evidence (Nov 2026): `GET /api/v3/web-music/generations/{id}` polled
Suno inline across every pool key (30s timeout each) and the browser calls that
route every few seconds. Requests reached 200s+, piled up, and starved the API
(auth refresh took 13-90s and returned 499/502). These tests pin the fix: at
most one bounded poll per task per window, shared across request instances.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from platform_api.clients.suno_client import SunoGeneratePollResult
from platform_api.services import web_music_service as wms


def _service() -> wms.WebMusicService:
    return wms.WebMusicService(pool=AsyncMock(), generation_service=AsyncMock(), redis=None)


def _pending_row() -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "status": "pending",
        "external_task_id": "ext-1",
    }


@pytest.fixture(autouse=True)
def _reset_cache():
    wms.reset_pending_poll_cache()
    yield
    wms.reset_pending_poll_cache()


@pytest.mark.asyncio
async def test_poll_is_shared_across_request_instances_within_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def _poll(_external_id: str):
        nonlocal calls
        calls += 1
        return SunoGeneratePollResult(state="pending")

    first = _service()
    second = _service()
    monkeypatch.setattr(first, "_poll_suno_task_status", _poll)
    monkeypatch.setattr(second, "_poll_suno_task_status", _poll)

    assert await first._refresh_pending_from_suno(_pending_row()) is not None
    assert await second._refresh_pending_from_suno(_pending_row()) is not None

    assert calls == 1


@pytest.mark.asyncio
async def test_concurrent_reads_poll_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def _poll(_external_id: str):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return SunoGeneratePollResult(state="pending")

    first = _service()
    second = _service()
    monkeypatch.setattr(first, "_poll_suno_task_status", _poll)
    monkeypatch.setattr(second, "_poll_suno_task_status", _poll)

    await asyncio.gather(
        first._refresh_pending_from_suno(_pending_row()),
        second._refresh_pending_from_suno(_pending_row()),
    )

    assert calls == 1


@pytest.mark.asyncio
async def test_slow_poll_times_out_and_serves_the_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wms, "_PENDING_POLL_TIMEOUT_SECONDS", 0.05)

    async def _poll(_external_id: str):
        await asyncio.sleep(1.0)
        return SunoGeneratePollResult(state="pending")

    service = _service()
    monkeypatch.setattr(service, "_poll_suno_task_status", _poll)
    row = _pending_row()

    result = await service._refresh_pending_from_suno(row)

    assert result is row


@pytest.mark.asyncio
async def test_poll_runs_again_after_the_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wms, "_PENDING_POLL_TTL_SECONDS", 0.02)
    calls = 0

    async def _poll(_external_id: str):
        nonlocal calls
        calls += 1
        return SunoGeneratePollResult(state="pending")

    service = _service()
    monkeypatch.setattr(service, "_poll_suno_task_status", _poll)

    await service._refresh_pending_from_suno(_pending_row())
    await asyncio.sleep(0.03)
    await service._refresh_pending_from_suno(_pending_row())

    assert calls == 2


@pytest.mark.asyncio
async def test_poll_failure_is_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _poll(_external_id: str):
        raise RuntimeError("provider down")

    service = _service()
    monkeypatch.setattr(service, "_poll_suno_task_status", _poll)
    row = _pending_row()

    result = await service._refresh_pending_from_suno(row)

    assert result is row
