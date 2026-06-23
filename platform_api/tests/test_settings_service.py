"""Unit tests for SettingsRepository and SettingsService.

Tests value type validation, serialization/deserialization round-trips,
merged settings logic, patch atomicity, and sensitive key filtering
using an in-memory fake asyncpg pool.

Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.repositories.settings_repo import (
    MAX_JSON_BYTES,
    MAX_KEY_LENGTH,
    MAX_STRING_LENGTH,
    SettingsRepository,
    _deserialize_value,
    _detect_value_type,
    _serialize_value,
    validate_key,
    validate_setting,
)
from platform_api.services.settings_service import (
    MAX_PATCH_SIZE,
    MIN_PATCH_SIZE,
    SENSITIVE_PATTERNS,
    SettingsService,
    filter_sensitive,
    is_sensitive_key,
)


# ---------------------------------------------------------------------------
# Fake asyncpg primitives
# ---------------------------------------------------------------------------


class FakeRecord(dict):
    """Simulates an asyncpg Record."""

    def __getitem__(self, key: str) -> Any:
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        return super().get(key, default)


class FakeConnection:
    """Simulates an asyncpg connection with transaction support."""

    def __init__(self, pool: "FakeAsyncPGPool") -> None:
        self._pool = pool

    async def fetchrow(self, query: str, *args: Any) -> FakeRecord | None:
        return await self._pool._handle_query(query, args, mode="fetchrow")

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self._pool._handle_query(query, args, mode="fetchval")

    async def fetch(self, query: str, *args: Any) -> list[FakeRecord]:
        return await self._pool._handle_query(query, args, mode="fetch")

    async def execute(self, query: str, *args: Any) -> str:
        return await self._pool._handle_query(query, args, mode="execute")

    def transaction(self) -> "FakeTransaction":
        return FakeTransaction()

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


class FakeTransaction:
    """No-op transaction context manager."""

    async def __aenter__(self) -> "FakeTransaction":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


class FakeAsyncPGPool:
    """In-memory asyncpg pool that simulates user_settings and system_settings tables.

    Stores user_settings as {user_id: {key: (value_type, value_text)}} and
    system_settings as {key: (value_type, value_text)}.
    """

    def __init__(self) -> None:
        self._user_settings: dict[UUID, dict[str, tuple[str, str]]] = {}
        self._system_settings: dict[str, tuple[str, str]] = {}

    def seed_user_setting(
        self, user_id: UUID, key: str, value_type: str, value: str
    ) -> None:
        """Seed a user setting for testing."""
        if user_id not in self._user_settings:
            self._user_settings[user_id] = {}
        self._user_settings[user_id][key] = (value_type, value)

    def seed_system_setting(self, key: str, value_type: str, value: str) -> None:
        """Seed a system setting for testing."""
        self._system_settings[key] = (value_type, value)

    def acquire(self) -> FakeConnection:
        return FakeConnection(self)

    async def fetchrow(self, query: str, *args: Any) -> FakeRecord | None:
        return await self._handle_query(query, args, mode="fetchrow")

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self._handle_query(query, args, mode="fetchval")

    async def fetch(self, query: str, *args: Any) -> list[FakeRecord]:
        return await self._handle_query(query, args, mode="fetch")

    async def execute(self, query: str, *args: Any) -> str:
        return await self._handle_query(query, args, mode="execute")

    async def _handle_query(self, query: str, args: tuple, mode: str) -> Any:
        q = query.strip().lower()

        # DELETE FROM user_settings WHERE user_id = $1 AND key = $2
        if "delete from user_settings" in q:
            user_id = args[0]
            key = args[1]
            user_data = self._user_settings.get(user_id, {})
            if key in user_data:
                del user_data[key]
                return "DELETE 1"
            return "DELETE 0"

        # INSERT INTO user_settings ... ON CONFLICT ... DO UPDATE
        if "insert into user_settings" in q and "on conflict" in q:
            user_id = args[0]
            key = args[1]
            value_type = args[2]
            value = args[3]
            if user_id not in self._user_settings:
                self._user_settings[user_id] = {}
            self._user_settings[user_id][key] = (value_type, value)
            return "INSERT 0 1"

        # SELECT value_type, value FROM user_settings WHERE user_id = $1 AND key = $2
        if "from user_settings" in q and "and key" in q:
            user_id = args[0]
            key = args[1]
            user_data = self._user_settings.get(user_id, {})
            if key in user_data:
                vt, v = user_data[key]
                if mode == "fetchrow":
                    return FakeRecord({"value_type": vt, "value": v})
                return FakeRecord({"value_type": vt, "value": v})
            return None

        # SELECT key, value_type, value FROM user_settings WHERE user_id = $1
        if "from user_settings" in q and "where user_id" in q:
            user_id = args[0]
            user_data = self._user_settings.get(user_id, {})
            rows = [
                FakeRecord({"key": k, "value_type": vt, "value": v})
                for k, (vt, v) in user_data.items()
            ]
            if mode == "fetch":
                return rows
            return rows[0] if rows else None

        # DELETE FROM system_settings WHERE key = $1
        if "delete from system_settings" in q:
            key = args[0]
            if key in self._system_settings:
                del self._system_settings[key]
                return "DELETE 1"
            return "DELETE 0"

        # INSERT INTO system_settings ... ON CONFLICT ... DO UPDATE
        if "insert into system_settings" in q and "on conflict" in q:
            key = args[0]
            value_type = args[1]
            value = args[2]
            self._system_settings[key] = (value_type, value)
            return "INSERT 0 1"

        # SELECT value_type, value FROM system_settings WHERE key = $1
        if "from system_settings" in q and "where" in q:
            key = args[0]
            if key in self._system_settings:
                vt, v = self._system_settings[key]
                if mode == "fetchrow":
                    return FakeRecord({"value_type": vt, "value": v})
                return FakeRecord({"value_type": vt, "value": v})
            return None

        # SELECT key, value_type, value FROM system_settings (no WHERE)
        if "from system_settings" in q:
            rows = [
                FakeRecord({"key": k, "value_type": vt, "value": v})
                for k, (vt, v) in self._system_settings.items()
            ]
            if mode == "fetch":
                return rows
            return rows[0] if rows else None

        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pool() -> FakeAsyncPGPool:
    return FakeAsyncPGPool()


@pytest.fixture
def repo(pool: FakeAsyncPGPool) -> SettingsRepository:
    return SettingsRepository(pool)


@pytest.fixture
def service(repo: SettingsRepository) -> SettingsService:
    return SettingsService(repo)


# ---------------------------------------------------------------------------
# Tests: Value type detection
# ---------------------------------------------------------------------------


class TestValueTypeDetection:
    """Tests for _detect_value_type."""

    def test_string(self) -> None:
        assert _detect_value_type("hello") == "string"

    def test_integer(self) -> None:
        assert _detect_value_type(42) == "integer"

    def test_float(self) -> None:
        assert _detect_value_type(3.14) == "float"

    def test_boolean_true(self) -> None:
        assert _detect_value_type(True) == "boolean"

    def test_boolean_false(self) -> None:
        assert _detect_value_type(False) == "boolean"

    def test_dict_json(self) -> None:
        assert _detect_value_type({"a": 1}) == "json"

    def test_list_json(self) -> None:
        assert _detect_value_type([1, 2, 3]) == "json"

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(ValidationError, match="Unsupported value type"):
            _detect_value_type(None)

    def test_unsupported_type_set_raises(self) -> None:
        with pytest.raises(ValidationError, match="Unsupported value type"):
            _detect_value_type({1, 2, 3})


# ---------------------------------------------------------------------------
# Tests: Serialization / deserialization round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    """Tests for _serialize_value and _deserialize_value."""

    def test_string_roundtrip(self) -> None:
        val = "hello world"
        serialized = _serialize_value(val, "string")
        assert _deserialize_value(serialized, "string") == val

    def test_integer_roundtrip(self) -> None:
        val = -42
        serialized = _serialize_value(val, "integer")
        assert _deserialize_value(serialized, "integer") == val

    def test_float_roundtrip(self) -> None:
        val = 3.14159
        serialized = _serialize_value(val, "float")
        assert _deserialize_value(serialized, "float") == pytest.approx(val)

    def test_boolean_true_roundtrip(self) -> None:
        serialized = _serialize_value(True, "boolean")
        assert _deserialize_value(serialized, "boolean") is True

    def test_boolean_false_roundtrip(self) -> None:
        serialized = _serialize_value(False, "boolean")
        assert _deserialize_value(serialized, "boolean") is False

    def test_json_dict_roundtrip(self) -> None:
        val = {"theme": "dark", "count": 5, "nested": {"a": [1, 2]}}
        serialized = _serialize_value(val, "json")
        assert _deserialize_value(serialized, "json") == val

    def test_json_list_roundtrip(self) -> None:
        val = [1, "two", True, None]
        serialized = _serialize_value(val, "json")
        assert _deserialize_value(serialized, "json") == val

    def test_string_exceeds_max_length_raises(self) -> None:
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            _serialize_value("x" * (MAX_STRING_LENGTH + 1), "string")

    def test_json_exceeds_max_size_raises(self) -> None:
        # Create a JSON value that exceeds 64 KB when serialized
        large_value = {"data": "x" * (MAX_JSON_BYTES + 1)}
        with pytest.raises(ValidationError, match="exceeds maximum size"):
            _serialize_value(large_value, "json")


# ---------------------------------------------------------------------------
# Tests: Key validation
# ---------------------------------------------------------------------------


class TestKeyValidation:
    """Tests for validate_key."""

    def test_valid_key(self) -> None:
        validate_key("theme.color")  # Should not raise

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ValidationError, match="must not be empty"):
            validate_key("")

    def test_whitespace_only_key_raises(self) -> None:
        with pytest.raises(ValidationError, match="must not be empty"):
            validate_key("   ")

    def test_key_exceeds_max_length_raises(self) -> None:
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            validate_key("x" * (MAX_KEY_LENGTH + 1))

    def test_key_at_max_length_passes(self) -> None:
        validate_key("x" * MAX_KEY_LENGTH)  # Should not raise


# ---------------------------------------------------------------------------
# Tests: Sensitive key filtering
# ---------------------------------------------------------------------------


class TestSensitiveKeyFiltering:
    """Tests for is_sensitive_key and filter_sensitive."""

    @pytest.mark.parametrize(
        "key",
        [
            "db_password",
            "DATABASE_PASSWORD",
            "suno_api_key",
            "SUNO_API_KEY",
            "jwt_secret",
            "JWT_SECRET",
            "refresh_token_secret",
            "access_token",
            "encryption_key",
        ],
    )
    def test_sensitive_keys_detected(self, key: str) -> None:
        assert is_sensitive_key(key) is True

    @pytest.mark.parametrize(
        "key",
        [
            "theme",
            "language",
            "volume",
            "output_resolution",
            "auto_save",
        ],
    )
    def test_non_sensitive_keys_allowed(self, key: str) -> None:
        assert is_sensitive_key(key) is False

    def test_filter_sensitive_removes_matching_keys(self) -> None:
        settings = {
            "theme": "dark",
            "api_key": "secret123",
            "language": "en",
            "db_password": "hunter2",
        }
        filtered = filter_sensitive(settings)
        assert filtered == {"theme": "dark", "language": "en"}


# ---------------------------------------------------------------------------
# Tests: SettingsRepository
# ---------------------------------------------------------------------------


class TestSettingsRepository:
    """Tests for SettingsRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_user_settings_empty(self, repo: SettingsRepository) -> None:
        user_id = uuid4()
        result = await repo.get_user_settings(user_id)
        assert result == {}

    @pytest.mark.asyncio
    async def test_upsert_and_get_user_settings(
        self, repo: SettingsRepository, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        await repo.upsert_user_settings(
            user_id, {"theme": "dark", "volume": 80, "auto_save": True}
        )
        result = await repo.get_user_settings(user_id)
        assert result == {"theme": "dark", "volume": 80, "auto_save": True}

    @pytest.mark.asyncio
    async def test_upsert_overwrites_existing(
        self, repo: SettingsRepository, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        await repo.upsert_user_settings(user_id, {"theme": "dark"})
        await repo.upsert_user_settings(user_id, {"theme": "light"})
        result = await repo.get_user_settings(user_id)
        assert result == {"theme": "light"}

    @pytest.mark.asyncio
    async def test_get_user_setting_returns_none_for_missing(
        self, repo: SettingsRepository
    ) -> None:
        user_id = uuid4()
        result = await repo.get_user_setting(user_id, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_user_setting(
        self, repo: SettingsRepository, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        await repo.upsert_user_settings(user_id, {"theme": "dark"})
        deleted = await repo.delete_user_setting(user_id, "theme")
        assert deleted is True
        result = await repo.get_user_settings(user_id)
        assert result == {}

    @pytest.mark.asyncio
    async def test_delete_user_setting_returns_false_when_not_found(
        self, repo: SettingsRepository
    ) -> None:
        user_id = uuid4()
        deleted = await repo.delete_user_setting(user_id, "nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_get_system_settings_empty(
        self, repo: SettingsRepository
    ) -> None:
        result = await repo.get_system_settings()
        assert result == {}

    @pytest.mark.asyncio
    async def test_upsert_and_get_system_settings(
        self, repo: SettingsRepository
    ) -> None:
        await repo.upsert_system_settings(
            {"default_theme": "light", "max_volume": 100}
        )
        result = await repo.get_system_settings()
        assert result == {"default_theme": "light", "max_volume": 100}

    @pytest.mark.asyncio
    async def test_upsert_invalid_value_rejects_entire_batch(
        self, repo: SettingsRepository
    ) -> None:
        user_id = uuid4()
        with pytest.raises(ValidationError, match="invalid values"):
            await repo.upsert_user_settings(
                user_id, {"valid_key": "ok", "bad_key": None}  # type: ignore
            )
        # Ensure no partial writes occurred
        result = await repo.get_user_settings(user_id)
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: SettingsService
# ---------------------------------------------------------------------------


class TestSettingsService:
    """Tests for SettingsService merge logic, patch operations, and filtering."""

    @pytest.mark.asyncio
    async def test_get_merged_settings_system_only(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        pool.seed_system_setting("theme", "string", "light")
        pool.seed_system_setting("volume", "integer", "80")
        user_id = uuid4()

        result = await service.get_merged_settings(user_id)
        assert result == {"theme": "light", "volume": 80}

    @pytest.mark.asyncio
    async def test_get_merged_settings_user_overrides_system(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        pool.seed_system_setting("theme", "string", "light")
        pool.seed_system_setting("volume", "integer", "80")
        pool.seed_user_setting(user_id, "theme", "string", "dark")

        result = await service.get_merged_settings(user_id)
        assert result == {"theme": "dark", "volume": 80}

    @pytest.mark.asyncio
    async def test_get_merged_settings_user_only_keys_included(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        pool.seed_system_setting("theme", "string", "light")
        pool.seed_user_setting(user_id, "custom_setting", "string", "value")

        result = await service.get_merged_settings(user_id)
        assert result == {"theme": "light", "custom_setting": "value"}

    @pytest.mark.asyncio
    async def test_get_merged_settings_filters_sensitive_keys(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        pool.seed_system_setting("theme", "string", "light")
        pool.seed_system_setting("db_password", "string", "secret123")
        pool.seed_system_setting("suno_api_key", "string", "key123")

        result = await service.get_merged_settings(user_id)
        assert "db_password" not in result
        assert "suno_api_key" not in result
        assert result == {"theme": "light"}

    @pytest.mark.asyncio
    async def test_get_merged_settings_include_sensitive(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        pool.seed_system_setting("theme", "string", "light")
        pool.seed_system_setting("db_password", "string", "secret123")

        result = await service.get_merged_settings(user_id, include_sensitive=True)
        assert "db_password" in result
        assert result["db_password"] == "secret123"

    @pytest.mark.asyncio
    async def test_patch_settings_applies_and_returns_merged(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        pool.seed_system_setting("theme", "string", "light")
        pool.seed_system_setting("volume", "integer", "80")

        result = await service.patch_settings(user_id, {"theme": "dark"})
        assert result["theme"] == "dark"
        assert result["volume"] == 80

    @pytest.mark.asyncio
    async def test_patch_settings_empty_raises(
        self, service: SettingsService
    ) -> None:
        user_id = uuid4()
        with pytest.raises(ValidationError, match="at least 1"):
            await service.patch_settings(user_id, {})

    @pytest.mark.asyncio
    async def test_patch_settings_exceeds_max_raises(
        self, service: SettingsService
    ) -> None:
        user_id = uuid4()
        big_patch = {f"key_{i}": f"val_{i}" for i in range(MAX_PATCH_SIZE + 1)}
        with pytest.raises(ValidationError, match="exceeds maximum"):
            await service.patch_settings(user_id, big_patch)

    @pytest.mark.asyncio
    async def test_patch_settings_invalid_value_rejects_all(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        pool.seed_system_setting("theme", "string", "light")

        with pytest.raises(ValidationError):
            await service.patch_settings(
                user_id, {"valid": "value", "bad": None}  # type: ignore
            )

        # Ensure no partial writes
        result = await service.get_merged_settings(user_id)
        assert "valid" not in result

    @pytest.mark.asyncio
    async def test_patch_settings_idempotent(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        patch = {"theme": "dark", "volume": 90}

        result1 = await service.patch_settings(user_id, patch)
        result2 = await service.patch_settings(user_id, patch)
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_patch_settings_preserves_unpatched_keys(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        await service.patch_settings(user_id, {"a": "1", "b": "2"})
        result = await service.patch_settings(user_id, {"b": "3"})
        assert result["a"] == "1"
        assert result["b"] == "3"

    @pytest.mark.asyncio
    async def test_patch_system_settings(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        result = await service.patch_system_settings({"default_theme": "dark"})
        assert result == {"default_theme": "dark"}

    @pytest.mark.asyncio
    async def test_delete_user_setting(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        await service.patch_settings(user_id, {"theme": "dark"})
        deleted = await service.delete_user_setting(user_id, "theme")
        assert deleted is True

    @pytest.mark.asyncio
    async def test_patch_settings_with_all_types(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        user_id = uuid4()
        patch = {
            "str_setting": "hello",
            "int_setting": 42,
            "float_setting": 3.14,
            "bool_setting": True,
            "json_setting": {"nested": [1, 2, 3]},
        }
        result = await service.patch_settings(user_id, patch)
        assert result["str_setting"] == "hello"
        assert result["int_setting"] == 42
        assert result["float_setting"] == pytest.approx(3.14)
        assert result["bool_setting"] is True
        assert result["json_setting"] == {"nested": [1, 2, 3]}


# ---------------------------------------------------------------------------
# Tests: Global Credit Value methods
# ---------------------------------------------------------------------------


class TestGlobalCreditValue:
    """Tests for SettingsService global credit value methods."""

    @pytest.mark.asyncio
    async def test_get_global_credit_value_not_configured(
        self, service: SettingsService
    ) -> None:
        result = await service.get_global_credit_value()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_global_credit_value_returns_float(
        self, service: SettingsService, pool: FakeAsyncPGPool
    ) -> None:
        pool.seed_system_setting("global_credit_value", "float", "0.003333")
        result = await service.get_global_credit_value()
        assert result == pytest.approx(0.003333)

    @pytest.mark.asyncio
    async def test_update_global_credit_value_valid(
        self, service: SettingsService
    ) -> None:
        result = await service.update_global_credit_value(0.003333)
        assert result == pytest.approx(0.003333)

    @pytest.mark.asyncio
    async def test_update_global_credit_value_persists(
        self, service: SettingsService
    ) -> None:
        await service.update_global_credit_value(0.005)
        result = await service.get_global_credit_value()
        assert result == pytest.approx(0.005)

    @pytest.mark.asyncio
    async def test_update_global_credit_value_exactly_one(
        self, service: SettingsService
    ) -> None:
        result = await service.update_global_credit_value(1.0)
        assert result == 1.0

    @pytest.mark.asyncio
    async def test_update_global_credit_value_zero_raises(
        self, service: SettingsService
    ) -> None:
        with pytest.raises(ValidationError, match="greater than 0 and at most 1.0"):
            await service.update_global_credit_value(0.0)

    @pytest.mark.asyncio
    async def test_update_global_credit_value_negative_raises(
        self, service: SettingsService
    ) -> None:
        with pytest.raises(ValidationError, match="greater than 0 and at most 1.0"):
            await service.update_global_credit_value(-0.5)

    @pytest.mark.asyncio
    async def test_update_global_credit_value_above_one_raises(
        self, service: SettingsService
    ) -> None:
        with pytest.raises(ValidationError, match="greater than 0 and at most 1.0"):
            await service.update_global_credit_value(1.1)

    @pytest.mark.asyncio
    async def test_update_global_credit_value_small_positive(
        self, service: SettingsService
    ) -> None:
        result = await service.update_global_credit_value(0.000001)
        assert result == pytest.approx(0.000001)
