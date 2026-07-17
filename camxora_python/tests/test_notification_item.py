from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shared.models.notification_item import (
    NotificationItem,
    format_notification_timestamp,
    group_notifications,
    notification_group_label,
)


def test_notification_group_label_today_and_yesterday() -> None:
    now = datetime.now(timezone.utc)
    assert notification_group_label(now) == "Today"
    assert notification_group_label(now - timedelta(days=1)) == "Yesterday"


def test_group_notifications_orders_newest_first() -> None:
    now = datetime.now(timezone.utc)
    items = [
        NotificationItem(
            id="a",
            kind="push",
            title="Older",
            message="Body",
            icon="activity",
            created_at=now - timedelta(hours=2),
        ),
        NotificationItem(
            id="b",
            kind="push",
            title="Newer",
            message="Body",
            icon="activity",
            created_at=now - timedelta(minutes=5),
        ),
    ]
    grouped = group_notifications(items)
    assert grouped[0][0] == "Today"
    assert [item.id for item in grouped[0][1]] == ["b", "a"]


def test_format_notification_timestamp() -> None:
    value = datetime(2025, 2, 13, 10, 45, tzinfo=timezone.utc).astimezone()
    formatted = format_notification_timestamp(value)
    assert "February, 2025" in formatted
    assert "•" in formatted
