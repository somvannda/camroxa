"""Process-wide throttle for SLAI image requests.

Serializes and spaces SLAI calls so parallel image workers do not hammer the
cheapest provider and trigger immediate fallback to more expensive models.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from platform_api.services import image_progress_log as image_log

_DEFAULT_MIN_INTERVAL_SECONDS = 5.0
_DEFAULT_MAX_CONCURRENT = 1


class SlaiImageRateLimiter:
    """Limit concurrent SLAI image calls and enforce a minimum interval."""

    def __init__(self) -> None:
        self._min_interval_seconds = _DEFAULT_MIN_INTERVAL_SECONDS
        self._max_concurrent = _DEFAULT_MAX_CONCURRENT
        self._semaphore = asyncio.Semaphore(_DEFAULT_MAX_CONCURRENT)
        self._spacing_lock = asyncio.Lock()
        self._last_request_at = 0.0

    def configure(
        self,
        *,
        min_interval_seconds: float | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        if min_interval_seconds is not None:
            self._min_interval_seconds = max(0.0, float(min_interval_seconds))

        if max_concurrent is not None:
            normalized = max(1, min(8, int(max_concurrent)))
            if normalized != self._max_concurrent:
                self._max_concurrent = normalized
                self._semaphore = asyncio.Semaphore(normalized)

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        await self._semaphore.acquire()
        try:
            wait_seconds = 0.0
            async with self._spacing_lock:
                if self._last_request_at > 0 and self._min_interval_seconds > 0:
                    elapsed = time.monotonic() - self._last_request_at
                    wait_seconds = self._min_interval_seconds - elapsed
                    if wait_seconds > 0:
                        image_log.log_slai_rate_limit_wait(wait_seconds)
                        await asyncio.sleep(wait_seconds)
                self._last_request_at = time.monotonic()
            yield
        finally:
            self._semaphore.release()


_limiter = SlaiImageRateLimiter()


def get_slai_image_rate_limiter() -> SlaiImageRateLimiter:
    return _limiter


def configure_slai_image_rate_limit(
    *,
    min_interval_seconds: float | None = None,
    max_concurrent: int | None = None,
) -> None:
    _limiter.configure(
        min_interval_seconds=min_interval_seconds,
        max_concurrent=max_concurrent,
    )
