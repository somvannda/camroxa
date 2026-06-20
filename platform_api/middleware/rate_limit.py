"""Rate limiting middleware using Redis sliding window algorithm.

Implements per-user, per-endpoint-type rate limiting using Redis sorted sets.
Rate limit configuration is cached in Redis with a 5-second TTL to allow
Admin live-updates to propagate quickly without database queries on every request.

Algorithm:
  1. Remove expired entries from the sorted set (score < now - window)
  2. Add the current timestamp to the sorted set
  3. Count entries in the set
  4. If count > limit, reject with 429 + Retry-After header

Requirements: 19.1, 19.2, 19.3, 19.4
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default rate limit configuration
# ---------------------------------------------------------------------------

DEFAULT_RATE_LIMIT = 60
DEFAULT_RATE_WINDOW_SECONDS = 60

SUNO_RATE_LIMIT = 20
SUNO_RATE_WINDOW_SECONDS = 10

# Redis key prefix for cached rate limit config
CONFIG_CACHE_PREFIX = "ratelimit:config:"
CONFIG_CACHE_TTL = 5  # seconds — Admin updates apply within this window


# ---------------------------------------------------------------------------
# Rate limit configuration dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Rate limit configuration for an endpoint type.

    Attributes:
        max_requests: Maximum number of requests allowed in the window.
        window_seconds: Duration of the sliding window in seconds.
    """

    max_requests: int
    window_seconds: int


# ---------------------------------------------------------------------------
# Redis Protocol (minimal interface needed for rate limiting)
# ---------------------------------------------------------------------------


class RedisPipeline(Protocol):
    """Protocol for a Redis pipeline supporting the rate limit operations."""

    def zremrangebyscore(self, name: str, min: float, max: float) -> None: ...
    def zadd(self, name: str, mapping: dict[str, float]) -> None: ...
    def zcard(self, name: str) -> None: ...
    def expire(self, name: str, time: int) -> None: ...
    async def execute(self) -> list: ...


class RedisClient(Protocol):
    """Protocol for async Redis client needed by the rate limiter."""

    def pipeline(self) -> RedisPipeline: ...
    async def get(self, name: str) -> str | bytes | None: ...
    async def setex(self, name: str, time: int, value: str) -> None: ...


# ---------------------------------------------------------------------------
# Repository Protocol for fetching rate limit config from the database
# ---------------------------------------------------------------------------


class RateLimitConfigRepository(Protocol):
    """Protocol for fetching rate limit configuration from the database."""

    async def get_config(self, endpoint_type: str) -> RateLimitConfig | None:
        """Return the rate limit config for the given endpoint type, or None if not configured."""
        ...


# ---------------------------------------------------------------------------
# Core rate limit check function (sliding window with Redis sorted sets)
# ---------------------------------------------------------------------------


_request_counter: int = 0


async def check_rate_limit(
    redis: RedisClient,
    user_id: str,
    endpoint_type: str,
    limit: int,
    window_sec: int,
) -> tuple[bool, int]:
    """Check if a request is within the rate limit using a sliding window.

    Uses Redis sorted sets where each member is a unique request identifier
    and the score is the request timestamp.

    Args:
        redis: Async Redis client.
        user_id: The authenticated user's ID.
        endpoint_type: The endpoint type being rate-limited (e.g., "suno", "default").
        limit: Maximum requests allowed in the window.
        window_sec: Sliding window duration in seconds.

    Returns:
        A tuple of (allowed, retry_after_seconds).
        If allowed is True, retry_after is 0.
        If allowed is False, retry_after is the number of seconds to wait.
    """
    global _request_counter
    _request_counter += 1

    key = f"ratelimit:{user_id}:{endpoint_type}"
    now = time.time()

    # Use a unique member ID (timestamp + counter) to avoid overwrites
    # when multiple requests arrive within the same timestamp
    member = f"{now}:{_request_counter}"

    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_sec)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window_sec)
    results = await pipe.execute()

    count = results[2]

    if count <= limit:
        return True, 0

    # The request exceeds the limit. Calculate retry-after as the full window
    # duration (conservative estimate of when enough old requests will expire).
    retry_after = math.ceil(window_sec)

    return False, retry_after


# ---------------------------------------------------------------------------
# Rate limit config resolution (with Redis caching for fast Admin updates)
# ---------------------------------------------------------------------------


async def get_rate_limit_config(
    redis: RedisClient,
    endpoint_type: str,
    config_repo: RateLimitConfigRepository | None,
) -> RateLimitConfig:
    """Resolve the rate limit config for an endpoint type.

    Checks Redis cache first (5s TTL), falls back to database, then defaults.

    Args:
        redis: Async Redis client.
        endpoint_type: The endpoint type to look up.
        config_repo: Optional repository for database lookups.

    Returns:
        The resolved RateLimitConfig.
    """
    # Check Redis cache first
    cache_key = f"{CONFIG_CACHE_PREFIX}{endpoint_type}"
    cached = await redis.get(cache_key)

    if cached is not None:
        try:
            data = json.loads(cached if isinstance(cached, str) else cached.decode())
            return RateLimitConfig(
                max_requests=data["max_requests"],
                window_seconds=data["window_seconds"],
            )
        except (json.JSONDecodeError, KeyError):
            pass  # Fall through to DB/defaults

    # Try database lookup
    if config_repo is not None:
        db_config = await config_repo.get_config(endpoint_type)
        if db_config is not None:
            # Cache in Redis for 5 seconds
            cache_value = json.dumps({
                "max_requests": db_config.max_requests,
                "window_seconds": db_config.window_seconds,
            })
            await redis.setex(cache_key, CONFIG_CACHE_TTL, cache_value)
            return db_config

    # Fall back to hardcoded defaults
    if endpoint_type == "suno":
        config = RateLimitConfig(
            max_requests=SUNO_RATE_LIMIT,
            window_seconds=SUNO_RATE_WINDOW_SECONDS,
        )
    else:
        config = RateLimitConfig(
            max_requests=DEFAULT_RATE_LIMIT,
            window_seconds=DEFAULT_RATE_WINDOW_SECONDS,
        )

    # Cache the default too so we don't hit DB every time
    cache_value = json.dumps({
        "max_requests": config.max_requests,
        "window_seconds": config.window_seconds,
    })
    await redis.setex(cache_key, CONFIG_CACHE_TTL, cache_value)

    return config


