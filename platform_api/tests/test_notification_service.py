"""Tests for NotificationService and ConnectionRegistry.

Requirements: 17.1, 17.2, 17.3, 17.4, 17.5
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from platform_api.services.notification_service import (
    ConnectionRegistry,
    NotificationService,
    PGNotificationQueueRepository,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry() -> ConnectionRegistry:
    return ConnectionRegistry()


@pytest.fixture
def mock_queue_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.enqueue = AsyncMock()
    repo.drain = AsyncMock(return_value=[])
    repo.mark_delivered = AsyncMock()
    repo.purge_expired = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def service(registry: ConnectionRegistry, mock_queue_repo: AsyncMock) -> NotificationService:
    return NotificationService(registry=registry, queue_repo=mock_queue_repo)


@pytest.fixture
def mock_websocket() -> AsyncMock:
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# ConnectionRegistry Tests
# ---------------------------------------------------------------------------


class TestConnectionRegistry:
    """Tests for the in-memory per-user connection registry."""

    @pytest.mark.asyncio
    async def test_add_connection(self, registry: ConnectionRegistry) -> None:
        """A connection can be added for a user."""
        ws = AsyncMock()
        result = await registry.add("user-1", ws)
        assert result is True
        assert await registry.has_connections("user-1") is True

    @pytest.mark.asyncio
    async def test_max_connections_enforced(self, registry: ConnectionRegistry) -> None:
        """Maximum 3 concurrent connections per user; 4th is rejected."""
        user_id = "user-1"
        for _ in range(3):
            result = await registry.add(user_id, AsyncMock())
            assert result is True

        # 4th connection should be rejected
        result = await registry.add(user_id, AsyncMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_connection(self, registry: ConnectionRegistry) -> None:
        """Removing a connection frees a slot."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()

        await registry.add("user-1", ws1)
        await registry.add("user-1", ws2)
        await registry.add("user-1", ws3)

        # Remove one, then adding a new one should succeed
        await registry.remove("user-1", ws2)
        ws4 = AsyncMock()
        result = await registry.add("user-1", ws4)
        assert result is True

    @pytest.mark.asyncio
    async def test_remove_nonexistent_connection(self, registry: ConnectionRegistry) -> None:
        """Removing a connection that isn't registered doesn't raise."""
        ws = AsyncMock()
        # Should not raise
        await registry.remove("user-1", ws)

    @pytest.mark.asyncio
    async def test_has_connections_false_when_empty(self, registry: ConnectionRegistry) -> None:
        """has_connections returns False for users with no connections."""
        assert await registry.has_connections("no-user") is False

    @pytest.mark.asyncio
    async def test_get_connections_returns_copy(self, registry: ConnectionRegistry) -> None:
        """get_connections returns a copy, not a reference to internal list."""
        ws = AsyncMock()
        await registry.add("user-1", ws)
        conns = await registry.get_connections("user-1")
        assert len(conns) == 1
        conns.clear()
        # Internal state not affected
        assert await registry.has_connections("user-1") is True

    @pytest.mark.asyncio
    async def test_remove_all_cleans_up_user_entry(self, registry: ConnectionRegistry) -> None:
        """Removing all connections for a user cleans up the internal dict."""
        ws = AsyncMock()
        await registry.add("user-1", ws)
        await registry.remove("user-1", ws)
        assert await registry.has_connections("user-1") is False


# ---------------------------------------------------------------------------
# NotificationService.push Tests
# ---------------------------------------------------------------------------


