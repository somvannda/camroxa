"""Fire-and-forget LRC tasks must not log unretrieved exceptions on shutdown."""

from __future__ import annotations

import asyncio
import logging

import pytest

from platform_api.services.streaming_upload_service import _log_background_task_error


async def _failed_task(message: str) -> asyncio.Task:
    async def _boom() -> None:
        raise RuntimeError(message)

    task = asyncio.create_task(_boom())
    with pytest.raises(RuntimeError):
        await task
    return task


@pytest.mark.asyncio
async def test_pool_closing_error_is_consumed(caplog: pytest.LogCaptureFixture) -> None:
    task = await _failed_task("pool is closing")

    _log_background_task_error(task)

    assert task.exception() is not None


@pytest.mark.asyncio
async def test_other_errors_are_logged_as_warnings(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    task = await _failed_task("unexpected failure")

    _log_background_task_error(task)

    assert any("LRC upload task failed" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_successful_and_cancelled_tasks_are_ignored() -> None:
    ok = asyncio.create_task(asyncio.sleep(0))
    await ok
    _log_background_task_error(ok)

    cancelled = asyncio.create_task(asyncio.sleep(1))
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    _log_background_task_error(cancelled)
