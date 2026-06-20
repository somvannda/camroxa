"""Tests for the rate limiting middleware (platform_api.middleware.rate_limit).

Uses a fake Redis implementation to test the sliding window algorithm,
endpoint type resolution, config caching, and 429 rejection behavior.

Requirements: 19.1, 19.2, 19.3, 19.4
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from platform_api.middleware.rate_limit import (
    CONFIG_CACHE_PREFIX,
    CONFIG_CACHE_TTL,
    DEFAULT_RATE_LIMIT,
    DEFAULT_RATE_WINDOW_SECONDS,
    SUNO_RATE_LIMIT,
    SUNO_RATE_WINDOW_SECONDS,
    RateLimitConfig,
    RateLimiter,
    check_rate_limit,
    get_rate_limit_config,
    resolve_endpoint_type,
)


# ---------------------------------------------------------------------------
# Fake Redis implementation for testing
# ---------------------------------------------------------------------------


class FakeRedisPipeline:
    """Fake Redis pipeline that records and executes sorted set operations."""

    def __init__(self, store: dict[str, dict[str, float]], ttls: dict[str, int]) -> None:
        self._store = store
        self._ttls = ttls
        self._ops: list[tuple[str, ...]] = []

    def zremrangebyscore(self, name: str, min: float, max: float) -> None:
        self._ops.append(("zremrangebyscore", name, str(min), str(max)))

    def zadd(self, name: str, mapping: dict[str, float]) -> None:
        self._ops.append(("zadd", name, json.dumps(mapping)))

    def zcard(self, name: str) -> None:
        self._ops.append(("zcard", name))

    def expire(self, name: str, time: int) -> None:
        self._ops.append(("expire", name, str(time)))

    async def execute(self) -> list:
        """Execute all queued operations and return results."""
        results = []
        for op in self._ops:
            if op[0] == "zremrangebyscore":
                name, min_score, max_score = op[1], float(op[2]), float(op[3])
                if name in self._store:
                    to_remove = [
                        k for k, v in self._store[name].items()
                        if v >= min_score and v <= max_score
                    ]
                    for k in to_remove:
                        del self._store[name][k]
                    results.append(len(to_remove))
                else:
                    results.append(0)

            elif op[0] == "zadd":
                name = op[1]
                mapping = json.loads(op[2])
                if name not in self._store:
                    self._store[name] = {}
                added = 0
                for k, v in mapping.items():
                    if k not in self._store[name]:
                        added += 1
                    self._store[name][k] = v
                results.append(added)

            elif op[0] == "zcard":
                name = op[1]
                results.append(len(self._store.get(name, {})))

            elif op[0] == "expire":
                name, ttl = op[1], int(op[2])
                self._ttls[name] = ttl
                results.append(True)

        return results


class FakeRedis:
    """Fake async Redis client supporting sorted sets, get, and setex."""

    def __init__(self) -> None:
        self._sorted_sets: dict[str, dict[str, float]] = {}
        self._kv_store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    def pipeline(self) -> FakeRedisPipeline:
        return FakeRedisPipeline(self._sorted_sets, self._ttls)

    async def get(self, name: str) -> str | None:
        return self._kv_store.get(name)

    async def setex(self, name: str, time: int, value: str) -> None:
        self._kv_store[name] = value
        self._ttls[name] = time


# ---------------------------------------------------------------------------
# Fake config repository
# ---------------------------------------------------------------------------


class FakeConfigRepo:
    """Fake rate limit config repository for testing."""

    def __init__(self, configs: dict[str, RateLimitConfig] | None = None) -> None:
        self._configs = configs or {}

    async def get_config(self, endpoint_type: str) -> RateLimitConfig | None:
        return self._configs.get(endpoint_type)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def rate_limiter(fake_redis: FakeRedis) -> RateLimiter:
    return RateLimiter(redis=fake_redis)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests for resolve_endpoint_type
# ---------------------------------------------------------------------------


class TestResolveEndpointType:
    """Tests for endpoint type resolution from request paths."""

    def test_suno_path(self) -> None:
        assert resolve_endpoint_type("/api/v1/generation/suno") == "suno"

    def test_suno_path_with_task_id(self) -> None:
        assert resolve_endpoint_type("/api/v1/generation/suno/task123") == "suno"

    def test_suno_path_without_prefix(self) -> None:
        assert resolve_endpoint_type("/generation/suno") == "suno"

    def test_image_path(self) -> None:
        assert resolve_endpoint_type("/api/v1/generation/image") == "image"

    def test_draft_path(self) -> None:
        assert resolve_endpoint_type("/api/v1/generation/draft") == "llm"

    def test_other_path_defaults(self) -> None:
        assert resolve_endpoint_type("/api/v1/users/me") == "default"

    def test_root_path(self) -> None:
        assert resolve_endpoint_type("/") == "default"

    def test_empty_path(self) -> None:
        assert resolve_endpoint_type("") == "default"

    def test_case_insensitive(self) -> None:
        assert resolve_endpoint_type("/API/V1/Generation/Suno") == "suno"


# ---------------------------------------------------------------------------
# Tests for check_rate_limit (core sliding window algorithm)
# ---------------------------------------------------------------------------


class TestCheckRateLimit:
    """Tests for the sliding window rate limit check."""

    async def test_allows_first_request(self, fake_redis: FakeRedis) -> None:
        """First request should always be allowed."""
        allowed, retry_after = await check_rate_limit(
            fake_redis, "user1", "default", 60, 60  # type: ignore[arg-type]
        )
        assert allowed is True
        assert retry_after == 0

    async def test_allows_up_to_limit(self, fake_redis: FakeRedis) -> None:
        """Requests up to the limit should all be allowed."""
        limit = 5
        for i in range(limit):
            allowed, _ = await check_rate_limit(
                fake_redis, "user1", "default", limit, 60  # type: ignore[arg-type]
            )
            assert allowed is True, f"Request {i+1} should be allowed"

    async def test_rejects_over_limit(self, fake_redis: FakeRedis) -> None:
        """The (limit+1)th request should be rejected."""
        limit = 3
        for _ in range(limit):
            await check_rate_limit(
                fake_redis, "user1", "default", limit, 60  # type: ignore[arg-type]
            )

        allowed, retry_after = await check_rate_limit(
            fake_redis, "user1", "default", limit, 60  # type: ignore[arg-type]
        )
        assert allowed is False
        assert retry_after > 0

    async def test_retry_after_is_positive_integer(self, fake_redis: FakeRedis) -> None:
        """Retry-After should be a positive integer (seconds)."""
        limit = 1
        await check_rate_limit(
            fake_redis, "user1", "default", limit, 30  # type: ignore[arg-type]
        )
        _, retry_after = await check_rate_limit(
            fake_redis, "user1", "default", limit, 30  # type: ignore[arg-type]
        )
        assert retry_after > 0
        assert isinstance(retry_after, int)

    async def test_separate_users_tracked_independently(self, fake_redis: FakeRedis) -> None:
        """Rate limits are per-user: one user hitting the limit doesn't affect another."""
        limit = 2
        # User 1 hits the limit
        for _ in range(limit):
            await check_rate_limit(
                fake_redis, "user1", "default", limit, 60  # type: ignore[arg-type]
            )
        allowed_user1, _ = await check_rate_limit(
            fake_redis, "user1", "default", limit, 60  # type: ignore[arg-type]
        )
        assert allowed_user1 is False

        # User 2 should still be allowed
        allowed_user2, _ = await check_rate_limit(
            fake_redis, "user2", "default", limit, 60  # type: ignore[arg-type]
        )
        assert allowed_user2 is True

    async def test_separate_endpoint_types_tracked_independently(
        self, fake_redis: FakeRedis
    ) -> None:
        """Rate limits are per-endpoint-type: hitting "suno" limit doesn't affect "image"."""
        limit = 2
        for _ in range(limit):
            await check_rate_limit(
                fake_redis, "user1", "suno", limit, 60  # type: ignore[arg-type]
            )
        allowed_suno, _ = await check_rate_limit(
            fake_redis, "user1", "suno", limit, 60  # type: ignore[arg-type]
        )
        assert allowed_suno is False

        allowed_image, _ = await check_rate_limit(
            fake_redis, "user1", "image", limit, 60  # type: ignore[arg-type]
        )
        assert allowed_image is True

    async def test_suno_specific_limit(self, fake_redis: FakeRedis) -> None:
        """Suno endpoint respects its specific 20 requests per 10s window."""
        limit = SUNO_RATE_LIMIT  # 20
        window = SUNO_RATE_WINDOW_SECONDS  # 10

        for _ in range(limit):
            allowed, _ = await check_rate_limit(
                fake_redis, "user1", "suno", limit, window  # type: ignore[arg-type]
            )
            assert allowed is True

        # 21st request should be rejected
        allowed, retry_after = await check_rate_limit(
            fake_redis, "user1", "suno", limit, window  # type: ignore[arg-type]
        )
        assert allowed is False
        assert retry_after == window


