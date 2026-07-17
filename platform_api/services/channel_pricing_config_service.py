"""Admin-managed channel block and profile add-on bundle pricing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

CHANNEL_PRICING_CONFIG_KEY = "channel_pricing_config"

DEFAULT_TWO_CHANNEL_BLOCK_CENTS = 7900
DEFAULT_ADDON_BUNDLE_CENTS: dict[int, int] = {
    2: 7900,
    4: 15800,
    6: 23700,
    8: 31600,
}


@dataclass(frozen=True, slots=True)
class ChannelPricingConfig:
    """Fixed linear pricing: each 2-channel block costs the same; no tier discounts."""

    two_channel_block_cents: int
    addon_bundle_cents: dict[int, int]
    semi_annual_discount_percent: int
    annual_discount_percent: int

    def addon_price_cents(self, addon_channels: int) -> int:
        if addon_channels in self.addon_bundle_cents:
            return int(self.addon_bundle_cents[addon_channels])
        pairs = max(0, addon_channels // 2)
        return pairs * self.two_channel_block_cents

    def linear_plan_monthly_cents(self, channel_count: int) -> int:
        pairs = max(0, channel_count // 2)
        return pairs * self.two_channel_block_cents


def default_channel_pricing_config() -> ChannelPricingConfig:
    return ChannelPricingConfig(
        two_channel_block_cents=DEFAULT_TWO_CHANNEL_BLOCK_CENTS,
        addon_bundle_cents=dict(DEFAULT_ADDON_BUNDLE_CENTS),
        semi_annual_discount_percent=15,
        annual_discount_percent=25,
    )


def _parse_addon_bundles(raw: Any) -> dict[int, int]:
    if not isinstance(raw, dict) or not raw:
        return dict(DEFAULT_ADDON_BUNDLE_CENTS)
    bundles: dict[int, int] = {}
    for key, value in raw.items():
        try:
            channels = int(key)
            cents = int(value)
        except (TypeError, ValueError):
            continue
        if channels >= 2 and channels <= 8 and channels % 2 == 0 and cents >= 0:
            bundles[channels] = cents
    return bundles if bundles else dict(DEFAULT_ADDON_BUNDLE_CENTS)


def config_from_dict(data: dict[str, Any] | None) -> ChannelPricingConfig:
    defaults = default_channel_pricing_config()
    if not data:
        return defaults
    block = int(data.get("two_channel_block_cents") or defaults.two_channel_block_cents)
    return ChannelPricingConfig(
        two_channel_block_cents=max(0, block),
        addon_bundle_cents=_parse_addon_bundles(data.get("addon_bundle_cents")),
        semi_annual_discount_percent=int(
            data.get("semi_annual_discount_percent") or defaults.semi_annual_discount_percent
        ),
        annual_discount_percent=int(
            data.get("annual_discount_percent") or defaults.annual_discount_percent
        ),
    )


def config_to_dict(config: ChannelPricingConfig) -> dict[str, Any]:
    return {
        "two_channel_block_cents": config.two_channel_block_cents,
        "addon_bundle_cents": {str(k): v for k, v in sorted(config.addon_bundle_cents.items())},
        "semi_annual_discount_percent": config.semi_annual_discount_percent,
        "annual_discount_percent": config.annual_discount_percent,
    }


async def load_channel_pricing_config(pool: Any) -> ChannelPricingConfig:
    row = await pool.fetchrow(
        "SELECT value FROM system_settings WHERE key = $1",
        CHANNEL_PRICING_CONFIG_KEY,
    )
    if row is None or not row.get("value"):
        return default_channel_pricing_config()
    raw = row["value"]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return default_channel_pricing_config()
    elif isinstance(raw, dict):
        data = raw
    else:
        return default_channel_pricing_config()
    return config_from_dict(data)


async def save_channel_pricing_config(pool: Any, config: ChannelPricingConfig) -> None:
    payload = json.dumps(config_to_dict(config))
    await pool.execute(
        """
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES ($1, 'json', $2::jsonb, NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            value_type = EXCLUDED.value_type,
            updated_at = NOW()
        """,
        CHANNEL_PRICING_CONFIG_KEY,
        payload,
    )
