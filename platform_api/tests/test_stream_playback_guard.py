"""Tests for stream play client gate and unique-window pacing."""

from __future__ import annotations

import json

import pytest

from platform_api.exceptions import ForbiddenError, RateLimitedError
from platform_api.services.stream_playback_guard import (
    PaceSnapshot,
    STREAM_UNIQUE_WINDOW_LIMIT,
    STREAM_UNIQUE_WINDOW_SECONDS,
    assert_browser_audio_request,
    enforce_unique_window_pace,
    evaluate_unique_window_pace,
    is_browser_audio_request,
    window_id_for_range,
)


def test_window_id_uses_clamped_256kib_windows() -> None:
    assert window_id_for_range(None) == 0
    assert window_id_for_range("bytes=0-") == 0
    assert window_id_for_range("bytes=262144-") == 1
    assert window_id_for_range("bytes=4780000-") == 18


def test_browser_audio_dest_is_required_when_present() -> None:
    assert is_browser_audio_request({"Sec-Fetch-Dest": "audio"}) is True
    assert is_browser_audio_request({"sec-fetch-dest": "empty"}) is False
    assert is_browser_audio_request({"sec-fetch-dest": "document"}) is False


def test_legacy_browser_can_use_music_referer() -> None:
    assert (
        is_browser_audio_request({"Referer": "https://music.camxora.com/create"}) is True
    )
    assert (
        is_browser_audio_request(
            {"Referer": "https://music.sandbox.camxora.com/explore"}
        )
        is True
    )
    assert is_browser_audio_request({"Referer": "http://localhost:3003/create"}) is True
    assert is_browser_audio_request({"Referer": "https://evil.example/download"}) is False


def test_curl_without_browser_hints_is_denied() -> None:
    assert is_browser_audio_request(None) is False
    assert is_browser_audio_request({}) is False
    assert is_browser_audio_request({"User-Agent": "curl/8.0"}) is False
    with pytest.raises(ForbiddenError) as exc:
        assert_browser_audio_request({"Range": "bytes=0-"})
    assert exc.value.details["code"] == "playback_client_denied"


def test_pace_retries_same_window_without_consuming_budget() -> None:
    now = 1_000.0
    first = evaluate_unique_window_pace(PaceSnapshot(frozenset(), ()), 0, now=now)
    assert first.allowed is True
    retry = evaluate_unique_window_pace(first.snapshot, 0, now=now + 0.01)
    assert retry.allowed is True
    assert retry.snapshot.seen == first.snapshot.seen
    assert retry.snapshot.new_at == first.snapshot.new_at


def test_pace_blocks_fast_unique_window_walk() -> None:
    snapshot = PaceSnapshot(frozenset(), ())
    now = 5_000.0
    for window_id in range(STREAM_UNIQUE_WINDOW_LIMIT):
        decision = evaluate_unique_window_pace(snapshot, window_id, now=now)
        assert decision.allowed is True
        snapshot = decision.snapshot
    blocked = evaluate_unique_window_pace(
        snapshot,
        STREAM_UNIQUE_WINDOW_LIMIT,
        now=now + 1,
    )
    assert blocked.allowed is False
    assert blocked.retry_after >= 1
    later = evaluate_unique_window_pace(
        snapshot,
        STREAM_UNIQUE_WINDOW_LIMIT,
        now=now + STREAM_UNIQUE_WINDOW_SECONDS,
    )
    assert later.allowed is True


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value


@pytest.mark.asyncio
async def test_enforce_pace_persists_seen_windows() -> None:
    redis = _FakeRedis()
    await enforce_unique_window_pace(redis, "user:1:task:abc:ok", "bytes=0-", now=10.0)
    await enforce_unique_window_pace(
        redis, "user:1:task:abc:ok", "bytes=0-262143", now=10.1
    )
    payload = json.loads(redis.store["web_music:stream_pace:user:1:task:abc:ok"])
    assert payload["seen"] == [0]


@pytest.mark.asyncio
async def test_enforce_pace_raises_rate_limited() -> None:
    redis = _FakeRedis()
    now = 20.0
    for index in range(STREAM_UNIQUE_WINDOW_LIMIT):
        start = index * 262144
        await enforce_unique_window_pace(
            redis,
            "user:1:track:t",
            f"bytes={start}-",
            now=now,
        )
    with pytest.raises(RateLimitedError) as exc:
        await enforce_unique_window_pace(
            redis,
            "user:1:track:t",
            f"bytes={STREAM_UNIQUE_WINDOW_LIMIT * 262144}-",
            now=now + 0.5,
        )
    assert exc.value.retry_after >= 1
    assert exc.value.details["code"] == "stream_window_pace"


@pytest.mark.asyncio
async def test_enforce_pace_without_redis_is_noop() -> None:
    await enforce_unique_window_pace(None, "user:1:track:t", "bytes=0-")