# ---------------------------------------------------------------------------
# Tests for get_rate_limit_config
# ---------------------------------------------------------------------------


class TestGetRateLimitConfig:
    """Tests for rate limit config resolution with caching."""

    async def test_returns_default_for_unknown_type(self, fake_redis: FakeRedis) -> None:
        """Unknown endpoint types get the default config."""
        config = await get_rate_limit_config(
            fake_redis, "unknown", None  # type: ignore[arg-type]
        )
        assert config.max_requests == DEFAULT_RATE_LIMIT
        assert config.window_seconds == DEFAULT_RATE_WINDOW_SECONDS

    async def test_returns_suno_defaults(self, fake_redis: FakeRedis) -> None:
        """Suno endpoint type gets its specific defaults."""
        config = await get_rate_limit_config(
            fake_redis, "suno", None  # type: ignore[arg-type]
        )
        assert config.max_requests == SUNO_RATE_LIMIT
        assert config.window_seconds == SUNO_RATE_WINDOW_SECONDS

    async def test_uses_cached_config(self, fake_redis: FakeRedis) -> None:
        """Config cached in Redis is used without hitting the DB."""
        cache_key = f"{CONFIG_CACHE_PREFIX}custom"
        fake_redis._kv_store[cache_key] = json.dumps({
            "max_requests": 100,
            "window_seconds": 120,
        })

        config = await get_rate_limit_config(
            fake_redis, "custom", None  # type: ignore[arg-type]
        )
        assert config.max_requests == 100
        assert config.window_seconds == 120

    async def test_uses_db_config(self, fake_redis: FakeRedis) -> None:
        """Database config is used when cache is empty."""
        repo = FakeConfigRepo(configs={
            "custom": RateLimitConfig(max_requests=50, window_seconds=30),
        })

        config = await get_rate_limit_config(
            fake_redis, "custom", repo  # type: ignore[arg-type]
        )
        assert config.max_requests == 50
        assert config.window_seconds == 30

    async def test_db_config_is_cached(self, fake_redis: FakeRedis) -> None:
        """After fetching from DB, config is cached in Redis."""
        repo = FakeConfigRepo(configs={
            "custom": RateLimitConfig(max_requests=50, window_seconds=30),
        })

        await get_rate_limit_config(
            fake_redis, "custom", repo  # type: ignore[arg-type]
        )

        cache_key = f"{CONFIG_CACHE_PREFIX}custom"
        assert cache_key in fake_redis._kv_store
        assert fake_redis._ttls[cache_key] == CONFIG_CACHE_TTL

        cached_data = json.loads(fake_redis._kv_store[cache_key])
        assert cached_data["max_requests"] == 50
        assert cached_data["window_seconds"] == 30

    async def test_cache_takes_priority_over_db(self, fake_redis: FakeRedis) -> None:
        """Cached value is returned even if DB has different config."""
        cache_key = f"{CONFIG_CACHE_PREFIX}custom"
        fake_redis._kv_store[cache_key] = json.dumps({
            "max_requests": 100,
            "window_seconds": 120,
        })

        repo = FakeConfigRepo(configs={
            "custom": RateLimitConfig(max_requests=50, window_seconds=30),
        })

        config = await get_rate_limit_config(
            fake_redis, "custom", repo  # type: ignore[arg-type]
        )
        # Should use cached value, not DB
        assert config.max_requests == 100
        assert config.window_seconds == 120

    async def test_admin_update_propagation(self, fake_redis: FakeRedis) -> None:
        """Simulates Admin updating config: new config is picked up after cache expires.

        The 5-second TTL ensures Admin updates propagate within 5 seconds.
        """
        # Initial config from DB
        repo = FakeConfigRepo(configs={
            "suno": RateLimitConfig(max_requests=10, window_seconds=5),
        })

        config = await get_rate_limit_config(
            fake_redis, "suno", repo  # type: ignore[arg-type]
        )
        assert config.max_requests == 10

        # Simulate Admin updating DB config
        repo._configs["suno"] = RateLimitConfig(max_requests=30, window_seconds=15)

        # Cache is still active — returns old value
        config = await get_rate_limit_config(
            fake_redis, "suno", repo  # type: ignore[arg-type]
        )
        assert config.max_requests == 10  # Still cached

        # Simulate cache expiry by removing from store
        del fake_redis._kv_store[f"{CONFIG_CACHE_PREFIX}suno"]

        # Now fetches from DB again — new config
        config = await get_rate_limit_config(
            fake_redis, "suno", repo  # type: ignore[arg-type]
        )
        assert config.max_requests == 30
        assert config.window_seconds == 15


