"""Tests for UTC datetime helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from platform_api.utils.datetime_utils import ensure_utc, format_utc_iso, utc_now


def test_utc_now_is_timezone_aware() -> None:
    now = utc_now()
    assert now.tzinfo == timezone.utc


def test_format_utc_iso_appends_z() -> None:
    value = datetime(2026, 7, 16, 8, 19, 47, tzinfo=timezone.utc)
    assert format_utc_iso(value) == "2026-07-16T08:19:47Z"


def test_ensure_utc_treats_naive_as_utc() -> None:
    naive = datetime(2026, 7, 16, 8, 19, 47)
    converted = ensure_utc(naive)
    assert converted.tzinfo == timezone.utc
    assert converted.hour == 8
