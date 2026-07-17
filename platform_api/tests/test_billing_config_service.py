from __future__ import annotations

import pytest

from platform_api.services.billing_config_service import (
    CUTLUY_SECRET_KEY_SETTING,
    mask_secret_value,
    normalize_cutluy_payment_link_id,
    resolve_cutluy_config,
)


class FakePool:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    async def fetchrow(self, query: str, key: str):
        if key not in self.values:
            return None
        return {"value": self.values[key]}


class FakeSettings:
    cutluy_secret_key = "env-secret-key"
    cutluy_payment_link_id = "env-link"
    cutluy_api_base_url = "https://cutluy.com"
    cutluy_webhook_secret = "env-webhook-secret"


@pytest.mark.asyncio
async def test_resolve_cutluy_config_prefers_database_over_env() -> None:
    pool = FakePool(
        {
            CUTLUY_SECRET_KEY_SETTING: "db-secret-key",
            "billing.cutluy.payment_link_id": "db-link",
            "billing.cutluy.api_base_url": "https://api.cutluy.com",
        }
    )
    config = await resolve_cutluy_config(pool, settings=FakeSettings())  # type: ignore[arg-type]
    assert config.secret_key == "db-secret-key"
    assert config.secret_source == "database"
    assert config.payment_link_id == "db-link"
    assert config.api_base_url == "https://api.cutluy.com"
    assert config.webhook_secret == "env-webhook-secret"
    assert config.webhook_secret_source == "environment"


@pytest.mark.asyncio
async def test_resolve_cutluy_config_falls_back_to_env() -> None:
    pool = FakePool({})
    config = await resolve_cutluy_config(pool, settings=FakeSettings())  # type: ignore[arg-type]
    assert config.secret_key == "env-secret-key"
    assert config.secret_source == "environment"
    assert config.payment_link_id == "env-link"
    assert config.webhook_secret == "env-webhook-secret"


def test_mask_secret_value() -> None:
    assert mask_secret_value("abcdefghijklmnop") == "abcd••••mnop"
    assert mask_secret_value("short") == "••••••••"


def test_normalize_cutluy_payment_link_id() -> None:
    assert normalize_cutluy_payment_link_id(None) is None
    assert normalize_cutluy_payment_link_id("") is None
    assert normalize_cutluy_payment_link_id("abc123") == "abc123"
    assert (
        normalize_cutluy_payment_link_id("https://cutluy.com/pay/aZL6ZCePqIYgFQAA8Mi9MqszCT0GpRpR")
        == "aZL6ZCePqIYgFQAA8Mi9MqszCT0GpRpR"
    )
    assert (
        normalize_cutluy_payment_link_id("https://link.payway.com.kh/ABAPAYl4480237P")
        is None
    )
