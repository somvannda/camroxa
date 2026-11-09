"""Back-pressure guards for the asyncpg pool.

Production auth refresh was seen waiting 13-90s for a pooled connection while
slow web-music reads held all 8 connections per worker. The pool now bounds the
acquire wait, returns 503 (retryable) instead of hanging, and warns when it
stays saturated.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from platform_api import main as api_main
from platform_api.config import Settings


class _Pool:
    def __init__(self, *, idle: int, size: int) -> None:
        self._idle = idle
        self._size = size

    def get_idle_size(self) -> int:
        return self._idle

    def get_size(self) -> int:
        return self._size


def test_pool_is_saturated_only_when_no_idle_connections() -> None:
    assert api_main._pool_is_saturated(_Pool(idle=0, size=8), max_size=8) is True
    assert api_main._pool_is_saturated(_Pool(idle=1, size=8), max_size=8) is False
    assert api_main._pool_is_saturated(_Pool(idle=0, size=4), max_size=8) is False


def test_pool_is_saturated_is_exception_safe() -> None:
    assert api_main._pool_is_saturated(object(), max_size=8) is False


def test_db_busy_response_is_retryable() -> None:
    response = api_main._db_busy_response()

    assert response.status_code == 503
    assert response.headers["retry-after"] == "2"


@pytest.mark.asyncio
async def test_acquire_timeout_maps_to_503() -> None:
    request = SimpleNamespace(method="GET", url=SimpleNamespace(path="/api/v3/users/me"))

    response = await api_main._db_pool_timeout_handler(request, TimeoutError())

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_pool_monitor_warns_when_saturated(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("WARNING")
    task = asyncio.create_task(
        api_main._watch_pool_saturation(
            _Pool(idle=0, size=8),
            max_size=8,
            warn_after_seconds=0.01,
            interval_seconds=0.01,
        )
    )
    await asyncio.sleep(0.06)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert any("Database pool saturated" in record.message for record in caplog.records)


def test_pool_acquire_timeout_defaults_are_bounded() -> None:
    settings = Settings()

    assert 0 < settings.db_pool_acquire_timeout_seconds <= 30
    assert settings.db_pool_saturation_log_seconds > 0
