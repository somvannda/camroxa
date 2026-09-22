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
from platform_api.models.domain import AuditLog, User
from platform_api.models.enums import UserRole, UserStatus
from platform_api.repositories.audit_repo import PaginatedAuditResult
from platform_api.repositories.rate_limit_repo import RateLimitConfigRecord
from platform_api.repositories.youtube_oauth_app_repo import YouTubeOAuthAppRecord
from platform_api.routers.admin import (
    _get_audit_service,
    _get_user_repo,
    _get_rate_limit_repo,
    _get_settings_repo,
    _get_suno_balance_service,
    _get_youtube_oauth_app_repo,
    _get_youtube_oauth_encryption,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADMIN_CONTEXT = AuthContext(user_id=str(uuid4()), email="admin@example.com", role="admin")
NOW = datetime(2024, 6, 15, 10, 30, 0)


class FakeEncryption:
    def encrypt(self, plaintext: str) -> bytes:
        return f"enc::{plaintext}".encode()


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
def mock_youtube_oauth_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.list_all = AsyncMock(return_value=[])
    repo.create = AsyncMock(
        return_value=YouTubeOAuthAppRecord(
            id=str(uuid4()),
            name="Main Google App",
            client_id="client-123",
            encrypted_client_secret=b"enc::secret",
            is_default=True,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repo.update = AsyncMock(
        return_value=YouTubeOAuthAppRecord(
            id=str(uuid4()),
            name="Updated Google App",
            client_id="client-456",
            encrypted_client_secret=b"enc::new-secret",
            is_default=False,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_settings_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_system_setting = AsyncMock(return_value=None)
    repo.upsert_system_settings = AsyncMock()
    return repo


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def app(
    mock_audit_service: AsyncMock,
    mock_suno_balance_service: AsyncMock,
    mock_rate_limit_repo: AsyncMock,
    mock_settings_repo: AsyncMock,
    mock_youtube_oauth_repo: AsyncMock,
    mock_user_repo: AsyncMock,
):
    """Create a test app with admin auth and all admin service overrides."""
    application = create_app()
    application.dependency_overrides[require_admin] = lambda: ADMIN_CONTEXT
    application.dependency_overrides[_get_audit_service] = lambda: mock_audit_service
    application.dependency_overrides[_get_suno_balance_service] = lambda: mock_suno_balance_service
    application.dependency_overrides[_get_rate_limit_repo] = lambda: mock_rate_limit_repo
    application.dependency_overrides[_get_settings_repo] = lambda: mock_settings_repo
    application.dependency_overrides[_get_youtube_oauth_app_repo] = lambda: mock_youtube_oauth_repo
    application.dependency_overrides[_get_youtube_oauth_encryption] = lambda: FakeEncryption()
    application.dependency_overrides[_get_user_repo] = lambda: mock_user_repo
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
    mock_settings_repo: AsyncMock,
    mock_youtube_oauth_repo: AsyncMock,
    mock_user_repo: AsyncMock,
):
    """Create a test app where the user is NOT an admin."""
    application = create_app()
    application.dependency_overrides[_get_audit_service] = lambda: mock_audit_service
    application.dependency_overrides[_get_suno_balance_service] = lambda: mock_suno_balance_service
    application.dependency_overrides[_get_rate_limit_repo] = lambda: mock_rate_limit_repo
    application.dependency_overrides[_get_settings_repo] = lambda: mock_settings_repo
    application.dependency_overrides[_get_youtube_oauth_app_repo] = lambda: mock_youtube_oauth_repo
    application.dependency_overrides[_get_youtube_oauth_encryption] = lambda: FakeEncryption()
    application.dependency_overrides[_get_user_repo] = lambda: mock_user_repo

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
        self, client: AsyncClient, mock_audit_service: AsyncMock, mock_user_repo: AsyncMock
    ) -> None:
        """Returns audit log entries with pagination metadata."""
        actor_id = uuid4()
        mock_user_repo.get_by_id.return_value = User(
            id=actor_id,
            email="operator@example.com",
            password_hash="hashed",
            display_name="Operations Admin",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            created_at=NOW,
            updated_at=NOW,
        )
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
        assert entry_data["actor_email"] == "operator@example.com"
        assert entry_data["actor_display_name"] == "Operations Admin"
        assert entry_data["actor_role"] == "admin"
        assert entry_data["actor_label"] == "Operations Admin"
        assert entry_data["target_resource"] == "user:abc123"
        assert entry_data["outcome"] == "success"
        assert entry_data["source_ip"] == "192.168.1.1"
        assert entry_data["credits_involved"] is False
        assert entry_data["credit_summary"] == "No recorded credit involvement."
        assert entry_data["metadata"] == {"browser": "chrome"}

    async def test_returns_credit_context_fields(
        self, client: AsyncClient, mock_audit_service: AsyncMock
    ) -> None:
        """Returns derived credit context for audit entries."""
        entry = AuditLog(
            id=uuid4(),
            actor_id=None,
            action_type="credit.purchase",
            target_resource="credit_wallet:user-1",
            outcome="success",
            credit_impact=25,
            source_ip="192.168.1.1",
            client_id="admin-portal",
            endpoint_path="/api/v1/credits/purchase",
            metadata={"reason": "monthly pack", "payment_ref": "pay_123"},
            created_at=NOW,
        )
        mock_audit_service.query.return_value = PaginatedAuditResult(
            entries=[entry], total=1, page=1, page_size=50
        )

        response = await client.get("/api/v1/admin/audit-log")
        assert response.status_code == 200
        entry_data = response.json()["entries"][0]
        assert entry_data["actor_label"] == "System"
        assert entry_data["credits_involved"] is True
        assert entry_data["credit_direction"] == "debit"
        assert entry_data["credit_reason"] == "monthly pack"
        assert entry_data["payment_reference"] == "pay_123"
        assert entry_data["credit_summary"] == "Deducted 25 credits. Reason: monthly pack."

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
                "outcome": "failure",
                "endpoint_path": "/api/v1/generation",
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
            outcome="failure",
            endpoint_path="/api/v1/generation",
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
            outcome=None,
            endpoint_path=None,
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


class TestSlaiImageProviderConfig:
    async def test_get_returns_defaults_when_unset(
        self, client: AsyncClient, mock_settings_repo: AsyncMock
    ) -> None:
        mock_settings_repo.get_system_setting.return_value = None
        response = await client.get("/api/v1/admin/rate-limits/slai-image-provider")
        assert response.status_code == 200
        data = response.json()
        assert data["min_interval_seconds"] == 5.0
        assert data["max_concurrent"] == 1
        assert data["provider_retries"] == 5

    async def test_put_persists_settings(
        self, client: AsyncClient, mock_settings_repo: AsyncMock
    ) -> None:
        payload = {
            "min_interval_seconds": 8.0,
            "max_concurrent": 2,
            "provider_retries": 7,
            "retry_base_delay_seconds": 6.0,
            "retry_max_delay_seconds": 60.0,
            "fallback_provider_retries": 2,
        }
        response = await client.put(
            "/api/v1/admin/rate-limits/slai-image-provider",
            json=payload,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider_retries"] == 7
        mock_settings_repo.upsert_system_settings.assert_awaited_once()

    async def test_non_admin_rejected(self, non_admin_client: AsyncClient) -> None:
        response = await non_admin_client.get(
            "/api/v1/admin/rate-limits/slai-image-provider"
        )
        assert response.status_code == 403


class TestYouTubeOAuthApps:
    async def test_lists_apps(
        self, client: AsyncClient, mock_youtube_oauth_repo: AsyncMock
    ) -> None:
        app_id = str(uuid4())
        mock_youtube_oauth_repo.list_all.return_value = [
            YouTubeOAuthAppRecord(
                id=app_id,
                name="Studio Google App",
                client_id="client-123",
                encrypted_client_secret=b"enc::secret",
                is_default=True,
                created_at=NOW,
                updated_at=NOW,
            )
        ]

        response = await client.get("/api/v1/admin/youtube-oauth-apps")
        assert response.status_code == 200
        data = response.json()
        assert len(data["apps"]) == 1
        assert data["apps"][0]["id"] == app_id
        assert data["apps"][0]["name"] == "Studio Google App"
        assert data["apps"][0]["client_id"] == "client-123"
        assert data["apps"][0]["has_client_secret"] is True
        assert data["apps"][0]["created_at"] == "2024-06-15T10:30:00Z"
        assert data["apps"][0]["updated_at"] == "2024-06-15T10:30:00Z"

    async def test_creates_app(
        self, client: AsyncClient, mock_youtube_oauth_repo: AsyncMock
    ) -> None:
        response = await client.post(
            "/api/v1/admin/youtube-oauth-apps",
            json={
                "name": "Main Google App",
                "client_id": "client-123",
                "client_secret": "secret-value",
                "is_default": True,
            },
        )
        assert response.status_code == 200
        mock_youtube_oauth_repo.create.assert_called_once()
        call_kwargs = mock_youtube_oauth_repo.create.call_args.kwargs
        assert call_kwargs["name"] == "Main Google App"
        assert call_kwargs["client_id"] == "client-123"
        assert call_kwargs["encrypted_client_secret"] == b"enc::secret-value"
        assert call_kwargs["is_default"] is True

    async def test_updates_app(
        self, client: AsyncClient, mock_youtube_oauth_repo: AsyncMock
    ) -> None:
        response = await client.patch(
            "/api/v1/admin/youtube-oauth-apps/app-123",
            json={
                "name": "Updated Google App",
                "client_secret": "new-secret",
                "is_default": False,
            },
        )
        assert response.status_code == 200
        mock_youtube_oauth_repo.update.assert_called_once()
        call_args = mock_youtube_oauth_repo.update.call_args
        assert call_args.args[0] == "app-123"
        assert call_args.kwargs["name"] == "Updated Google App"
        assert call_args.kwargs["encrypted_client_secret"] == b"enc::new-secret"
        assert call_args.kwargs["is_default"] is False

    async def test_deletes_app(
        self, client: AsyncClient, mock_youtube_oauth_repo: AsyncMock
    ) -> None:
        response = await client.delete("/api/v1/admin/youtube-oauth-apps/app-123")
        assert response.status_code == 200
        assert response.json()["message"] == "YouTube OAuth app deleted."
        mock_youtube_oauth_repo.delete.assert_called_once_with("app-123")

    async def test_non_admin_rejected(self, non_admin_client: AsyncClient) -> None:
        response = await non_admin_client.get("/api/v1/admin/youtube-oauth-apps")
        assert response.status_code == 403
