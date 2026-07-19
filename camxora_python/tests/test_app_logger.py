"""Tests for performance-safe AppLogger."""

from __future__ import annotations

from shared.services.app_logger import AppLogger, LogLevel, redact_text, sanitize_error_body


def test_redact_text_masks_secrets() -> None:
    jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    text = f"Authorization: Bearer abc.def.ghi password=supersecret token={jwt}"
    out = redact_text(text)
    assert "supersecret" not in out
    assert jwt not in out
    assert "[REDACTED]" in out


def test_sanitize_error_body_omits_html_gateway_dumps() -> None:
    html = "<!DOCTYPE html><html><head><title>502</title></head><body>nginx/1.18.0</body></html>"
    out = sanitize_error_body(html, status=502)
    assert "nginx/1.18.0" not in out
    assert "omitted HTML/gateway" in out
    assert "502" in out
    assert redact_text(f"GET /progress → 502: {html}").count("<html") == 0


def test_app_logger_ring_buffer_and_snapshot() -> None:
    logger = AppLogger()
    logger.set_min_level(LogLevel.INFO)
    logger.clear()
    for i in range(10):
        logger.info(f"line-{i}", category="test")
    snap = logger.snapshot()
    assert len(snap) == 10
    assert "line-9" in snap[-1].message
    text = logger.snapshot_text()
    assert "line-0" in text
    assert "password=" not in text or "[REDACTED]" in text
    logger.clear()
    assert logger.snapshot() == []
