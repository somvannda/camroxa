"""Account lockout service for brute-force login protection.

Tracks consecutive failed login attempts per email using Redis and locks the
account for a configurable duration once the threshold is reached.

Implements Requirement 1.7: If a User fails authentication 5 consecutive times
for the same email, the Auth_Service locks the account for 15 minutes.
"""

from __future__ import annotations

from redis.asyncio import Redis

from platform_api.exceptions import AccountLockedError

# --- Constants ---
LOCKOUT_THRESHOLD: int = 5
"""Number of consecutive failed attempts before lockout triggers."""

LOCKOUT_DURATION_SEC: int = 900
"""Duration in seconds (15 minutes) that the account remains locked."""


class AccountLockout:
    """Manages account lockout state via Redis.

    Redis keys used:
        - ``auth:lockout:{email}`` — presence indicates the account is locked.
        - ``auth:failures:{email}`` — integer counter of consecutive failures.

    Args:
        redis: An async Redis client instance.
    """

    def __init__(self, redis: Redis) -> None:  # type: ignore[type-arg]
        self.redis = redis

    async def check_lockout(self, email: str) -> None:
        """Raise if the account associated with *email* is currently locked.

        Args:
            email: The email address to check.

        Raises:
            AccountLockedError: If a lockout key exists for this email.
        """
        key = f"auth:lockout:{email}"
        if await self.redis.exists(key):
            raise AccountLockedError()

    async def record_failed_attempt(self, email: str) -> None:
        """Increment the failure counter and trigger lockout at threshold.

        Each call increments the ``auth:failures:{email}`` counter. The key's
        TTL is (re)set to :data:`LOCKOUT_DURATION_SEC` on every increment so
        that the counter auto-expires if no further failures occur.

        When the counter reaches :data:`LOCKOUT_THRESHOLD`, a lockout key is
        set and the failure counter is deleted.

        Args:
            email: The email address that failed authentication.
        """
        key = f"auth:failures:{email}"
        count: int = await self.redis.incr(key)
        await self.redis.expire(key, LOCKOUT_DURATION_SEC)

        if count >= LOCKOUT_THRESHOLD:
            await self.redis.setex(
                f"auth:lockout:{email}", LOCKOUT_DURATION_SEC, "1"
            )
            await self.redis.delete(key)

    async def reset_failures(self, email: str) -> None:
        """Clear the failure counter on successful login.

        Should be called after a successful authentication to ensure that
        previous failures don't accumulate across separate login sessions.

        Args:
            email: The email address that successfully authenticated.
        """
        await self.redis.delete(f"auth:failures:{email}")
