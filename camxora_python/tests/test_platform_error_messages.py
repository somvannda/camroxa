"""User-facing API error message extraction."""

from __future__ import annotations

from shared.services.platform_client import _extract_error_message


def test_extracts_nested_platform_api_error_envelope() -> None:
    payload = {"error": {"code": "AUTHENTICATION_ERROR", "message": "Invalid credentials."}}
    assert _extract_error_message(payload, 401) == "Incorrect email or password."


def test_extracts_fastapi_detail_string() -> None:
    assert _extract_error_message({"detail": "Account locked for 15 minutes."}, 403) == (
        "Account locked for 15 minutes."
    )


def test_falls_back_to_friendly_status_copy() -> None:
    assert _extract_error_message(None, 401) == "Incorrect email or password."
    assert "try again" in _extract_error_message({}, 500).lower()


def test_omits_html_gateway_bodies() -> None:
    html = (
        "<html><head><title>502 Bad Gateway</title></head>"
        "<body><center><h1>502 Bad Gateway</h1></center>"
        "<hr><center>nginx/1.18.0 (Ubuntu)</center></body></html>"
    )
    assert _extract_error_message(html, 502) == (
        "The service is temporarily unavailable. Please try again."
    )
    assert _extract_error_message({"detail": html}, 502) == (
        "The service is temporarily unavailable. Please try again."
    )
