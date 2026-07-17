"""CutLuy timestamp parsing for billing payment refresh."""

from __future__ import annotations

from datetime import datetime, timezone

from platform_api.routers.billing import _parse_cutluy_timestamp


def test_parse_cutluy_timestamp_accepts_zulu_iso_string() -> None:
    parsed = _parse_cutluy_timestamp("2026-07-16T05:10:48.000Z")
    assert parsed == datetime(2026, 7, 16, 5, 10, 48, tzinfo=timezone.utc)


def test_parse_cutluy_timestamp_returns_none_for_empty() -> None:
    assert _parse_cutluy_timestamp(None) is None
    assert _parse_cutluy_timestamp("") is None
