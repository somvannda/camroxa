"""Tests for SLAI image rate limiting."""

from __future__ import annotations

import asyncio
import time

import pytest

from platform_api.services.slai_image_rate_limiter import SlaiImageRateLimiter


@pytest.mark.asyncio
async def test_slai_rate_limiter_enforces_minimum_interval() -> None:
    limiter = SlaiImageRateLimiter()
    limiter.configure(min_interval_seconds=0.2, max_concurrent=1)

    async with limiter.slot():
        first = time.monotonic()

    async with limiter.slot():
        second = time.monotonic()

    assert second - first >= 0.19


@pytest.mark.asyncio
async def test_slai_rate_limiter_limits_concurrency() -> None:
    limiter = SlaiImageRateLimiter()
    limiter.configure(min_interval_seconds=0.0, max_concurrent=1)

    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def worker() -> None:
        nonlocal active, peak
        async with limiter.slot():
            async with lock:
                active += 1
                peak = max(peak, active)
            await asyncio.sleep(0.05)
            async with lock:
                active -= 1

    await asyncio.gather(*(worker() for _ in range(4)))
    assert peak == 1
