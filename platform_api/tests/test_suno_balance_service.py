"""Tests for SunoBalanceService.

Validates external Suno balance monitoring: Redis caching, threshold checks,
graceful degradation on unreachable endpoint, and Admin WebSocket alerts.

Requirements: 15.1, 15.2, 15.3, 15.4, 15.5
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from platform_api.services.suno_balance_service import (
    SunoBalanceService,
    _REDIS_KEY,
)


# ---------------------------------------------------------------------------
# Fake Redis for unit testing
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal async Redis stub supporting get/setex."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        self._store[key] = value
        self._ttls[key] = seconds
        return True


# ---------------------------------------------------------------------------
# Fake Suno client
# ---------------------------------------------------------------------------


class FakeSunoClient:
    """Fake Suno client that returns a configurable balance or raises."""

    def __init__(
        self,
        balance: int | None = 500,
        *,
        should_raise: bool = False,
        error: Exception | None = None,
    ) -> None:
        self._balance = balance
        self._should_raise = should_raise
        self._error = error or ConnectionError("Suno unreachable")
        self.call_count = 0

    async def get_credit_balance(self) -> dict[str, Any]:
        self.call_count += 1
        if self._should_raise:
            raise self._error
        return {"credits": self._balance}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def fake_suno_client() -> FakeSunoClient:
    return FakeSunoClient(balance=500)


@pytest.fixture
def mock_notification_service() -> AsyncMock:
    svc = AsyncMock()
    svc.push = AsyncMock()
    return svc


@pytest.fixture
def mock_admin_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.get_admin_user_ids = AsyncMock(return_value=["admin-1", "admin-2"])
    return provider


@pytest.fixture
def service(
    fake_redis: FakeRedis,
    fake_suno_client: FakeSunoClient,
    mock_notification_service: AsyncMock,
    mock_admin_provider: AsyncMock,
) -> SunoBalanceService:
    return SunoBalanceService(
        redis=fake_redis,  # type: ignore[arg-type]
        suno_client=fake_suno_client,  # type: ignore[arg-type]
        notification_service=mock_notification_service,
        admin_provider=mock_admin_provider,
        reserve_threshold=100,
        cache_ttl_seconds=30,
    )


# ---------------------------------------------------------------------------
# get_balance tests
# ---------------------------------------------------------------------------


class TestGetBalance:
    """Tests for SunoBalanceService.get_balance."""

    async def test_returns_balance_from_suno_api(
        self, service: SunoBalanceService
    ) -> None:
        """Should return balance with status 'ok' when API is reachable."""
        result = await service.get_balance()
        assert result["credits"] == 500
        assert result["status"] == "ok"

    async def test_caches_balance_in_redis(
        self, service: SunoBalanceService, fake_redis: FakeRedis
    ) -> None:
        """Should cache the balance in Redis with the configured TTL."""
        await service.get_balance()

        cached_raw = fake_redis._store.get(_REDIS_KEY)
        assert cached_raw is not None

        cached = json.loads(cached_raw)
        assert cached["credits"] == 500
        assert fake_redis._ttls[_REDIS_KEY] == 30

    async def test_serves_cached_on_suno_unreachable(
        self, fake_redis: FakeRedis, mock_notification_service: AsyncMock, mock_admin_provider: AsyncMock
    ) -> None:
        """Should serve cached value when Suno API is unreachable."""
        # Pre-populate cache
        cached_data = {"credits": 200, "status": "ok", "raw": {"credits": 200}}
        fake_redis._store[_REDIS_KEY] = json.dumps(cached_data)

        unreachable_client = FakeSunoClient(should_raise=True)
        svc = SunoBalanceService(
            redis=fake_redis,  # type: ignore[arg-type]
            suno_client=unreachable_client,  # type: ignore[arg-type]
            notification_service=mock_notification_service,
            admin_provider=mock_admin_provider,
        )

        result = await svc.get_balance()
        assert result["credits"] == 200
        assert result["status"] == "cached"

    async def test_returns_unknown_when_no_cache_and_unreachable(
        self, fake_redis: FakeRedis
    ) -> None:
        """Should return unknown status when Suno unreachable and no cache."""
        unreachable_client = FakeSunoClient(should_raise=True)
        svc = SunoBalanceService(
            redis=fake_redis,  # type: ignore[arg-type]
            suno_client=unreachable_client,  # type: ignore[arg-type]
        )

        result = await svc.get_balance()
        assert result["credits"] is None
        assert result["status"] == "unknown"

    async def test_pushes_alert_when_below_threshold(
        self,
        fake_redis: FakeRedis,
        mock_notification_service: AsyncMock,
        mock_admin_provider: AsyncMock,
    ) -> None:
        """Should push low-balance alert to Admins when below threshold."""
        low_balance_client = FakeSunoClient(balance=50)
        svc = SunoBalanceService(
            redis=fake_redis,  # type: ignore[arg-type]
            suno_client=low_balance_client,  # type: ignore[arg-type]
            notification_service=mock_notification_service,
            admin_provider=mock_admin_provider,
            reserve_threshold=100,
        )

        await svc.get_balance()

        # Should push to both admins
        assert mock_notification_service.push.call_count == 2
        calls = mock_notification_service.push.call_args_list

        for call in calls:
            assert call[0][1] == "admin:low_balance_alert"
            assert call[0][2]["current_balance"] == 50
            assert call[0][2]["threshold"] == 100

    async def test_no_alert_when_above_threshold(
        self,
        service: SunoBalanceService,
        mock_notification_service: AsyncMock,
    ) -> None:
        """Should not push alert when balance is above threshold."""
        await service.get_balance()
        mock_notification_service.push.assert_not_called()


# ---------------------------------------------------------------------------
# check_reserve tests
# ---------------------------------------------------------------------------


class TestCheckReserve:
    """Tests for SunoBalanceService.check_reserve."""

    async def test_returns_true_when_above_threshold(
        self, service: SunoBalanceService
    ) -> None:
        """Should return True when balance >= threshold."""
        result = await service.check_reserve()
        assert result is True

    async def test_returns_false_when_below_threshold(
        self, fake_redis: FakeRedis
    ) -> None:
        """Should return False when balance < threshold."""
        low_client = FakeSunoClient(balance=50)
        svc = SunoBalanceService(
            redis=fake_redis,  # type: ignore[arg-type]
            suno_client=low_client,  # type: ignore[arg-type]
            reserve_threshold=100,
        )

        result = await svc.check_reserve()
        assert result is False

    async def test_returns_true_when_at_threshold(
        self, fake_redis: FakeRedis
    ) -> None:
        """Should return True when balance == threshold (>= check)."""
        exact_client = FakeSunoClient(balance=100)
        svc = SunoBalanceService(
            redis=fake_redis,  # type: ignore[arg-type]
            suno_client=exact_client,  # type: ignore[arg-type]
            reserve_threshold=100,
        )

        result = await svc.check_reserve()
        assert result is True

    async def test_returns_true_when_unknown(
        self, fake_redis: FakeRedis
    ) -> None:
        """Should return True (not block) when balance is unknown (Req 15.5)."""
        unreachable_client = FakeSunoClient(should_raise=True)
        svc = SunoBalanceService(
            redis=fake_redis,  # type: ignore[arg-type]
            suno_client=unreachable_client,  # type: ignore[arg-type]
            reserve_threshold=100,
        )

        result = await svc.check_reserve()
        assert result is True

    async def test_custom_threshold_override(
        self, fake_redis: FakeRedis
    ) -> None:
        """Should respect custom threshold override."""
        client = FakeSunoClient(balance=150)
        svc = SunoBalanceService(
            redis=fake_redis,  # type: ignore[arg-type]
            suno_client=client,  # type: ignore[arg-type]
            reserve_threshold=100,
        )

        # Custom threshold of 200 — balance 150 is below
        assert await svc.check_reserve(threshold=200) is False
        # Custom threshold of 100 — balance 150 is above
        assert await svc.check_reserve(threshold=100) is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for SunoBalanceService."""

    async def test_balance_key_alternative_format(
        self, fake_redis: FakeRedis
    ) -> None:
        """Should handle Suno API returning balance under 'balance' key."""
        client = AsyncMock()
        client.get_credit_balance = AsyncMock(return_value={"balance": 300})

        svc = SunoBalanceService(
            redis=fake_redis,  # type: ignore[arg-type]
            suno_client=client,
        )

        result = await svc.get_balance()
        assert result["credits"] == 300
        assert result["status"] == "ok"

    async def test_no_notification_service_configured(
        self, fake_redis: FakeRedis
    ) -> None:
        """Should not crash when notification service is not configured."""
        low_client = FakeSunoClient(balance=10)
        svc = SunoBalanceService(
            redis=fake_redis,  # type: ignore[arg-type]
            suno_client=low_client,  # type: ignore[arg-type]
            reserve_threshold=100,
            # No notification_service or admin_provider
        )

        # Should not raise
        result = await svc.get_balance()
        assert result["credits"] == 10

    async def test_admin_provider_failure_handled_gracefully(
        self, fake_redis: FakeRedis, mock_notification_service: AsyncMock
    ) -> None:
        """Should not crash if admin provider raises an error."""
        failing_provider = AsyncMock()
        failing_provider.get_admin_user_ids = AsyncMock(
            side_effect=RuntimeError("DB unavailable")
        )

        low_client = FakeSunoClient(balance=10)
        svc = SunoBalanceService(
            redis=fake_redis,  # type: ignore[arg-type]
            suno_client=low_client,  # type: ignore[arg-type]
            notification_service=mock_notification_service,
            admin_provider=failing_provider,
            reserve_threshold=100,
        )

        # Should not raise despite admin provider failure
        result = await svc.get_balance()
        assert result["credits"] == 10
        mock_notification_service.push.assert_not_called()

    async def test_redis_get_failure_returns_unknown(
        self, fake_redis: FakeRedis
    ) -> None:
        """Should return unknown if Redis get fails during fallback."""
        unreachable_client = FakeSunoClient(should_raise=True)

        # Make Redis get raise
        broken_redis = AsyncMock()
        broken_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        broken_redis.setex = AsyncMock()

        svc = SunoBalanceService(
            redis=broken_redis,
            suno_client=unreachable_client,  # type: ignore[arg-type]
        )

        result = await svc.get_balance()
        assert result["status"] == "unknown"
        assert result["credits"] is None
