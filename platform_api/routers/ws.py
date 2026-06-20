"""WebSocket router for real-time notification delivery.

Provides the /ws endpoint for authenticated WebSocket connections.
Implements connection lifecycle management with JWT authentication,
per-user connection registry, ping/pong keepalive, and notification
queue drain on connect.

Requirements: 17.1, 17.2, 17.3, 17.4, 17.5
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from platform_api.ports.auth_port import TokenPayload

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(tags=["websocket"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Ping/pong timing (Requirement 17.5)
IDLE_TIMEOUT_SECONDS = 60  # Send ping after this many seconds of idle
PONG_TIMEOUT_SECONDS = 10  # Close connection if no pong within this time

# Connection limit (Requirement 17.1)
MAX_CONNECTIONS_PER_USER = 3

# Close codes
CLOSE_CODE_AUTH_FAILED = 4001
CLOSE_CODE_MAX_CONNECTIONS = 4003


# ---------------------------------------------------------------------------
# Protocols for dependencies
# ---------------------------------------------------------------------------


class AuthServiceProtocol(Protocol):
    """Minimal protocol for token validation."""

    async def validate_token(self, token: str) -> TokenPayload:
        """Validate an access token and return its decoded payload.

        Raises AuthenticationError if invalid.
        """
        ...


class NotificationServiceProtocol(Protocol):
    """Minimal protocol for the notification service."""

    @property
    def registry(self) -> "ConnectionRegistryProtocol":
        ...

    async def drain_queue(self, user_id: str, websocket: WebSocket) -> None:
        ...


class ConnectionRegistryProtocol(Protocol):
    """Minimal protocol for the connection registry."""

    async def add(self, user_id: str, websocket: WebSocket) -> bool:
        ...

    async def remove(self, user_id: str, websocket: WebSocket) -> None:
        ...


# ---------------------------------------------------------------------------
# Module-level dependency placeholders (configured at startup)
# ---------------------------------------------------------------------------

_auth_service: AuthServiceProtocol | None = None
_notification_service: NotificationServiceProtocol | None = None


def configure_ws_dependencies(
    *,
    auth_service: AuthServiceProtocol,
    notification_service: NotificationServiceProtocol,
) -> None:
    """Configure WebSocket router dependencies at application startup.

    Args:
        auth_service: Service for JWT token validation.
        notification_service: Service for push/queue notifications and connection registry.
    """
    global _auth_service, _notification_service
    _auth_service = auth_service
    _notification_service = notification_service


def _get_auth_service() -> AuthServiceProtocol:
    if _auth_service is None:
        raise RuntimeError(
            "WebSocket dependencies not configured. Call configure_ws_dependencies() at startup."
        )
    return _auth_service


def _get_notification_service() -> NotificationServiceProtocol:
    if _notification_service is None:
        raise RuntimeError(
            "WebSocket dependencies not configured. Call configure_ws_dependencies() at startup."
        )
    return _notification_service


# ---------------------------------------------------------------------------
# Token extraction from WebSocket handshake
# ---------------------------------------------------------------------------


def _extract_token(websocket: WebSocket) -> str | None:
    """Extract access token from WebSocket connection query params or headers.

    Looks for the token in:
    1. Query parameter: ?token=<access_token>
    2. Authorization header: Bearer <access_token>

    Returns:
        The token string, or None if not found.
    """
    # Try query parameter first
    token = websocket.query_params.get("token")
    if token:
        return token

    # Try Authorization header
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    return None


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time notifications.

    Connection lifecycle (Requirements 17.1, 17.4, 17.5):
    1. Extract access token from query params (?token=...) or Authorization header.
    2. Validate token via AuthService. Close with 4001 if invalid.
    3. Register connection in the per-user registry. Close with 4003 if max reached.
    4. Drain queued notifications (chronological order).
    5. Enter receive loop with ping/pong keepalive:
       - If idle for 60s, send ping frame.
       - If no pong within 10s, close connection.
    6. On disconnect: unregister connection from registry.
    """
    auth_service = _get_auth_service()
    notification_service = _get_notification_service()
    registry = notification_service.registry

    # --- Step 1: Extract token ---
    token = _extract_token(websocket)
    if not token:
        await websocket.close(code=CLOSE_CODE_AUTH_FAILED, reason="Missing access token")
        return

    # --- Step 2: Validate token ---
    try:
        payload: TokenPayload = await auth_service.validate_token(token)
    except Exception as exc:
        logger.warning("WebSocket auth failed: %s", str(exc)[:100])
        await websocket.close(code=CLOSE_CODE_AUTH_FAILED, reason="Invalid access token")
        return

    user_id = payload.user_id

    # --- Step 3: Accept connection and register ---
    await websocket.accept()

    registered = await registry.add(user_id, websocket)
    if not registered:
        await websocket.close(
            code=CLOSE_CODE_MAX_CONNECTIONS,
            reason=f"Maximum {MAX_CONNECTIONS_PER_USER} concurrent connections exceeded",
        )
        return

    logger.info("WebSocket connected: user_id=%s", user_id)

    try:
        # --- Step 4: Drain queued notifications ---
        await notification_service.drain_queue(user_id, websocket)

        # --- Step 5: Receive loop with ping/pong keepalive ---
        await _connection_loop(websocket, user_id)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user_id=%s", user_id)
    except Exception as exc:
        logger.error(
            "WebSocket error for user %s: %s",
            user_id,
            str(exc)[:200],
        )
    finally:
        # --- Step 6: Unregister connection ---
        await registry.remove(user_id, websocket)
        logger.info("WebSocket unregistered: user_id=%s", user_id)


