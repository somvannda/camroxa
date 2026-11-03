"""A cancelled web Create request must not keep the user's credits.

Regression for the charge-without-a-song bug: the debit is written before the
``suno_tasks`` row exists, so a cancellation (client double-click, navigation,
timeout) used to escape the ``except Exception`` handler - ``CancelledError``
derives from ``BaseException`` - leaving a paid song with no task and no refund.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.services.web_music_service import WebMusicService


@pytest.fixture
def mute_blocklist(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MagicMock()
    service.get_runtime_config = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "platform_api.dependencies.get_suno_blocklist_service",
        lambda: service,
    )


def _service() -> WebMusicService:
    service = WebMusicService(MagicMock(), MagicMock())
    service._is_paid_queue_user = AsyncMock(return_value=True)
    service._active_generate_queue_count = AsyncMock(return_value=0)
    service._reserve_daily_slot = AsyncMock(
        return_value={"limit": 1000, "used": 0, "remaining": 100, "is_pro": True}
    )
    service._release_daily_slot = AsyncMock()
    service._link_generation_debit_reference = AsyncMock()
    service._resolve_workspace_id = AsyncMock(return_value=uuid4())
    service._with_queue_fields = AsyncMock(side_effect=lambda _uid, quota: dict(quota))
    return service


async def _generate(service: WebMusicService):
    return await service.generate(
        uuid4(),
        mode="advanced",
        lyrics="verse",
        style="pop",
        title="Hello Song",
        instrumental=False,
        model="V6_MINI",
        prompt="",
    )


@pytest.mark.asyncio
async def test_cancelled_enqueue_refunds_the_charge(mute_blocklist) -> None:
    service = _service()
    service._enqueue_web_generate = AsyncMock(side_effect=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await _generate(service)

    service._release_daily_slot.assert_awaited_once()
    kwargs = service._release_daily_slot.await_args.kwargs
    assert kwargs["reference_id"]
    assert kwargs["task_id"] is None


@pytest.mark.asyncio
async def test_cancelling_the_request_task_still_refunds(mute_blocklist) -> None:
    """A real task.cancel() (client disconnected) must still reverse the debit."""
    service = _service()
    started = asyncio.Event()

    async def slow_enqueue(*_args, **_kwargs):
        started.set()
        await asyncio.sleep(30)
        return uuid4()

    service._enqueue_web_generate = AsyncMock(side_effect=slow_enqueue)

    task = asyncio.create_task(_generate(service))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    # The refund runs in a shielded task, so let it finish.
    for _ in range(5):
        if service._release_daily_slot.await_count:
            break
        await asyncio.sleep(0.01)

    service._release_daily_slot.assert_awaited()


@pytest.mark.asyncio
async def test_failed_enqueue_still_refunds(mute_blocklist) -> None:
    service = _service()
    service._enqueue_web_generate = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await _generate(service)

    service._release_daily_slot.assert_awaited_once()
