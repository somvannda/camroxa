"""Connect / health error message tests for release vs local builds."""

from __future__ import annotations

from shared.services.api_health import _unreachable_message
from shared.services.platform_client import _connect_error_message


def test_connect_error_message_local_keeps_dev_hint(monkeypatch) -> None:
    monkeypatch.setattr(
        "shared.services.platform_client.is_api_url_locked",
        lambda: False,
    )
    msg = _connect_error_message("http://localhost:8000/api/v1")
    assert "Start platform_api" in msg
    assert "uvicorn" in msg


def test_connect_error_message_release_hides_uvicorn(monkeypatch) -> None:
    monkeypatch.setattr(
        "shared.services.platform_client.is_api_url_locked",
        lambda: True,
    )
    msg = _connect_error_message("https://api.camxora.com/api/v1")
    assert "uvicorn" not in msg
    assert "port 8000" not in msg
    assert "Cannot reach Camxora servers" in msg
    assert "https://api.camxora.com/api/v1" in msg


def test_health_unreachable_message_release(monkeypatch) -> None:
    monkeypatch.setattr(
        "shared.services.api_health.is_api_url_locked",
        lambda: True,
    )
    msg = _unreachable_message("https://api.sandbox.camxora.com/api/v1")
    assert "uvicorn" not in msg
    assert "Cannot reach Camxora servers" in msg
