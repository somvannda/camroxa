"""Background WebSocket client for platform push notifications."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class PushNotificationWorker(QThread):
    """Maintains a persistent /api/v1/ws connection for server push events."""

    notification_received = Signal(str, object)
    connection_state_changed = Signal(str)

    def __init__(
        self,
        *,
        ws_url_provider: Callable[[], str | None],
        ws_headers_provider: Callable[[], dict[str, str] | None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ws_url_provider = ws_url_provider
        self._ws_headers_provider = ws_headers_provider
        self._stop_event = threading.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            asyncio.run(self._run_loop())
        except Exception as exc:
            logger.warning("Push notification worker stopped: %s", str(exc)[:120])
            self.connection_state_changed.emit("stopped")

    async def _run_loop(self) -> None:
        import websockets

        backoff_seconds = 2
        while not self._stop_event.is_set():
            ws_url = self._ws_url_provider()
            if not ws_url:
                self.connection_state_changed.emit("waiting_for_session")
                await asyncio.sleep(backoff_seconds)
                continue

            try:
                headers = self._ws_headers_provider() if self._ws_headers_provider else None
                connect_kwargs: dict[str, Any] = {
                    "ping_interval": None,
                    "close_timeout": 5,
                    "open_timeout": 10,
                }
                if headers:
                    connect_kwargs["additional_headers"] = headers
                async with websockets.connect(
                    ws_url,
                    **connect_kwargs,
                ) as websocket:
                    self.connection_state_changed.emit("connected")
                    backoff_seconds = 2
                    while not self._stop_event.is_set():
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=65)
                        except asyncio.TimeoutError:
                            continue

                        if message == "ping":
                            await websocket.send("pong")
                            continue

                        event, payload = self._parse_message(message)
                        if event:
                            self.notification_received.emit(event, payload)
            except Exception as exc:
                close_code = getattr(exc, "code", None)
                if close_code == 4001:
                    self.connection_state_changed.emit("auth_failed")
                else:
                    logger.debug("Push websocket disconnected: %s", str(exc)[:120])
                    self.connection_state_changed.emit("disconnected")
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 30)

    @staticmethod
    def _parse_message(message: str) -> tuple[str, dict[str, Any]]:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return "", {}
        if not isinstance(data, dict):
            return "", {}
        event = str(data.get("event") or "").strip()
        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        return event, payload
