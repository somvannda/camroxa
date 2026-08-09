"""In-app push notification hub for WebSocket and future server events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import QObject, Signal

from shared.models.push_events import (
    NOTIFICATION_MESSAGE,
    SOFTWARE_UPDATE_AVAILABLE,
    WORKSPACE_CHANGED,
)


@dataclass(slots=True)
class PushInboxItem:
    id: str
    event: str
    title: str
    message: str
    created_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)


class PushNotificationHub(QObject):
    """Routes push events to desktop UI and background refresh handlers."""

    event_received = Signal(str, object)
    inbox_changed = Signal()

    _instance: PushNotificationHub | None = None

    def __init__(self) -> None:
        super().__init__()
        self._inbox: list[PushInboxItem] = []
        self._dismissed_ids: set[str] = set()

    @classmethod
    def instance(cls) -> PushNotificationHub:
        if cls._instance is None:
            cls._instance = PushNotificationHub()
        return cls._instance

    @property
    def inbox_items(self) -> list[PushInboxItem]:
        return list(self._inbox)

    def is_dismissed(self, notification_id: str) -> bool:
        return notification_id in self._dismissed_ids

    def dismiss(self, notification_id: str) -> None:
        normalized = str(notification_id or "").strip()
        if not normalized:
            return
        from shared.services.software_update_service import SoftwareUpdateService

        if not SoftwareUpdateService.instance().can_dismiss(normalized):
            return
        self._dismissed_ids.add(normalized)
        next_inbox = [item for item in self._inbox if item.id != normalized]
        if len(next_inbox) != len(self._inbox):
            self._inbox = next_inbox
        self.inbox_changed.emit()

    def dispatch(self, event: str, payload: dict[str, Any] | None = None) -> None:
        normalized_event = str(event or "").strip()
        if not normalized_event:
            return
        safe_payload = dict(payload or {})
        self.event_received.emit(normalized_event, safe_payload)

        if normalized_event == SOFTWARE_UPDATE_AVAILABLE:
            from shared.constants.app_version import get_app_version
            from shared.lib.version_compare import is_remote_version_newer
            from shared.services.software_update_service import SoftwareUpdateService

            version = str(safe_payload.get("version") or "").strip()
            if not version or not is_remote_version_newer(get_app_version(), version):
                SoftwareUpdateService.instance().reconcile_with_installed_version()
                return
            # Mid-session: header icon only — never slam the mandatory gate overlay.
            # Force update still applies on the next app open via public desktop-release.
            SoftwareUpdateService.instance().apply_session_notice(safe_payload)
            return

        inbox_item = self._build_inbox_item(normalized_event, safe_payload)
        if inbox_item is not None:
            self._inbox.insert(0, inbox_item)
            self.inbox_changed.emit()

    def _build_inbox_item(
        self,
        event: str,
        payload: dict[str, Any],
    ) -> PushInboxItem | None:
        if event == SOFTWARE_UPDATE_AVAILABLE:
            version = str(payload.get("version") or "unknown")
            mandatory = bool(payload.get("mandatory"))
            title = "Software update available"
            if mandatory:
                title = "Required software update"
            message = f"Version {version} is ready to install."
            notes = str(payload.get("release_notes") or "").strip()
            if notes:
                message = f"{message} {notes}"
            return PushInboxItem(
                id=str(payload.get("notification_id") or uuid.uuid4()),
                event=event,
                title=title,
                message=message,
                created_at=self._payload_created_at(payload),
                payload=payload,
            )

        if event == NOTIFICATION_MESSAGE:
            title = str(payload.get("title") or "Notification").strip() or "Notification"
            message = str(payload.get("message") or "").strip()
            if not message:
                return None
            return PushInboxItem(
                id=str(payload.get("notification_id") or uuid.uuid4()),
                event=event,
                title=title,
                message=message,
                created_at=self._payload_created_at(payload),
                payload=payload,
            )

        return None

    @staticmethod
    def _payload_created_at(payload: dict[str, Any]) -> datetime:
        raw = str(payload.get("created_at") or "").strip()
        if raw:
            try:
                normalized = raw.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def clear_inbox(self) -> None:
        if not self._inbox and not self._dismissed_ids:
            return
        self._inbox.clear()
        self._dismissed_ids.clear()
        self.inbox_changed.emit()

    @staticmethod
    def is_workspace_event(event: str) -> bool:
        return event == WORKSPACE_CHANGED
