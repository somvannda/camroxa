"""API v2 is a sibling of /api/v1 — never nested as /api/v1/v2."""

from __future__ import annotations

from platform_api.http_paths import (
    API_V2_PREFIX,
    rewrite_legacy_nested_v2_path,
    strip_api_version_prefix,
)
from platform_api.routers import v2_credits, v2_subscriptions, v2_topups


def test_v2_routers_use_resource_prefixes_not_nested_versions() -> None:
    assert v2_subscriptions.router.prefix == "/subscriptions"
    assert v2_credits.router.prefix == "/credits"
    assert v2_topups.router.prefix == "/topups"


def test_rewrite_legacy_nested_v2_path() -> None:
    assert rewrite_legacy_nested_v2_path("/api/v1/auth/login") == "/api/v1/auth/login"
    assert rewrite_legacy_nested_v2_path("/api/v2/credits/balance") == "/api/v2/credits/balance"
    assert (
        rewrite_legacy_nested_v2_path("/api/v1/v2/subscriptions/purchase")
        == "/api/v2/subscriptions/purchase"
    )
    assert (
        rewrite_legacy_nested_v2_path("/api/v1/v2/credits/balance")
        == "/api/v2/credits/balance"
    )
    assert rewrite_legacy_nested_v2_path("/api/v1/v2/topups/packs") == "/api/v2/topups/packs"
    assert rewrite_legacy_nested_v2_path("/api/v1/v2") == API_V2_PREFIX


def test_strip_api_version_prefix() -> None:
    assert strip_api_version_prefix("/api/v1/auth/login") == "auth/login"
    assert strip_api_version_prefix("/api/v2/subscriptions/purchase") == "subscriptions/purchase"
    assert (
        strip_api_version_prefix("/api/v1/v2/subscriptions/purchase")
        == "subscriptions/purchase"
    )
    assert strip_api_version_prefix("/api/v2/credits/balance") == "credits/balance"
