"""Audit log repository for append-only audit record storage and querying.

Provides paginated, filtered queries over the audit_logs table.
No update or delete operations are exposed (append-only).

Requirements: 20.1, 20.2, 20.3, 20.4
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import AuditLog


# ---------------------------------------------------------------------------
# Query filter dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuditQueryFilters:
    """Filters for querying the audit log.

    Attributes:
        actor_id: Filter by the actor who performed the action.
        action_type: Filter by action type (e.g., 'generation.suno', 'auth.login_failed').
        resource_type: Filter by target resource type prefix.
        from_date: Filter entries created at or after this timestamp.
        to_date: Filter entries created at or before this timestamp.
    """

    actor_id: str | None = None
    action_type: str | None = None
    resource_type: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None


@dataclass(frozen=True, slots=True)
class PaginatedAuditResult:
    """Paginated audit log query result.

    Attributes:
        entries: The audit log entries for the current page.
        total: Total number of entries matching the filters.
        page: Current page number (1-based).
        page_size: Number of entries per page.
    """

    entries: list[AuditLog]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Total number of pages."""
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


# ---------------------------------------------------------------------------
# Database Protocol (minimal interface for the repository)
# ---------------------------------------------------------------------------


class DatabaseProtocol(Protocol):
    """Minimal async database interface for audit log operations."""

    async def execute(self, query: str, *args: Any) -> None: ...
    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]: ...
    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class AuditRepository:
    """Append-only audit log repository.

    Provides:
        - insert: Append a new audit log entry.
        - query: Paginated, filtered retrieval of audit log entries.

    No update or delete operations are provided (Requirement 20.4).

    Args:
        db: Async database connection or pool implementing DatabaseProtocol.
    """

    def __init__(self, db: DatabaseProtocol) -> None:
        self._db = db

    async def insert(self, entry: AuditLog) -> AuditLog:
        """Insert a new audit log entry.

        Args:
            entry: The AuditLog domain object to persist.

        Returns:
            The persisted AuditLog entry (unchanged).
        """
        import json as _json
        metadata_str = _json.dumps(entry.metadata) if entry.metadata else None
        await self._db.execute(
            """
            INSERT INTO audit_logs (id, actor_id, action_type, target_resource,
                                    outcome, credit_impact, source_ip, client_id,
                                    endpoint_path, metadata, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            str(entry.id),
            str(entry.actor_id) if entry.actor_id else None,
            entry.action_type,
            entry.target_resource,
            entry.outcome,
            entry.credit_impact,
            entry.source_ip,
            entry.client_id,
            entry.endpoint_path,
            metadata_str,
            entry.created_at,
        )
        return entry

    async def query(
        self,
        filters: AuditQueryFilters | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedAuditResult:
        """Query audit log entries with optional filters and pagination.

        Args:
            filters: Optional filters to apply.
            page: Page number (1-based). Defaults to 1.
            page_size: Number of entries per page. Clamped to [1, 200].

        Returns:
            PaginatedAuditResult with entries and pagination metadata.
        """
        # Clamp page_size to [1, 200]
        page_size = max(1, min(page_size, 200))
        page = max(1, page)

        conditions: list[str] = []
        params: list[Any] = []
        param_idx = 0

        if filters:
            if filters.actor_id:
                param_idx += 1
                conditions.append(f"actor_id = ${param_idx}")
                params.append(filters.actor_id)

            if filters.action_type:
                param_idx += 1
                conditions.append(f"action_type = ${param_idx}")
                params.append(filters.action_type)

            if filters.resource_type:
                param_idx += 1
                conditions.append(f"target_resource LIKE ${param_idx}")
                params.append(f"{filters.resource_type}%")

            if filters.from_date:
                param_idx += 1
                conditions.append(f"created_at >= ${param_idx}")
                params.append(filters.from_date)

            if filters.to_date:
                param_idx += 1
                conditions.append(f"created_at <= ${param_idx}")
                params.append(filters.to_date)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Count total matching entries
        count_query = f"SELECT COUNT(*) FROM audit_logs {where_clause}"
        total = await self._db.fetchval(count_query, *params) or 0

        # Fetch page of entries
        offset = (page - 1) * page_size
        param_idx += 1
        limit_param = f"${param_idx}"
        param_idx += 1
        offset_param = f"${param_idx}"

        select_query = f"""
            SELECT id, actor_id, action_type, target_resource, outcome,
                   credit_impact, source_ip, client_id, endpoint_path,
                   metadata, created_at
            FROM audit_logs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT {limit_param} OFFSET {offset_param}
        """
        rows = await self._db.fetch(select_query, *params, page_size, offset)

        entries = [self._row_to_audit_log(row) for row in rows]

        return PaginatedAuditResult(
            entries=entries,
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def _row_to_audit_log(row: dict[str, Any]) -> AuditLog:
        """Convert a database row dict to an AuditLog domain object."""
        from uuid import UUID as _UUID

        return AuditLog(
            id=_UUID(row["id"]) if isinstance(row["id"], str) else row["id"],
            actor_id=_UUID(row["actor_id"]) if row.get("actor_id") else None,
            action_type=row.get("action_type", ""),
            target_resource=row.get("target_resource"),
            outcome=row.get("outcome", "success"),
            credit_impact=row.get("credit_impact", 0),
            source_ip=row.get("source_ip"),
            client_id=row.get("client_id"),
            endpoint_path=row.get("endpoint_path"),
            metadata=row.get("metadata"),
            created_at=row.get("created_at", datetime.utcnow()),
        )