# ---------------------------------------------------------------------------
# Connection loop with ping/pong
# ---------------------------------------------------------------------------


async def _connection_loop(websocket: WebSocket, user_id: str) -> None:
    """Run the WebSocket receive loop with ping/pong keepalive.

    Sends a ping frame after 60 seconds of idle. If no pong is received
    within 10 seconds, the connection is closed.

    Args:
        websocket: The accepted WebSocket connection.
        user_id: The authenticated user's ID.
    """
    while True:
        try:
            # Wait for incoming message with idle timeout
            message = await asyncio.wait_for(
                websocket.receive(),
                timeout=IDLE_TIMEOUT_SECONDS,
            )

            # Handle the received message
            msg_type = message.get("type", "")

            if msg_type == "websocket.disconnect":
                # Client initiated disconnect
                break

            # Client sent a text/bytes message — we don't process client messages
            # but receiving them resets the idle timer
            if msg_type in ("websocket.receive",):
                # Check if it's a text message and possibly a pong response
                text = message.get("text", "")
                if text == "pong":
                    # Client-side pong response (application-level)
                    continue
                # Otherwise ignore client messages (notifications are server->client)
                continue

        except asyncio.TimeoutError:
            # No message received for IDLE_TIMEOUT_SECONDS — send ping
            try:
                await websocket.send_text("ping")
            except Exception:
                # Connection broken during ping send
                break

            # Wait for pong response
            try:
                response = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=PONG_TIMEOUT_SECONDS,
                )
                msg_type = response.get("type", "")
                if msg_type == "websocket.disconnect":
                    break
                # Any response from client counts as alive
            except asyncio.TimeoutError:
                # No pong within timeout — close connection
                logger.info(
                    "WebSocket ping timeout for user %s. Closing connection.",
                    user_id,
                )
                try:
                    await websocket.close(code=1001, reason="Ping timeout")
                except Exception:
                    pass
                break

        except WebSocketDisconnect:
            raise
        except Exception as exc:
            logger.error(
                "Unexpected error in WebSocket loop for user %s: %s",
                user_id,
                str(exc)[:200],
            )
            break