class TestNotificationServicePush:
    """Tests for the push method."""

    @pytest.mark.asyncio
    async def test_push_to_connected_user(
        self, service: NotificationService, registry: ConnectionRegistry
    ) -> None:
        """push sends JSON message to all connected WebSocket clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await registry.add("user-1", ws1)
        await registry.add("user-1", ws2)

        await service.push("user-1", "suno_completed", {"task_id": "abc123"})

        expected_msg = json.dumps({"event": "suno_completed", "payload": {"task_id": "abc123"}})
        ws1.send_text.assert_called_once_with(expected_msg)
        ws2.send_text.assert_called_once_with(expected_msg)

    @pytest.mark.asyncio
    async def test_push_to_offline_user_is_dropped(
        self, service: NotificationService
    ) -> None:
        """push silently drops notification when user has no connections."""
        # Should not raise
        await service.push("offline-user", "event", {"key": "value"})

    @pytest.mark.asyncio
    async def test_push_removes_disconnected_sockets(
        self, service: NotificationService, registry: ConnectionRegistry
    ) -> None:
        """push removes WebSocket connections that fail on send."""
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_text.side_effect = RuntimeError("Connection closed")

        await registry.add("user-1", ws_good)
        await registry.add("user-1", ws_bad)

        await service.push("user-1", "event", {"data": 1})

        # Good socket should have received the message
        ws_good.send_text.assert_called_once()
        # Bad socket should have been removed from registry
        conns = await registry.get_connections("user-1")
        assert ws_bad not in conns
        assert ws_good in conns


# ---------------------------------------------------------------------------
# NotificationService.queue Tests
# ---------------------------------------------------------------------------


class TestNotificationServiceQueue:
    """Tests for the queue method."""

    @pytest.mark.asyncio
    async def test_queue_stores_notification(
        self, service: NotificationService, mock_queue_repo: AsyncMock
    ) -> None:
        """queue calls repository to store the notification with 24h expiry."""
        await service.queue("user-1", "suno_completed", {"task_id": "t1"})

        mock_queue_repo.enqueue.assert_called_once()
        call_kwargs = mock_queue_repo.enqueue.call_args[1]
        assert call_kwargs["user_id"] == "user-1"
        assert call_kwargs["event_type"] == "suno_completed"
        assert call_kwargs["payload"] == {"task_id": "t1"}
        # Expires within 24 hours from now
        expires_at = call_kwargs["expires_at"]
        now = datetime.now(timezone.utc)
        assert expires_at > now
        assert expires_at <= now + timedelta(hours=24, seconds=5)

    @pytest.mark.asyncio
    async def test_queue_without_repo_logs_warning(
        self, registry: ConnectionRegistry
    ) -> None:
        """queue without a configured repository logs but doesn't raise."""
        service = NotificationService(registry=registry, queue_repo=None)
        # Should not raise
        await service.queue("user-1", "event", {"data": 1})


# ---------------------------------------------------------------------------
# NotificationService.drain_queue Tests
# ---------------------------------------------------------------------------


class TestNotificationServiceDrainQueue:
    """Tests for the drain_queue method."""

    @pytest.mark.asyncio
    async def test_drain_delivers_in_chronological_order(
        self, service: NotificationService, mock_queue_repo: AsyncMock
    ) -> None:
        """drain_queue sends queued notifications in chronological order."""
        ws = AsyncMock()
        now = datetime.now(timezone.utc)
        notifications = [
            {
                "id": uuid4(),
                "event_type": "suno_completed",
                "payload": {"task_id": "t1"},
                "created_at": now - timedelta(hours=2),
            },
            {
                "id": uuid4(),
                "event_type": "image_completed",
                "payload": {"job_id": "j1"},
                "created_at": now - timedelta(hours=1),
            },
        ]
        mock_queue_repo.drain.return_value = notifications

        await service.drain_queue("user-1", ws)

        # Both notifications should be sent
        assert ws.send_text.call_count == 2
        # First call should be the older notification
        first_msg = json.loads(ws.send_text.call_args_list[0][0][0])
        assert first_msg["event"] == "suno_completed"
        second_msg = json.loads(ws.send_text.call_args_list[1][0][0])
        assert second_msg["event"] == "image_completed"

        # All should be marked as delivered
        mock_queue_repo.mark_delivered.assert_called_once()
        delivered_ids = mock_queue_repo.mark_delivered.call_args[0][0]
        assert len(delivered_ids) == 2

    @pytest.mark.asyncio
    async def test_drain_stops_on_send_failure(
        self, service: NotificationService, mock_queue_repo: AsyncMock
    ) -> None:
        """drain_queue stops delivering when WebSocket send fails."""
        ws = AsyncMock()
        now = datetime.now(timezone.utc)
        n1_id = uuid4()
        n2_id = uuid4()
        notifications = [
            {
                "id": n1_id,
                "event_type": "event1",
                "payload": {"a": 1},
                "created_at": now - timedelta(hours=2),
            },
            {
                "id": n2_id,
                "event_type": "event2",
                "payload": {"b": 2},
                "created_at": now - timedelta(hours=1),
            },
        ]
        mock_queue_repo.drain.return_value = notifications

        # First send succeeds, second fails
        ws.send_text.side_effect = [None, RuntimeError("Connection closed")]

        await service.drain_queue("user-1", ws)

        # Only first notification should be marked delivered
        mock_queue_repo.mark_delivered.assert_called_once()
        delivered_ids = mock_queue_repo.mark_delivered.call_args[0][0]
        assert delivered_ids == [n1_id]

    @pytest.mark.asyncio
    async def test_drain_empty_queue(
        self, service: NotificationService, mock_queue_repo: AsyncMock
    ) -> None:
        """drain_queue does nothing when queue is empty."""
        ws = AsyncMock()
        mock_queue_repo.drain.return_value = []

        await service.drain_queue("user-1", ws)

        ws.send_text.assert_not_called()
        mock_queue_repo.mark_delivered.assert_not_called()

    @pytest.mark.asyncio
    async def test_drain_without_repo(self, registry: ConnectionRegistry) -> None:
        """drain_queue does nothing when no queue repository is configured."""
        service = NotificationService(registry=registry, queue_repo=None)
        ws = AsyncMock()
        await service.drain_queue("user-1", ws)
        ws.send_text.assert_not_called()


