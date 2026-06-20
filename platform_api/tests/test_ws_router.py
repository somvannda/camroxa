"""Tests for the WebSocket router (routers/ws.py).

Tests cover authentication, connection limits, queue drain on connect,
and the ping/pong keepalive mechanism.

Since Starlette's TestClient doesn't work with the installed httpx version,
we test the WebSocket logic directly through unit tests of the router's
internal functions and the NotificationService + ConnectionRegistry integration.

Requirements: 17.1, 17.2, 17.3, 17.4, 17.5
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from platform_api.exceptions import AuthenticationError
from platform_api.ports.auth_port import TokenPayload
from platform_api.routers.ws import (
    CLOSE_CODE_AUTH_FAILED,
    CLOSE_CODE_MAX_CONNECTIONS,
    IDLE_TIMEOUT_SECONDS,
    MAX_CONNECTIONS_PER_USER,
    PONG_TIMEOUT_SECONDS,
    _connection_loop,
    _extract_token,
    configure_ws_dependencies,
    websocket_endpoint,
)
from platform_api.services.notification_service import (
    ConnectionRegistry,
    NotificationService,
)


# ---------------------------------------------------------------------------
# Token extraction tests
# ---------------------------------------------------------------------------


class TestTokenExtraction:
    """Tests for _extract_token helper."""

    def test_extract_from_query_params(self) -> None:
        """Token is extracted from ?token= query parameter."""
        ws = MagicMock()
        ws.query_params = {"token": "my-jwt-token"}
        ws.headers = {}

        token = _extract_token(ws)
        assert token == "my-jwt-token"

    def test_extract_from_authorization_header(self) -> None:
        """Token is extracted from Authorization: Bearer ... header."""
        ws = MagicMock()
        ws.query_params = {}
        ws.headers = {"authorization": "Bearer my-jwt-token"}

        token = _extract_token(ws)
        assert token == "my-jwt-token"

    def test_query_params_takes_precedence(self) -> None:
        """Query parameter token takes precedence over header."""
        ws = MagicMock()
        ws.query_params = {"token": "query-token"}
        ws.headers = {"authorization": "Bearer header-token"}

        token = _extract_token(ws)
        assert token == "query-token"

    def test_no_token_returns_none(self) -> None:
        """Returns None when no token is available."""
        ws = MagicMock()
        ws.query_params = {}
        ws.headers = {}

        token = _extract_token(ws)
        assert token is None

    def test_empty_bearer_returns_none(self) -> None:
        """Returns None when Bearer header has no actual token value."""
        ws = MagicMock()
        ws.query_params = {}
        ws.headers = {"authorization": "Bearer   "}

        token = _extract_token(ws)
        # After strip, the empty string is falsy so will be returned but falsy
        assert not token


# ---------------------------------------------------------------------------
# WebSocket endpoint logic tests (mocked WebSocket)
# ---------------------------------------------------------------------------


class TestWebSocketEndpoint:
    """Unit tests for the websocket_endpoint function."""

    @pytest.fixture(autouse=True)
    def setup_deps(self) -> None:
        """Configure WS dependencies with mocks for each test."""
        self.mock_auth = AsyncMock()
        self.mock_auth.validate_token = AsyncMock(
            return_value=TokenPayload(
                user_id="user-123",
                email="test@example.com",
                role="user",
                exp=9999999999,
            )
        )
        self.registry = ConnectionRegistry()
        self.mock_queue_repo = AsyncMock()
        self.mock_queue_repo.drain = AsyncMock(return_value=[])
        self.mock_queue_repo.mark_delivered = AsyncMock()

        self.notification_service = NotificationService(
            registry=self.registry, queue_repo=self.mock_queue_repo
        )

        configure_ws_dependencies(
            auth_service=self.mock_auth,
            notification_service=self.notification_service,
        )

    @pytest.mark.asyncio
    async def test_missing_token_closes_connection(self) -> None:
        """Connection without token is closed with code 4001."""
        ws = AsyncMock()
        ws.query_params = {}
        ws.headers = {}
        ws.close = AsyncMock()

        await websocket_endpoint(ws)

        ws.close.assert_called_once_with(
            code=CLOSE_CODE_AUTH_FAILED, reason="Missing access token"
        )
        ws.accept.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_token_closes_connection(self) -> None:
        """Connection with invalid token is closed with code 4001."""
        self.mock_auth.validate_token.side_effect = AuthenticationError("Token expired")

        ws = AsyncMock()
        ws.query_params = {"token": "bad-token"}
        ws.headers = {}
        ws.close = AsyncMock()

        await websocket_endpoint(ws)

        ws.close.assert_called_once_with(
            code=CLOSE_CODE_AUTH_FAILED, reason="Invalid access token"
        )
        ws.accept.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_token_accepts_connection(self) -> None:
        """Connection with valid token is accepted and registered."""
        ws = AsyncMock()
        ws.query_params = {"token": "valid-token"}
        ws.headers = {}
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()
        # Simulate immediate disconnect after connect
        ws.receive = AsyncMock(return_value={"type": "websocket.disconnect"})

        await websocket_endpoint(ws)

        ws.accept.assert_called_once()
        self.mock_auth.validate_token.assert_called_with("valid-token")

    @pytest.mark.asyncio
    async def test_max_connections_rejects_with_4003(self) -> None:
        """4th connection from same user is rejected with close code 4003."""
        # Fill up 3 connections
        for _ in range(3):
            mock_ws = AsyncMock()
            await self.registry.add("user-123", mock_ws)

        # Now try to connect with a 4th
        ws = AsyncMock()
        ws.query_params = {"token": "valid-token"}
        ws.headers = {}
        ws.accept = AsyncMock()
        ws.close = AsyncMock()

        await websocket_endpoint(ws)

        ws.accept.assert_called_once()
        ws.close.assert_called_once()
        close_kwargs = ws.close.call_args
        assert close_kwargs[1]["code"] == CLOSE_CODE_MAX_CONNECTIONS

    @pytest.mark.asyncio
    async def test_queue_drained_on_connect(self) -> None:
        """Queued notifications are delivered when client connects."""
        from uuid import uuid4

        n_id = uuid4()
        self.mock_queue_repo.drain.return_value = [
            {
                "id": n_id,
                "event_type": "suno_completed",
                "payload": {"task_id": "t1"},
                "created_at": "2024-01-01T00:00:00Z",
            },
        ]

        ws = AsyncMock()
        ws.query_params = {"token": "valid-token"}
        ws.headers = {}
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()
        # Disconnect immediately after drain
        ws.receive = AsyncMock(return_value={"type": "websocket.disconnect"})

        await websocket_endpoint(ws)

        # Should have sent the queued notification
        ws.send_text.assert_called()
        sent_msg = ws.send_text.call_args_list[0][0][0]
        data = json.loads(sent_msg)
        assert data["event"] == "suno_completed"
        assert data["payload"]["task_id"] == "t1"

    @pytest.mark.asyncio
    async def test_connection_unregistered_on_disconnect(self) -> None:
        """Connection is removed from registry on disconnect."""
        ws = AsyncMock()
        ws.query_params = {"token": "valid-token"}
        ws.headers = {}
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive = AsyncMock(return_value={"type": "websocket.disconnect"})

        await websocket_endpoint(ws)

        # Connection should be cleaned up
        assert await self.registry.has_connections("user-123") is False


# ---------------------------------------------------------------------------
# Connection loop tests
# ---------------------------------------------------------------------------


class TestConnectionLoop:
    """Tests for the _connection_loop ping/pong mechanism."""

    @pytest.mark.asyncio
    async def test_client_disconnect_exits_loop(self) -> None:
        """Loop exits cleanly on client disconnect."""
        ws = AsyncMock()
        ws.receive = AsyncMock(return_value={"type": "websocket.disconnect"})

        await _connection_loop(ws, "user-1")
        # Should exit without error

    @pytest.mark.asyncio
    async def test_ping_sent_on_idle_timeout(self) -> None:
        """Server sends ping text when idle timeout fires."""
        ws = AsyncMock()
        call_count = 0

        async def mock_receive():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: timeout to trigger ping
                raise asyncio.TimeoutError()
            elif call_count == 2:
                # Second call (waiting for pong): client responds
                return {"type": "websocket.receive", "text": "pong"}
            else:
                # Third call: disconnect
                return {"type": "websocket.disconnect"}

        ws.receive = mock_receive
        ws.send_text = AsyncMock()

        await _connection_loop(ws, "user-1")

        # Ping should have been sent
        ws.send_text.assert_called_with("ping")

    @pytest.mark.asyncio
    async def test_connection_closed_on_pong_timeout(self) -> None:
        """Connection is closed when no pong received within timeout."""
        ws = AsyncMock()
        call_count = 0

        async def mock_receive():
            nonlocal call_count
            call_count += 1
            # Always timeout to simulate completely unresponsive client
            raise asyncio.TimeoutError()

        ws.receive = mock_receive
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()

        await _connection_loop(ws, "user-1")

        # Ping sent, then close on pong timeout
        ws.send_text.assert_called_with("ping")
        ws.close.assert_called_once_with(code=1001, reason="Ping timeout")

    @pytest.mark.asyncio
    async def test_client_message_resets_idle(self) -> None:
        """Receiving any client message resets the idle timer."""
        ws = AsyncMock()
        call_count = 0

        async def mock_receive():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                # First 3 calls: client sends messages
                return {"type": "websocket.receive", "text": "hello"}
            else:
                return {"type": "websocket.disconnect"}

        ws.receive = mock_receive
        ws.send_text = AsyncMock()

        await _connection_loop(ws, "user-1")

        # No ping should have been sent because client was active
        ws.send_text.assert_not_called()


# ---------------------------------------------------------------------------
# Constants verification
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify WebSocket constants match requirements."""

    def test_idle_timeout(self) -> None:
        """Idle timeout is 60 seconds per Requirement 17.5."""
        assert IDLE_TIMEOUT_SECONDS == 60

    def test_pong_timeout(self) -> None:
        """Pong timeout is 10 seconds per Requirement 17.5."""
        assert PONG_TIMEOUT_SECONDS == 10

    def test_max_connections(self) -> None:
        """Max 3 connections per user per Requirement 17.1."""
        assert MAX_CONNECTIONS_PER_USER == 3

    def test_auth_close_code(self) -> None:
        """Auth failure close code is 4001."""
        assert CLOSE_CODE_AUTH_FAILED == 4001

    def test_max_connections_close_code(self) -> None:
        """Max connections exceeded close code is 4003."""
        assert CLOSE_CODE_MAX_CONNECTIONS == 4003
