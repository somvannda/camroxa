"""Startup background loops wait for the restart burst to drain first."""

from __future__ import annotations

import asyncio

import pytest

from platform_api.services import grant_maintenance, streaming_upload_service


@pytest.mark.asyncio
async def test_grant_maintenance_waits_for_startup_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passes: list[int] = []

    async def _run_once(_pool):
        passes.append(1)
        return {}

    monkeypatch.setattr(grant_maintenance, "_run_once", _run_once)
    task = asyncio.create_task(
        grant_maintenance.run_grant_maintenance_loop(None, startup_delay=30)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert passes == []


@pytest.mark.asyncio
async def test_streaming_retry_does_not_touch_the_pool_during_grace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: list[object] = []

    class _Service:
        def __init__(self, pool) -> None:
            constructed.append(pool)

    monkeypatch.setattr(streaming_upload_service, "StreamingUploadService", _Service)
    task = asyncio.create_task(
        streaming_upload_service.run_streaming_auto_retry_loop(None, startup_delay=30)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert constructed == []
