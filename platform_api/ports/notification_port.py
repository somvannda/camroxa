"""Notification service protocol interface.

Defines the contract for real-time notification delivery via WebSocket
and offline notification queuing.
"""

from __future__ import annotations

from typing import Protocol


class NotificationServicePort(Protocol):
    """Port for real-time notification delivery.

    Implementations handle pushing events to connected WebSocket clients
    and queuing notifications for users who are offline.
    """

    async def push(self, user_id: str, event: str, payload: dict) -> None:
        """Push a notification to all connected WebSocket clients for a user.

        If the user has no active WebSocket connections, the notification is
        silently dropped (use `queue` for persistent delivery).
        """
        ...

    async def queue(self, user_id: str, event: str, payload: dict) -> None:
        """Queue a notification for delivery on the user's next connection.

        Stored in the notification_queue table with a 24-hour expiration.
        Delivered in chronological order when the user reconnects.
        """
        ...
