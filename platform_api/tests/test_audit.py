"""Tests for the audit logging system (repository, service, and middleware).

Tests cover:
  - AuditRepository: append-only insert, paginated filtered queries
  - AuditService: log_event with all parameters, timestamp handling, query delegation
  - AuditMiddleware: intercepts state-changing requests, skips GET/HEAD/OPTIONS

Requirements: 20.1, 20.2, 20.3, 20.4
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from platform_api.middleware.audit import (
    AuditMiddleware,
    _determine_action_type,
    _determine_outcome,
    _extract_target_resource,
    _get_client_id,
    _get_client_ip,
)
from platform_api.models.domain import AuditLog
from platform_api.repositories.audit_repo import (
    AuditQueryFilters,
    AuditRepository,
    PaginatedAuditResult,
)
from platform_api.services.audit_service import AuditService


# ---------------------------------------------------------------------------
# Fake Database for Repository Tests
# ---------------------------------------------------------------------------


class FakeDatabase:
    """In-memory fake database implementing the DatabaseProtocol."""

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    async def execute(self, query: str, *args: Any) -> None:
        """Simulate INSERT by capturing the arguments."""
        if "INSERT INTO audit_logs" in query:
            self._rows.append({
                "id": args[0],
                "actor_id": args[1],
                "action_type": args[2],
                "target_resource": args[3],
                "outcome": args[4],
                "credit_impact": args[5],
                "source_ip": args[6],
                "client_id": args[7],
                "endpoint_path": args[8],
                "metadata": args[9],
                "created_at": args[10],
            })

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        """Simulate SELECT with basic filtering and pagination."""
        results = self._filter_rows(query, args)
        # Extract LIMIT/OFFSET from the last two params
        if "LIMIT" in query:
            limit = args[-2] if len(args) >= 2 else 50
            offset = args[-1] if len(args) >= 1 else 0
            results = results[offset: offset + limit]
        return results

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        """Not used for audit repo."""
        return None

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Simulate COUNT query."""
        if "COUNT" in query:
            results = self._filter_rows(query, args)
            return len(results)
        return 0

    def _filter_rows(self, query: str, args: tuple[Any, ...]) -> list[dict[str, Any]]:
        """Apply basic WHERE clause filtering."""
        results = list(self._rows)

        # Simple filter simulation based on query content
        param_idx = 0
        if "actor_id = " in query:
            actor_id = args[param_idx]
            param_idx += 1
            results = [r for r in results if r["actor_id"] == actor_id]

        if "action_type = " in query:
            action_type = args[param_idx]
            param_idx += 1
            results = [r for r in results if r["action_type"] == action_type]

        if "target_resource LIKE" in query:
            prefix = args[param_idx].rstrip("%")
            param_idx += 1
            results = [
                r for r in results
                if r.get("target_resource") and r["target_resource"].startswith(prefix)
            ]

        if "created_at >= " in query:
            from_date = args[param_idx]
            param_idx += 1
            results = [r for r in results if r["created_at"] >= from_date]

        if "created_at <= " in query:
            to_date = args[param_idx]
            param_idx += 1
            results = [r for r in results if r["created_at"] <= to_date]

        # Sort by created_at DESC
        results.sort(key=lambda r: r.get("created_at", datetime.min), reverse=True)
        return results


# ---------------------------------------------------------------------------
# Repository Tests
# ---------------------------------------------------------------------------


