"""Resolve which KHQR payment provider powers paid checkout.

Both the desktop/onboarding billing routes (``routers/billing.py``) and the
music-web top-up service need the same answer, so the registry and the
enabled/active/available rules live here instead of inside a router.

Admin controls two things per provider in ``system_settings``:

* ``billing.provider.<id>.enabled`` — may the provider be used at all?
* ``billing.active_provider`` — which enabled+available provider is selected?

``none``/``off``/``disabled`` in ``billing.active_provider`` turns paid checkout
off entirely. When the key is absent the historical default applies (mock in
debug, CutLuy in production); ChmabaPay always starts disabled so adding it can
never silently re-route live money.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from platform_api.config import get_settings
from platform_api.services.billing_config_service import (
    resolve_chmaba_config,
    resolve_cutluy_config,
)

BILLING_ACTIVE_PROVIDER_SETTING_KEY = "billing.active_provider"
BILLING_PORTAL_BASE_URL_SETTING_KEY = "billing.portal_base_url"

PROVIDER_REGISTRY: dict[str, dict[str, str]] = {
    "mock": {
        "label": "Mock Checkout",
        "kind": "khqr",
        "description": (
            "Development-only hosted checkout simulator for testing onboarding "
            "and billing flows."
        ),
    },
    "cutluy": {
        "label": "CutLuy KHQR",
        "kind": "khqr",
        "description": "Hosted KHQR checkout via CutLuy payment pages.",
    },
    "chmaba": {
        "label": "ChmabaPay KHQR",
        "kind": "khqr",
        "description": "Direct KHQR / ABA PayWay checkout via pay.chmaba.com.",
    },
}

_DISABLED_ACTIVE_VALUES = {"none", "off", "disabled"}


@dataclass(frozen=True, slots=True)
class ProviderState:
    id: str
    label: str
    kind: str
    description: str
    enabled: bool
    available: bool
    active: bool


@dataclass(frozen=True, slots=True)
class BillingProviderConfig:
    active_provider: str | None
    providers: list[ProviderState]

    @property
    def paid_checkout_available(self) -> bool:
        return self.active_provider is not None


def parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return default


async def load_system_setting(pool: Any, key: str) -> str | None:
    """Fetch a raw system setting value by key."""
    row = await pool.fetchrow(
        """
        SELECT value
        FROM system_settings
        WHERE key = $1
        """,
        key,
    )
    if row is None:
        return None
    value = row.get("value")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def provider_enabled_setting_key(provider_id: str) -> str:
    return f"billing.provider.{provider_id}.enabled"


def default_provider_enabled(provider_id: str) -> bool:
    """Return the implicit enabled state when admin has not saved a setting."""
    settings = get_settings()
    if provider_id == "mock":
        return bool(settings.debug)
    if provider_id == "cutluy":
        return not settings.debug
    # ChmabaPay is opt-in: enabling it is an explicit operator decision.
    return False


async def is_provider_enabled(pool: Any, provider_id: str) -> bool:
    raw = await load_system_setting(pool, provider_enabled_setting_key(provider_id))
    return parse_bool(raw, default_provider_enabled(provider_id))


async def provider_available(pool: Any, provider_id: str) -> bool:
    """Return whether the provider has usable credentials right now."""
    if provider_id == "mock":
        return bool(get_settings().debug)
    if provider_id == "cutluy":
        cutluy = await resolve_cutluy_config(pool)
        return bool(cutluy.secret_key)
    if provider_id == "chmaba":
        chmaba = await resolve_chmaba_config(pool)
        return chmaba.configured
    return False


async def get_provider_config(pool: Any) -> BillingProviderConfig:
    """Build the provider registry with enabled/active/available flags."""
    raw_active = await load_system_setting(pool, BILLING_ACTIVE_PROVIDER_SETTING_KEY)
    configured_active = (raw_active or "").strip().lower()
    explicit_off = configured_active in _DISABLED_ACTIVE_VALUES
    if not configured_active:
        configured_active = "mock" if get_settings().debug else "cutluy"

    rows: list[ProviderState] = []
    resolved_active: str | None = None

    for provider_id, meta in PROVIDER_REGISTRY.items():
        enabled = await is_provider_enabled(pool, provider_id)
        available = await provider_available(pool, provider_id)
        is_active = enabled and available and configured_active == provider_id
        if is_active:
            resolved_active = provider_id
        rows.append(
            ProviderState(
                id=provider_id,
                label=meta["label"],
                kind=meta["kind"],
                description=meta["description"],
                enabled=enabled,
                available=available,
                active=is_active,
            )
        )

    if resolved_active is None and not explicit_off:
        fallback = next((row.id for row in rows if row.enabled and row.available), None)
        resolved_active = fallback
        rows = [
            ProviderState(
                id=row.id,
                label=row.label,
                kind=row.kind,
                description=row.description,
                enabled=row.enabled,
                available=row.available,
                active=row.id == resolved_active,
            )
            for row in rows
        ]

    return BillingProviderConfig(active_provider=resolved_active, providers=rows)


async def resolve_active_provider(pool: Any) -> str | None:
    """Return the active enabled+available provider, or None when checkout is off."""
    config = await get_provider_config(pool)
    return config.active_provider
