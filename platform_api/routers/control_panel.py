"""User control-panel support endpoints.

Provides authenticated user-facing data for the portal control panel:
- notification center items backed by the notification queue
- security/session visibility backed by audit logs
"""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, get_current_user

router = APIRouter(prefix="/control-panel", tags=["control-panel"])

CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


class NotificationItemResponse(BaseModel):
    id: str
    event_type: str
    category: str
    title: str
    message: str
    delivered: bool = False
    created_at: str
    expires_at: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NotificationCenterResponse(BaseModel):
    items: list[NotificationItemResponse] = Field(default_factory=list)
    unread_count: int = 0
    total: int = 0


class MarkNotificationsReadRequest(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=100)
    mark_all: bool = False


class MarkNotificationsReadResponse(BaseModel):
    updated: int
    unread_count: int


class SessionSummaryResponse(BaseModel):
    client_id: str
    source_ip: str
    last_seen: str
    successful_logins: int = 0
    failed_attempts: int = 0
    refresh_events: int = 0
    logout_events: int = 0
    last_outcome: str = "success"
    activity_count: int = 0


class SecurityEventResponse(BaseModel):
    id: str
    action_type: str
    outcome: str
    client_id: str
    source_ip: str
    endpoint_path: str | None = None
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecurityOverviewResponse(BaseModel):
    sessions: list[SessionSummaryResponse] = Field(default_factory=list)
    events: list[SecurityEventResponse] = Field(default_factory=list)
    desktop_last_seen: str | None = None
    web_last_seen: str | None = None


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _coerce_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _notification_category(event_type: str) -> str:
    normalized = event_type.lower()
    if "billing" in normalized or "redeem" in normalized:
        return "billing"
    if "desktop" in normalized or "download" in normalized:
        return "desktop"
    if "security" in normalized or normalized.startswith("auth"):
        return "security"
    return "production"


def _notification_copy(event_type: str, payload: dict[str, Any]) -> tuple[str, str]:
    normalized = event_type.lower()
    if normalized == "suno_task_completed":
        status = str(payload.get("status") or "completed").replace("_", " ")
        task_id = str(payload.get("task_id") or "")[:8]
        if status == "success":
            return (
                "Music generation completed",
                f"Task {task_id or 'job'} finished successfully and is ready for the next production step.",
            )
        return (
            "Music generation updated",
            f"Task {task_id or 'job'} returned status {status}.",
        )
    if "billing" in normalized:
        return ("Billing update", "A billing-related event was recorded for your account.")
    if "redeem" in normalized:
        return ("Redeem code activity", "A redeem-code event was recorded for your account.")
    if "download" in normalized:
        return ("Desktop sync update", "A desktop download or sync event was recorded.")
    return ("Control-panel notification", event_type.replace("_", " ").title())


@router.get("/notifications", response_model=NotificationCenterResponse, status_code=200)
async def get_notification_center(
    ctx: CurrentUserDep,
) -> NotificationCenterResponse:
    pool = get_db_pool()
    user_id = UUID(ctx.user_id)

    rows = await pool.fetch(
        """
        SELECT id, event_type, payload, delivered, created_at, expires_at
        FROM notification_queue
        WHERE user_id = $1
          AND expires_at > NOW()
        ORDER BY created_at DESC
        LIMIT 20
        """,
        user_id,
    )
    unread_count = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM notification_queue
        WHERE user_id = $1
          AND delivered = FALSE
          AND expires_at > NOW()
        """,
        user_id,
    )

    items: list[NotificationItemResponse] = []
    for row in rows:
        payload = _coerce_payload(row["payload"])
        title, message = _notification_copy(str(row["event_type"]), payload)
        items.append(
            NotificationItemResponse(
                id=str(row["id"]),
                event_type=str(row["event_type"]),
                category=_notification_category(str(row["event_type"])),
                title=title,
                message=message,
                delivered=bool(row["delivered"]),
                created_at=_iso(row["created_at"]) or "",
                expires_at=_iso(row["expires_at"]),
                payload=payload,
            )
        )

    return NotificationCenterResponse(
        items=items,
        unread_count=int(unread_count or 0),
        total=len(items),
    )


@router.post("/notifications/read", response_model=MarkNotificationsReadResponse, status_code=200)
async def mark_notifications_read(
    request: MarkNotificationsReadRequest,
    ctx: CurrentUserDep,
) -> MarkNotificationsReadResponse:
    pool = get_db_pool()
    user_id = UUID(ctx.user_id)
    updated = 0

    if request.mark_all or not request.ids:
        result = await pool.execute(
            """
            UPDATE notification_queue
            SET delivered = TRUE
            WHERE user_id = $1
              AND delivered = FALSE
              AND expires_at > NOW()
            """,
            user_id,
        )
        try:
            updated = int(str(result).split()[-1])
        except (IndexError, ValueError):
            updated = 0
    else:
        notification_ids = [UUID(item_id) for item_id in request.ids]
        result = await pool.execute(
            """
            UPDATE notification_queue
            SET delivered = TRUE
            WHERE user_id = $1
              AND id = ANY($2::uuid[])
              AND expires_at > NOW()
            """,
            user_id,
            notification_ids,
        )
        try:
            updated = int(str(result).split()[-1])
        except (IndexError, ValueError):
            updated = 0

    unread_count = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM notification_queue
        WHERE user_id = $1
          AND delivered = FALSE
          AND expires_at > NOW()
        """,
        user_id,
    )
    return MarkNotificationsReadResponse(updated=updated, unread_count=int(unread_count or 0))


