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
    """Maintains a persistent /api/v3/ws connection for server push events."""

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
        self.setObjectName("PushNotificationWorker")
        self._ws_url_provider = ws_url_provider
        self._ws_headers_provider = ws_headers_provider
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._websocket: Any = None

    def request_stop(self) -> None:
        self._stop_event.set()
        # Unblock recv()/connect promptly — otherwise quit can destroy this
        # QThread while the OS thread is still waiting (up to ~65s).
        loop = self._loop
        websocket = self._websocket
        if loop is None:
            return
        try:
            if websocket is not None:
                asyncio.run_coroutine_threadsafe(websocket.close(), loop)
        except Exception:
            pass

    def run(self) -> None:
        try:
            asyncio.run(self._run_loop())
        except Exception as exc:
            logger.warning("Push notification worker stopped: %s", str(exc)[:120])
            self.connection_state_changed.emit("stopped")
        finally:
            self._loop = None
            self._websocket = None

    async def _run_loop(self) -> None:
        import websockets

        self._loop = asyncio.get_running_loop()
        backoff_seconds = 2
        while not self._stop_event.is_set():
            ws_url = self._ws_url_provider()
            if not ws_url:
                self.connection_state_changed.emit("waiting_for_session")
                await asyncio.sleep(1.0 if self._stop_event.is_set() else backoff_seconds)
                continue

            try:
                headers = self._ws_headers_provider() if self._ws_headers_provider else None
                connect_kwargs: dict[str, Any] = {
                    "ping_interval": None,
                    "close_timeout": 2,
                    "open_timeout": 10,
                }
                if headers:
                    connect_kwargs["additional_headers"] = headers
                async with websockets.connect(
                    ws_url,
                    **connect_kwargs,
                ) as websocket:
                    self._websocket = websocket
                    self.connection_state_changed.emit("connected")
                    backoff_seconds = 2
                    try:
                        while not self._stop_event.is_set():
                            try:
                                # Short poll so request_stop is noticed quickly even
                                # if websocket.close() is delayed.
                                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            except asyncio.TimeoutError:
                                continue

                            if message == "ping":
                                await websocket.send("pong")
                                continue

                            event, payload = self._parse_message(message)
                            if event:
                                self.notification_received.emit(event, payload)
                    finally:
                        self._websocket = None
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                close_code = getattr(exc, "code", None)
                if close_code == 4001:
                    self.connection_state_changed.emit("auth_failed")
                else:
                    logger.debug("Push websocket disconnected: %s", str(exc)[:120])
                    self.connection_state_changed.emit("disconnected")
                await asyncio.sleep(1.0 if self._stop_event.is_set() else backoff_seconds)
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
