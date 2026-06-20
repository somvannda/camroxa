"""User repository with asyncpg-based CRUD operations.

Provides paginated listing with filters, soft-delete, suspension,
and reactivation for the users table.

Requirements: 3.1, 3.2, 3.3, 3.4
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import User
from platform_api.models.enums import UserRole, UserStatus

logger = logging.getLogger(__name__)


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


def _row_to_user(row: Any) -> User:
    """Convert an asyncpg Record to a User domain object."""
    return User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        display_name=row["display_name"],
        role=UserRole(row["role"]),
        status=UserStatus(row["status"]),
        email_confirmed=row.get("email_confirmed", False),
        suspension_reason=row.get("suspension_reason"),
        deleted_at=row.get("deleted_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class UserRepository:
    """Repository for user CRUD operations using asyncpg.

    Implements the UserRepository protocol expected by AuthService (get_by_email)
    and provides additional methods for user management.

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Return the user with the given ID, or None if not found.

        Args:
            user_id: The UUID of the user to look up.

        Returns:
            The User domain object, or None if no matching user exists.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, email, password_hash, display_name, role, status,
                   email_confirmed, suspension_reason, deleted_at, created_at, updated_at
            FROM users
            WHERE id = $1
            """,
            user_id,
        )
        if row is None:
            return None
        return _row_to_user(row)

    async def get_by_email(self, email: str) -> User | None:
        """Return the user with the given email, or None if not found.

        Args:
            email: The email address to look up (case-insensitive).

        Returns:
            The User domain object, or None if no matching user exists.
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, email, password_hash, display_name, role, status,
                   email_confirmed, suspension_reason, deleted_at, created_at, updated_at
            FROM users
            WHERE LOWER(email) = LOWER($1)
            """,
            email,
        )
        if row is None:
            return None
        return _row_to_user(row)

    async def get_status(self, user_id: str) -> str | None:
        """Return the account status for the given user ID.

        Used by auth middleware for suspension checks.

        Args:
            user_id: The string UUID of the user.

        Returns:
            The status string ('active', 'suspended', 'deleted'), or None
            if the user does not exist.
        """
        result = await self._pool.fetchval(
            "SELECT status FROM users WHERE id = $1",
            UUID(user_id),
        )
        return result

    async def create(self, user: User) -> User:
        """Insert a new user and initialize their credit wallet.

        Creates a row in both the ``users`` table and ``credit_wallets`` table
        (with balance=0).

        Args:
            user: The User domain object to persist.

        Returns:
            The persisted User with server-assigned timestamps.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO users (id, email, password_hash, display_name, role, status,
                                       email_confirmed, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, false, NOW(), NOW())
                    RETURNING id, email, password_hash, display_name, role, status,
                              email_confirmed, suspension_reason, deleted_at, created_at, updated_at
                    """,
                    user.id,
                    user.email,
                    user.password_hash,
                    user.display_name,
                    user.role.value,
                    user.status.value,
                )
                # Initialize credit wallet with zero balance
                await conn.execute(
                    """
                    INSERT INTO credit_wallets (user_id, balance, updated_at)
                    VALUES ($1, 0, NOW())
                    """,
                    user.id,
                )
        return _row_to_user(row)

    async def update(self, user_id: UUID, **fields: Any) -> User | None:
        """Update specified fields on a user record.

        Only the provided keyword arguments are updated. The ``updated_at``
        timestamp is always refreshed.

        Args:
            user_id: The UUID of the user to update.
            **fields: Column names and their new values.

        Returns:
            The updated User domain object, or None if the user was not found.
        """
        if not fields:
            return await self.get_by_id(user_id)

        # Build SET clause dynamically
        set_parts: list[str] = []
        values: list[Any] = []
        param_idx = 1

        for col, val in fields.items():
            set_parts.append(f"{col} = ${param_idx}")
            values.append(val)
            param_idx += 1

        set_parts.append(f"updated_at = ${param_idx}")
        values.append(datetime.now(timezone.utc))
        param_idx += 1

        values.append(user_id)

        query = f"""
            UPDATE users
            SET {', '.join(set_parts)}
            WHERE id = ${param_idx}
            RETURNING id, email, password_hash, display_name, role, status,
                      email_confirmed, suspension_reason, deleted_at, created_at, updated_at
        """

        row = await self._pool.fetchrow(query, *values)
        if row is None:
            return None
        return _row_to_user(row)

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
        plan_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[User], int]:
        """Return a paginated list of users with optional filters.

        Args:
            page: The 1-based page number.
            page_size: Number of records per page.
            status: Filter by user status ('active', 'suspended', 'deleted').
            plan_type: Filter by plan type (joins through licenses → plans).
            date_from: Filter users registered on or after this datetime.
            date_to: Filter users registered on or before this datetime.

        Returns:
            A tuple of (list of User objects, total count matching filters).
        """
        where_clauses: list[str] = []
        params: list[Any] = []
        param_idx = 1

        if status is not None:
            where_clauses.append(f"u.status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if date_from is not None:
            where_clauses.append(f"u.created_at >= ${param_idx}")
            params.append(date_from)
            param_idx += 1

        if date_to is not None:
            where_clauses.append(f"u.created_at <= ${param_idx}")
            params.append(date_to)
            param_idx += 1

        # Plan type requires a join through licenses → plans
        join_clause = ""
        if plan_type is not None:
            join_clause = """
                INNER JOIN licenses l ON l.user_id = u.id AND l.status = 'active'
                INNER JOIN plans p ON p.id = l.plan_id
            """
            where_clauses.append(f"p.name = ${param_idx}")
            params.append(plan_type)
            param_idx += 1

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # Count query
        count_query = f"""
            SELECT COUNT(DISTINCT u.id)
            FROM users u
            {join_clause}
            {where_sql}
        """
        total = await self._pool.fetchval(count_query, *params)

        # Data query with pagination
        offset = (page - 1) * page_size
        params.append(page_size)
        limit_param = param_idx
        param_idx += 1
        params.append(offset)
        offset_param = param_idx

        data_query = f"""
            SELECT DISTINCT u.id, u.email, u.password_hash, u.display_name,
                   u.role, u.status, u.suspension_reason, u.deleted_at,
                   u.created_at, u.updated_at
            FROM users u
            {join_clause}
            {where_sql}
            ORDER BY u.created_at DESC
            LIMIT ${limit_param} OFFSET ${offset_param}
        """

        rows = await self._pool.fetch(data_query, *params)
        users = [_row_to_user(row) for row in rows]
        return users, total or 0

    async def soft_delete(self, user_id: UUID) -> bool:
        """Soft-delete a user by setting deleted_at and status to 'deleted'.

        Args:
            user_id: The UUID of the user to soft-delete.

        Returns:
            True if the user was found and updated, False otherwise.
        """
        result = await self._pool.execute(
            """
            UPDATE users
            SET status = 'deleted',
                deleted_at = NOW(),
                updated_at = NOW()
            WHERE id = $1 AND status != 'deleted'
            """,
            user_id,
        )
        # asyncpg returns "UPDATE N" where N is the affected row count
        return result == "UPDATE 1"

    async def suspend(self, user_id: UUID, reason: str) -> bool:
        """Suspend a user account with a reason.

        Sets the status to 'suspended' and records the suspension reason.

        Args:
            user_id: The UUID of the user to suspend.
            reason: The reason for suspension.

        Returns:
            True if the user was found and suspended, False otherwise.
        """
        result = await self._pool.execute(
            """
            UPDATE users
            SET status = 'suspended',
                suspension_reason = $2,
                updated_at = NOW()
            WHERE id = $1 AND status = 'active'
            """,
            user_id,
            reason,
        )
        return result == "UPDATE 1"

    async def reactivate(self, user_id: UUID) -> bool:
        """Reactivate a suspended user account.

        Restores the status to 'active' and clears the suspension reason.

        Args:
            user_id: The UUID of the user to reactivate.

        Returns:
            True if the user was found and reactivated, False otherwise.
        """
        result = await self._pool.execute(
            """
            UPDATE users
            SET status = 'active',
                suspension_reason = NULL,
                updated_at = NOW()
            WHERE id = $1 AND status = 'suspended'
            """,
            user_id,
        )
        return result == "UPDATE 1"
