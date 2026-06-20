"""Application settings service.

Provides merged settings (user values override system defaults), atomic patch
operations (1-50 key-value pairs), and sensitive key filtering.

Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sensitive key patterns
# ---------------------------------------------------------------------------

# Keys containing any of these substrings (case-insensitive) are considered
# sensitive and excluded from user-facing responses.
SENSITIVE_PATTERNS: tuple[str, ...] = (
    "secret",
    "password",
    "token",
    "key",
    "api_key",
)

# Minimum and maximum number of key-value pairs in a patch request.
MIN_PATCH_SIZE = 1
MAX_PATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Dependency Protocols
# ---------------------------------------------------------------------------


class SettingsRepositoryPort(Protocol):
    """Protocol for the settings repository dependency."""

    async def get_user_settings(self, user_id: UUID) -> dict[str, Any]: ...
    async def get_system_settings(self) -> dict[str, Any]: ...
    async def upsert_user_settings(
        self, user_id: UUID, settings: dict[str, Any]
    ) -> None: ...
    async def delete_user_setting(self, user_id: UUID, key: str) -> bool: ...
    async def upsert_system_settings(self, settings: dict[str, Any]) -> None: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_sensitive_key(key: str) -> bool:
    """Check whether a settings key is considered sensitive.

    A key is sensitive if it contains any of the sensitive patterns
    (case-insensitive comparison).

    Args:
        key: The settings key to check.

    Returns:
        True if the key matches a sensitive pattern.
    """
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in SENSITIVE_PATTERNS)


def filter_sensitive(settings: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive keys from a settings dict.

    Args:
        settings: The full settings dict.

    Returns:
        A new dict with sensitive keys excluded.
    """
    return {k: v for k, v in settings.items() if not is_sensitive_key(k)}


# ---------------------------------------------------------------------------
# Settings Service
# ---------------------------------------------------------------------------


class SettingsService:
    """Application service for settings management.

    Handles merged settings retrieval (user overrides system defaults),
    atomic patch operations with validation, and sensitive key filtering.

    Args:
        settings_repo: Repository for settings persistence operations.
    """

    def __init__(self, settings_repo: SettingsRepositoryPort) -> None:
        self._settings_repo = settings_repo

    async def get_merged_settings(
        self, user_id: UUID, *, include_sensitive: bool = False
    ) -> dict[str, Any]:
        """Return merged settings with user values overriding system defaults.

        The merge logic:
        1. Start with all system settings (defaults).
        2. Overlay user-specific settings on top (user values take precedence).
        3. Filter out sensitive keys unless explicitly requested.

        Args:
            user_id: The UUID of the authenticated user.
            include_sensitive: If True, include sensitive keys in the response.
                Defaults to False for user-facing API responses.

        Returns:
            Dict of merged settings with appropriate filtering applied.
        """
        system_settings = await self._settings_repo.get_system_settings()
        user_settings = await self._settings_repo.get_user_settings(user_id)

        # Merge: system defaults first, then user overrides
        merged = {**system_settings, **user_settings}

        # Filter sensitive keys for user-facing responses
        if not include_sensitive:
            merged = filter_sensitive(merged)

        return merged

    async def patch_settings(
        self, user_id: UUID, patch: dict[str, Any]
    ) -> dict[str, Any]:
        """Atomically apply a settings patch for a user.

        Validates the patch size (1-50 keys) and all values before persisting.
        If any value is invalid, the entire patch is rejected with no changes.

        After successful persistence, returns the full merged settings
        (with sensitive keys filtered).

        Args:
            user_id: The UUID of the authenticated user.
            patch: Dict of 1-50 key-value pairs to upsert.

        Returns:
            The full merged settings after the patch is applied.

        Raises:
            ValidationError: If the patch is empty, exceeds 50 keys, or
                contains invalid values.
        """
        # Validate patch size
        if not patch:
            raise ValidationError(
                "Settings patch must contain at least 1 key-value pair.",
                details={"patch_size": 0, "min": MIN_PATCH_SIZE, "max": MAX_PATCH_SIZE},
            )

        if len(patch) > MAX_PATCH_SIZE:
            raise ValidationError(
                f"Settings patch exceeds maximum of {MAX_PATCH_SIZE} key-value pairs.",
                details={
                    "patch_size": len(patch),
                    "max": MAX_PATCH_SIZE,
                },
            )

        # Persist the patch (repository handles per-value validation atomically)
        await self._settings_repo.upsert_user_settings(user_id, patch)

        logger.info(
            "Applied settings patch of %d keys for user %s.", len(patch), user_id
        )

        # Return the full merged settings
        return await self.get_merged_settings(user_id)

    async def patch_system_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Atomically apply a system settings patch (Admin operation).

        Updates system defaults. Users who have not explicitly overridden
        these keys will see the new defaults.

        Args:
            patch: Dict of key-value pairs to upsert as system defaults.

        Returns:
            The updated system settings.

        Raises:
            ValidationError: If the patch is empty or contains invalid values.
        """
        if not patch:
            raise ValidationError(
                "Settings patch must contain at least 1 key-value pair.",
                details={"patch_size": 0},
            )

        if len(patch) > MAX_PATCH_SIZE:
            raise ValidationError(
                f"Settings patch exceeds maximum of {MAX_PATCH_SIZE} key-value pairs.",
                details={"patch_size": len(patch), "max": MAX_PATCH_SIZE},
            )

        await self._settings_repo.upsert_system_settings(patch)

        logger.info("Applied system settings patch of %d keys.", len(patch))

        return await self._settings_repo.get_system_settings()

    async def delete_user_setting(self, user_id: UUID, key: str) -> bool:
        """Delete a specific user setting, reverting to system default.

        Args:
            user_id: The UUID of the user.
            key: The setting key to delete.

        Returns:
            True if the setting was found and deleted, False otherwise.
        """
        deleted = await self._settings_repo.delete_user_setting(user_id, key)
        if deleted:
            logger.info("Deleted user setting '%s' for user %s.", key, user_id)
        return deleted
