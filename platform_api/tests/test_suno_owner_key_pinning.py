"""Owner-key pinning for Suno status polls.

Suno's record-info endpoint is account-scoped. Before pinning, every poll tried
each active key until the owner answered (3 provider calls with 3 keys). The
resolver now tries the recorded owner first and persists the winner.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import ExternalServiceError
from platform_api.services import suno_audio_resolver as resolver


KEY_A, KEY_B, KEY_C = str(uuid4()), str(uuid4()), str(uuid4())


class _Pool:
    def __init__(self, *, pinned_id: str | None = None, lookup_error: bool = False) -> None:
        self.pinned_id = pinned_id
        self.lookup_error = lookup_error
        self.updates: list[tuple] = []

    async def fetchrow(self, _query: str, *_args):
        if self.lookup_error:
            raise RuntimeError("column does not exist")
        if self.pinned_id:
            return {"suno_key_id": self.pinned_id}
        return None

    async def execute(self, _query: str, *args) -> None:
        self.updates.append(args)


class _FakeSunoClient:
    owner = "A"
    calls: list[str] = []

    def __init__(self, _settings) -> None:
        pass

    async def check_status(self, _task_id: str, *, api_key: str):
        type(self).calls.append(api_key)
        if api_key != type(self).owner:
            raise ExternalServiceError(
                "wrong account", details={"status_code": 403}
            )
        return {"api_key": api_key}


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch):
    _FakeSunoClient.calls = []
    _FakeSunoClient.owner = "A"
    monkeypatch.setattr(
        "platform_api.clients.suno_client.SunoClient", _FakeSunoClient
    )
    monkeypatch.setattr(
        "platform_api.clients.suno_client.parse_suno_generate_poll",
        lambda response: response,
    )

    async def _entries(_pool, provider=None):
        return [(KEY_A, "A"), (KEY_B, "B"), (KEY_C, "C")]

    monkeypatch.setattr(resolver, "active_suno_key_entries", _entries)
    yield


@pytest.mark.asyncio
async def test_pinned_key_is_tried_first_and_only_once() -> None:
    _FakeSunoClient.owner = "C"
    pool = _Pool(pinned_id=KEY_C)

    result = await resolver.poll_suno_generate_with_pool(pool, "task-1")

    assert result == {"api_key": "C"}
    assert _FakeSunoClient.calls == ["C"]
    assert pool.updates == []


@pytest.mark.asyncio
async def test_unpinned_poll_scans_then_persists_the_owner() -> None:
    _FakeSunoClient.owner = "B"
    pool = _Pool()

    result = await resolver.poll_suno_generate_with_pool(pool, "task-1")

    assert result == {"api_key": "B"}
    assert _FakeSunoClient.calls == ["A", "B"]
    assert pool.updates == [("task-1", UUID(KEY_B))]


@pytest.mark.asyncio
async def test_stale_pin_falls_back_and_re_pins() -> None:
    _FakeSunoClient.owner = "C"
    pool = _Pool(pinned_id=KEY_A)

    result = await resolver.poll_suno_generate_with_pool(pool, "task-1")

    assert result == {"api_key": "C"}
    assert _FakeSunoClient.calls == ["A", "B", "C"]
    assert pool.updates == [("task-1", UUID(KEY_C))]


@pytest.mark.asyncio
async def test_pin_lookup_failure_falls_back_to_a_scan() -> None:
    _FakeSunoClient.owner = "B"
    pool = _Pool(lookup_error=True)

    result = await resolver.poll_suno_generate_with_pool(pool, "task-1")

    assert result == {"api_key": "B"}
    assert _FakeSunoClient.calls == ["A", "B"]


@pytest.mark.asyncio
async def test_key_value_helper_still_returns_plain_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _entries(_pool, provider=None):
        return [(KEY_A, "A"), (KEY_B, "B")]

    monkeypatch.setattr(resolver, "active_suno_key_entries", _entries)

    assert await resolver.active_suno_key_values(None) == ["A", "B"]
