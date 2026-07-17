"""Resolve billing provider credentials from system_settings with env fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from platform_api.config import Settings, get_settings

CUTLUY_API_BASE_URL_KEY = "billing.cutluy.api_base_url"
CUTLUY_SECRET_KEY_SETTING = "billing.cutluy.secret_key"
CUTLUY_PAYMENT_LINK_ID_KEY = "billing.cutluy.payment_link_id"
CUTLUY_WEBHOOK_SECRET_KEY = "billing.cutluy.webhook_secret"

CutluySecretSource = Literal["database", "environment", "none"]


@dataclass(frozen=True, slots=True)
class CutluyConfig:
    api_base_url: str
    secret_key: str
    payment_link_id: str | None
    secret_source: CutluySecretSource
    webhook_secret: str = ""
    webhook_secret_source: CutluySecretSource = "none"


async def load_system_setting(pool: Any, key: str) -> str | None:
    row = await pool.fetchrow(
        "SELECT value FROM system_settings WHERE key = $1",
        key,
    )
    if row is None:
        return None
    value = row.get("value")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def resolve_cutluy_config(
    pool: Any,
    *,
    settings: Settings | None = None,
) -> CutluyConfig:
    """Load CutLuy credentials — admin portal DB settings override env vars."""
    resolved = settings or get_settings()

    db_secret = await load_system_setting(pool, CUTLUY_SECRET_KEY_SETTING)
    db_payment_link_id = await load_system_setting(pool, CUTLUY_PAYMENT_LINK_ID_KEY)
    db_api_base_url = await load_system_setting(pool, CUTLUY_API_BASE_URL_KEY)
    db_webhook_secret = await load_system_setting(pool, CUTLUY_WEBHOOK_SECRET_KEY)

    secret_source: CutluySecretSource = "none"
    secret_key = ""
    if db_secret:
        secret_key = db_secret
        secret_source = "database"
    elif resolved.cutluy_secret_key.strip():
        secret_key = resolved.cutluy_secret_key.strip()
        secret_source = "environment"

    webhook_secret_source: CutluySecretSource = "none"
    webhook_secret = ""
    if db_webhook_secret:
        webhook_secret = db_webhook_secret
        webhook_secret_source = "database"
    elif (getattr(resolved, "cutluy_webhook_secret", "") or "").strip():
        webhook_secret = resolved.cutluy_webhook_secret.strip()
        webhook_secret_source = "environment"

    payment_link_id = normalize_cutluy_payment_link_id(
        db_payment_link_id or resolved.cutluy_payment_link_id or None
    )
    api_base_url = (
        db_api_base_url or resolved.cutluy_api_base_url or "https://cutluy.com"
    ).rstrip("/")

    return CutluyConfig(
        api_base_url=api_base_url,
        secret_key=secret_key,
        payment_link_id=payment_link_id,
        secret_source=secret_source,
        webhook_secret=webhook_secret,
        webhook_secret_source=webhook_secret_source,
    )


def mask_secret_value(value: str) -> str:
    """Return a display-safe masked secret for admin UIs."""
    trimmed = value.strip()
    if not trimmed:
        return ""
    if len(trimmed) <= 8:
        return "••••••••"
    return f"{trimmed[:4]}••••{trimmed[-4:]}"


def normalize_cutluy_payment_link_id(raw: str | None) -> str | None:
    """Return a CutLuy payment-link slug suitable for POST /v1/payments.

    Accepts a bare slug or a hosted CutLuy URL (`https://cutluy.com/pay/<slug>`).
    Rejects unrelated checkout URLs (for example PayWay/ABA links) so checkout
    can fall back to dynamic payment creation.
    """
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None

    lowered = value.lower()
    for prefix in ("https://cutluy.com/pay/", "http://cutluy.com/pay/"):
        if lowered.startswith(prefix):
            slug = value[len(prefix) :].split("/")[0].split("?")[0].strip()
            return slug or None

    if "://" in value or lowered.startswith("http"):
        return None
    if "payway.com" in lowered or "link.payway" in lowered:
        return None

    return value

