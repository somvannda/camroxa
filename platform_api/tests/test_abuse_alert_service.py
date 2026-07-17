"""Phase 3 abuse alert service unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from platform_api.services.abuse_alert_service import AbuseAlertService


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def incr(self, key: str) -> int:
        value = int(self.store.get(key, "0")) + 1
        self.store[key] = str(value)
        return value

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> Any:
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True


@pytest.mark.asyncio
async def test_polish_probe_storm_alerts_once() -> None:
    redis = FakeRedis()
    notifier = AsyncMock()
    admin = AsyncMock()
    admin.get_admin_user_ids = AsyncMock(return_value=["admin-1"])
    service = AbuseAlertService(
        redis=redis,  # type: ignore[arg-type]
        notification_service=notifier,
        admin_provider=admin,
        polish_probe_threshold=3,
    )

    await service.note_polish_probe(user_id="u1")
    await service.note_polish_probe(user_id="u1")
    assert notifier.push.await_count == 0

    await service.note_polish_probe(user_id="u1")
    assert notifier.push.await_count == 1
    assert notifier.push.await_args.args[1] == "admin:abuse_alert"

    await service.note_polish_probe(user_id="u1")
    # Cooldown blocks a second push
    assert notifier.push.await_count == 1


@pytest.mark.asyncio
async def test_absorb_spike_alerts_near_budget() -> None:
    redis = FakeRedis()
    notifier = AsyncMock()
    admin = AsyncMock()
    admin.get_admin_user_ids = AsyncMock(return_value=["admin-1"])
    service = AbuseAlertService(
        redis=redis,  # type: ignore[arg-type]
        notification_service=notifier,
        admin_provider=admin,
        absorb_alert_threshold=20,
    )
    await service.note_absorb(user_id="u1", count=20, budget=25)
    assert notifier.push.await_count == 1
    payload = notifier.push.await_args.args[2]
    assert payload["kind"] == "absorb_spike"
