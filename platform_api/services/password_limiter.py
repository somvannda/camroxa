"""Password attempt rate limiter for admin reset/restore operations.

Tracks consecutive failed password verification attempts per admin using Redis
and locks them out for a configurable duration once the threshold is reached.

Implements Requirement 1.6: If the admin has failed password verification 5
consecutive times for reset confirmation, reject further attempts for 15 minutes.
"""

from __future__ import annotations

from redis.asyncio import Redis

from platform_api.exceptions import RateLimitExceededError


class PasswordAttemptLimiter:
    """Tracks failed password attempts per admin in Redis.

    Uses a simple counter with TTL approach: each failed attempt increments a
    Redis key. When the counter reaches MAX_ATTEMPTS, subsequent calls raise
    RateLimitExceededError until the key expires after LOCKOUT_SECONDS.

    Redis keys used:
        - ``reset_pwd_attempts:{admin_id}`` — integer counter of consecutive
          failed password verification attempts.

    Args:
        redis: An async Redis client instance.
    """

    REDIS_KEY_PREFIX: str = "reset_pwd_attempts:"
    MAX_ATTEMPTS: int = 5
    LOCKOUT_SECONDS: int = 900  # 15 minutes

    def __init__(self, redis: Redis) -> None:  # type: ignore[type-arg]
        self._redis = redis

    def _key(self, admin_id: str) -> str:
        """Build the Redis key for a given admin."""
        return f"{self.REDIS_KEY_PREFIX}{admin_id}"

    async def check_and_increment(self, admin_id: str) -> None:
        """Check if admin is locked out; if not, increment failure count.

        If the current attempt count is already at or above MAX_ATTEMPTS, the
        admin is considered locked out and a RateLimitExceededError is raised
        immediately without incrementing.

        Otherwise, the counter is incremented and the TTL is set (or refreshed)
        to LOCKOUT_SECONDS so that the lockout window resets on each new failure.

        Args:
            admin_id: The unique identifier of the admin user.

        Raises:
            RateLimitExceededError: If attempts >= MAX_ATTEMPTS within the
                lockout window.
        """
        key = self._key(admin_id)

        # Check current count before incrementing
        current = await self._redis.get(key)
        if current is not None and int(current) >= self.MAX_ATTEMPTS:
            raise RateLimitExceededError()

        # Increment and set/refresh TTL
        await self._redis.incr(key)
        await self._redis.expire(key, self.LOCKOUT_SECONDS)

    async def reset(self, admin_id: str) -> None:
        """Clear failed attempts on successful verification.

        Should be called after a successful password verification to ensure
        that previous failures don't accumulate across separate sessions.

        Args:
            admin_id: The unique identifier of the admin user.
        """
        await self._redis.delete(self._key(admin_id))
