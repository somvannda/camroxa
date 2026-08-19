"""Tests for timed music-web generation freeze and attack counters."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.requests import Request

from platform_api.exceptions import GenerationFrozenError
from platform_api.services import generation_freeze as freeze_mod
from platform_api.services.generation_freeze import (
    RATE_LIMIT_STORM_THRESHOLD,
    configure_generation_freeze,
    enforce_generation_freeze,
    freeze_generation,
    freeze_status,
    note_rate_limit_storm,
    payload_looks_like_probe,
    unfreeze_generation,
)


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._ttl: dict[str, int] = {}

    async def get(self, name: str) -> str | None:
        value = self._store.get(name)
        return None if value is None else str(value)

    async def setex(self, name: str, time: int, value: str) -> None:
        self._store[name] = value
        self._ttl[name] = time

    async def incr(self, name: str) -> int:
        current = int(self._store.get(name) or 0) + 1
        self._store[name] = current
        return current

    async def expire(self, name: str, time: int) -> None:
        if name in self._store:
            self._ttl[name] = time

    async def delete(self, *names: str) -> None:
        for name in names:
            self._store.pop(name, None)
            self._ttl.pop(name, None)

    async def ttl(self, name: str) -> int:
        if name not in self._store:
            return -2
        return int(self._ttl.get(name, -1))


def _request(path: str = "/api/v1/web-music/generate", ip: str = "203.0.113.9") -> Request:
    async def receive() -> dict:
        return {"type": "http.request"}

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [
            (b"host", b"music.camxora.com"),
            (b"cf-connecting-ip", ip.encode()),
            (b"cf-ipcountry", b"KH"),
        ],
        "client": (ip, 1234),
        "server": ("music.camxora.com", 443),
    }
    return Request(scope, receive)


@pytest.fixture
def redis() -> FakeRedis:
    client = FakeRedis()
    configure_generation_freeze(client)
    return client


@pytest.mark.asyncio
async def test_freeze_blocks_then_unfreeze_clears(redis: FakeRedis) -> None:
    user_id = "11111111-1111-1111-1111-111111111111"
    request = _request()
    await enforce_generation_freeze(request, user_id)
    await freeze_generation(user_id=user_id, ip="203.0.113.9", hours=6, reason="admin")
    with pytest.raises(GenerationFrozenError) as exc_info:
        await enforce_generation_freeze(request, user_id)
    assert exc_info.value.error_code == "GENERATION_FROZEN"
    assert exc_info.value.details["retry_after"] > 0
    status = await freeze_status(user_id)
    assert status["generation_frozen"] is True
    await unfreeze_generation(user_id=user_id, ip="203.0.113.9")
    await enforce_generation_freeze(request, user_id)
    status = await freeze_status(user_id)
    assert status["generation_frozen"] is False


@pytest.mark.asyncio
async def test_rate_limit_storm_freezes_user_and_ip(redis: FakeRedis) -> None:
    user_id = "22222222-2222-2222-2222-222222222222"
    request = _request()
    for _ in range(RATE_LIMIT_STORM_THRESHOLD - 1):
        await note_rate_limit_storm(request, user_id)
    await enforce_generation_freeze(request, user_id)
    await note_rate_limit_storm(request, user_id)
    with pytest.raises(GenerationFrozenError):
        await enforce_generation_freeze(request, user_id)
    other_user = _request()
    with pytest.raises(GenerationFrozenError):
        await enforce_generation_freeze(other_user, "33333333-3333-3333-3333-333333333333")


@pytest.mark.asyncio
async def test_expired_ttl_unfreezes(redis: FakeRedis) -> None:
    user_id = "44444444-4444-4444-4444-444444444444"
    await freeze_generation(user_id=user_id, ip=None, hours=1, reason="test")
    redis._store.clear()
    redis._ttl.clear()
    await enforce_generation_freeze(_request(), user_id)


def test_payload_probe_detects_injection() -> None:
    assert payload_looks_like_probe("hello union select password from users")
    assert payload_looks_like_probe("../etc/passwd")
    assert payload_looks_like_probe("<script>alert(1)</script>")
    assert not payload_looks_like_probe("a calm khmer ballad about rain")


@pytest.fixture(autouse=True)
def _mute_admin_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(freeze_mod, "_alert_admins", _noop)
