"""Settings repository with key-value CRUD for user and system settings.

Supports value types: string (≤10000 chars), integer, float, boolean,
JSON (≤64KB serialized). Keys are limited to 255 characters.

Provides operations for both user_settings and system_settings tables,
with atomic batch upsert for patch operations.

Requirements: 14.1, 14.2, 14.3, 14.5, 14.6
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Constraints
MAX_KEY_LENGTH = 255
MAX_STRING_LENGTH = 10_000
MAX_JSON_BYTES = 64 * 1024  # 64 KB
SUPPORTED_VALUE_TYPES = {"string", "integer", "float", "boolean", "json"}


class AsyncPGPool(Protocol):
    """Minimal protocol for an asyncpg connection pool."""

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        ...

    async def fetchrow(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single row."""
        ...

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        """Execute a query and return all rows."""
        ...

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single value."""
        ...

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status."""
        ...


def _detect_value_type(value: Any) -> str:
    """Detect the value type string for a given Python value.

    Args:
        value: The Python value to classify.

    Returns:
        One of 'string', 'integer', 'float', 'boolean', 'json'.

    Raises:
        ValidationError: If the value is not a supported type.
    """
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (dict, list)):
        return "json"
    raise ValidationError(
        f"Unsupported value type: {type(value).__name__}. "
        f"Supported types: string, integer, float, boolean, JSON object.",
        details={"type": type(value).__name__},
    )