# ---------------------------------------------------------------------------
# Tests for RateLimiter class (integration with Request object)
# ---------------------------------------------------------------------------


class TestRateLimiter:
    """Tests for the RateLimiter dependency class."""

    def _make_request(self, path: str) -> MagicMock:
        """Create a mock FastAPI Request with the given path."""
        request = MagicMock()
        request.url.path = path
        return request

    async def test_allows_requests_within_limit(
        self, fake_redis: FakeRedis
    ) -> None:
        """Requests within the limit should pass without exception."""
        limiter = RateLimiter(redis=fake_redis)  # type: ignore[arg-type]
        request = self._make_request("/api/v1/generation/suno")

        # First request should pass
        await limiter.check(request, "user1")

    async def test_raises_429_when_limit_exceeded(
        self, fake_redis: FakeRedis
    ) -> None:
        """Should raise HTTPException 429 when rate limit is exceeded."""
        # Use a very low limit for testing
        repo = FakeConfigRepo(configs={
            "suno": RateLimitConfig(max_requests=2, window_seconds=60),
        })
        limiter = RateLimiter(redis=fake_redis, config_repo=repo)  # type: ignore[arg-type]
        request = self._make_request("/api/v1/generation/suno")

        # First 2 requests pass
        await limiter.check(request, "user1")
        await limiter.check(request, "user1")

        # Third request should be rejected
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check(request, "user1")

        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers
        assert int(exc_info.value.headers["Retry-After"]) > 0
        assert exc_info.value.detail["error_code"] == "RATE_LIMITED"

    async def test_no_credits_deducted_for_rejected_request(
        self, fake_redis: FakeRedis
    ) -> None:
        """Verify that rejected requests don't interact with credits.

        The rate limiter raises HTTPException BEFORE any credit logic runs,
        ensuring credits are never deducted for rate-limited requests.
        """
        repo = FakeConfigRepo(configs={
            "default": RateLimitConfig(max_requests=1, window_seconds=60),
        })
        limiter = RateLimiter(redis=fake_redis, config_repo=repo)  # type: ignore[arg-type]
        request = self._make_request("/api/v1/users/me")

        await limiter.check(request, "user1")

        # Second request is rejected — if this raises 429, credit logic never runs
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check(request, "user1")
        assert exc_info.value.status_code == 429

    async def test_check_for_endpoint_direct(self, fake_redis: FakeRedis) -> None:
        """check_for_endpoint works without a Request object."""
        repo = FakeConfigRepo(configs={
            "suno": RateLimitConfig(max_requests=1, window_seconds=60),
        })
        limiter = RateLimiter(redis=fake_redis, config_repo=repo)  # type: ignore[arg-type]

        # First passes
        await limiter.check_for_endpoint("user1", "suno")

        # Second is rejected
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_for_endpoint("user1", "suno")
        assert exc_info.value.status_code == 429

    async def test_different_paths_use_different_limits(
        self, fake_redis: FakeRedis
    ) -> None:
        """Different endpoint types use their respective configured limits."""
        repo = FakeConfigRepo(configs={
            "suno": RateLimitConfig(max_requests=2, window_seconds=10),
            "default": RateLimitConfig(max_requests=5, window_seconds=60),
        })
        limiter = RateLimiter(redis=fake_redis, config_repo=repo)  # type: ignore[arg-type]

        suno_request = self._make_request("/api/v1/generation/suno")
        other_request = self._make_request("/api/v1/users/me")

        # Exhaust suno limit
        await limiter.check(suno_request, "user1")
        await limiter.check(suno_request, "user1")
        with pytest.raises(HTTPException):
            await limiter.check(suno_request, "user1")

        # Default endpoint still has capacity
        await limiter.check(other_request, "user1")
