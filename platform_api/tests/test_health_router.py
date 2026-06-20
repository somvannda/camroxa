"""Tests for the health check router.

Requirements: 18.1, 18.2, 18.3
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.routers.health import (
    DatabasePool,
    _START_TIME,
    get_db_pool,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeDbPoolHealthy:
    """A fake database pool that reports healthy."""

    async def execute(self, query: str) -> Any:
        return [(1,)]


class FakeDbPoolUnhealthy:
    """A fake database pool that simulates connection failure."""

    async def execute(self, query: str) -> Any:
        raise ConnectionError("Database unreachable")


class FakeDbPoolSlow:
    """A fake database pool that exceeds the timeout."""

    async def execute(self, query: str) -> Any:
        await asyncio.sleep(5)  # Exceeds 3s timeout
        return [(1,)]


@pytest.fixture
def app_healthy():
    """App with a healthy database pool dependency."""
    application = create_app()

    application.dependency_overrides[get_db_pool] = lambda: FakeDbPoolHealthy()
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def app_unhealthy_db():
    """App with an unhealthy database pool."""
    application = create_app()

    application.dependency_overrides[get_db_pool] = lambda: FakeDbPoolUnhealthy()
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def app_slow_db():
    """App with a slow database pool (timeout)."""
    application = create_app()

    application.dependency_overrides[get_db_pool] = lambda: FakeDbPoolSlow()
    yield application
    application.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: Response structure (Requirement 18.1)
# ---------------------------------------------------------------------------


class TestHealthResponseStructure:
    """Health endpoint returns correct JSON structure."""

    async def test_returns_required_fields(self, app_healthy) -> None:
        """Health response must include status, database, services, uptime_seconds, timestamp."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "database" in body
        assert "services" in body
        assert "uptime_seconds" in body
        assert "timestamp" in body

    async def test_services_contains_all_providers(self, app_healthy) -> None:
        """Services dict must include suno, fal, slai."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        services = resp.json()["services"]
        assert "suno" in services
        assert "fal" in services
        assert "slai" in services

    async def test_timestamp_is_iso8601_utc(self, app_healthy) -> None:
        """Timestamp must be valid ISO 8601 UTC."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        timestamp = resp.json()["timestamp"]
        # Should be parseable as ISO 8601 and contain timezone info
        from datetime import datetime

        dt = datetime.fromisoformat(timestamp)
        assert dt.tzinfo is not None

    async def test_uptime_seconds_is_non_negative_integer(self, app_healthy) -> None:
        """uptime_seconds must be a non-negative integer."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        uptime = resp.json()["uptime_seconds"]
        assert isinstance(uptime, int)
        assert uptime >= 0

    async def test_no_auth_required(self, app_healthy) -> None:
        """Health endpoint does not require authentication."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # No Authorization header
                resp = await client.get("/health")

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: Status determination (Requirement 18.2)
# ---------------------------------------------------------------------------


class TestHealthStatus:
    """Status is healthy/degraded/unhealthy based on service reachability."""

    async def test_healthy_when_all_services_up(self, app_healthy) -> None:
        """All services reachable -> healthy."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        body = resp.json()
        assert body["status"] == "healthy"
        assert body["database"] is True
        assert body["services"]["suno"] is True
        assert body["services"]["fal"] is True
        assert body["services"]["slai"] is True

    async def test_degraded_when_suno_down(self, app_healthy) -> None:
        """Database up, Suno down -> degraded."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=False
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        body = resp.json()
        assert body["status"] == "degraded"
        assert body["database"] is True
        assert body["services"]["suno"] is False

    async def test_degraded_when_fal_down(self, app_healthy) -> None:
        """Database up, Fal down -> degraded."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=False
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        body = resp.json()
        assert body["status"] == "degraded"
        assert body["services"]["fal"] is False

    async def test_degraded_when_slai_down(self, app_healthy) -> None:
        """Database up, SLAI down -> degraded."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=False
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        body = resp.json()
        assert body["status"] == "degraded"
        assert body["services"]["slai"] is False

    async def test_degraded_when_all_external_down(self, app_healthy) -> None:
        """Database up, all external services down -> degraded."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=False
        ), patch(
            "platform_api.routers.health._check_fal", return_value=False
        ), patch(
            "platform_api.routers.health._check_slai", return_value=False
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        body = resp.json()
        assert body["status"] == "degraded"
        assert body["database"] is True

    async def test_unhealthy_when_database_down(self, app_unhealthy_db) -> None:
        """Database unreachable -> unhealthy (regardless of external services)."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_unhealthy_db)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["database"] is False

    async def test_unhealthy_when_database_times_out(self, app_slow_db) -> None:
        """Database exceeds 3s timeout -> unhealthy."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_slow_db)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")

        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["database"] is False


# ---------------------------------------------------------------------------
# Tests: Response time (Requirement 18.3)
# ---------------------------------------------------------------------------


class TestHealthResponseTime:
    """Health endpoint must respond within 500ms."""

    async def test_responds_within_500ms_all_healthy(self, app_healthy) -> None:
        """With mocked services, response should be well within 500ms."""
        with patch(
            "platform_api.routers.health._check_suno", return_value=True
        ), patch(
            "platform_api.routers.health._check_fal", return_value=True
        ), patch(
            "platform_api.routers.health._check_slai", return_value=True
        ):
            transport = ASGITransport(app=app_healthy)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                start = time.monotonic()
                resp = await client.get("/health")
                elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert elapsed < 0.5  # 500ms
