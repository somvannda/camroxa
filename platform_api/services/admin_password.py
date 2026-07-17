"""Admin password verification helper for reset/restore operations.

Verifies the admin's password against the stored bcrypt hash with integrated
rate limiting via PasswordAttemptLimiter.

Implements Requirements:
    1.1: Verify password against stored bcrypt hash before initiating reset.
    1.2: Reject with 401 if password does not match.
    1.3: Initiate operation on successful verification.
    1.6: Rate limit after 5 consecutive failures (15 min lockout).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

import bcrypt
from redis.asyncio import Redis

from platform_api.exceptions import AuthenticationError
from platform_api.services.password_limiter import PasswordAttemptLimiter

logger = logging.getLogger(__name__)


class _Pool(Protocol):
    """Minimal asyncpg pool protocol for fetching a single row."""

    async def fetchrow(self, query: str, *args: Any) -> Any: ...


async def verify_admin_password(
    admin_id: str,
    password: str,
    pool: _Pool,
    redis: Redis,  # type: ignore[type-arg]
) -> None:
    """Verify admin password with rate limiting.

    Flow:
        1. Check if the admin is already locked out (raises RateLimitExceededError).
        2. Increment the failure counter (optimistic — will be reset on success).
        3. Fetch the admin's password hash from the database.
        4. Verify the provided password against the bcrypt hash.
        5. On success: reset the failure counter and return.
        6. On failure: raise AuthenticationError (counter was already incremented).

    Args:
        admin_id: UUID string of the authenticated admin user.
        password: Plaintext password provided by the admin for re-verification.
        pool: An asyncpg-compatible connection pool.
        redis: An async Redis client instance.

    Raises:
        AuthenticationError: Wrong password (HTTP 401).
        RateLimitExceededError: Too many failed attempts (HTTP 429).
    """
    limiter = PasswordAttemptLimiter(redis)

    # Step 1+2: Check lockout and increment failure counter
    await limiter.check_and_increment(admin_id)

    # Step 3: Fetch admin's password hash from the database
    row = await pool.fetchrow(
        "SELECT password_hash FROM users WHERE id = $1",
        UUID(admin_id),
    )

    if row is None:
        # Admin not found — should not happen for authenticated requests,
        # but raise AuthenticationError to avoid leaking info.
        logger.warning("verify_admin_password: admin_id=%s not found in DB", admin_id)
        raise AuthenticationError("Invalid credentials.")

    stored_hash: str = row["password_hash"]

    # Step 4: Verify bcrypt hash
    password_bytes = password.encode("utf-8")
    hashed_bytes = stored_hash.encode("utf-8")
    is_valid = bcrypt.checkpw(password_bytes, hashed_bytes)

    if is_valid:
        # Step 5: Success — reset the failure counter
        await limiter.reset(admin_id)
        return

    # Step 6: Wrong password — counter was already incremented in step 2
    raise AuthenticationError("Invalid credentials.")
