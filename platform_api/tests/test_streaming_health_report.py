"""Tests for the streaming capture Telegram health report."""

from __future__ import annotations

from uuid import uuid4

from platform_api.services.streaming_health_report import (
    format_streaming_health_message,
    has_failures,
)


def _health(**overrides):
    base = {
        "failed_total": 0,
        "failed_window": 0,
        "web_missing_mp3": 0,
        "web_missing_assets": 0,
        "errors": [],
        "window_hours": 24,
    }
    base.update(overrides)
    return base


def test_has_failures_false_when_all_zero() -> None:
    assert has_failures(_health()) is False


def test_has_failures_true_for_each_category() -> None:
    assert has_failures(_health(failed_total=1)) is True
    assert has_failures(_health(web_missing_mp3=2)) is True
    assert has_failures(_health(web_missing_assets=3)) is True


def test_format_message_includes_counts_and_errors() -> None:
    health = _health(
        failed_total=5,
        failed_window=2,
        web_missing_mp3=1,
        web_missing_assets=4,
        errors=[
            {
                "id": str(uuid4()),
                "kind": "mp3_ok",
                "error": "404 Not Found",
            }
        ],
    )
    text = format_streaming_health_message(health, "Production")
    assert "STREAMING CAPTURE" in text
    assert "Production" in text
    assert "desktop failed mp3: <b>5</b> (last 24h: 2)" in text
    assert "web music missing mp3: <b>1</b>" in text
    assert "web music missing assets: <b>4</b>" in text
    assert "mp3_ok" in text
    assert "404 Not Found" in text


def test_format_message_escapes_html() -> None:
    health = _health(
        failed_total=1,
        errors=[{"id": "abc", "kind": "mp3_ok", "error": "<script>x</script>"}],
    )
    text = format_streaming_health_message(health, "Prod & Test")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "Prod &amp; Test" in text