# ---------------------------------------------------------------------------
# Endpoint type resolution from request path
# ---------------------------------------------------------------------------


def resolve_endpoint_type(path: str) -> str:
    """Determine the endpoint type from the request path.

    Maps request paths to rate limit endpoint types:
      - /generation/suno or /api/v1/generation/suno → "suno"
      - /generation/image → "image"
      - /generation/draft → "llm"
      - Everything else → "default"

    Args:
        path: The request URL path.

    Returns:
        The endpoint type string.
    """
    # Normalize path: strip leading slashes and API prefix
    normalized = path.lower().strip("/")

    # Remove api/v1 prefix if present
    if normalized.startswith("api/v1/"):
        normalized = normalized[7:]

    if normalized.startswith("generation/suno"):
        return "suno"
    elif normalized.startswith("generation/image"):
        return "image"
    elif normalized.startswith("generation/draft"):
        return "llm"
    else:
        return "default"


# ---------------------------------------------------------------------------
# RateLimiter class — combines all logic into a reusable dependency
# ---------------------------------------------------------------------------


class RateLimiter:
    """Rate limiter that can be used as a FastAPI dependency.

    Checks per-user, per-endpoint-type rate limits using Redis sorted sets.
    Configuration is resolved from Redis cache → database → hardcoded defaults.

    Usage:
        rate_limiter = RateLimiter(redis=redis_client, config_repo=repo)

        @router.post("/generation/suno")
        async def submit_suno(
            request: Request,
            ctx: AuthContext = Depends(get_current_user),
        ):
            await rate_limiter.check(request, ctx.user_id)
            ...
    """

    def __init__(
        self,
        redis: RedisClient,
        config_repo: RateLimitConfigRepository | None = None,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            redis: Async Redis client for sorted set operations.
            config_repo: Optional repository for DB-backed rate limit config.
        """
        self._redis = redis
        self._config_repo = config_repo

    async def check(self, request: Request, user_id: str) -> None:
        """Check rate limit for the current request and user.

        Raises HTTPException 429 if the rate limit is exceeded.
        Does NOT deduct credits for rejected requests.

        Args:
            request: The current FastAPI Request object.
            user_id: The authenticated user's ID.

        Raises:
            HTTPException: 429 Too Many Requests with Retry-After header.
        """
        endpoint_type = resolve_endpoint_type(request.url.path)

        config = await get_rate_limit_config(
            self._redis,
            endpoint_type,
            self._config_repo,
        )

        allowed, retry_after = await check_rate_limit(
            self._redis,
            user_id,
            endpoint_type,
            config.max_requests,
            config.window_seconds,
        )

        if not allowed:
            logger.warning(
                "Rate limit exceeded for user=%s endpoint_type=%s limit=%d/%ds",
                user_id,
                endpoint_type,
                config.max_requests,
                config.window_seconds,
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error_code": "RATE_LIMITED",
                    "message": "Rate limit exceeded. Please retry later.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

    async def check_for_endpoint(
        self, user_id: str, endpoint_type: str
    ) -> None:
        """Check rate limit for a specific endpoint type (no Request object needed).

        Useful when the endpoint type is already known.

        Args:
            user_id: The authenticated user's ID.
            endpoint_type: The endpoint type to check.

        Raises:
            HTTPException: 429 Too Many Requests with Retry-After header.
        """
        config = await get_rate_limit_config(
            self._redis,
            endpoint_type,
            self._config_repo,
        )

        allowed, retry_after = await check_rate_limit(
            self._redis,
            user_id,
            endpoint_type,
            config.max_requests,
            config.window_seconds,
        )

        if not allowed:
            logger.warning(
                "Rate limit exceeded for user=%s endpoint_type=%s limit=%d/%ds",
                user_id,
                endpoint_type,
                config.max_requests,
                config.window_seconds,
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error_code": "RATE_LIMITED",
                    "message": "Rate limit exceeded. Please retry later.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )


# ---------------------------------------------------------------------------
# Module-level singleton (configured at startup like auth middleware)
# ---------------------------------------------------------------------------

_rate_limiter: RateLimiter | None = None


def configure_rate_limiter(
    *,
    redis: RedisClient,
    config_repo: RateLimitConfigRepository | None = None,
) -> RateLimiter:
    """Configure and return the rate limiter singleton.

    Call this once during application startup.

    Args:
        redis: Async Redis client.
        config_repo: Optional repository for database-backed config.

    Returns:
        The configured RateLimiter instance.
    """
    global _rate_limiter
    _rate_limiter = RateLimiter(redis=redis, config_repo=config_repo)
    return _rate_limiter


def get_rate_limiter() -> RateLimiter:
    """Return the configured rate limiter or raise if not configured."""
    if _rate_limiter is None:
        raise RuntimeError(
            "Rate limiter not configured. Call configure_rate_limiter() at startup."
        )
    return _rate_limiter
