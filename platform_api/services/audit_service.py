"""Audit logging service.

Provides a high-level interface for recording audit events and querying
the audit log. Intercepts state-changing operations to auto-log them.

Requirements: 20.1, 20.2, 20.3, 20.4
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from platform_api.models.domain import AuditLog
from platform_api.repositories.audit_repo import (
    AuditQueryFilters,
    AuditRepository,
    PaginatedAuditResult,
)

logger = logging.getLogger(__name__)


class AuditService:
    """Service for recording and querying audit log entries.

    Responsibilities:
        - Record audit events from any service layer (generation, auth, credits).
        - Query audit logs with filters and pagination for Admin viewing.
        - Ensure entries are append-only (no update/delete operations).

    Args:
        audit_repo: Repository for persisting and querying audit log entries.
    """

    def __init__(self, audit_repo: AuditRepository) -> None:
        self._repo = audit_repo

    async def log_event(
        self,
        *,
        actor_id: str | None = None,
        action_type: str,
        target_resource: str | None = None,
        timestamp: str | datetime | None = None,
        credit_impact: int = 0,
        outcome: str = "success",
        source_ip: str | None = None,
        client_id: str | None = None,
        endpoint_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Record an audit log entry.

        Args:
            actor_id: UUID string of the user performing the action (None for system actions).
            action_type: Type of action (e.g., 'auth.login', 'generation.suno', 'credit.purchase').
            target_resource: Identifier of the affected resource (e.g., 'user:uuid', 'batch:uuid').
            timestamp: Optional UTC ISO 8601 timestamp; defaults to current UTC time.
            credit_impact: Number of credits affected (positive = deducted, negative = refunded).
            outcome: Result of the action ('success' or 'failure').
            source_ip: Client IP address.
            client_id: Client application identifier.
            endpoint_path: The API endpoint path.
            metadata: Additional JSON metadata about the event.

        Returns:
            The persisted AuditLog entry.
        """
        from uuid import UUID

        # Resolve timestamp
        if timestamp is None:
            created_at = datetime.utcnow()
        elif isinstance(timestamp, str):
            # Parse ISO 8601 string
            created_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).replace(tzinfo=None)
        else:
            created_at = timestamp

        entry = AuditLog(
            id=uuid4(),
            actor_id=UUID(actor_id) if actor_id else None,
            action_type=action_type,
            target_resource=target_resource,
            outcome=outcome,
            credit_impact=credit_impact,
            source_ip=source_ip,
            client_id=client_id,
            endpoint_path=endpoint_path,
            metadata=metadata,
            created_at=created_at,
        )

        try:
            await self._repo.insert(entry)
        except Exception as exc:
            # Audit logging should never break the request — log and continue
            logger.error("Failed to record audit event: %s", str(exc)[:200])

        return entry

    async def query(
        self,
        *,
        actor_id: str | None = None,
        action_type: str | None = None,
        resource_type: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedAuditResult:
        """Query audit log entries with optional filters and pagination.

        Args:
            actor_id: Filter by actor UUID string.
            action_type: Filter by action type.
            resource_type: Filter by target resource type prefix.
            from_date: Filter entries on or after this date.
            to_date: Filter entries on or before this date.
            page: Page number (1-based, default 1).
            page_size: Entries per page (default 50, max 200).

        Returns:
            PaginatedAuditResult with entries and pagination metadata.
        """
        filters = AuditQueryFilters(
            actor_id=actor_id,
            action_type=action_type,
            resource_type=resource_type,
            from_date=from_date,
            to_date=to_date,
        )

        return await self._repo.query(
            filters=filters,
            page=page,
            page_size=page_size,
        )
