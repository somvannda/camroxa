from __future__ import annotations

import pytest

from shared.lib.ws_url import build_platform_ws_url


def test_build_platform_ws_url_without_token() -> None:
    url = build_platform_ws_url("https://api.example.com")
    assert url == "wss://api.example.com/api/v1/ws"


def test_build_platform_ws_url_legacy_token_query() -> None:
    url = build_platform_ws_url("https://api.example.com", "token-123")
    assert url == "wss://api.example.com/api/v1/ws?token=token-123"


def test_build_platform_ws_url_from_v1_prefix() -> None:
    url = build_platform_ws_url("http://localhost:8000/api/v1", "abc def")
    assert url == "ws://localhost:8000/api/v1/ws?token=abc%20def"


def test_build_platform_ws_url_requires_base() -> None:
    with pytest.raises(ValueError):
        build_platform_ws_url("", "token")
