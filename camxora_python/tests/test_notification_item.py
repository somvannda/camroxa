from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from shared.lib.app_install import get_or_seed_install_datetime, reset_install_datetime_cache_for_tests
from shared.lib.music_readiness import ReadinessItem
from shared.models.notification_item import (
    NotificationItem,
    format_notification_timestamp,
    group_notifications,
    notification_group_label,
    notification_item_from_setup,
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


def test_setup_notification_uses_install_datetime_not_year_2000(tmp_path: Path, monkeypatch) -> None:
    reset_install_datetime_cache_for_tests()
    monkeypatch.setattr("shared.lib.app_install.get_user_data_dir", lambda: tmp_path)
    item = notification_item_from_setup(
        ReadinessItem(
            id="youtube:p1:connected",
            label="YouTube connected for Bass Drive",
            section="YouTube",
            complete=False,
            required_for_generate=False,
            required_for_upload=True,
            hint="Settings → YouTube → Connect Channel.",
        )
    )
    assert item.created_at.year != 2000
    assert item.created_at.year >= 2024
    stamp = format_notification_timestamp(item.created_at)
    assert "2000" not in stamp
    reset_install_datetime_cache_for_tests()


def test_get_or_seed_install_datetime_persists(tmp_path: Path, monkeypatch) -> None:
    reset_install_datetime_cache_for_tests()
    monkeypatch.setattr("shared.lib.app_install.get_user_data_dir", lambda: tmp_path)
    first = get_or_seed_install_datetime()
    reset_install_datetime_cache_for_tests()
    second = get_or_seed_install_datetime()
    assert first == second
    assert (tmp_path / "install.json").is_file()
    reset_install_datetime_cache_for_tests()