# ---------------------------------------------------------------------------
# PGNotificationQueueRepository Tests (with mock pool)
# ---------------------------------------------------------------------------


class TestPGNotificationQueueRepository:
    """Tests for the PostgreSQL-backed notification queue repository."""

    @pytest.mark.asyncio
    async def test_enqueue(self) -> None:
        """enqueue inserts a row into the notification_queue table."""
        pool = AsyncMock()
        repo = PGNotificationQueueRepository(pool)

        nid = uuid4()
        expires = datetime.now(timezone.utc) + timedelta(hours=24)

        await repo.enqueue(
            notification_id=nid,
            user_id="user-1",
            event_type="suno_completed",
            payload={"task_id": "t1"},
            expires_at=expires,
        )

        pool.execute.assert_called_once()
        call_args = pool.execute.call_args[0]
        assert "INSERT INTO notification_queue" in call_args[0]
        assert call_args[1] == nid
        assert call_args[2] == "user-1"
        assert call_args[3] == "suno_completed"
        assert json.loads(call_args[4]) == {"task_id": "t1"}

    @pytest.mark.asyncio
    async def test_drain_returns_chronological(self) -> None:
        """drain returns notifications ordered by created_at ASC."""
        pool = AsyncMock()
        n1_id = uuid4()
        n2_id = uuid4()
        now = datetime.now(timezone.utc)

        pool.fetch.return_value = [
            {
                "id": n1_id,
                "event_type": "event1",
                "payload": json.dumps({"a": 1}),
                "created_at": now - timedelta(hours=2),
            },
            {
                "id": n2_id,
                "event_type": "event2",
                "payload": json.dumps({"b": 2}),
                "created_at": now - timedelta(hours=1),
            },
        ]

        repo = PGNotificationQueueRepository(pool)
        results = await repo.drain("user-1")

        assert len(results) == 2
        assert results[0]["event_type"] == "event1"
        assert results[0]["payload"] == {"a": 1}
        assert results[1]["event_type"] == "event2"

    @pytest.mark.asyncio
    async def test_mark_delivered(self) -> None:
        """mark_delivered updates delivered flag for given IDs."""
        pool = AsyncMock()
        repo = PGNotificationQueueRepository(pool)

        ids = [uuid4(), uuid4()]
        await repo.mark_delivered(ids)

        pool.execute.assert_called_once()
        call_args = pool.execute.call_args[0]
        assert "UPDATE notification_queue" in call_args[0]
        assert call_args[1] == ids

    @pytest.mark.asyncio
    async def test_mark_delivered_empty_list(self) -> None:
        """mark_delivered does nothing with an empty list."""
        pool = AsyncMock()
        repo = PGNotificationQueueRepository(pool)

        await repo.mark_delivered([])
        pool.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_purge_expired(self) -> None:
        """purge_expired deletes expired notifications."""
        pool = AsyncMock()
        pool.execute.return_value = "DELETE 5"
        repo = PGNotificationQueueRepository(pool)

        count = await repo.purge_expired()
        assert count == 5
