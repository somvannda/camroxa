from __future__ import annotations

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


def test_push_notification_hub_soft_notice_does_not_block_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Mid-session push shows a header notice only — never the mandatory gate."""
    monkeypatch.setattr(
        "shared.lib.software_update_persistence.get_updates_work_dir",
        lambda: tmp_path / "updates",
    )
    (tmp_path / "updates").mkdir()
    hub = PushNotificationHub()
    hub.clear_inbox()
    received: list[str] = []
    hub.event_received.connect(lambda event, _payload: received.append(event))
    hub.dispatch(
        SOFTWARE_UPDATE_AVAILABLE,
        {
            "version": "2.4.0",
            "mandatory": True,
            "download_url": "https://example.com/CamxoraSetup-2.4.0.exe",
            "release_notes": "Security fixes included.",
        },
    )

    assert received == [SOFTWARE_UPDATE_AVAILABLE]
    assert hub.inbox_items == []
    service = SoftwareUpdateService.instance()
    assert service.pending is not None
    assert service.pending.version == "2.4.0"
    assert service.pending.mandatory is False
    assert not service.should_block_app()


def test_push_notification_hub_dismiss_noop_for_empty_inbox() -> None:
    hub = PushNotificationHub()
    hub.clear_inbox()
    hub.dismiss("missing")
    assert hub.inbox_items == []


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
