"""User management service for admin operations.

Provides paginated user listing, updates, suspension, reactivation,
and soft-deletion with token revocation.

Requirements: 3.1, 3.2, 3.3, 3.4
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.models.domain import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE: int = 25
"""Default number of users returned per page."""

MAX_PAGE_SIZE: int = 100
"""Maximum allowed page size for user listings."""

# Fields that admins are allowed to update on a user record
_ALLOWED_UPDATE_FIELDS: frozenset[str] = frozenset(
    {"display_name", "role", "email"}
)


# ---------------------------------------------------------------------------
# Dependency Protocols
# ---------------------------------------------------------------------------


class UserRepositoryPort(Protocol):
    """Protocol for the user repository dependency."""

    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def update(self, user_id: UUID, **fields: Any) -> User | None: ...
    async def list_paginated(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
        plan_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[User], int]: ...
    async def soft_delete(self, user_id: UUID) -> bool: ...
    async def suspend(self, user_id: UUID, reason: str) -> bool: ...
    async def reactivate(self, user_id: UUID) -> bool: ...


class AuthServicePort(Protocol):
    """Protocol for token revocation dependency."""

    async def revoke_tokens(self, user_id: str) -> None: ...


# ---------------------------------------------------------------------------
# User Service
# ---------------------------------------------------------------------------


class UserService:
    """Application service for user management operations.

    Handles paginated listing, profile updates, suspension/reactivation,
    and soft-deletion with token and license revocation.

    Args:
        user_repo: Repository for user persistence operations.
        auth_service: Service for token revocation on suspension/deletion.
    """

    def __init__(
        self,
        user_repo: UserRepositoryPort,
        auth_service: AuthServicePort,
    ) -> None:
        self._user_repo = user_repo
        self._auth_service = auth_service

    async def get_users(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        status: str | None = None,
        plan_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[User], int]:
        """Return a paginated list of users with optional filters.

        Validates page_size does not exceed MAX_PAGE_SIZE and page is >= 1.

        Args:
            page: 1-based page number.
            page_size: Number of users per page (max 100, default 25).
            status: Filter by user status (active/suspended/deleted).
            plan_type: Filter by associated plan type name.
            date_from: Filter by registration date (on or after).
            date_to: Filter by registration date (on or before).

        Returns:
            A tuple of (list of User objects, total matching count).

        Raises:
            ValidationError: If page_size exceeds 100 or page is less than 1.
        """
        if page_size > MAX_PAGE_SIZE:
            raise ValidationError(
                f"page_size must not exceed {MAX_PAGE_SIZE}.",
                details={"page_size": page_size, "max": MAX_PAGE_SIZE},
            )
        if page_size < 1:
            raise ValidationError(
                "page_size must be at least 1.",
                details={"page_size": page_size},
            )
        if page < 1:
            raise ValidationError(
                "page must be at least 1.",
                details={"page": page},
            )

        return await self._user_repo.list_paginated(
            page=page,
            page_size=page_size,
            status=status,
            plan_type=plan_type,
            date_from=date_from,
            date_to=date_to,
        )

    async def get_user(self, user_id: UUID) -> User:
        """Retrieve a single user by ID.

        Args:
            user_id: The UUID of the user to retrieve.

        Returns:
            The User domain object.

        Raises:
            NotFoundError: If no user exists with the given ID.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        return user

    async def update_user(self, user_id: UUID, **fields: Any) -> User:
        """Update specified fields on a user account.

        Only allowed fields (display_name, role, email) can be updated.
        Other fields are silently ignored.

        Args:
            user_id: The UUID of the user to update.
            **fields: Key-value pairs of fields to update.

        Returns:
            The updated User domain object.

        Raises:
            NotFoundError: If no user exists with the given ID.
            ValidationError: If no valid fields are provided.
        """
        # Filter to allowed fields only
        valid_fields = {
            k: v for k, v in fields.items() if k in _ALLOWED_UPDATE_FIELDS
        }

        if not valid_fields:
            raise ValidationError(
                "No valid fields provided for update.",
                details={"allowed_fields": sorted(_ALLOWED_UPDATE_FIELDS)},
            )

        updated_user = await self._user_repo.update(user_id, **valid_fields)
        if updated_user is None:
            raise NotFoundError(f"User {user_id} not found.")
        return updated_user

    async def suspend_user(self, user_id: UUID, reason: str) -> User:
        """Suspend a user account and revoke all their tokens.

        Sets the user status to 'suspended', records the suspension reason,
        and revokes all active refresh tokens so the user is immediately
        logged out.

        Args:
            user_id: The UUID of the user to suspend.
            reason: The reason for suspension.

        Returns:
            The updated User domain object.

        Raises:
            NotFoundError: If no user exists with the given ID.
            ValidationError: If the reason is empty or the user cannot be
                suspended (e.g., already suspended or deleted).
        """
        if not reason or not reason.strip():
            raise ValidationError(
                "Suspension reason is required.",
                details={"reason": reason},
            )

        success = await self._user_repo.suspend(user_id, reason.strip())
        if not success:
            # Check if user exists to differentiate 404 vs invalid state
            user = await self._user_repo.get_by_id(user_id)
            if user is None:
                raise NotFoundError(f"User {user_id} not found.")
            raise ValidationError(
                f"Cannot suspend user with status '{user.status.value}'.",
                details={"current_status": user.status.value},
            )

        # Revoke all tokens so user is immediately logged out
        await self._auth_service.revoke_tokens(str(user_id))
        logger.info("Suspended user %s. Reason: %s", user_id, reason.strip())

        # Return the updated user record
        user = await self._user_repo.get_by_id(user_id)
        assert user is not None  # We just suspended them, they must exist
        return user

    async def reactivate_user(self, user_id: UUID) -> User:
        """Reactivate a suspended user account.

        Restores the user status to 'active' and clears the suspension reason.
        Authentication access is restored.

        Args:
            user_id: The UUID of the user to reactivate.

        Returns:
            The updated User domain object.

        Raises:
            NotFoundError: If no user exists with the given ID.
            ValidationError: If the user is not currently suspended.
        """
        success = await self._user_repo.reactivate(user_id)
        if not success:
            # Check if user exists to differentiate 404 vs invalid state
            user = await self._user_repo.get_by_id(user_id)
            if user is None:
                raise NotFoundError(f"User {user_id} not found.")
            raise ValidationError(
                f"Cannot reactivate user with status '{user.status.value}'.",
                details={"current_status": user.status.value},
            )

        logger.info("Reactivated user %s.", user_id)

        # Return the updated user record
        user = await self._user_repo.get_by_id(user_id)
        assert user is not None
        return user

    async def delete_user(self, user_id: UUID) -> None:
        """Soft-delete a user account.

        Sets deleted_at timestamp, changes status to 'deleted', revokes all
        tokens, and revokes all associated licenses. Audit history is preserved.

        Args:
            user_id: The UUID of the user to delete.

        Raises:
            NotFoundError: If no user exists with the given ID.
            ValidationError: If the user is already deleted.
        """
        success = await self._user_repo.soft_delete(user_id)
        if not success:
            # Check if user exists to differentiate 404 vs invalid state
            user = await self._user_repo.get_by_id(user_id)
            if user is None:
                raise NotFoundError(f"User {user_id} not found.")
            raise ValidationError(
                f"Cannot delete user with status '{user.status.value}'.",
                details={"current_status": user.status.value},
            )

        # Revoke all tokens so user is immediately logged out
        await self._auth_service.revoke_tokens(str(user_id))
        logger.info("Soft-deleted user %s.", user_id)

    async def hard_delete_user(self, user_id: UUID) -> None:
        """Permanently delete a user account and all associated data.

        Removes the user row and ALL related records from every table.
        Use with extreme caution — this is irreversible.

        Args:
            user_id: The UUID of the user to permanently delete.

        Raises:
            NotFoundError: If no user exists with the given ID.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")

        # Revoke all tokens first
        await self._auth_service.revoke_tokens(str(user_id))

        pool = self._user_repo._pool

        # Delete ALL related records in dependency order.
        # Tables with user_id FK:
        tables_with_user_id = [
            "credit_transactions",
            "credit_wallets",
            "email_verifications",
            "youtube_upload_jobs",
            "image_jobs",
            "suno_tasks",
            "songs",
            "batches",
            "channel_profiles",
            "licenses",
            "user_settings",
            "notification_queue",
            "plan_usage",
        ]
        for table in tables_with_user_id:
            try:
                await pool.execute(f"DELETE FROM {table} WHERE user_id = $1", user_id)
            except Exception:
                logger.debug("Cleanup skip %s (may not exist)", table)

        # Tables with actor_id FK
        tables_with_actor_id = [
            "audit_logs",
        ]
        for table in tables_with_actor_id:
            try:
                await pool.execute(f"DELETE FROM {table} WHERE actor_id = $1", user_id)
            except Exception:
                logger.debug("Cleanup skip %s (may not exist)", table)

        # Finally delete the user itself
        await pool.execute("DELETE FROM users WHERE id = $1", user_id)
        logger.info("Hard-deleted user %s and all related data.", str(user_id))
