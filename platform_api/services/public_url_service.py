"""Resolve public-facing portal and API base URLs from settings."""

from __future__ import annotations

import os
from typing import Any

from platform_api.config import Settings, get_settings
from platform_api.services.billing_config_service import load_system_setting

PUBLIC_API_BASE_URL_KEY = "platform.public_api_base_url"
BILLING_PORTAL_BASE_URL_SETTING_KEY = "billing.portal_base_url"


async def resolve_public_api_base_url(
    pool: Any,
    *,
    settings: Settings | None = None,
) -> str:
    """Return the browser-facing API origin (e.g. https://api.sandbox.camxora.com)."""
    resolved = settings or get_settings()
    configured = (await load_system_setting(pool, PUBLIC_API_BASE_URL_KEY) or "").strip()
    if configured:
        return configured.rstrip("/")

    env_value = (os.environ.get("PLATFORM_PUBLIC_API_BASE_URL") or "").strip()
    if env_value:
        return env_value.rstrip("/")

    if resolved.debug:
        return f"http://127.0.0.1:{resolved.port}"

    return "https://api.camxora.com"


def build_youtube_oauth_callback_url(api_base_url: str, *, api_v1_prefix: str | None = None) -> str:
    """Build the Google OAuth redirect URI registered for YouTube connect."""
    prefix = (api_v1_prefix or get_settings().api_v3_prefix).rstrip("/")
    return f"{api_base_url.rstrip('/')}{prefix}/youtube/oauth/callback"
