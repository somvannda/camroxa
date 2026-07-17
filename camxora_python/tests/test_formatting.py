"""Formatting helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from shared.lib.formatting import (
    format_album_slot_label,
    format_channel_role_label,
    format_datetime_label,
    format_progress_updated_time,
    format_run_date_label,
)


def test_format_run_date_label_formats_batch_date() -> None:
    assert format_run_date_label("2026-07-10") == "Jul 10, 2026"


def test_format_datetime_label_converts_utc_to_local() -> None:
    utc = datetime(2026, 7, 10, 11, 30, tzinfo=timezone.utc)
    local = format_datetime_label(utc)
    expected = utc.astimezone().strftime("%b %d, %Y %H:%M")
    assert local == expected


def test_format_progress_updated_time_uses_local_clock_for_today(qtbot) -> None:
    from PySide6.QtCore import QDateTime, QLocale
    from PySide6.QtWidgets import QApplication

    _ = QApplication.instance() or QApplication([])
    utc = datetime.now(timezone.utc)
    local = format_progress_updated_time(utc)
    qdt = QDateTime(
        utc.astimezone().year,
        utc.astimezone().month,
        utc.astimezone().day,
        utc.astimezone().hour,
        utc.astimezone().minute,
        utc.astimezone().second,
    )
    expected = QLocale.system().toString(qdt, QLocale.FormatType.ShortFormat)
    assert local == expected


def test_format_progress_updated_time_includes_date_for_older_rows(qtbot) -> None:
    from PySide6.QtCore import QDateTime, QLocale
    from PySide6.QtWidgets import QApplication

    _ = QApplication.instance() or QApplication([])
    utc = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
    local = format_progress_updated_time(utc)
    local_dt = utc.astimezone()
    qdt = QDateTime(
        local_dt.year,
        local_dt.month,
        local_dt.day,
        local_dt.hour,
        local_dt.minute,
        local_dt.second,
    )
    expected = QLocale.system().toString(qdt, QLocale.FormatType.ShortFormat)
    assert local == expected


def test_format_channel_role_label_uses_primary_secondary() -> None:
    assert format_channel_role_label("ok") == "Primary"
    assert format_channel_role_label("ALT") == "Secondary"
    assert format_channel_role_label("primary") == "Primary"


def test_format_album_slot_label_uses_album_1_album_2() -> None:
    assert format_album_slot_label("ok") == "album 1"
    assert format_album_slot_label("primary") == "album 1"
    assert format_album_slot_label("ALT") == "album 2"
    assert format_album_slot_label("secondary") == "album 2"
