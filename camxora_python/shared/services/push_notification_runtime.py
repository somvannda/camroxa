"""Start/stop desktop WebSocket push notifications and refresh workspace state."""

from __future__ import annotations

from PySide6.QtCore import QObject

from shared.lib.ws_url import build_platform_ws_auth_headers, build_platform_ws_url
from shared.models.push_events import WORKSPACE_CHANGED
from shared.services.push_notification_hub import PushNotificationHub
from shared.services.session_service import SessionService
from shared.services.setup_readiness_service import refresh_setup_readiness
from shared.workers.data_workers import WorkspacePushRefreshWorker
from shared.workers.push_notification_worker import PushNotificationWorker


class PushNotificationRuntime(QObject):
    """Owns the WebSocket worker lifecycle for the signed-in desktop session."""

    def __init__(self, session: SessionService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._worker: PushNotificationWorker | None = None
        self._refresh_worker: WorkspacePushRefreshWorker | None = None
        self._hub = PushNotificationHub.instance()
        self._hub.event_received.connect(self._on_push_event)

    def start(self) -> None:
        self.stop()
        self._worker = PushNotificationWorker(
            ws_url_provider=self._build_ws_url,
            ws_headers_provider=self._build_ws_headers,
            parent=self,
        )
        self._worker.notification_received.connect(self._hub.dispatch)
        self._worker.connection_state_changed.connect(self._on_connection_state)
        self._worker.start()

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()
            self._worker.wait(2500)
            self._worker = None
        if self._refresh_worker is not None and self._refresh_worker.isRunning():
            self._refresh_worker.wait(1500)
        self._refresh_worker = None
        self._hub.clear_inbox()

    def _build_ws_url(self) -> str | None:
        try:
            return build_platform_ws_url(self._session.get_api_base_url())
        except ValueError:
            return None

    def _build_ws_headers(self) -> dict[str, str] | None:
        tokens = self._session.get_tokens()
        if tokens is None or not tokens.accessToken:
            return None
        try:
            return build_platform_ws_auth_headers(tokens.accessToken)
        except ValueError:
            return None

    def _on_connection_state(self, state: str) -> None:
        if state == "auth_failed":
            self._session.ensure_fresh_session(force=True)

    def _on_push_event(self, event: str, payload: object) -> None:
        if event != WORKSPACE_CHANGED:
            return
        self._refresh_workspace_after_push(payload if isinstance(payload, dict) else {})

    def _refresh_workspace_after_push(self, payload: dict) -> None:
        if self._refresh_worker is not None and self._refresh_worker.isRunning():
            return
        scope = str(payload.get("scope") or payload.get("source") or "workspace")
        worker = WorkspacePushRefreshWorker(
            self._session.api,
            self._session.workspace_cache,
            scope=scope,
            parent=self,
        )
        worker.succeeded.connect(self._on_workspace_refreshed)
        worker.finished.connect(lambda: setattr(self, "_refresh_worker", None))
        self._refresh_worker = worker
        worker.start()

    def _on_workspace_refreshed(self, payload: object) -> None:
        if isinstance(payload, dict):
            settings_raw = payload.get("settings_raw")
            if isinstance(settings_raw, dict):
                self._session.sync_workspace_prefs_from_settings(settings_raw)
        refresh_setup_readiness(
            api=self._session.api,
            cache=self._session.workspace_cache,
            parent=self,
            force_network=False,
        )