class TestAuditRepository:
    """Tests for AuditRepository."""

    @pytest.fixture
    def db(self) -> FakeDatabase:
        return FakeDatabase()

    @pytest.fixture
    def repo(self, db: FakeDatabase) -> AuditRepository:
        return AuditRepository(db)

    @pytest.mark.asyncio
    async def test_insert_creates_entry(self, repo: AuditRepository, db: FakeDatabase) -> None:
        """Insert stores the audit log entry in the database."""
        entry = AuditLog(
            id=uuid4(),
            actor_id=uuid4(),
            action_type="auth.login",
            target_resource="user:abc",
            outcome="success",
            credit_impact=0,
            source_ip="192.168.1.1",
            client_id="desktop-app",
            endpoint_path="/api/v1/auth/login",
            metadata={"http_method": "POST"},
            created_at=datetime.utcnow(),
        )

        result = await repo.insert(entry)

        assert result is entry
        assert len(db._rows) == 1
        assert db._rows[0]["action_type"] == "auth.login"
        assert db._rows[0]["source_ip"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_insert_with_none_actor(self, repo: AuditRepository, db: FakeDatabase) -> None:
        """Insert handles None actor_id (system actions)."""
        entry = AuditLog(
            id=uuid4(),
            actor_id=None,
            action_type="system.startup",
            outcome="success",
        )

        await repo.insert(entry)

        assert db._rows[0]["actor_id"] is None

    @pytest.mark.asyncio
    async def test_query_default_pagination(self, repo: AuditRepository, db: FakeDatabase) -> None:
        """Query returns default page size of 50 with page metadata."""
        # Insert 3 entries
        for i in range(3):
            entry = AuditLog(
                id=uuid4(),
                action_type=f"test.action_{i}",
                outcome="success",
                created_at=datetime.utcnow() + timedelta(seconds=i),
            )
            await repo.insert(entry)

        result = await repo.query()

        assert isinstance(result, PaginatedAuditResult)
        assert len(result.entries) == 3
        assert result.total == 3
        assert result.page == 1
        assert result.page_size == 50

    @pytest.mark.asyncio
    async def test_query_clamps_page_size_to_max_200(self, repo: AuditRepository) -> None:
        """Page size is clamped to maximum 200."""
        result = await repo.query(page_size=500)
        assert result.page_size == 200

    @pytest.mark.asyncio
    async def test_query_clamps_page_size_to_min_1(self, repo: AuditRepository) -> None:
        """Page size is clamped to minimum 1."""
        result = await repo.query(page_size=0)
        assert result.page_size == 1

    @pytest.mark.asyncio
    async def test_query_filter_by_actor_id(self, repo: AuditRepository, db: FakeDatabase) -> None:
        """Filter by actor_id returns only matching entries."""
        actor_uuid = uuid4()
        other_uuid = uuid4()

        for uid in [actor_uuid, actor_uuid, other_uuid]:
            entry = AuditLog(
                id=uuid4(),
                actor_id=uid,
                action_type="test.action",
                outcome="success",
                created_at=datetime.utcnow(),
            )
            await repo.insert(entry)

        filters = AuditQueryFilters(actor_id=str(actor_uuid))
        result = await repo.query(filters=filters)

        assert result.total == 2
        assert len(result.entries) == 2

    @pytest.mark.asyncio
    async def test_query_filter_by_action_type(self, repo: AuditRepository, db: FakeDatabase) -> None:
        """Filter by action_type returns only matching entries."""
        for action in ["auth.login", "auth.login", "generation.suno"]:
            entry = AuditLog(
                id=uuid4(),
                action_type=action,
                outcome="success",
                created_at=datetime.utcnow(),
            )
            await repo.insert(entry)

        filters = AuditQueryFilters(action_type="auth.login")
        result = await repo.query(filters=filters)

        assert result.total == 2

    @pytest.mark.asyncio
    async def test_query_filter_by_date_range(self, repo: AuditRepository, db: FakeDatabase) -> None:
        """Filter by date range returns only entries within range."""
        now = datetime.utcnow()
        old = now - timedelta(days=10)
        recent = now - timedelta(days=1)

        for ts in [old, recent, now]:
            entry = AuditLog(
                id=uuid4(),
                action_type="test.action",
                outcome="success",
                created_at=ts,
            )
            await repo.insert(entry)

        filters = AuditQueryFilters(
            from_date=now - timedelta(days=2),
            to_date=now,
        )
        result = await repo.query(filters=filters)

        assert result.total == 2

    @pytest.mark.asyncio
    async def test_query_filter_by_resource_type(self, repo: AuditRepository, db: FakeDatabase) -> None:
        """Filter by resource_type prefix returns matching entries."""
        for resource in ["user:abc", "user:def", "batch:xyz"]:
            entry = AuditLog(
                id=uuid4(),
                action_type="test.action",
                target_resource=resource,
                outcome="success",
                created_at=datetime.utcnow(),
            )
            await repo.insert(entry)

        filters = AuditQueryFilters(resource_type="user")
        result = await repo.query(filters=filters)

        assert result.total == 2

    @pytest.mark.asyncio
    async def test_total_pages_calculation(self, repo: AuditRepository, db: FakeDatabase) -> None:
        """PaginatedAuditResult.total_pages calculates correctly."""
        for i in range(5):
            entry = AuditLog(
                id=uuid4(),
                action_type="test.action",
                outcome="success",
                created_at=datetime.utcnow(),
            )
            await repo.insert(entry)

        result = await repo.query(page_size=2)

        assert result.total == 5
        assert result.total_pages == 3  # ceil(5/2)

    @pytest.mark.asyncio
    async def test_no_update_or_delete_operations_exposed(self, repo: AuditRepository) -> None:
        """Repository does not expose update or delete methods (Requirement 20.4)."""
        assert not hasattr(repo, "update")
        assert not hasattr(repo, "delete")
        assert not hasattr(repo, "remove")


# ---------------------------------------------------------------------------
# Service Tests
# ---------------------------------------------------------------------------


class TestAuditService:
    """Tests for AuditService."""

    @pytest.fixture
    def mock_repo(self) -> AsyncMock:
        repo = AsyncMock(spec=AuditRepository)
        repo.insert = AsyncMock(side_effect=lambda entry: entry)
        repo.query = AsyncMock(
            return_value=PaginatedAuditResult(entries=[], total=0, page=1, page_size=50)
        )
        return repo

    @pytest.fixture
    def service(self, mock_repo: AsyncMock) -> AuditService:
        return AuditService(audit_repo=mock_repo)

    @pytest.mark.asyncio
    async def test_log_event_creates_entry(self, service: AuditService, mock_repo: AsyncMock) -> None:
        """log_event creates and persists an AuditLog entry."""
        actor = str(uuid4())
        result = await service.log_event(
            actor_id=actor,
            action_type="generation.suno",
            target_resource="batch:123",
            credit_impact=14,
            outcome="success",
            source_ip="10.0.0.1",
            client_id="desktop-app",
            endpoint_path="/api/v1/generation/suno",
            metadata={"model": "V5"},
        )

        assert isinstance(result, AuditLog)
        assert result.action_type == "generation.suno"
        assert result.credit_impact == 14
        assert result.source_ip == "10.0.0.1"
        assert str(result.actor_id) == actor
        mock_repo.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_event_with_timestamp_string(self, service: AuditService, mock_repo: AsyncMock) -> None:
        """log_event accepts ISO 8601 timestamp string."""
        ts = "2024-06-15T10:30:00Z"
        result = await service.log_event(
            action_type="test.action",
            timestamp=ts,
        )

        assert result.created_at.year == 2024
        assert result.created_at.month == 6
        assert result.created_at.day == 15
        assert result.created_at.hour == 10
        assert result.created_at.minute == 30

    @pytest.mark.asyncio
    async def test_log_event_with_timestamp_datetime(self, service: AuditService, mock_repo: AsyncMock) -> None:
        """log_event accepts datetime object as timestamp."""
        ts = datetime(2024, 1, 15, 8, 0, 0)
        result = await service.log_event(
            action_type="test.action",
            timestamp=ts,
        )

        assert result.created_at == ts

    @pytest.mark.asyncio
    async def test_log_event_defaults_timestamp_to_utcnow(self, service: AuditService) -> None:
        """log_event uses current UTC time when no timestamp provided."""
        before = datetime.utcnow()
        result = await service.log_event(action_type="test.action")
        after = datetime.utcnow()

        assert before <= result.created_at <= after

    @pytest.mark.asyncio
    async def test_log_event_none_actor_id(self, service: AuditService) -> None:
        """log_event handles None actor_id for system events."""
        result = await service.log_event(
            actor_id=None,
            action_type="system.cleanup",
        )

        assert result.actor_id is None

    @pytest.mark.asyncio
    async def test_log_event_survives_repo_failure(self, service: AuditService, mock_repo: AsyncMock) -> None:
        """log_event does not raise if repository insert fails."""
        mock_repo.insert.side_effect = RuntimeError("DB connection lost")

        # Should not raise
        result = await service.log_event(action_type="test.action")
        assert result is not None

    @pytest.mark.asyncio
    async def test_query_delegates_to_repo(self, service: AuditService, mock_repo: AsyncMock) -> None:
        """query passes filters and pagination to the repository."""
        await service.query(
            actor_id="user-123",
            action_type="auth.login",
            resource_type="user",
            from_date=datetime(2024, 1, 1),
            to_date=datetime(2024, 12, 31),
            page=2,
            page_size=100,
        )

        mock_repo.query.assert_called_once()
        call_kwargs = mock_repo.query.call_args[1]
        assert call_kwargs["page"] == 2
        assert call_kwargs["page_size"] == 100
        filters = call_kwargs["filters"]
        assert filters.actor_id == "user-123"
        assert filters.action_type == "auth.login"
        assert filters.resource_type == "user"


# ---------------------------------------------------------------------------
# Middleware Tests
# ---------------------------------------------------------------------------


class TestAuditMiddleware:
    """Tests for the audit middleware helper functions."""

    def test_determine_action_type_auth_login(self) -> None:
        """Maps auth login path correctly."""
        assert _determine_action_type("POST", "/api/v1/auth/login") == "auth.login"

    def test_determine_action_type_generation_suno(self) -> None:
        """Maps generation suno path correctly."""
        assert _determine_action_type("POST", "/api/v1/generation/suno") == "generation.suno"

    def test_determine_action_type_profile_create(self) -> None:
        """Maps profile POST to profile.create."""
        assert _determine_action_type("POST", "/api/v1/profiles") == "profile.create"

    def test_determine_action_type_profile_update(self) -> None:
        """Maps profile PUT to profile.update."""
        assert _determine_action_type("PUT", "/api/v1/profiles/abc-123") == "profile.update"

    def test_determine_action_type_profile_delete(self) -> None:
        """Maps profile DELETE to profile.delete."""
        assert _determine_action_type("DELETE", "/api/v1/profiles/abc-123") == "profile.delete"

    def test_determine_action_type_credit_purchase(self) -> None:
        """Maps credit purchase path correctly."""
        assert _determine_action_type("POST", "/api/v1/credits/purchase") == "credit.purchase"

    def test_determine_action_type_license_assign(self) -> None:
        """Maps license assign path correctly."""
        assert _determine_action_type("POST", "/api/v1/licenses/abc/assign") == "license.assign"

    def test_determine_action_type_license_revoke(self) -> None:
        """Maps license revoke path correctly."""
        assert _determine_action_type("POST", "/api/v1/licenses/abc/revoke") == "license.revoke"

    def test_determine_action_type_user_suspend(self) -> None:
        """Maps user suspend path correctly."""
        assert _determine_action_type("POST", "/api/v1/users/abc/suspend") == "user.suspend"

    def test_determine_action_type_batch_create(self) -> None:
        """Maps batch POST to batch.create."""
        assert _determine_action_type("POST", "/api/v1/batches") == "batch.create"

    def test_determine_action_type_settings_update(self) -> None:
        """Maps settings PATCH to settings.update."""
        assert _determine_action_type("PATCH", "/api/v1/settings") == "settings.update"

    def test_determine_action_type_unknown_fallback(self) -> None:
        """Unknown paths produce generic fallback."""
        assert _determine_action_type("POST", "/api/v1/unknown/endpoint") == "api.post"

    def test_determine_outcome_success_2xx(self) -> None:
        """2xx status codes map to 'success'."""
        assert _determine_outcome(200) == "success"
        assert _determine_outcome(201) == "success"
        assert _determine_outcome(204) == "success"

    def test_determine_outcome_failure_4xx(self) -> None:
        """4xx status codes map to 'failure'."""
        assert _determine_outcome(400) == "failure"
        assert _determine_outcome(401) == "failure"
        assert _determine_outcome(403) == "failure"
        assert _determine_outcome(404) == "failure"
        assert _determine_outcome(422) == "failure"

    def test_determine_outcome_failure_5xx(self) -> None:
        """5xx status codes map to 'failure'."""
        assert _determine_outcome(500) == "failure"
        assert _determine_outcome(502) == "failure"

    def test_get_client_ip_from_forwarded_for(self) -> None:
        """Extracts first IP from X-Forwarded-For header."""
        request = MagicMock()
        request.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        assert _get_client_ip(request) == "1.2.3.4"

    def test_get_client_ip_from_client_host(self) -> None:
        """Falls back to request.client.host if no X-Forwarded-For."""
        request = MagicMock()
        request.headers = {}
        request.client.host = "192.168.0.1"
        assert _get_client_ip(request) == "192.168.0.1"

    def test_get_client_ip_none_when_unavailable(self) -> None:
        """Returns None when no IP info available."""
        request = MagicMock()
        request.headers = {}
        request.client = None
        assert _get_client_ip(request) is None

    def test_get_client_id_from_header(self) -> None:
        """Extracts X-Client-ID header value."""
        request = MagicMock()
        request.headers = {"x-client-id": "desktop-app"}
        assert _get_client_id(request) == "desktop-app"

    def test_get_client_id_none_when_missing(self) -> None:
        """Returns None when X-Client-ID header is not present."""
        request = MagicMock()
        request.headers = {}
        assert _get_client_id(request) is None

    def test_extract_target_resource_with_uuid(self) -> None:
        """Extracts resource type and ID from path."""
        result = _extract_target_resource("/api/v1/users/550e8400-e29b-41d4-a716-446655440000")
        assert result == "users:550e8400-e29b-41d4-a716-446655440000"

    def test_extract_target_resource_short_path(self) -> None:
        """Returns None for paths without resource identifiers."""
        result = _extract_target_resource("/api/v1/health")
        assert result is None


# ---------------------------------------------------------------------------
# PaginatedAuditResult Tests
# ---------------------------------------------------------------------------


class TestPaginatedAuditResult:
    """Tests for PaginatedAuditResult dataclass."""

    def test_total_pages_exact_division(self) -> None:
        """Total pages when entries divide evenly."""
        result = PaginatedAuditResult(entries=[], total=100, page=1, page_size=50)
        assert result.total_pages == 2

    def test_total_pages_with_remainder(self) -> None:
        """Total pages rounds up when there's a remainder."""
        result = PaginatedAuditResult(entries=[], total=101, page=1, page_size=50)
        assert result.total_pages == 3

    def test_total_pages_zero_total(self) -> None:
        """Total pages is 0 when total is 0."""
        result = PaginatedAuditResult(entries=[], total=0, page=1, page_size=50)
        assert result.total_pages == 0

    def test_total_pages_zero_page_size(self) -> None:
        """Total pages is 0 when page_size is 0 (avoids division by zero)."""
        result = PaginatedAuditResult(entries=[], total=10, page=1, page_size=0)
        assert result.total_pages == 0
