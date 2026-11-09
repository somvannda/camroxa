"""Retry-After plumbing for platform_api 429 responses."""

from __future__ import annotations

import httpx

from shared.services.platform_client import PlatformApiError, _retry_after_header


def test_retry_after_header_is_parsed_as_seconds() -> None:
    response = httpx.Response(429, headers={"Retry-After": "42"})
    assert _retry_after_header(response) == 42


def test_retry_after_header_ignores_http_date_and_junk() -> None:
    date_form = httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
    junk = httpx.Response(429, headers={"Retry-After": "soon"})
    missing = httpx.Response(429)
    assert _retry_after_header(date_form) is None
    assert _retry_after_header(junk) is None
    assert _retry_after_header(missing) is None


def test_error_exposes_header_value() -> None:
    error = PlatformApiError(429, "Rate limit exceeded.", None, retry_after=30)
    assert error.retry_after == 30


def test_error_falls_back_to_detail_body() -> None:
    error = PlatformApiError(
        429,
        "Rate limit exceeded.",
        {"detail": {"error_code": "RATE_LIMITED", "retry_after": 17}},
    )
    assert error.retry_after == 17


def test_error_without_retry_hint_is_none() -> None:
    assert PlatformApiError(429, "Rate limit exceeded.").retry_after is None
    assert PlatformApiError(422, "Invalid plan", {"detail": "nope"}).retry_after is None
