"""Tests for shell/app QThread registry shutdown."""

from __future__ import annotations

from unittest.mock import MagicMock

from shared.services import app_thread_registry as registry


def test_shutdown_app_threads_requests_stop_and_waits() -> None:
    live = MagicMock()
    live.isRunning.side_effect = [True, True, False]
    live.finished = MagicMock()
    live.finished.connect = MagicMock()
    live.request_stop = MagicMock()
    live.wait = MagicMock(return_value=True)
    registry.track_app_thread(live)

    registry.shutdown_app_threads(wait_ms=100)

    live.request_stop.assert_called_once()
    live.wait.assert_called()
