"""API v3 is the canonical full surface; v1/v2 remain temporary dual-mounts."""

from __future__ import annotations

from platform_api.http_paths import (
    API_V3_PREFIX,
    canonical_api_path,
    strip_api_version_prefix,
)
from platform_api.routers import v2_credits, v2_subscriptions, v2_topups


def test_v2_routers_use_resource_prefixes_not_nested_versions() -> None:
    assert v2_subscriptions.router.prefix == "/subscriptions"
    assert v2_credits.router.prefix == "/credits"
    assert v2_topups.router.prefix == "/topups"


def test_canonical_api_path_uses_v3() -> None:
    assert canonical_api_path("web-music/play/tok") == "/api/v3/web-music/play/tok"
    assert canonical_api_path("/me/credits") == "/api/v3/me/credits"


def test_strip_api_version_prefix_includes_v3() -> None:
    assert strip_api_version_prefix("/api/v3/auth/login") == "auth/login"
    assert strip_api_version_prefix("/api/v3/subscriptions/plans") == "subscriptions/plans"
    assert strip_api_version_prefix("/api/v3/me/credits") == "me/credits"
    assert strip_api_version_prefix("/api/v3") == ""
    assert strip_api_version_prefix(API_V3_PREFIX) == ""


def test_create_app_dual_mounts_core_and_billing_under_v3() -> None:
    from platform_api.main import create_app

    app = create_app()
    paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/v1/auth/login" in paths or any(
        p.endswith("/auth/login") and p.startswith("/api/v1") for p in paths
    )
    assert any(p.startswith("/api/v3") and p.endswith("/auth/login") for p in paths)
    assert any(p == "/api/v3/subscriptions/plans" or p.endswith("/subscriptions/plans") for p in paths)
    assert any("/api/v2/subscriptions" in p or p.endswith("/subscriptions/plans") for p in paths)
    assert any(p.startswith("/api/v3") and "/webhooks/cutluy" in p for p in paths)
    assert any(p.startswith("/api/v1") and "/webhooks/cutluy" in p for p in paths)
    assert any(p.startswith("/api/v3") and p.endswith("/me/credits") for p in paths)
    assert any(p.startswith("/api/v3") and p.endswith("/health") for p in paths)
