"""Notification service implementing NotificationServicePort.

Provides real-time push notifications to connected WebSocket clients
and queues notifications for offline users with 24-hour expiration.

Requirements: 17.1, 17.2, 17.3, 17.4, 17.5
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from fastapi import WebSocket

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Repository Protocol for notification queue persistence
# ---------------------------------------------------------------------------


class NotificationQueueRepository(Protocol):
    """Minimal protocol for the notification_queue table operations."""

    async def enqueue(
        self,
        notification_id: UUID,
        user_id: str,
        event_type: str,
        payload: dict[str, Any],
        expires_at: datetime,
    ) -> None:
        """Insert a notification into the queue for offline delivery."""
        ...

    async def drain(self, user_id: str) -> list[dict[str, Any]]:
        """Return all undelivered, non-expired notifications for a user in chronological order.

        Each dict has keys: id, event_type, payload, created_at.
        """
        ...

    async def mark_delivered(self, notification_ids: list[UUID]) -> None:
        """Mark notifications as delivered so they are not re-sent."""
        ...

    async def purge_expired(self) -> int:
        """Delete expired notifications. Returns count of deleted rows."""
        ...


# ---------------------------------------------------------------------------
# AsyncPG Pool Protocol (same as user_repo)
# ---------------------------------------------------------------------------


class AsyncPGPool(Protocol):
    """Minimal protocol for an asyncpg connection pool."""

    async def fetchrow(self, query: str, *args: Any) -> Any:
        ...

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        ...

    async def fetchval(self, query: str, *args: Any) -> Any:
        ...

    async def execute(self, query: str, *args: Any) -> str:
        ...


# ---------------------------------------------------------------------------
# Connection Registry
# ---------------------------------------------------------------------------


class ConnectionRegistry:
    """In-memory registry of active WebSocket connections per user.

    Thread-safe via asyncio (single event loop). Maps user_id to a list
    of active WebSocket connections.
    """

    MAX_CONNECTIONS_PER_USER = 3

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def add(self, user_id: str, websocket: WebSocket) -> bool:
        """Register a WebSocket connection for a user.

        Returns:
            True if successfully added, False if the user already has
            the maximum number of connections (3).
        """
        async with self._lock:
            conns = self._connections.setdefault(user_id, [])
            if len(conns) >= self.MAX_CONNECTIONS_PER_USER:
                return False
            conns.append(websocket)
            return True

    async def remove(self, user_id: str, websocket: WebSocket) -> None:
        """Unregister a WebSocket connection for a user."""
        async with self._lock:
            conns = self._connections.get(user_id, [])
            try:
                conns.remove(websocket)
            except ValueError:
                pass
            if not conns:
                self._connections.pop(user_id, None)

    async def get_connections(self, user_id: str) -> list[WebSocket]:
        """Return a copy of the active connections list for a user."""
        async with self._lock:
            return list(self._connections.get(user_id, []))

    async def has_connections(self, user_id: str) -> bool:
        """Check if a user has any active WebSocket connections."""
        async with self._lock:
            conns = self._connections.get(user_id, [])
            return len(conns) > 0


# ---------------------------------------------------------------------------
# Default Notification Queue Repository (asyncpg-based)
# ---------------------------------------------------------------------------


class PGNotificationQueueRepository:
    """PostgreSQL-backed notification queue repository.

    Uses asyncpg pool to store and retrieve queued notifications
    from the notification_queue table.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def enqueue(
        self,
        notification_id: UUID,
        user_id: str,
        event_type: str,
        payload: dict[str, Any],
        expires_at: datetime,
    ) -> None:
        """Insert a notification into the queue."""
        await self._pool.execute(
            """
            INSERT INTO notification_queue (id, user_id, event_type, payload, delivered, created_at, expires_at)
            VALUES ($1, $2::uuid, $3, $4::jsonb, FALSE, NOW(), $5)
            """,
            notification_id,
            user_id,
            event_type,
            json.dumps(payload),
            expires_at,
        )

    async def drain(self, user_id: str) -> list[dict[str, Any]]:
        """Return all undelivered, non-expired notifications in chronological order."""
        rows = await self._pool.fetch(
            """
            SELECT id, event_type, payload, created_at
            FROM notification_queue
            WHERE user_id = $1::uuid
              AND delivered = FALSE
              AND expires_at > NOW()
            ORDER BY created_at ASC
            """,
            user_id,
        )
        results = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            results.append({
                "id": row["id"],
                "event_type": row["event_type"],
                "payload": payload,
                "created_at": row["created_at"],
            })
        return results

    async def mark_delivered(self, notification_ids: list[UUID]) -> None:
        """Mark notifications as delivered."""
        if not notification_ids:
            return
        await self._pool.execute(
            """
            UPDATE notification_queue
            SET delivered = TRUE
            WHERE id = ANY($1::uuid[])
            """,
            notification_ids,
        )

    async def purge_expired(self) -> int:
        """Delete expired notifications. Returns count of deleted rows."""
        result = await self._pool.execute(
            "DELETE FROM notification_queue WHERE expires_at <= NOW()"
        )
        # asyncpg returns "DELETE N"
        try:
            return int(result.split()[-1])
        except (IndexError, ValueError):
            return 0


