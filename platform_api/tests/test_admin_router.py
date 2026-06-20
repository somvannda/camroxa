"""Tests for the admin router endpoints (platform_api.routers.admin).

Validates:
- GET /admin/suno-balance (Admin-only)
- GET /admin/audit-log (Admin-only, with filters and pagination)
- GET /admin/rate-limits (Admin-only)
- PUT /admin/rate-limits (Admin-only)

Requirements: 15.1, 19.4, 20.2
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.exceptions import ForbiddenError
from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.models.domain import AuditLog
from platform_api.repositories.audit_repo import PaginatedAuditResult
from platform_api.repositories.rate_limit_repo import RateLimitConfigRecord
from platform_api.routers.admin import (
    _get_audit_service,
    _get_rate_limit_repo,
    _get_suno_balance_service,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADMIN_CONTEXT = AuthContext(user_id=str(uuid4()), email="admin@example.com", role="admin")
NOW = datetime(2024, 6, 15, 10, 30, 0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_audit_service() -> AsyncMock:
    """Create a mock AuditService."""
    service = AsyncMock()
    service.query = AsyncMock(
        return_value=PaginatedAuditResult(entries=[], total=0, page=1, page_size=50)
    )
    return service


@pytest.fixture
def mock_suno_balance_service() -> AsyncMock:
    """Create a mock SunoBalanceService."""
    service = AsyncMock()
    service.get_balance = AsyncMock(
        return_value={"credits": 5000, "status": "ok", "raw": {"balance": 5000}}
    )
    return service


@pytest.fixture
def mock_rate_limit_repo() -> AsyncMock:
    """Create a mock RateLimitConfigRepository."""
    repo = AsyncMock()
    repo.get_all = AsyncMock(return_value=[])
    repo.upsert = AsyncMock(
        return_value=RateLimitConfigRecord(
            id=str(uuid4()),
            endpoint_type="default",
            max_requests=60,
            window_seconds=60,
            updated_at=NOW,
        )
    )
    return repo


@pytest.fixture
def app(
    mock_audit_service: AsyncMock,
    mock_suno_balance_service: AsyncMock,
    mock_rate_limit_repo: AsyncMock,
):
    """Create a test app with admin auth and all admin service overrides."""
    application = create_app()
    application.dependency_overrides[require_admin] = lambda: ADMIN_CONTEXT
    application.dependency_overrides[_get_audit_service] = lambda: mock_audit_service
    application.dependency_overrides[_get_suno_balance_service] = lambda: mock_suno_balance_service
    application.dependency_overrides[_get_rate_limit_repo] = lambda: mock_rate_limit_repo
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def non_admin_app(
    mock_audit_service: AsyncMock,
    mock_suno_balance_service: AsyncMock,
    mock_rate_limit_repo: AsyncMock,
):
    """Create a test app where the user is NOT an admin."""
    application = create_app()
    application.dependency_overrides[_get_audit_service] = lambda: mock_audit_service
    application.dependency_overrides[_get_suno_balance_service] = lambda: mock_suno_balance_service
    application.dependency_overrides[_get_rate_limit_repo] = lambda: mock_rate_limit_repo

    def _reject_non_admin():
        raise ForbiddenError("You do not have permission to perform this action.")

    application.dependency_overrides[require_admin] = _reject_non_admin
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def non_admin_client(non_admin_app) -> AsyncClient:
    """Create a test client with non-admin user."""
    transport = ASGITransport(app=non_admin_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /admin/suno-balance
# ---------------------------------------------------------------------------


class TestGetSunoBalance:
    """Tests for GET /admin/suno-balance endpoint."""

    async def test_returns_balance(self, client: AsyncClient) -> None:
        """Admin receives the external Suno credit balance."""
        response = await client.get("/api/v1/admin/suno-balance")
        assert response.status_code == 200
        data = response.json()
        assert data["credits"] == 5000
        assert data["status"] == "ok"
        assert data["raw"] == {"balance": 5000}

    async def test_unknown_balance(
        self, client: AsyncClient, mock_suno_balance_service: AsyncMock
    ) -> None:
        """Returns unknown status when Suno API is unreachable."""
        mock_suno_balance_service.get_balance.return_value = {
            "credits": None,
            "status": "unknown",
            "raw": None,
        }
        response = await client.get("/api/v1/admin/suno-balance")
        assert response.status_code == 200
        data = response.json()
        assert data["credits"] is None
        assert data["status"] == "unknown"

    async def test_non_admin_rejected(self, non_admin_client: AsyncClient) -> None:
        """Non-admin user receives 403."""
        response = await non_admin_client.get("/api/v1/admin/suno-balance")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/audit-log
# ---------------------------------------------------------------------------


class TestGetAuditLog:
    """Tests for GET /admin/audit-log endpoint."""

    async def test_returns_empty_list(self, client: AsyncClient) -> None:
        """Returns empty audit log when no entries exist."""
        response = await client.get("/api/v1/admin/audit-log")
        assert response.status_code == 200
        data = response.json()
        assert data["entries"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 50
        assert data["total_pages"] == 0

    async def test_returns_entries(
        self, client: AsyncClient, mock_audit_service: AsyncMock
    ) -> None:
        """Returns audit log entries with pagination metadata."""
        actor_id = uuid4()
        entry = AuditLog(
            id=uuid4(),
            actor_id=actor_id,
            action_type="auth.login",
            target_resource="user:abc123",
            outcome="success",
            credit_impact=0,
            source_ip="192.168.1.1",
            client_id="desktop-app",
            endpoint_path="/api/v1/auth/login",
            metadata={"browser": "chrome"},
            created_at=NOW,
        )
        mock_audit_service.query.return_value = PaginatedAuditResult(
            entries=[entry], total=1, page=1, page_size=50
        )

        response = await client.get("/api/v1/admin/audit-log")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["total_pages"] == 1
        assert len(data["entries"]) == 1

        entry_data = data["entries"][0]
        assert entry_data["action_type"] == "auth.login"
        assert entry_data["actor_id"] == str(actor_id)
        assert entry_data["target_resource"] == "user:abc123"
        assert entry_data["outcome"] == "success"
        assert entry_data["source_ip"] == "192.168.1.1"
        assert entry_data["metadata"] == {"browser": "chrome"}

    async def test_passes_filters(
        self, client: AsyncClient, mock_audit_service: AsyncMock
    ) -> None:
        """Passes query parameters as filters to the audit service."""
        response = await client.get(
            "/api/v1/admin/audit-log",
            params={
                "actor_id": "user-123",
                "action_type": "generation.suno",
                "resource_type": "batch",
                "from_date": "2024-01-01T00:00:00",
                "to_date": "2024-12-31T23:59:59",
                "page": 2,
                "page_size": 25,
            },
        )
        assert response.status_code == 200
        mock_audit_service.query.assert_called_once_with(
            actor_id="user-123",
            action_type="generation.suno",
            resource_type="batch",
            from_date=datetime(2024, 1, 1, 0, 0, 0),
            to_date=datetime(2024, 12, 31, 23, 59, 59),
            page=2,
            page_size=25,
        )

    async def test_pagination_defaults(
        self, client: AsyncClient, mock_audit_service: AsyncMock
    ) -> None:
        """Uses default page=1, page_size=50 when not specified."""
        await client.get("/api/v1/admin/audit-log")
        mock_audit_service.query.assert_called_once_with(
            actor_id=None,
            action_type=None,
            resource_type=None,
            from_date=None,
            to_date=None,
            page=1,
            page_size=50,
        )

    async def test_page_size_max_200(self, client: AsyncClient) -> None:
        """Rejects page_size over 200."""
        response = await client.get(
            "/api/v1/admin/audit-log", params={"page_size": 201}
        )
        assert response.status_code == 422

    async def test_non_admin_rejected(self, non_admin_client: AsyncClient) -> None:
        """Non-admin user receives 403."""
        response = await non_admin_client.get("/api/v1/admin/audit-log")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/rate-limits
# ---------------------------------------------------------------------------


class TestGetRateLimits:
    """Tests for GET /admin/rate-limits endpoint."""

    async def test_returns_empty_list(self, client: AsyncClient) -> None:
        """Returns empty config list when no rate limits are configured."""
        response = await client.get("/api/v1/admin/rate-limits")
        assert response.status_code == 200
        data = response.json()
        assert data["configs"] == []

    async def test_returns_configs(
        self, client: AsyncClient, mock_rate_limit_repo: AsyncMock
    ) -> None:
        """Returns all rate limit configurations."""
        record = RateLimitConfigRecord(
            id=str(uuid4()),
            endpoint_type="suno",
            max_requests=10,
            window_seconds=60,
            updated_at=NOW,
        )
        mock_rate_limit_repo.get_all.return_value = [record]

        response = await client.get("/api/v1/admin/rate-limits")
        assert response.status_code == 200
        data = response.json()
        assert len(data["configs"]) == 1
        assert data["configs"][0]["endpoint_type"] == "suno"
        assert data["configs"][0]["max_requests"] == 10
        assert data["configs"][0]["window_seconds"] == 60

    async def test_non_admin_rejected(self, non_admin_client: AsyncClient) -> None:
        """Non-admin user receives 403."""
        response = await non_admin_client.get("/api/v1/admin/rate-limits")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# PUT /admin/rate-limits
# ---------------------------------------------------------------------------


class TestUpdateRateLimits:
    """Tests for PUT /admin/rate-limits endpoint."""

    async def test_updates_config(
        self, client: AsyncClient, mock_rate_limit_repo: AsyncMock
    ) -> None:
        """Admin can update rate limit configuration."""
        mock_rate_limit_repo.upsert.return_value = RateLimitConfigRecord(
            id=str(uuid4()),
            endpoint_type="suno",
            max_requests=20,
            window_seconds=120,
            updated_at=NOW,
        )

        response = await client.put(
            "/api/v1/admin/rate-limits",
            json={
                "endpoint_type": "suno",
                "max_requests": 20,
                "window_seconds": 120,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["endpoint_type"] == "suno"
        assert data["max_requests"] == 20
        assert data["window_seconds"] == 120

        mock_rate_limit_repo.upsert.assert_called_once_with(
            endpoint_type="suno",
            max_requests=20,
            window_seconds=120,
        )

    async def test_validates_max_requests_minimum(self, client: AsyncClient) -> None:
        """Rejects max_requests below 1."""
        response = await client.put(
            "/api/v1/admin/rate-limits",
            json={"endpoint_type": "suno", "max_requests": 0, "window_seconds": 60},
        )
        assert response.status_code == 422

    async def test_validates_window_seconds_minimum(self, client: AsyncClient) -> None:
        """Rejects window_seconds below 1."""
        response = await client.put(
            "/api/v1/admin/rate-limits",
            json={"endpoint_type": "suno", "max_requests": 10, "window_seconds": 0},
        )
        assert response.status_code == 422

    async def test_validates_endpoint_type_not_empty(self, client: AsyncClient) -> None:
        """Rejects empty endpoint_type."""
        response = await client.put(
            "/api/v1/admin/rate-limits",
            json={"endpoint_type": "", "max_requests": 10, "window_seconds": 60},
        )
        assert response.status_code == 422

    async def test_non_admin_rejected(self, non_admin_client: AsyncClient) -> None:
        """Non-admin user receives 403."""
        response = await non_admin_client.put(
            "/api/v1/admin/rate-limits",
            json={"endpoint_type": "suno", "max_requests": 20, "window_seconds": 120},
        )
        assert response.status_code == 403