def _serialize_value(value: Any, value_type: str) -> str:
    """Serialize a Python value to its TEXT storage representation.

    Args:
        value: The value to serialize.
        value_type: The detected type string.

    Returns:
        The TEXT representation for database storage.

    Raises:
        ValidationError: If the value violates size constraints.
    """
    if value_type == "string":
        if len(value) > MAX_STRING_LENGTH:
            raise ValidationError(
                f"String value exceeds maximum length of {MAX_STRING_LENGTH} characters.",
                details={"length": len(value), "max": MAX_STRING_LENGTH},
            )
        return value
    elif value_type == "integer":
        return str(value)
    elif value_type == "float":
        return str(value)
    elif value_type == "boolean":
        return "true" if value else "false"
    elif value_type == "json":
        serialized = json.dumps(value, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > MAX_JSON_BYTES:
            raise ValidationError(
                f"JSON value exceeds maximum size of {MAX_JSON_BYTES // 1024} KB.",
                details={
                    "size_bytes": len(serialized.encode("utf-8")),
                    "max_bytes": MAX_JSON_BYTES,
                },
            )
        return serialized
    else:
        raise ValidationError(
            f"Unsupported value type: {value_type}.",
            details={"value_type": value_type},
        )


def _deserialize_value(raw: str, value_type: str) -> Any:
    """Deserialize a TEXT storage representation to its Python value.

    Args:
        raw: The raw TEXT string from the database.
        value_type: The stored type string.

    Returns:
        The deserialized Python value.
    """
    if value_type == "string":
        return raw
    elif value_type == "integer":
        return int(raw)
    elif value_type == "float":
        return float(raw)
    elif value_type == "boolean":
        return raw.lower() == "true"
    elif value_type == "json":
        return json.loads(raw)
    else:
        # Fall back to string for unknown types
        return raw


def validate_key(key: str) -> None:
    """Validate a settings key.

    Args:
        key: The settings key to validate.

    Raises:
        ValidationError: If the key is empty or exceeds 255 characters.
    """
    if not key or not key.strip():
        raise ValidationError(
            "Settings key must not be empty.",
            details={"key": key},
        )
    if len(key) > MAX_KEY_LENGTH:
        raise ValidationError(
            f"Settings key exceeds maximum length of {MAX_KEY_LENGTH} characters.",
            details={"key_length": len(key), "max": MAX_KEY_LENGTH},
        )


def validate_setting(key: str, value: Any) -> tuple[str, str, str]:
    """Validate a single key-value setting pair.

    Args:
        key: The settings key.
        value: The value to store.

    Returns:
        A tuple of (key, value_type, serialized_value).

    Raises:
        ValidationError: If key or value is invalid.
    """
    validate_key(key)
    value_type = _detect_value_type(value)
    serialized = _serialize_value(value, value_type)
    return key, value_type, serialized


class SettingsRepository:
    """Repository for settings CRUD operations using asyncpg.

    Manages both user_settings and system_settings tables with support
    for atomic batch upserts and type-aware serialization.

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    # -----------------------------------------------------------------------
    # User Settings
    # -----------------------------------------------------------------------

    async def get_user_settings(self, user_id: UUID) -> dict[str, Any]:
        """Return all user settings as a key→value dict.

        Args:
            user_id: The UUID of the user.

        Returns:
            Dict mapping setting keys to their deserialized Python values.
        """
        rows = await self._pool.fetch(
            """
            SELECT key, value_type, value
            FROM user_settings
            WHERE user_id = $1
            """,
            user_id,
        )
        return {
            row["key"]: _deserialize_value(row["value"], row["value_type"])
            for row in rows
        }

    async def get_user_setting(self, user_id: UUID, key: str) -> Any | None:
        """Return a single user setting value, or None if not set.

        Args:
            user_id: The UUID of the user.
            key: The setting key to retrieve.

        Returns:
            The deserialized value, or None if the key doesn't exist.
        """
        row = await self._pool.fetchrow(
            """
            SELECT value_type, value
            FROM user_settings
            WHERE user_id = $1 AND key = $2
            """,
            user_id,
            key,
        )
        if row is None:
            return None
        return _deserialize_value(row["value"], row["value_type"])

    async def upsert_user_settings(
        self, user_id: UUID, settings: dict[str, Any]
    ) -> None:
        """Atomically upsert multiple user settings.

        All settings are validated before any writes occur. If any value
        is invalid, the entire operation is rejected (no partial writes).

        Args:
            user_id: The UUID of the user.
            settings: Dict of key→value pairs to upsert.

        Raises:
            ValidationError: If any key or value is invalid.
        """
        # Validate all settings first (fail-fast, no partial writes)
        validated: list[tuple[str, str, str]] = []
        errors: list[dict[str, str]] = []

        for key, value in settings.items():
            try:
                validated.append(validate_setting(key, value))
            except ValidationError as e:
                errors.append({"key": key, "error": e.message})

        if errors:
            raise ValidationError(
                "Settings patch contains invalid values.",
                details={"invalid_keys": errors},
            )

        # Perform atomic upsert within a transaction
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for key, value_type, serialized in validated:
                    await conn.execute(
                        """
                        INSERT INTO user_settings (user_id, key, value_type, value, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, NOW(), NOW())
                        ON CONFLICT (user_id, key)
                        DO UPDATE SET value_type = $3, value = $4, updated_at = NOW()
                        """,
                        user_id,
                        key,
                        value_type,
                        serialized,
                    )

        logger.info(
            "Upserted %d user settings for user %s.", len(validated), user_id
        )

    async def delete_user_setting(self, user_id: UUID, key: str) -> bool:
        """Delete a single user setting.

        Args:
            user_id: The UUID of the user.
            key: The setting key to delete.

        Returns:
            True if the setting was found and deleted, False otherwise.
        """
        result = await self._pool.execute(
            """
            DELETE FROM user_settings
            WHERE user_id = $1 AND key = $2
            """,
            user_id,
            key,
        )
        return result == "DELETE 1"

    # -----------------------------------------------------------------------
    # System Settings
    # -----------------------------------------------------------------------

    async def get_system_settings(self) -> dict[str, Any]:
        """Return all system settings as a key→value dict.

        Returns:
            Dict mapping setting keys to their deserialized Python values.
        """
        rows = await self._pool.fetch(
            """
            SELECT key, value_type, value
            FROM system_settings
            """
        )
        return {
            row["key"]: _deserialize_value(row["value"], row["value_type"])
            for row in rows
        }

    async def get_system_setting(self, key: str) -> Any | None:
        """Return a single system setting value, or None if not set.

        Args:
            key: The setting key to retrieve.

        Returns:
            The deserialized value, or None if the key doesn't exist.
        """
        row = await self._pool.fetchrow(
            """
            SELECT value_type, value
            FROM system_settings
            WHERE key = $1
            """,
            key,
        )
        if row is None:
            return None
        return _deserialize_value(row["value"], row["value_type"])

    async def upsert_system_settings(self, settings: dict[str, Any]) -> None:
        """Atomically upsert multiple system settings.

        All settings are validated before any writes occur. If any value
        is invalid, the entire operation is rejected.

        Args:
            settings: Dict of key→value pairs to upsert.

        Raises:
            ValidationError: If any key or value is invalid.
        """
        # Validate all settings first
        validated: list[tuple[str, str, str]] = []
        errors: list[dict[str, str]] = []

        for key, value in settings.items():
            try:
                validated.append(validate_setting(key, value))
            except ValidationError as e:
                errors.append({"key": key, "error": e.message})

        if errors:
            raise ValidationError(
                "Settings patch contains invalid values.",
                details={"invalid_keys": errors},
            )

        # Perform atomic upsert within a transaction
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for key, value_type, serialized in validated:
                    await conn.execute(
                        """
                        INSERT INTO system_settings (key, value_type, value, updated_at)
                        VALUES ($1, $2, $3, NOW())
                        ON CONFLICT (key)
                        DO UPDATE SET value_type = $2, value = $3, updated_at = NOW()
                        """,
                        key,
                        value_type,
                        serialized,
                    )

        logger.info("Upserted %d system settings.", len(validated))

    async def delete_system_setting(self, key: str) -> bool:
        """Delete a single system setting.

        Args:
            key: The setting key to delete.

        Returns:
            True if the setting was found and deleted, False otherwise.
        """
        result = await self._pool.execute(
            """
            DELETE FROM system_settings
            WHERE key = $1
            """,
            key,
        )
        return result == "DELETE 1"
