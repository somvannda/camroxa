"""Unit tests for marketplace preview URL resolution."""

from __future__ import annotations

from features.marketplace.views.marketplace_view import resolve_marketplace_asset_url


def test_resolve_strips_duplicated_api_v3_prefix() -> None:
    """Desktop base already ends with /api/v3; catalog preview_url also includes it."""
    url = resolve_marketplace_asset_url(
        "http://localhost:8000/api/v3",
        "/api/v3/marketplace/items/abc-123/preview",
    )
    assert url == "http://localhost:8000/api/v3/marketplace/items/abc-123/preview"


def test_resolve_handles_relative_marketplace_path() -> None:
    url = resolve_marketplace_asset_url(
        "http://localhost:8000/api/v3",
        "/marketplace/items/abc-123/preview",
    )
    assert url == "http://localhost:8000/api/v3/marketplace/items/abc-123/preview"


def test_resolve_handles_host_only_base() -> None:
    """Host-only base + absolute API path."""
    url = resolve_marketplace_asset_url(
        "http://localhost:8000",
        "/api/v3/marketplace/items/abc-123/preview",
    )
    assert url == "http://localhost:8000/api/v3/marketplace/items/abc-123/preview"


def test_resolve_passthrough_absolute_http() -> None:
    absolute = "https://cdn.example.com/previews/x.png"
    assert resolve_marketplace_asset_url("http://localhost:8000/api/v3", absolute) == absolute


def test_resolve_empty_path() -> None:
    assert resolve_marketplace_asset_url("http://localhost:8000/api/v3", "") == ""
    assert resolve_marketplace_asset_url("http://localhost:8000/api/v3", "   ") == ""