@router.get("/security-overview", response_model=SecurityOverviewResponse, status_code=200)
async def get_security_overview(
    ctx: CurrentUserDep,
) -> SecurityOverviewResponse:
    pool = get_db_pool()
    user_id = UUID(ctx.user_id)

    session_rows = await pool.fetch(
        """
        SELECT
            COALESCE(client_id, 'browser') AS client_id,
            COALESCE(source_ip, 'unknown') AS source_ip,
            MAX(created_at) AS last_seen,
            COUNT(*) FILTER (WHERE action_type = 'auth.login' AND outcome = 'success') AS successful_logins,
            COUNT(*) FILTER (WHERE action_type = 'auth.login' AND outcome = 'failure') AS failed_attempts,
            COUNT(*) FILTER (WHERE action_type = 'auth.refresh') AS refresh_events,
            COUNT(*) FILTER (WHERE action_type = 'auth.logout') AS logout_events,
            COUNT(*) AS activity_count
        FROM audit_logs
        WHERE actor_id = $1
          AND (
              action_type LIKE 'auth.%'
              OR action_type IN ('user.update', 'settings.update')
          )
        GROUP BY COALESCE(client_id, 'browser'), COALESCE(source_ip, 'unknown')
        ORDER BY MAX(created_at) DESC
        LIMIT 12
        """,
        user_id,
    )

    event_rows = await pool.fetch(
        """
        SELECT id, action_type, outcome, client_id, source_ip, endpoint_path, metadata, created_at
        FROM audit_logs
        WHERE actor_id = $1
          AND (
              action_type LIKE 'auth.%'
              OR action_type IN ('user.update', 'settings.update')
          )
        ORDER BY created_at DESC
        LIMIT 24
        """,
        user_id,
    )

    desktop_last_seen = await pool.fetchval(
        """
        SELECT MAX(created_at)
        FROM audit_logs
        WHERE actor_id = $1
          AND client_id IS NOT NULL
          AND client_id ILIKE '%desktop%'
        """,
        user_id,
    )
    web_last_seen = await pool.fetchval(
        """
        SELECT MAX(created_at)
        FROM audit_logs
        WHERE actor_id = $1
          AND (
              client_id IS NULL
              OR client_id ILIKE '%web%'
              OR client_id ILIKE '%portal%'
              OR client_id = 'browser'
          )
        """,
        user_id,
    )

    last_outcome_by_key: dict[tuple[str, str], str] = {}
    for row in event_rows:
        key = (
            str(row["client_id"] or "browser"),
            str(row["source_ip"] or "unknown"),
        )
        last_outcome_by_key.setdefault(key, str(row["outcome"] or "success"))

    sessions = [
        SessionSummaryResponse(
            client_id=str(row["client_id"] or "browser"),
            source_ip=str(row["source_ip"] or "unknown"),
            last_seen=_iso(row["last_seen"]) or "",
            successful_logins=int(row["successful_logins"] or 0),
            failed_attempts=int(row["failed_attempts"] or 0),
            refresh_events=int(row["refresh_events"] or 0),
            logout_events=int(row["logout_events"] or 0),
            last_outcome=last_outcome_by_key.get(
                (str(row["client_id"] or "browser"), str(row["source_ip"] or "unknown")),
                "success",
            ),
            activity_count=int(row["activity_count"] or 0),
        )
        for row in session_rows
    ]

    events = [
        SecurityEventResponse(
            id=str(row["id"]),
            action_type=str(row["action_type"]),
            outcome=str(row["outcome"]),
            client_id=str(row["client_id"] or "browser"),
            source_ip=str(row["source_ip"] or "unknown"),
            endpoint_path=row["endpoint_path"],
            created_at=_iso(row["created_at"]) or "",
            metadata=_coerce_payload(row["metadata"]),
        )
        for row in event_rows
    ]

    return SecurityOverviewResponse(
        sessions=sessions,
        events=events,
        desktop_last_seen=_iso(desktop_last_seen),
        web_last_seen=_iso(web_last_seen),
    )
