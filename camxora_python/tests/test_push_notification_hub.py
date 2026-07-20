from __future__ import annotations

from datetime import datetime

import pytest

from shared.models.push_events import NOTIFICATION_MESSAGE, SOFTWARE_UPDATE_AVAILABLE, WORKSPACE_CHANGED
from shared.services.push_notification_hub import PushNotificationHub
from shared.services.software_update_service import SoftwareUpdateService


@pytest.fixture(autouse=True)
def _reset_update_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "shared.constants.app_version.get_app_version",
        lambda: "0.1.0",
    )
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "0.1.0",
    )
    SoftwareUpdateService._instance = None


def test_push_notification_hub_dispatches_workspace_event() -> None:
    hub = PushNotificationHub()
    received: list[tuple[str, dict]] = []

    def on_event(event: str, payload: object) -> None:
        received.append((event, dict(payload) if isinstance(payload, dict) else {}))

    hub.event_received.connect(on_event)
    hub.dispatch(WORKSPACE_CHANGED, {"source": "settings", "scope": "settings"})

    assert received == [(WORKSPACE_CHANGED, {"source": "settings", "scope": "settings"})]
    assert hub.inbox_items == []


def test_push_notification_hub_collects_software_updates() -> None:
    hub = PushNotificationHub()
    hub.clear_inbox()
    hub.dispatch(
        SOFTWARE_UPDATE_AVAILABLE,
        {
            "version": "2.4.0",
            "mandatory": True,
            "release_notes": "Security fixes included.",
        },
    )

    assert len(hub.inbox_items) == 1
    item = hub.inbox_items[0]
    assert item.event == SOFTWARE_UPDATE_AVAILABLE
    assert "2.4.0" in item.message
    assert item.title == "Required software update"
    assert item.id
    assert isinstance(item.created_at, datetime)
    assert SoftwareUpdateService.instance().should_block_app()


def test_push_notification_hub_skips_same_or_older_software_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "shared.constants.app_version.get_app_version",
        lambda: "2.4.0",
    )
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "2.4.0",
    )
    hub = PushNotificationHub()
    hub.clear_inbox()
    hub.dispatch(
        SOFTWARE_UPDATE_AVAILABLE,
        {"version": "2.4.0", "mandatory": True, "release_notes": "Already installed."},
    )
    assert hub.inbox_items == []
    assert not SoftwareUpdateService.instance().should_block_app()


def test_push_notification_hub_dismiss_removes_item() -> None:
    hub = PushNotificationHub()
    hub.clear_inbox()
    hub.dispatch(SOFTWARE_UPDATE_AVAILABLE, {"version": "1.0.0"})
    item_id = hub.inbox_items[0].id

    hub.dismiss(item_id)

    assert hub.inbox_items == []
    assert hub.is_dismissed(item_id)


def test_push_notification_hub_clear_resets_dismissed() -> None:
    hub = PushNotificationHub()
    hub.dismiss("setup:Profile:Name")
    hub.clear_inbox()
    assert not hub.is_dismissed("setup:Profile:Name")


def test_push_notification_hub_collects_admin_messages() -> None:
    hub = PushNotificationHub()
    hub.clear_inbox()
    hub.dispatch(
        NOTIFICATION_MESSAGE,
        {
            "notification_id": "msg-1",
            "title": "Maintenance tonight",
            "message": "Camxora will be unavailable from 11 PM to midnight.",
            "created_at": "2026-07-13T15:18:00+00:00",
        },
    )

    assert len(hub.inbox_items) == 1
    item = hub.inbox_items[0]
    assert item.title == "Maintenance tonight"
    assert item.event == NOTIFICATION_MESSAGE
