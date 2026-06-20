"""Refresh token repository backed by the refresh_tokens table."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


class RefreshTokenRepository:
    """Manages refresh token persistence in the refresh_tokens table.

    Implements the RefreshTokenRepository protocol expected by AuthService.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def store(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        """Store a new refresh token hash for the user."""
        await self._pool.execute(
            """
            INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            uuid4(),
            user_id,
            token_hash,
            expires_at,
        )

    async def get_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        """Return the refresh token record matching the hash, or None."""
        row = await self._pool.fetchrow(
            """
            SELECT user_id, token_hash, expires_at, revoked_at
            FROM refresh_tokens
            WHERE token_hash = $1
            """,
            token_hash,
        )
        if row is None:
            return None
        return dict(row)

    async def revoke(self, token_hash: str) -> None:
        """Mark a single refresh token as revoked."""
        await self._pool.execute(
            """
            UPDATE refresh_tokens SET revoked_at = NOW()
            WHERE token_hash = $1 AND revoked_at IS NULL
            """,
            token_hash,
        )

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """Mark ALL refresh tokens for a user as revoked."""
        await self._pool.execute(
            """
            UPDATE refresh_tokens SET revoked_at = NOW()
            WHERE user_id = $1 AND revoked_at IS NULL
            """,
            user_id,
        )
