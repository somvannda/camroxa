"""Unit tests for KeyPoolService key selection logic.

Tests round-robin and priority selection strategies, active key filtering,
NoAvailableKeysError, and CRUD operations.

Requirements: 2.1, 2.2, 2.3, 2.5, 3.3, 3.4
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import DuplicateKeyLabelError, NoAvailableKeysError
from platform_api.models.domain import ApiKeyEntry, KeyPoolConfig
from platform_api.models.enums import KeyStatus, SelectionStrategy
from platform_api.services.key_encryption import KeyEncryption
from platform_api.services.key_pool_service import KeyPoolService


# ---------------------------------------------------------------------------
# Fake Redis for unit-testing without a real server
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal async Redis stub supporting incr, delete, exists, scan, zadd, zrange, sadd."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._zsets: dict[str, dict[str, float]] = {}
        self._sets: dict[str, set[str]] = {}

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, "0"))
        current += 1
        self._store[key] = str(current)
        return current

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                count += 1
            if key in self._zsets:
                del self._zsets[key]
                count += 1
            if key in self._sets:
                del self._sets[key]
                count += 1
        return count

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, **kwargs: Any) -> None:
        self._store[key] = value

    async def setex(self, key: str, seconds: int, value: str) -> None:
        self._store[key] = value

    async def scan(self, cursor: int = 0, match: str | None = None, count: int = 100) -> tuple[int, list[str]]:
        """Simulate Redis SCAN with pattern matching."""
        import fnmatch

        if match:
            matched = [k for k in self._store if fnmatch.fnmatch(k, match)]
        else:
            matched = list(self._store.keys())
        # Return all matches at once (cursor=0 signals end)
        return 0, matched

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        """Add members to a sorted set with scores."""
        if key not in self._zsets:
            self._zsets[key] = {}
        added = 0
        for member, score in mapping.items():
            if member not in self._zsets[key]:
                added += 1
            self._zsets[key][member] = score
        return added

    async def zrange(self, key: str, start: int, end: int) -> list[str]:
        """Return members of a sorted set ordered by score (ascending)."""
        if key not in self._zsets:
            return []
        sorted_members = sorted(self._zsets[key].items(), key=lambda x: x[1])
        members = [m for m, _ in sorted_members]
        # Handle negative indexing
        if end < 0:
            end = len(members) + end + 1
        else:
            end = end + 1
        return members[start:end]

    async def sadd(self, key: str, *members: str) -> int:
        """Add members to a set."""
        if key not in self._sets:
            self._sets[key] = set()
        added = 0
        for m in members:
            if m not in self._sets[key]:
                self._sets[key].add(m)
                added += 1
        return added

    async def smembers(self, key: str) -> set[str]:
        """Return all members of a set."""
        return self._sets.get(key, set())


# ---------------------------------------------------------------------------
# Fake Repository
# ---------------------------------------------------------------------------


class FakeKeyPoolRepository:
    """In-memory repository stub for testing KeyPoolService."""

    def __init__(self) -> None:
        self._entries: dict[UUID, ApiKeyEntry] = {}
        self._configs: dict[str, KeyPoolConfig] = {}

    async def list_by_provider(self, provider: str) -> list[ApiKeyEntry]:
        return sorted(
            [e for e in self._entries.values() if e.provider == provider],
            key=lambda e: (e.priority, e.created_at),
        )

    async def get_active_by_provider(self, provider: str) -> list[ApiKeyEntry]:
        return sorted(
            [
                e
                for e in self._entries.values()
                if e.provider == provider and e.status == KeyStatus.ACTIVE
            ],
            key=lambda e: (e.priority, e.created_at),
        )

    async def get_by_id(self, key_id: UUID) -> ApiKeyEntry | None:
        return self._entries.get(key_id)

    async def create(self, entry: ApiKeyEntry) -> ApiKeyEntry:
        self._entries[entry.id] = entry
        return entry

    async def update(self, entry: ApiKeyEntry) -> None:
        self._entries[entry.id] = entry

    async def delete(self, key_id: UUID) -> None:
        self._entries.pop(key_id, None)

    async def get_provider_config(self, provider: str) -> KeyPoolConfig | None:
        return self._configs.get(provider)

    async def upsert_provider_config(self, config: KeyPoolConfig) -> None:
        self._configs[config.provider] = config

    async def increment_counters(
        self, key_id: UUID, *, success: bool, rate_limited: bool = False
    ) -> None:
        entry = self._entries.get(key_id)
        if entry is not None:
            entry.total_requests += 1
            entry.daily_requests += 1
            if success:
                entry.success_count += 1
            else:
                entry.failure_count += 1
            if rate_limited:
                entry.rate_limit_hits += 1
            entry.last_used_at = datetime.utcnow()

    async def reset_daily_counters(self) -> None:
        for entry in self._entries.values():
            entry.daily_requests = 0

    async def get_usage_stats(self, key_id: UUID) -> dict[str, Any]:
        return {}

    async def get_recent_events(self, provider: str, limit: int = 50) -> list[dict[str, Any]]:
        return []

    async def insert_status_event(self, event: Any) -> None:
        """Record status event (no-op for unit tests unless tracked)."""
        if not hasattr(self, "_events"):
            self._events: list[Any] = []
        self._events.append(event)

    async def get_all_providers(self) -> list[str]:
        """Return all distinct provider identifiers."""
        providers = sorted(set(e.provider for e in self._entries.values()))
        return providers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MASTER_KEY = "test-master-key-for-encryption"


@pytest.fixture
def encryption() -> KeyEncryption:
    return KeyEncryption(MASTER_KEY)


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def fake_repo() -> FakeKeyPoolRepository:
    return FakeKeyPoolRepository()


@pytest.fixture
def service(
    fake_repo: FakeKeyPoolRepository,
    encryption: KeyEncryption,
    fake_redis: FakeRedis,
) -> KeyPoolService:
    return KeyPoolService(
        repository=fake_repo,  # type: ignore[arg-type]
        encryption=encryption,
        redis=fake_redis,  # type: ignore[arg-type]
    )


def _make_entry(
    encryption: KeyEncryption,
    provider: str = "suno",
    label: str = "key-1",
    priority: int = 50,
    status: KeyStatus = KeyStatus.ACTIVE,
    key_value: str = "sk-test-key-value",
    key_id: UUID | None = None,
) -> ApiKeyEntry:
    """Helper to create an ApiKeyEntry with encrypted key value."""
    return ApiKeyEntry(
        id=key_id or uuid4(),
        provider=provider,
        label=label,
        encrypted_key_value=encryption.encrypt(key_value),
        priority=priority,
        status=status,
        created_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# Tests: Round-Robin Selection
# ---------------------------------------------------------------------------


class TestRoundRobinSelection:
    """Tests for round-robin key selection strategy."""

    @pytest.mark.asyncio
    async def test_cycles_through_active_keys(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Round-robin should cycle through all active keys in order."""
        # Configure round-robin strategy
        fake_repo._configs["suno"] = KeyPoolConfig(
            provider="suno", selection_strategy=SelectionStrategy.ROUND_ROBIN
        )

        keys = [
            _make_entry(encryption, label="key-A", priority=50, key_value="value-A"),
            _make_entry(encryption, label="key-B", priority=50, key_value="value-B"),
            _make_entry(encryption, label="key-C", priority=50, key_value="value-C"),
        ]
        for k in keys:
            fake_repo._entries[k.id] = k

        results = []
        for _ in range(6):
            result = await service.get_key("suno")
            results.append(result)

        # Should cycle A, B, C, A, B, C
        assert results == ["value-A", "value-B", "value-C", "value-A", "value-B", "value-C"]

    @pytest.mark.asyncio
    async def test_skips_non_active_keys(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Round-robin should only cycle through active keys."""
        fake_repo._configs["suno"] = KeyPoolConfig(
            provider="suno", selection_strategy=SelectionStrategy.ROUND_ROBIN
        )

        active_key = _make_entry(encryption, label="active", key_value="active-value")
        disabled_key = _make_entry(
            encryption, label="disabled", status=KeyStatus.DISABLED, key_value="disabled-value"
        )
        rate_limited_key = _make_entry(
            encryption, label="limited", status=KeyStatus.RATE_LIMITED, key_value="limited-value"
        )
        fake_repo._entries[active_key.id] = active_key
        fake_repo._entries[disabled_key.id] = disabled_key
        fake_repo._entries[rate_limited_key.id] = rate_limited_key

        result = await service.get_key("suno")
        assert result == "active-value"


# ---------------------------------------------------------------------------
# Tests: Priority Selection
# ---------------------------------------------------------------------------


class TestPrioritySelection:
    """Tests for priority-based key selection strategy."""

    @pytest.mark.asyncio
    async def test_selects_lowest_priority_number(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Priority strategy should select the key with the lowest priority number."""
        # Default config is priority strategy
        low_priority = _make_entry(encryption, label="low", priority=10, key_value="low-value")
        high_priority = _make_entry(encryption, label="high", priority=90, key_value="high-value")
        fake_repo._entries[low_priority.id] = low_priority
        fake_repo._entries[high_priority.id] = high_priority

        result = await service.get_key("suno")
        assert result == "low-value"

    @pytest.mark.asyncio
    async def test_round_robins_among_tied_priorities(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """When multiple keys share the same lowest priority, cycle among them."""
        key_a = _make_entry(encryption, label="tie-A", priority=10, key_value="tie-A-value")
        key_b = _make_entry(encryption, label="tie-B", priority=10, key_value="tie-B-value")
        # Lower priority number (higher priority key) should not be selected before ties
        key_c = _make_entry(encryption, label="fallback", priority=50, key_value="fallback-value")
        fake_repo._entries[key_a.id] = key_a
        fake_repo._entries[key_b.id] = key_b
        fake_repo._entries[key_c.id] = key_c

        results = []
        for _ in range(4):
            result = await service.get_key("suno")
            results.append(result)

        # Should cycle between tie-A and tie-B
        assert results == ["tie-A-value", "tie-B-value", "tie-A-value", "tie-B-value"]

    @pytest.mark.asyncio
    async def test_ignores_non_active_keys_in_priority(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Priority selection should skip keys with non-active status."""
        best_key = _make_entry(
            encryption, label="best", priority=1, status=KeyStatus.EXHAUSTED, key_value="best-value"
        )
        active_key = _make_entry(
            encryption, label="active", priority=50, key_value="active-value"
        )
        fake_repo._entries[best_key.id] = best_key
        fake_repo._entries[active_key.id] = active_key

        result = await service.get_key("suno")
        assert result == "active-value"


# ---------------------------------------------------------------------------
# Tests: NoAvailableKeysError
# ---------------------------------------------------------------------------


class TestNoAvailableKeys:
    """Tests for NoAvailableKeysError when all keys are non-active."""

    @pytest.mark.asyncio
    async def test_raises_when_no_keys_exist(
        self, service: KeyPoolService
    ) -> None:
        """Should raise NoAvailableKeysError when no keys exist for provider."""
        with pytest.raises(NoAvailableKeysError) as exc_info:
            await service.get_key("suno")

        assert exc_info.value.details["provider"] == "suno"

    @pytest.mark.asyncio
    async def test_raises_when_all_non_active(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """Should raise when all keys are rate_limited/exhausted/disabled."""
        disabled = _make_entry(encryption, label="d", status=KeyStatus.DISABLED)
        exhausted = _make_entry(encryption, label="e", status=KeyStatus.EXHAUSTED)
        rate_limited = _make_entry(encryption, label="r", status=KeyStatus.RATE_LIMITED)
        fake_repo._entries[disabled.id] = disabled
        fake_repo._entries[exhausted.id] = exhausted
        fake_repo._entries[rate_limited.id] = rate_limited

        # Set cooldown key so rate_limited key doesn't auto-recover
        cooldown_key = f"key_pool:suno:cooldown:{rate_limited.id}"
        fake_redis._store[cooldown_key] = "1"

        with pytest.raises(NoAvailableKeysError) as exc_info:
            await service.get_key("suno")

        counts = exc_info.value.details["status_counts"]
        assert counts["disabled"] == 1
        assert counts["exhausted"] == 1
        assert counts["rate_limited"] == 1
        assert counts["active"] == 0


# ---------------------------------------------------------------------------
# Tests: Key CRUD Operations
# ---------------------------------------------------------------------------


class TestKeyCrud:
    """Tests for key add/remove/update operations."""

    @pytest.mark.asyncio
    async def test_add_key_stores_and_encrypts(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Adding a key should store it encrypted with active status."""
        key_id = await service.add_key("suno", "sk-my-key", "Production Key", 10)

        entry = fake_repo._entries[key_id]
        assert entry.provider == "suno"
        assert entry.label == "Production Key"
        assert entry.priority == 10
        assert entry.status == KeyStatus.ACTIVE
        # Verify encryption round-trip
        assert encryption.decrypt(entry.encrypted_key_value) == "sk-my-key"

    @pytest.mark.asyncio
    async def test_add_key_duplicate_label_raises(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Adding a key with duplicate label for same provider should raise."""
        await service.add_key("suno", "sk-key-1", "My Label", 50)

        with pytest.raises(DuplicateKeyLabelError):
            await service.add_key("suno", "sk-key-2", "My Label", 50)

    @pytest.mark.asyncio
    async def test_add_key_same_label_different_provider_ok(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Same label is allowed across different providers."""
        await service.add_key("suno", "sk-key-1", "My Label", 50)
        key_id = await service.add_key("fal", "sk-key-2", "My Label", 50)

        assert key_id is not None

    @pytest.mark.asyncio
    async def test_remove_key_deletes_entry(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Removing a key should delete it from the repository."""
        key_id = await service.add_key("suno", "sk-key-1", "To Remove", 50)
        assert key_id in fake_repo._entries

        await service.remove_key(key_id)
        assert key_id not in fake_repo._entries

    @pytest.mark.asyncio
    async def test_update_key_changes_priority(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Updating priority should persist the change."""
        key_id = await service.add_key("suno", "sk-key-1", "Update Me", 50)

        await service.update_key(key_id, priority=1)
        assert fake_repo._entries[key_id].priority == 1

    @pytest.mark.asyncio
    async def test_update_key_changes_label(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Updating label should persist the change."""
        key_id = await service.add_key("suno", "sk-key-1", "Old Label", 50)

        await service.update_key(key_id, label="New Label")
        assert fake_repo._entries[key_id].label == "New Label"

    @pytest.mark.asyncio
    async def test_update_key_reencrypts_value(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Updating key_value should re-encrypt the new value."""
        key_id = await service.add_key("suno", "sk-old-key", "My Key", 50)

        await service.update_key(key_id, key_value="sk-new-key")
        decrypted = encryption.decrypt(fake_repo._entries[key_id].encrypted_key_value)
        assert decrypted == "sk-new-key"

    @pytest.mark.asyncio
    async def test_set_key_status(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """set_key_status should change the key's status."""
        key_id = await service.add_key("suno", "sk-key-1", "Status Key", 50)

        await service.set_key_status(key_id, "disabled")
        assert fake_repo._entries[key_id].status == KeyStatus.DISABLED

        await service.set_key_status(key_id, "active")
        assert fake_repo._entries[key_id].status == KeyStatus.ACTIVE


# ---------------------------------------------------------------------------
# Tests: Provider Configuration
# ---------------------------------------------------------------------------


class TestProviderConfig:
    """Tests for provider configuration management."""

    @pytest.mark.asyncio
    async def test_configure_creates_new_config(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository
    ) -> None:
        """configure_provider should create config if none exists."""
        await service.configure_provider("suno", strategy="round_robin", cooldown_seconds=120)

        config = fake_repo._configs["suno"]
        assert config.selection_strategy == SelectionStrategy.ROUND_ROBIN
        assert config.cooldown_seconds == 120

    @pytest.mark.asyncio
    async def test_configure_updates_existing_config(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository
    ) -> None:
        """configure_provider should update existing config."""
        fake_repo._configs["suno"] = KeyPoolConfig(
            provider="suno",
            selection_strategy=SelectionStrategy.PRIORITY,
            cooldown_seconds=60,
        )

        await service.configure_provider("suno", strategy="round_robin")
        assert fake_repo._configs["suno"].selection_strategy == SelectionStrategy.ROUND_ROBIN
        # Cooldown unchanged
        assert fake_repo._configs["suno"].cooldown_seconds == 60

    @pytest.mark.asyncio
    async def test_strategy_change_resets_rr_position(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis
    ) -> None:
        """Changing strategy should reset the round-robin position counter."""
        fake_redis._store["key_pool:suno:rr_position"] = "5"

        await service.configure_provider("suno", strategy="round_robin")
        assert "key_pool:suno:rr_position" not in fake_redis._store


# ---------------------------------------------------------------------------
# Tests: Pool Health Status
# ---------------------------------------------------------------------------


class TestPoolStatus:
    """Tests for pool health status calculation."""

    @pytest.mark.asyncio
    async def test_healthy_when_all_active(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Health should be 'healthy' when all keys are active."""
        for i in range(4):
            entry = _make_entry(encryption, label=f"key-{i}")
            fake_repo._entries[entry.id] = entry

        status = await service.get_pool_status("suno")
        assert status["health_indicator"] == "healthy"
        assert status["total_keys"] == 4
        assert status["active_keys"] == 4

    @pytest.mark.asyncio
    async def test_degraded_when_minority_active(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Health should be 'degraded' when less than half are active."""
        active = _make_entry(encryption, label="active")
        disabled1 = _make_entry(encryption, label="d1", status=KeyStatus.DISABLED)
        disabled2 = _make_entry(encryption, label="d2", status=KeyStatus.DISABLED)
        fake_repo._entries[active.id] = active
        fake_repo._entries[disabled1.id] = disabled1
        fake_repo._entries[disabled2.id] = disabled2

        status = await service.get_pool_status("suno")
        assert status["health_indicator"] == "degraded"

    @pytest.mark.asyncio
    async def test_critical_when_no_active(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Health should be 'critical' when no keys are active."""
        disabled = _make_entry(encryption, label="d", status=KeyStatus.DISABLED)
        fake_repo._entries[disabled.id] = disabled

        status = await service.get_pool_status("suno")
        assert status["health_indicator"] == "critical"

    @pytest.mark.asyncio
    async def test_healthy_when_exactly_half_active(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Health should be 'healthy' when exactly half of keys are active (active >= T/2)."""
        active1 = _make_entry(encryption, label="a1")
        active2 = _make_entry(encryption, label="a2")
        disabled1 = _make_entry(encryption, label="d1", status=KeyStatus.DISABLED)
        disabled2 = _make_entry(encryption, label="d2", status=KeyStatus.DISABLED)
        fake_repo._entries[active1.id] = active1
        fake_repo._entries[active2.id] = active2
        fake_repo._entries[disabled1.id] = disabled1
        fake_repo._entries[disabled2.id] = disabled2

        status = await service.get_pool_status("suno")
        assert status["health_indicator"] == "healthy"
        assert status["total_keys"] == 4
        assert status["active_keys"] == 2

    @pytest.mark.asyncio
    async def test_critical_when_no_keys(
        self, service: KeyPoolService
    ) -> None:
        """Health should be 'critical' when no keys exist at all."""
        status = await service.get_pool_status("suno")
        assert status["health_indicator"] == "critical"
        assert status["total_keys"] == 0

    @pytest.mark.asyncio
    async def test_status_counts_are_correct(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Pool status should return correct counts per key status."""
        active = _make_entry(encryption, label="a1")
        rate_limited = _make_entry(encryption, label="rl1", status=KeyStatus.RATE_LIMITED)
        exhausted = _make_entry(encryption, label="ex1", status=KeyStatus.EXHAUSTED)
        disabled = _make_entry(encryption, label="d1", status=KeyStatus.DISABLED)
        fake_repo._entries[active.id] = active
        fake_repo._entries[rate_limited.id] = rate_limited
        fake_repo._entries[exhausted.id] = exhausted
        fake_repo._entries[disabled.id] = disabled

        status = await service.get_pool_status("suno")
        assert status["provider"] == "suno"
        assert status["total_keys"] == 4
        assert status["active_keys"] == 1
        assert status["rate_limited_keys"] == 1
        assert status["exhausted_keys"] == 1
        assert status["disabled_keys"] == 1
        assert status["health_indicator"] == "degraded"


# ---------------------------------------------------------------------------
# Tests: Failover Handler
# ---------------------------------------------------------------------------

import httpx


def _make_http_status_error(status_code: int, body: str = "", headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    """Helper to create an httpx.HTTPStatusError for testing."""
    request = httpx.Request("POST", "https://api.example.com/v1/generate")
    response = httpx.Response(
        status_code,
        request=request,
        text=body,
        headers=headers or {},
    )
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=response,
    )


class TestExecuteWithFailover:
    """Tests for execute_with_failover method."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Should return response on successful first attempt."""
        entry = _make_entry(encryption, label="key-1", key_value="sk-test")
        fake_repo._entries[entry.id] = entry

        async def execute_fn(key: str) -> dict[str, str]:
            return {"result": "ok", "key_used": key}

        result = await service.execute_with_failover("suno", execute_fn)
        assert result == {"result": "ok", "key_used": "sk-test"}

    @pytest.mark.asyncio
    async def test_429_triggers_failover_to_next_key(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """HTTP 429 should mark key rate_limited and retry with next key."""
        key_a = _make_entry(encryption, label="key-A", priority=10, key_value="value-A")
        key_b = _make_entry(encryption, label="key-B", priority=20, key_value="value-B")
        fake_repo._entries[key_a.id] = key_a
        fake_repo._entries[key_b.id] = key_b

        call_count = 0

        async def execute_fn(key: str) -> dict[str, str]:
            nonlocal call_count
            call_count += 1
            if key == "value-A":
                raise _make_http_status_error(429, "rate limited")
            return {"result": "ok", "key_used": key}

        result = await service.execute_with_failover("suno", execute_fn)
        assert result == {"result": "ok", "key_used": "value-B"}
        assert call_count == 2
        # key_a should now be rate_limited
        assert fake_repo._entries[key_a.id].status == KeyStatus.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_402_triggers_exhausted_and_failover(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """HTTP 402 should mark key exhausted and retry with next key."""
        key_a = _make_entry(encryption, label="key-A", priority=10, key_value="value-A")
        key_b = _make_entry(encryption, label="key-B", priority=20, key_value="value-B")
        fake_repo._entries[key_a.id] = key_a
        fake_repo._entries[key_b.id] = key_b

        async def execute_fn(key: str) -> dict[str, str]:
            if key == "value-A":
                raise _make_http_status_error(402, "payment required")
            return {"result": "ok", "key_used": key}

        result = await service.execute_with_failover("suno", execute_fn)
        assert result == {"result": "ok", "key_used": "value-B"}
        assert fake_repo._entries[key_a.id].status == KeyStatus.EXHAUSTED

    @pytest.mark.asyncio
    async def test_403_billing_triggers_exhausted_and_failover(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """HTTP 403 should mark key exhausted and retry with next key."""
        key_a = _make_entry(encryption, label="key-A", priority=10, key_value="value-A")
        key_b = _make_entry(encryption, label="key-B", priority=20, key_value="value-B")
        fake_repo._entries[key_a.id] = key_a
        fake_repo._entries[key_b.id] = key_b

        async def execute_fn(key: str) -> dict[str, str]:
            if key == "value-A":
                raise _make_http_status_error(403, "billing exhausted")
            return {"result": "ok", "key_used": key}

        result = await service.execute_with_failover("suno", execute_fn)
        assert result == {"result": "ok", "key_used": "value-B"}
        assert fake_repo._entries[key_a.id].status == KeyStatus.EXHAUSTED

    @pytest.mark.asyncio
    async def test_max_3_retries_then_raises(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Should attempt max 3 times then re-raise the last error."""
        keys = [
            _make_entry(encryption, label=f"key-{i}", priority=i + 1, key_value=f"value-{i}")
            for i in range(5)
        ]
        for k in keys:
            fake_repo._entries[k.id] = k

        call_count = 0

        async def execute_fn(key: str) -> dict[str, str]:
            nonlocal call_count
            call_count += 1
            raise _make_http_status_error(429, "rate limited")

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await service.execute_with_failover("suno", execute_fn)

        assert call_count == 3  # Max 3 attempts
        assert exc_info.value.response.status_code == 429

    @pytest.mark.asyncio
    async def test_no_active_keys_raises_immediately(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Should raise NoAvailableKeysError when no active keys exist."""
        disabled = _make_entry(encryption, label="disabled", status=KeyStatus.DISABLED)
        fake_repo._entries[disabled.id] = disabled

        async def execute_fn(key: str) -> dict[str, str]:
            return {"result": "ok"}

        with pytest.raises(NoAvailableKeysError):
            await service.execute_with_failover("suno", execute_fn)

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_immediately(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Non-429/402/403 errors should raise immediately without retry."""
        key_a = _make_entry(encryption, label="key-A", priority=10, key_value="value-A")
        key_b = _make_entry(encryption, label="key-B", priority=20, key_value="value-B")
        fake_repo._entries[key_a.id] = key_a
        fake_repo._entries[key_b.id] = key_b

        call_count = 0

        async def execute_fn(key: str) -> dict[str, str]:
            nonlocal call_count
            call_count += 1
            raise _make_http_status_error(500, "internal server error")

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await service.execute_with_failover("suno", execute_fn)

        assert call_count == 1  # Only one attempt — no retry for 500
        assert exc_info.value.response.status_code == 500

    @pytest.mark.asyncio
    async def test_429_sets_cooldown_in_redis(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption, fake_redis: FakeRedis
    ) -> None:
        """Rate-limited key should get a cooldown TTL set in Redis."""
        key_a = _make_entry(encryption, label="key-A", priority=10, key_value="value-A")
        key_b = _make_entry(encryption, label="key-B", priority=20, key_value="value-B")
        fake_repo._entries[key_a.id] = key_a
        fake_repo._entries[key_b.id] = key_b

        async def execute_fn(key: str) -> dict[str, str]:
            if key == "value-A":
                raise _make_http_status_error(429, "rate limited")
            return {"result": "ok"}

        await service.execute_with_failover("suno", execute_fn)

        cooldown_key = f"key_pool:suno:cooldown:{key_a.id}"
        assert cooldown_key in fake_redis._store

    @pytest.mark.asyncio
    async def test_429_uses_retry_after_header(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption, fake_redis: FakeRedis
    ) -> None:
        """Retry-After header should be used for cooldown if present."""
        key_a = _make_entry(encryption, label="key-A", priority=10, key_value="value-A")
        key_b = _make_entry(encryption, label="key-B", priority=20, key_value="value-B")
        fake_repo._entries[key_a.id] = key_a
        fake_repo._entries[key_b.id] = key_b

        async def execute_fn(key: str) -> dict[str, str]:
            if key == "value-A":
                raise _make_http_status_error(
                    429, "rate limited", headers={"Retry-After": "120"}
                )
            return {"result": "ok"}

        await service.execute_with_failover("suno", execute_fn)
        # The cooldown key should be set (we can't verify the TTL in FakeRedis
        # but the test confirms the code path runs without error)
        cooldown_key = f"key_pool:suno:cooldown:{key_a.id}"
        assert cooldown_key in fake_redis._store

    @pytest.mark.asyncio
    async def test_records_status_event_on_429(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """A status event should be recorded when a key transitions to rate_limited."""
        key_a = _make_entry(encryption, label="key-A", priority=10, key_value="value-A")
        key_b = _make_entry(encryption, label="key-B", priority=20, key_value="value-B")
        fake_repo._entries[key_a.id] = key_a
        fake_repo._entries[key_b.id] = key_b

        async def execute_fn(key: str) -> dict[str, str]:
            if key == "value-A":
                raise _make_http_status_error(429, "rate limited")
            return {"result": "ok"}

        await service.execute_with_failover("suno", execute_fn)

        # Check that a status event was recorded
        assert hasattr(fake_repo, "_events")
        assert len(fake_repo._events) == 1
        event = fake_repo._events[0]
        assert event.key_id == key_a.id
        assert event.previous_status == KeyStatus.ACTIVE
        assert event.new_status == KeyStatus.RATE_LIMITED
        assert event.trigger_reason == "rate_limit_429"
        assert event.http_status_code == 429

    @pytest.mark.asyncio
    async def test_records_status_event_on_402(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """A status event should be recorded when a key transitions to exhausted."""
        key_a = _make_entry(encryption, label="key-A", priority=10, key_value="value-A")
        key_b = _make_entry(encryption, label="key-B", priority=20, key_value="value-B")
        fake_repo._entries[key_a.id] = key_a
        fake_repo._entries[key_b.id] = key_b

        async def execute_fn(key: str) -> dict[str, str]:
            if key == "value-A":
                raise _make_http_status_error(402, "payment required")
            return {"result": "ok"}

        await service.execute_with_failover("suno", execute_fn)

        assert hasattr(fake_repo, "_events")
        assert len(fake_repo._events) == 1
        event = fake_repo._events[0]
        assert event.key_id == key_a.id
        assert event.previous_status == KeyStatus.ACTIVE
        assert event.new_status == KeyStatus.EXHAUSTED
        assert event.trigger_reason == "exhausted_402"
        assert event.http_status_code == 402


# ---------------------------------------------------------------------------
# Tests: report_key_success and report_key_failure
# ---------------------------------------------------------------------------


class TestReportKeyMethods:
    """Tests for report_key_success and report_key_failure."""

    @pytest.mark.asyncio
    async def test_report_key_success_does_not_raise(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """report_key_success should not raise and should complete cleanly."""
        key = _make_entry(encryption, label="key-1", key_value="sk-test")
        fake_repo._entries[key.id] = key

        # Should not raise
        await service.report_key_success("suno", key.id)

    @pytest.mark.asyncio
    async def test_report_key_failure_does_not_raise(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """report_key_failure should not raise and should complete cleanly."""
        key = _make_entry(encryption, label="key-1", key_value="sk-test")
        fake_repo._entries[key.id] = key

        # Should not raise for various status codes
        await service.report_key_failure("suno", key.id, 500, "server error")
        await service.report_key_failure("suno", key.id, 429, "rate limited")
        await service.report_key_failure("suno", key.id, 402, "payment required")


# ---------------------------------------------------------------------------
# Tests: Cooldown Management (Requirements 4.1, 4.2, 4.3, 4.4, 4.5)
# ---------------------------------------------------------------------------


class TestCooldownRecovery:
    """Tests for cooldown-based key recovery logic."""

    @pytest.mark.asyncio
    async def test_rate_limited_key_recovers_when_cooldown_expires(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """A rate_limited key should transition back to active when its cooldown key expires from Redis."""
        key = _make_entry(encryption, label="cooldown-key", status=KeyStatus.RATE_LIMITED)
        key.rate_limited_at = datetime.utcnow()
        fake_repo._entries[key.id] = key

        # No cooldown key in Redis = cooldown has expired
        # (FakeRedis.exists returns 0 for missing keys)

        # get_key should recover this key and then select it
        result = await service.get_key("suno")
        assert result == "sk-test-key-value"

        # Verify key is now active in the repo
        assert fake_repo._entries[key.id].status == KeyStatus.ACTIVE
        assert fake_repo._entries[key.id].rate_limited_at is None

    @pytest.mark.asyncio
    async def test_rate_limited_key_skipped_when_cooldown_active(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """A rate_limited key should NOT recover while its cooldown TTL key still exists in Redis."""
        rate_limited_key = _make_entry(encryption, label="cooling", status=KeyStatus.RATE_LIMITED, key_value="cooling-value")
        rate_limited_key.rate_limited_at = datetime.utcnow()
        fake_repo._entries[rate_limited_key.id] = rate_limited_key

        active_key = _make_entry(encryption, label="active-key", status=KeyStatus.ACTIVE, key_value="active-value")
        fake_repo._entries[active_key.id] = active_key

        # Set cooldown key in Redis — simulates cooldown still active
        cooldown_redis_key = f"key_pool:suno:cooldown:{rate_limited_key.id}"
        fake_redis._store[cooldown_redis_key] = "1"

        result = await service.get_key("suno")
        assert result == "active-value"

        # Rate-limited key should still be rate_limited
        assert fake_repo._entries[rate_limited_key.id].status == KeyStatus.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_exhausted_key_never_auto_recovers(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """Exhausted keys should never auto-recover regardless of time elapsed."""
        exhausted_key = _make_entry(encryption, label="exhausted", status=KeyStatus.EXHAUSTED, key_value="exhausted-value")
        fake_repo._entries[exhausted_key.id] = exhausted_key

        active_key = _make_entry(encryption, label="active", status=KeyStatus.ACTIVE, key_value="active-value")
        fake_repo._entries[active_key.id] = active_key

        # Even without a cooldown key in Redis, exhausted keys should stay exhausted
        # (recovery only applies to rate_limited keys)

        result = await service.get_key("suno")
        assert result == "active-value"

        # Exhausted key remains exhausted
        assert fake_repo._entries[exhausted_key.id].status == KeyStatus.EXHAUSTED

    @pytest.mark.asyncio
    async def test_multiple_rate_limited_keys_recover_simultaneously(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """Multiple rate_limited keys should all recover if their cooldowns have expired."""
        key1 = _make_entry(encryption, label="rl-1", priority=10, status=KeyStatus.RATE_LIMITED, key_value="value-1")
        key1.rate_limited_at = datetime.utcnow()
        key2 = _make_entry(encryption, label="rl-2", priority=20, status=KeyStatus.RATE_LIMITED, key_value="value-2")
        key2.rate_limited_at = datetime.utcnow()
        fake_repo._entries[key1.id] = key1
        fake_repo._entries[key2.id] = key2

        # No cooldown keys in Redis = both have expired

        result = await service.get_key("suno")
        # Priority strategy: should select key1 (priority=10)
        assert result == "value-1"

        # Both keys should now be active
        assert fake_repo._entries[key1.id].status == KeyStatus.ACTIVE
        assert fake_repo._entries[key2.id].status == KeyStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_recovery_records_status_event(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """Recovery from rate_limited should record a cooldown_recovery status event."""
        key = _make_entry(encryption, label="event-key", status=KeyStatus.RATE_LIMITED)
        key.rate_limited_at = datetime.utcnow()
        fake_repo._entries[key.id] = key

        # Ensure events list is initialized
        fake_repo._events = []

        await service.get_key("suno")

        # Check that a recovery event was recorded
        assert len(fake_repo._events) == 1
        event = fake_repo._events[0]
        assert event.trigger_reason == "cooldown_recovery"
        assert event.previous_status == KeyStatus.RATE_LIMITED
        assert event.new_status == KeyStatus.ACTIVE
        assert event.key_id == key.id

    @pytest.mark.asyncio
    async def test_config_change_does_not_affect_existing_cooldowns(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """Changing cooldown_seconds config should NOT alter remaining cooldowns.

        The Redis TTL key was set at the original duration when the key became
        rate-limited. Changing the config only affects future rate-limit events.
        """
        key = _make_entry(encryption, label="existing-cooldown", status=KeyStatus.RATE_LIMITED)
        key.rate_limited_at = datetime.utcnow()
        fake_repo._entries[key.id] = key

        # Cooldown key still exists in Redis (was set with original duration)
        cooldown_redis_key = f"key_pool:suno:cooldown:{key.id}"
        fake_redis._store[cooldown_redis_key] = "1"

        # Add another active key so selection works
        active_key = _make_entry(encryption, label="other", status=KeyStatus.ACTIVE, key_value="other-value")
        fake_repo._entries[active_key.id] = active_key

        # Change provider config to a different cooldown duration
        await service.configure_provider("suno", cooldown_seconds=3600)

        # The existing key should still be rate_limited (TTL key still present)
        result = await service.get_key("suno")
        assert result == "other-value"
        assert fake_repo._entries[key.id].status == KeyStatus.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_no_active_keys_all_rate_limited_with_active_cooldowns(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """When all keys are rate_limited with active cooldowns, NoAvailableKeysError is raised."""
        key = _make_entry(encryption, label="only-key", status=KeyStatus.RATE_LIMITED)
        key.rate_limited_at = datetime.utcnow()
        fake_repo._entries[key.id] = key

        # Cooldown still active
        cooldown_redis_key = f"key_pool:suno:cooldown:{key.id}"
        fake_redis._store[cooldown_redis_key] = "1"

        with pytest.raises(NoAvailableKeysError):
            await service.get_key("suno")


# ---------------------------------------------------------------------------
# Tests: Usage Counter Logic (Requirements 5.1, 5.2, 5.3, 5.4, 5.5)
# ---------------------------------------------------------------------------


class TestUsageCounters:
    """Tests for usage counter logic including Redis fast-path and daily reset."""

    @pytest.mark.asyncio
    async def test_report_success_increments_counters_in_repo(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """report_key_success should increment total_requests, daily_requests, success_count."""
        key = _make_entry(encryption, label="counter-key", key_value="sk-test")
        fake_repo._entries[key.id] = key

        await service.report_key_success("suno", key.id)

        entry = fake_repo._entries[key.id]
        assert entry.total_requests == 1
        assert entry.daily_requests == 1
        assert entry.success_count == 1
        assert entry.failure_count == 0
        assert entry.rate_limit_hits == 0
        assert entry.last_used_at is not None

    @pytest.mark.asyncio
    async def test_report_failure_increments_failure_count(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """report_key_failure should increment total_requests, daily_requests, failure_count."""
        key = _make_entry(encryption, label="fail-key", key_value="sk-test")
        fake_repo._entries[key.id] = key

        await service.report_key_failure("suno", key.id, 500, "server error")

        entry = fake_repo._entries[key.id]
        assert entry.total_requests == 1
        assert entry.daily_requests == 1
        assert entry.success_count == 0
        assert entry.failure_count == 1
        assert entry.rate_limit_hits == 0

    @pytest.mark.asyncio
    async def test_report_429_failure_increments_rate_limit_hits(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """report_key_failure with 429 should increment rate_limit_hits."""
        key = _make_entry(encryption, label="rate-key", key_value="sk-test")
        fake_repo._entries[key.id] = key

        await service.report_key_failure("suno", key.id, 429, "rate limited")

        entry = fake_repo._entries[key.id]
        assert entry.total_requests == 1
        assert entry.daily_requests == 1
        assert entry.failure_count == 1
        assert entry.rate_limit_hits == 1

    @pytest.mark.asyncio
    async def test_multiple_requests_accumulate_counters(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """Multiple success/failure reports should accumulate correctly."""
        key = _make_entry(encryption, label="accum-key", key_value="sk-test")
        fake_repo._entries[key.id] = key

        # 3 successes, 2 failures, 1 rate limit
        await service.report_key_success("suno", key.id)
        await service.report_key_success("suno", key.id)
        await service.report_key_success("suno", key.id)
        await service.report_key_failure("suno", key.id, 500, "err")
        await service.report_key_failure("suno", key.id, 400, "bad request")
        await service.report_key_failure("suno", key.id, 429, "rate limited")

        entry = fake_repo._entries[key.id]
        assert entry.total_requests == 6
        assert entry.daily_requests == 6
        assert entry.success_count == 3
        assert entry.failure_count == 3
        assert entry.rate_limit_hits == 1

    @pytest.mark.asyncio
    async def test_report_success_increments_redis_counters(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """report_key_success should increment Redis daily counters (fast path)."""
        key = _make_entry(encryption, label="redis-key", key_value="sk-test")
        fake_repo._entries[key.id] = key

        await service.report_key_success("suno", key.id)

        prefix = f"key_pool:suno:{key.id}"
        assert fake_redis._store.get(f"{prefix}:daily_requests") == "1"
        assert fake_redis._store.get(f"{prefix}:daily_success") == "1"
        assert f"{prefix}:daily_failures" not in fake_redis._store

    @pytest.mark.asyncio
    async def test_report_failure_increments_redis_failure_counter(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """report_key_failure should increment Redis daily failure counter."""
        key = _make_entry(encryption, label="redis-fail", key_value="sk-test")
        fake_repo._entries[key.id] = key

        await service.report_key_failure("suno", key.id, 500, "error")

        prefix = f"key_pool:suno:{key.id}"
        assert fake_redis._store.get(f"{prefix}:daily_requests") == "1"
        assert fake_redis._store.get(f"{prefix}:daily_failures") == "1"
        assert f"{prefix}:daily_success" not in fake_redis._store

    @pytest.mark.asyncio
    async def test_report_429_failure_increments_redis_rate_limit_counter(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """report_key_failure with 429 should increment Redis rate limit counter."""
        key = _make_entry(encryption, label="redis-rl", key_value="sk-test")
        fake_repo._entries[key.id] = key

        await service.report_key_failure("suno", key.id, 429, "rate limited")

        prefix = f"key_pool:suno:{key.id}"
        assert fake_redis._store.get(f"{prefix}:daily_requests") == "1"
        assert fake_redis._store.get(f"{prefix}:daily_failures") == "1"
        assert fake_redis._store.get(f"{prefix}:daily_rate_limits") == "1"

    @pytest.mark.asyncio
    async def test_reset_daily_counters_zeroes_daily_preserves_total(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """reset_daily_counters should zero daily_requests but keep totals."""
        key = _make_entry(encryption, label="reset-key", key_value="sk-test")
        fake_repo._entries[key.id] = key

        # Accumulate some usage
        await service.report_key_success("suno", key.id)
        await service.report_key_success("suno", key.id)
        await service.report_key_failure("suno", key.id, 500, "err")

        entry = fake_repo._entries[key.id]
        assert entry.total_requests == 3
        assert entry.daily_requests == 3
        assert entry.success_count == 2
        assert entry.failure_count == 1

        # Reset daily counters
        await service.reset_daily_counters()

        entry = fake_repo._entries[key.id]
        assert entry.daily_requests == 0
        # Totals preserved
        assert entry.total_requests == 3
        assert entry.success_count == 2
        assert entry.failure_count == 1

    @pytest.mark.asyncio
    async def test_reset_daily_counters_clears_redis_daily_keys(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """reset_daily_counters should delete Redis daily counter keys."""
        key = _make_entry(encryption, label="redis-reset", key_value="sk-test")
        fake_repo._entries[key.id] = key

        # Build up Redis counters
        await service.report_key_success("suno", key.id)
        await service.report_key_success("suno", key.id)

        prefix = f"key_pool:suno:{key.id}"
        assert fake_redis._store.get(f"{prefix}:daily_requests") == "2"
        assert fake_redis._store.get(f"{prefix}:daily_success") == "2"

        # Reset
        await service.reset_daily_counters()

        # Redis daily keys should be gone
        assert f"{prefix}:daily_requests" not in fake_redis._store
        assert f"{prefix}:daily_success" not in fake_redis._store

    @pytest.mark.asyncio
    async def test_reset_daily_counters_preserves_non_daily_redis_keys(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """reset_daily_counters should NOT delete non-daily Redis keys."""
        # Set up some non-daily Redis keys
        fake_redis._store["key_pool:suno:rr_position"] = "5"
        fake_redis._store["key_pool:suno:version"] = "3"
        fake_redis._store["key_pool:suno:cooldown:some-id"] = "1"

        await service.reset_daily_counters()

        # Non-daily keys should remain
        assert fake_redis._store.get("key_pool:suno:rr_position") == "5"
        assert fake_redis._store.get("key_pool:suno:version") == "3"
        assert fake_redis._store.get("key_pool:suno:cooldown:some-id") == "1"

    @pytest.mark.asyncio
    async def test_reset_daily_counters_multiple_keys_multiple_providers(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """reset_daily_counters should reset all keys across all providers."""
        key_suno = _make_entry(encryption, provider="suno", label="suno-key", key_value="sk-suno")
        key_fal = _make_entry(encryption, provider="fal", label="fal-key", key_value="sk-fal")
        fake_repo._entries[key_suno.id] = key_suno
        fake_repo._entries[key_fal.id] = key_fal

        await service.report_key_success("suno", key_suno.id)
        await service.report_key_success("fal", key_fal.id)
        await service.report_key_success("fal", key_fal.id)

        # Verify pre-reset state
        assert fake_repo._entries[key_suno.id].daily_requests == 1
        assert fake_repo._entries[key_fal.id].daily_requests == 2

        await service.reset_daily_counters()

        # All daily counters zeroed
        assert fake_repo._entries[key_suno.id].daily_requests == 0
        assert fake_repo._entries[key_fal.id].daily_requests == 0

        # Totals preserved
        assert fake_repo._entries[key_suno.id].total_requests == 1
        assert fake_repo._entries[key_fal.id].total_requests == 2

    @pytest.mark.asyncio
    async def test_redis_failure_does_not_break_report_success(
        self, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """If Redis fails, report_key_success should still complete (non-fatal)."""

        class BrokenRedis(FakeRedis):
            async def incr(self, key: str) -> int:
                raise ConnectionError("Redis is down")

            async def scan(self, **kwargs: Any) -> tuple[int, list[str]]:
                raise ConnectionError("Redis is down")

        broken_redis = BrokenRedis()
        service = KeyPoolService(
            repository=fake_repo,  # type: ignore[arg-type]
            encryption=encryption,
            redis=broken_redis,  # type: ignore[arg-type]
        )

        key = _make_entry(encryption, label="resilient-key", key_value="sk-test")
        fake_repo._entries[key.id] = key

        # Should not raise even when Redis is broken
        await service.report_key_success("suno", key.id)

        # PostgreSQL counters should still be updated
        entry = fake_repo._entries[key.id]
        assert entry.total_requests == 1
        assert entry.success_count == 1

    @pytest.mark.asyncio
    async def test_last_used_at_updated_on_each_request(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """last_used_at should be updated on each key use."""
        key = _make_entry(encryption, label="timestamp-key", key_value="sk-test")
        fake_repo._entries[key.id] = key
        assert key.last_used_at is None

        await service.report_key_success("suno", key.id)
        first_used = fake_repo._entries[key.id].last_used_at
        assert first_used is not None

        await service.report_key_failure("suno", key.id, 400, "bad")
        second_used = fake_repo._entries[key.id].last_used_at
        assert second_used is not None
        assert second_used >= first_used


# ---------------------------------------------------------------------------
# Tests: Redis Cache Layer (Task 8.1)
# ---------------------------------------------------------------------------


class TestRedisCache:
    """Tests for Redis caching layer — populate, invalidate, and fallback."""

    @pytest.mark.asyncio
    async def test_populate_cache_stores_active_keys_in_zset(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """populate_cache should store active key IDs in a sorted set scored by priority."""
        key_a = _make_entry(encryption, label="a", priority=10)
        key_b = _make_entry(encryption, label="b", priority=30)
        key_disabled = _make_entry(encryption, label="d", status=KeyStatus.DISABLED)
        fake_repo._entries[key_a.id] = key_a
        fake_repo._entries[key_b.id] = key_b
        fake_repo._entries[key_disabled.id] = key_disabled

        await service.populate_cache("suno")

        zset_key = "key_pool:suno:active"
        assert zset_key in fake_redis._zsets
        zset = fake_redis._zsets[zset_key]
        assert str(key_a.id) in zset
        assert str(key_b.id) in zset
        assert str(key_disabled.id) not in zset
        # Scores should match priorities
        assert zset[str(key_a.id)] == 10.0
        assert zset[str(key_b.id)] == 30.0

    @pytest.mark.asyncio
    async def test_populate_cache_stores_rate_limited_set(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """populate_cache should store rate-limited key IDs in a SET."""
        key_active = _make_entry(encryption, label="active", priority=10)
        key_rl = _make_entry(encryption, label="rl", status=KeyStatus.RATE_LIMITED)
        fake_repo._entries[key_active.id] = key_active
        fake_repo._entries[key_rl.id] = key_rl

        # Set cooldown so rate_limited key doesn't auto-recover during populate
        fake_redis._store[f"key_pool:suno:cooldown:{key_rl.id}"] = "1"

        await service.populate_cache("suno")

        set_key = "key_pool:suno:rate_limited"
        assert set_key in fake_redis._sets
        assert str(key_rl.id) in fake_redis._sets[set_key]
        assert str(key_active.id) not in fake_redis._sets[set_key]

    @pytest.mark.asyncio
    async def test_populate_cache_handles_empty_pool(
        self, service: KeyPoolService, fake_redis: FakeRedis
    ) -> None:
        """populate_cache should handle a provider with no keys gracefully."""
        await service.populate_cache("empty_provider")

        # Should not create any ZSET or SET entries
        assert "key_pool:empty_provider:active" not in fake_redis._zsets
        assert "key_pool:empty_provider:rate_limited" not in fake_redis._sets

    @pytest.mark.asyncio
    async def test_load_all_caches_populates_all_providers(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """load_all_caches should populate caches for all providers with entries."""
        key_suno = _make_entry(encryption, provider="suno", label="suno-key", priority=10)
        key_fal = _make_entry(encryption, provider="fal", label="fal-key", priority=20)
        fake_repo._entries[key_suno.id] = key_suno
        fake_repo._entries[key_fal.id] = key_fal

        await service.load_all_caches()

        assert "key_pool:suno:active" in fake_redis._zsets
        assert "key_pool:fal:active" in fake_redis._zsets
        assert str(key_suno.id) in fake_redis._zsets["key_pool:suno:active"]
        assert str(key_fal.id) in fake_redis._zsets["key_pool:fal:active"]

    @pytest.mark.asyncio
    async def test_invalidate_cache_increments_version_and_clears_zset(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """_invalidate_cache should increment version and delete the active ZSET."""
        key = _make_entry(encryption, label="key-1", priority=10)
        fake_repo._entries[key.id] = key

        # First populate
        await service.populate_cache("suno")
        assert "key_pool:suno:active" in fake_redis._zsets

        # Invalidate
        await service._invalidate_cache("suno")

        # ZSET should be deleted
        assert "key_pool:suno:active" not in fake_redis._zsets
        # Version should be incremented
        assert fake_redis._store.get("key_pool:suno:version") == "1"

    @pytest.mark.asyncio
    async def test_invalidate_cache_clears_rate_limited_set(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """_invalidate_cache should also clear the rate_limited SET."""
        key_rl = _make_entry(encryption, label="rl", status=KeyStatus.RATE_LIMITED)
        fake_repo._entries[key_rl.id] = key_rl
        fake_redis._store[f"key_pool:suno:cooldown:{key_rl.id}"] = "1"

        await service.populate_cache("suno")
        assert "key_pool:suno:rate_limited" in fake_redis._sets

        await service._invalidate_cache("suno")
        assert "key_pool:suno:rate_limited" not in fake_redis._sets

    @pytest.mark.asyncio
    async def test_add_key_invalidates_cache(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """Adding a key should invalidate the provider's cache."""
        key = _make_entry(encryption, label="existing", priority=10)
        fake_repo._entries[key.id] = key
        await service.populate_cache("suno")

        # Add a new key
        await service.add_key("suno", "sk-new-key", "new-key", 20)

        # Cache should have been invalidated (ZSET cleared)
        assert "key_pool:suno:active" not in fake_redis._zsets
        # Version incremented
        assert int(fake_redis._store.get("key_pool:suno:version", "0")) >= 1

    @pytest.mark.asyncio
    async def test_remove_key_invalidates_cache(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """Removing a key should invalidate the provider's cache."""
        key = _make_entry(encryption, label="to-remove", priority=10)
        fake_repo._entries[key.id] = key
        await service.populate_cache("suno")

        await service.remove_key(key.id)

        # Cache invalidated
        assert "key_pool:suno:active" not in fake_redis._zsets

    @pytest.mark.asyncio
    async def test_set_key_status_invalidates_cache(
        self, service: KeyPoolService, fake_repo: FakeKeyPoolRepository, fake_redis: FakeRedis, encryption: KeyEncryption
    ) -> None:
        """Changing key status should invalidate the provider's cache."""
        key = _make_entry(encryption, label="status-change", priority=10)
        fake_repo._entries[key.id] = key
        await service.populate_cache("suno")

        await service.set_key_status(key.id, "disabled")

        # Cache invalidated
        assert "key_pool:suno:active" not in fake_redis._zsets

    @pytest.mark.asyncio
    async def test_get_active_keys_falls_back_to_postgres_when_redis_unavailable(
        self, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """When Redis is unavailable, _get_active_keys should fall back to PostgreSQL."""

        class BrokenCacheRedis(FakeRedis):
            """Redis that fails on cache reads but basic ops work."""

            async def zrange(self, key: str, start: int, end: int) -> list[str]:
                raise ConnectionError("Redis is down")

            async def zadd(self, key: str, mapping: dict[str, float]) -> int:
                raise ConnectionError("Redis is down")

            async def sadd(self, key: str, *members: str) -> int:
                raise ConnectionError("Redis is down")

        broken_redis = BrokenCacheRedis()
        service = KeyPoolService(
            repository=fake_repo,  # type: ignore[arg-type]
            encryption=encryption,
            redis=broken_redis,  # type: ignore[arg-type]
        )

        key = _make_entry(encryption, label="fallback-key", priority=10, key_value="sk-fallback")
        fake_repo._entries[key.id] = key

        # Should still be able to get keys via PostgreSQL fallback
        result = await service.get_key("suno")
        assert result == "sk-fallback"

    @pytest.mark.asyncio
    async def test_populate_cache_survives_redis_failure(
        self, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """populate_cache should not raise when Redis is unavailable."""

        class FullyBrokenRedis(FakeRedis):
            async def delete(self, *keys: str) -> int:
                raise ConnectionError("Redis is down")

            async def zadd(self, key: str, mapping: dict[str, float]) -> int:
                raise ConnectionError("Redis is down")

            async def sadd(self, key: str, *members: str) -> int:
                raise ConnectionError("Redis is down")

        broken_redis = FullyBrokenRedis()
        service = KeyPoolService(
            repository=fake_repo,  # type: ignore[arg-type]
            encryption=encryption,
            redis=broken_redis,  # type: ignore[arg-type]
        )

        key = _make_entry(encryption, label="cache-fail", priority=10)
        fake_repo._entries[key.id] = key

        # Should not raise — just log a warning
        await service.populate_cache("suno")

    @pytest.mark.asyncio
    async def test_invalidate_cache_survives_redis_failure(
        self, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """_invalidate_cache should not raise when Redis is unavailable."""

        class BrokenInvalidateRedis(FakeRedis):
            async def incr(self, key: str) -> int:
                raise ConnectionError("Redis is down")

            async def delete(self, *keys: str) -> int:
                raise ConnectionError("Redis is down")

        broken_redis = BrokenInvalidateRedis()
        service = KeyPoolService(
            repository=fake_repo,  # type: ignore[arg-type]
            encryption=encryption,
            redis=broken_redis,  # type: ignore[arg-type]
        )

        # Should not raise
        await service._invalidate_cache("suno")

    @pytest.mark.asyncio
    async def test_load_all_caches_survives_redis_failure(
        self, fake_repo: FakeKeyPoolRepository, encryption: KeyEncryption
    ) -> None:
        """load_all_caches should not raise when Redis is unavailable."""

        class BrokenLoadRedis(FakeRedis):
            async def delete(self, *keys: str) -> int:
                raise ConnectionError("Redis is down")

            async def zadd(self, key: str, mapping: dict[str, float]) -> int:
                raise ConnectionError("Redis is down")

        broken_redis = BrokenLoadRedis()
        service = KeyPoolService(
            repository=fake_repo,  # type: ignore[arg-type]
            encryption=encryption,
            redis=broken_redis,  # type: ignore[arg-type]
        )

        key = _make_entry(encryption, label="load-fail", priority=10)
        fake_repo._entries[key.id] = key

        # Should not raise — just log a warning
        await service.load_all_caches()