# ---------------------------------------------------------------------------
# Notification Service
# ---------------------------------------------------------------------------


class NotificationService:
    """Notification service implementing NotificationServicePort.

    Pushes real-time events to connected WebSocket clients and queues
    notifications for users who are offline.

    Args:
        registry: The in-memory WebSocket connection registry.
        queue_repo: Repository for persisting queued notifications.
    """

    # Notification queue expiration time
    QUEUE_EXPIRATION_HOURS = 24

    def __init__(
        self,
        registry: ConnectionRegistry,
        queue_repo: NotificationQueueRepository | None = None,
    ) -> None:
        self._registry = registry
        self._queue_repo = queue_repo

    @property
    def registry(self) -> ConnectionRegistry:
        """Expose the connection registry for WebSocket endpoint use."""
        return self._registry

    async def push(self, user_id: str, event: str, payload: dict) -> None:
        """Push a notification to all connected WebSocket clients for a user.

        If the user has no active connections, the notification is silently
        dropped. Use `queue()` for guaranteed delivery.

        The message format sent over WebSocket is JSON:
            {"event": "<event_type>", "payload": {...}}
        """
        connections = await self._registry.get_connections(user_id)
        if not connections:
            logger.debug(
                "No active connections for user %s. Notification dropped (event=%s).",
                user_id,
                event,
            )
            return

        message = json.dumps({"event": event, "payload": payload})

        # Send to all connections; remove any that have closed
        disconnected: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception as exc:
                logger.warning(
                    "Failed to send notification to user %s: %s",
                    user_id,
                    str(exc)[:100],
                )
                disconnected.append(ws)

        # Clean up disconnected sockets
        for ws in disconnected:
            await self._registry.remove(user_id, ws)

    async def queue(self, user_id: str, event: str, payload: dict) -> None:
        """Queue a notification for delivery on the user's next connection.

        Stored in the notification_queue table with a 24-hour expiration.
        If no queue repository is configured, logs a warning and drops.
        """
        if self._queue_repo is None:
            logger.warning(
                "Notification queue repository not configured. "
                "Dropping queued notification for user %s (event=%s).",
                user_id,
                event,
            )
            return

        notification_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self.QUEUE_EXPIRATION_HOURS
        )

        try:
            await self._queue_repo.enqueue(
                notification_id=notification_id,
                user_id=user_id,
                event_type=event,
                payload=payload,
                expires_at=expires_at,
            )
            logger.info(
                "Queued notification %s for user %s (event=%s, expires=%s).",
                notification_id,
                user_id,
                event,
                expires_at.isoformat(),
            )
        except Exception as exc:
            logger.error(
                "Failed to queue notification for user %s: %s",
                user_id,
                str(exc)[:200],
            )

    async def drain_queue(self, user_id: str, websocket: WebSocket) -> None:
        """Deliver all queued notifications to a newly connected client.

        Sends queued notifications in chronological order and marks them
        as delivered.

        Args:
            user_id: The user who just reconnected.
            websocket: The WebSocket connection to deliver notifications through.
        """
        if self._queue_repo is None:
            return

        try:
            notifications = await self._queue_repo.drain(user_id)
        except Exception as exc:
            logger.error(
                "Failed to drain notification queue for user %s: %s",
                user_id,
                str(exc)[:200],
            )
            return

        if not notifications:
            return

        delivered_ids: list[UUID] = []
        for notification in notifications:
            message = json.dumps({
                "event": notification["event_type"],
                "payload": notification["payload"],
            })
            try:
                await websocket.send_text(message)
                delivered_ids.append(notification["id"])
            except Exception as exc:
                logger.warning(
                    "Failed to deliver queued notification %s to user %s: %s",
                    notification["id"],
                    user_id,
                    str(exc)[:100],
                )
                break  # Stop delivering if connection is broken

        # Mark successfully delivered notifications
        if delivered_ids:
            try:
                await self._queue_repo.mark_delivered(delivered_ids)
                logger.info(
                    "Delivered %d queued notifications to user %s.",
                    len(delivered_ids),
                    user_id,
                )
            except Exception as exc:
                logger.error(
                    "Failed to mark notifications as delivered for user %s: %s",
                    user_id,
                    str(exc)[:200],
                )
