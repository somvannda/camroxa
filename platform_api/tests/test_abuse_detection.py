"""Unit tests for IP signup/generation farm caps."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from platform_api.middleware.abuse_detection import (
    MAX_ACCOUNTS_PER_IP_PER_HOUR,
    MAX_GENERATIONS_PER_IP_PER_DAY,
    check_ip_abuse,
)


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get(self, name: str) -> str | None:
        value = self._store.get(name)
        return None if value is None else str(value)

    async def setex(self, name: str, time: int, value: str) -> None:
        self._store[name] = value

    async def incr(self, name: str) -> int:
        current = int(self._store.get(name) or 0) + 1
        self._store[name] = current
        return current

    async def expire(self, name: str, time: int) -> None:
        return None


@pytest.mark.asyncio
async def test_signup_ip_hourly_cap() -> None:
    redis = _FakeRedis()
    ip = "203.0.113.10"
    for _ in range(MAX_ACCOUNTS_PER_IP_PER_HOUR):
        await check_ip_abuse(redis, ip, "", "account_creation")
    with pytest.raises(HTTPException) as exc_info:
        await check_ip_abuse(redis, ip, "", "account_creation")
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error_code"] == "SIGNUP_IP_LIMIT"


@pytest.mark.asyncio
async def test_signup_cap_still_429s_and_freeze_is_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generate freeze must not replace 3/hour signup farm protection."""
    redis = _FakeRedis()
    ip = "203.0.113.13"
    freeze_calls: list[tuple[str | None, str | None, str]] = []

    async def _fake_freeze(
        *,
        user_id: str | None = None,
        ip: str | None = None,
        reason: str = "",
        hours: int | None = None,
    ) -> None:
        freeze_calls.append((user_id, ip, reason))

    monkeypatch.setattr(
        "platform_api.services.generation_freeze.freeze_generation",
        _fake_freeze,
    )
    for _ in range(MAX_ACCOUNTS_PER_IP_PER_HOUR):
        await check_ip_abuse(redis, ip, "", "account_creation")
    with pytest.raises(HTTPException) as exc_info:
        await check_ip_abuse(redis, ip, "", "account_creation")
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error_code"] == "SIGNUP_IP_LIMIT"
    assert freeze_calls == [(None, ip, "signup_farm")]


@pytest.mark.asyncio
async def test_generation_ip_daily_cap() -> None:
    """Users with nothing to spend still hit the per-IP farm cap."""
    redis = _FakeRedis()
    ip = "203.0.113.11"
    for _ in range(MAX_GENERATIONS_PER_IP_PER_DAY):
        await check_ip_abuse(redis, ip, "user-1", "generation")
    with pytest.raises(HTTPException) as exc_info:
        await check_ip_abuse(redis, ip, "user-2", "generation")
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error_code"] == "IP_DAILY_LIMIT"


@pytest.mark.asyncio
async def test_generation_ip_daily_cap_skipped_for_credited_users() -> None:
    """Credit-funded users are gated by their balance, not the per-IP cap."""
    redis = _FakeRedis()
    ip = "203.0.113.14"
    for _ in range(MAX_GENERATIONS_PER_IP_PER_DAY * 3):
        await check_ip_abuse(redis, ip, "paid-user", "generation", credited=True)


@pytest.mark.asyncio
async def test_generation_does_not_call_geo_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _FakeRedis()

    async def _fail_geo(_ip: str) -> tuple[str, str]:
        raise AssertionError("geo lookup should stay disabled")

    monkeypatch.setattr(
        "platform_api.middleware.abuse_detection.check_ip_geolocation",
        _fail_geo,
    )
    await check_ip_abuse(redis, "203.0.113.12", "user-1", "generation")
