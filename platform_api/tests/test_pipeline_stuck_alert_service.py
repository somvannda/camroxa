"""Pipeline stuck-batch detection + admin alert unit tests (PLATFORM_WORKERS_REQUIREMENTS.md §8)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from platform_api.services.pipeline_stuck_alert_service import PipelineStuckAlertService


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> Any:
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True


def _stuck_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "batch_id": "11111111-1111-1111-1111-111111111111",
        "user_id": "22222222-2222-2222-2222-222222222222",
        "user_email": "user@example.com",
        "status": "processing",
        "last_activity_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "age_seconds": 1200,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_scan_and_alert_pushes_to_every_admin() -> None:
    batch_repo = AsyncMock()
    batch_repo.list_stuck_batches = AsyncMock(return_value=[_stuck_row()])
    notifier = AsyncMock()
    admin = AsyncMock()
    admin.get_admin_user_ids = AsyncMock(return_value=["admin-1", "admin-2"])
    service = PipelineStuckAlertService(
        batch_repo=batch_repo,
        redis=FakeRedis(),
        notification_service=notifier,
        admin_provider=admin,
    )

    result = await service.scan_and_alert()

    assert len(result) == 1
    assert notifier.push.await_count == 2
    admin_ids_alerted = {call.args[0] for call in notifier.push.await_args_list}
    assert admin_ids_alerted == {"admin-1", "admin-2"}
    event_names = {call.args[1] for call in notifier.push.await_args_list}
    assert event_names == {"admin:pipeline_stuck_alert"}
    payload = notifier.push.await_args_list[0].args[2]
    assert payload["kind"] == "pipeline_stuck"
    assert payload["batch_id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["age_seconds"] == 1200


@pytest.mark.asyncio
async def test_scan_and_alert_respects_cooldown_per_batch() -> None:
    batch_repo = AsyncMock()
    batch_repo.list_stuck_batches = AsyncMock(return_value=[_stuck_row()])
    notifier = AsyncMock()
    admin = AsyncMock()
    admin.get_admin_user_ids = AsyncMock(return_value=["admin-1"])
    service = PipelineStuckAlertService(
        batch_repo=batch_repo,
        redis=FakeRedis(),
        notification_service=notifier,
        admin_provider=admin,
    )

    first = await service.scan_and_alert()
    second = await service.scan_and_alert()

    # Still reported as stuck both times (detection isn't throttled)...
    assert len(first) == 1
    assert len(second) == 1
    # ...but only alerted once (the second scan is within the cooldown window).
    assert notifier.push.await_count == 1


@pytest.mark.asyncio
async def test_scan_and_alert_different_batches_alert_independently() -> None:
    batch_repo = AsyncMock()
    batch_repo.list_stuck_batches = AsyncMock(
        return_value=[
            _stuck_row(batch_id="batch-a"),
            _stuck_row(batch_id="batch-b"),
        ]
    )
    notifier = AsyncMock()
    admin = AsyncMock()
    admin.get_admin_user_ids = AsyncMock(return_value=["admin-1"])
    service = PipelineStuckAlertService(
        batch_repo=batch_repo,
        redis=FakeRedis(),
        notification_service=notifier,
        admin_provider=admin,
    )

    await service.scan_and_alert()

    assert notifier.push.await_count == 2
    alerted_batch_ids = {call.args[2]["batch_id"] for call in notifier.push.await_args_list}
    assert alerted_batch_ids == {"batch-a", "batch-b"}


@pytest.mark.asyncio
async def test_scan_and_alert_returns_empty_and_never_raises_when_repo_fails() -> None:
    batch_repo = AsyncMock()
    batch_repo.list_stuck_batches = AsyncMock(side_effect=RuntimeError("db unavailable"))
    service = PipelineStuckAlertService(
        batch_repo=batch_repo,
        redis=FakeRedis(),
        notification_service=AsyncMock(),
        admin_provider=AsyncMock(),
    )

    result = await service.scan_and_alert()

    assert result == []


@pytest.mark.asyncio
async def test_scan_and_alert_noop_when_notification_service_not_configured() -> None:
    batch_repo = AsyncMock()
    batch_repo.list_stuck_batches = AsyncMock(return_value=[_stuck_row()])
    service = PipelineStuckAlertService(
        batch_repo=batch_repo,
        redis=FakeRedis(),
        notification_service=None,
        admin_provider=None,
    )

    result = await service.scan_and_alert()

    assert len(result) == 1  # detection still works without alert wiring configured


@pytest.mark.asyncio
async def test_scan_and_alert_survives_a_single_admin_push_failure() -> None:
    batch_repo = AsyncMock()
    batch_repo.list_stuck_batches = AsyncMock(return_value=[_stuck_row()])
    notifier = AsyncMock()
    notifier.push = AsyncMock(side_effect=[RuntimeError("ws closed"), None])
    admin = AsyncMock()
    admin.get_admin_user_ids = AsyncMock(return_value=["admin-1", "admin-2"])
    service = PipelineStuckAlertService(
        batch_repo=batch_repo,
        redis=FakeRedis(),
        notification_service=notifier,
        admin_provider=admin,
    )

    result = await service.scan_and_alert()

    assert len(result) == 1
    assert notifier.push.await_count == 2  # still tried the second admin after the first failed
