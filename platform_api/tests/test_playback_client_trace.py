"""Client playback traces are stored and logged."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.services.content_license_service import ContentLicenseService


@pytest.mark.asyncio
async def test_record_client_trace_writes_playback_event() -> None:
    pool = AsyncMock()
    pool.execute = AsyncMock()
    service = ContentLicenseService(pool, redis=None)
    service.resolve_session = AsyncMock(return_value=None)  # type: ignore[method-assign]
    user_id = uuid4()
    result = await service.record_client_trace(
        user_id,
        token=None,
        event="play_error",
        detail="stage=html_play AbortError The operation was aborted.",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0)",
        ip="1.2.3.4",
    )
    assert result["ok"] is True
    pool.execute.assert_awaited()
    args = pool.execute.await_args.args
    assert "playback_events" in args[0]
    assert args[7] == "play_error"
    assert "aborted" in str(args[10])


@pytest.mark.asyncio
async def test_record_client_trace_unknown_event_becomes_play_error() -> None:
    pool = AsyncMock()
    pool.execute = AsyncMock()
    service = ContentLicenseService(pool, redis=None)
    service.resolve_session = AsyncMock(return_value=None)  # type: ignore[method-assign]
    await service.record_client_trace(
        uuid4(),
        token=None,
        event="not_a_real_event",
        detail="x",
    )
    assert pool.execute.await_args.args[7] == "play_error"
