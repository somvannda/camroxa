"""Unit tests for the ChmabaPay provider wiring (no network, no database)."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from platform_api.services.billing_config_service import (
    CHMABA_API_KEY_SETTING,
    CHMABA_STORE_ID_KEY,
    ChmabaConfig,
    resolve_chmaba_config,
)
from platform_api.services.billing_provider_service import (
    default_provider_enabled,
    parse_bool,
)
from platform_api.services.chmaba_webhook import (
    chmaba_event_type,
    find_chmaba_reference_id,
    verify_chmaba_webhook_signature,
)
from platform_api.services.shared.chmaba_service import (
    ChmabaService,
    extract_chmaba_qr_string,
    normalize_chmaba_payment_status,
)
from platform_api.services.v2.payment_security import (
    is_allowed_chmaba_checkout_url,
    is_allowed_cutluy_checkout_url,
)


class FakePool:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    async def fetchrow(self, query: str, key: str):
        if key not in self.values:
            return None
        return {"value": self.values[key]}


class FakeSettings:
    chmaba_api_key = "env-chmaba-key"
    chmaba_store_id = "env-store"
    chmaba_api_base_url = "https://pay.chmaba.com"
    chmaba_webhook_secret = "env-whsec"


def _sign(body: bytes, secret: str, timestamp: int) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_verify_chmaba_webhook_signature_accepts_fresh_delivery() -> None:
    body = b'{"type":"payment.completed"}'
    now = 1_700_000_000
    assert verify_chmaba_webhook_signature(
        raw_body=body,
        signature_header=_sign(body, "whsec_test", now),
        secret="whsec_test",
        now=now,
    )


def test_verify_chmaba_webhook_signature_rejects_tampering_and_stale() -> None:
    body = b'{"type":"payment.completed"}'
    now = 1_700_000_000
    assert not verify_chmaba_webhook_signature(
        raw_body=b'{"type":"payment.reversed"}',
        signature_header=_sign(body, "whsec_test", now),
        secret="whsec_test",
        now=now,
    )
    assert not verify_chmaba_webhook_signature(
        raw_body=body,
        signature_header=_sign(body, "wrong", now),
        secret="whsec_test",
        now=now,
    )
    assert not verify_chmaba_webhook_signature(
        raw_body=body,
        signature_header=_sign(body, "whsec_test", now - 10_000),
        secret="whsec_test",
        now=now,
    )
    assert not verify_chmaba_webhook_signature(
        raw_body=body,
        signature_header=None,
        secret="whsec_test",
        now=now,
    )


def test_find_chmaba_reference_id_scans_nested_envelopes() -> None:
    event = {"data": {"payment": {"metadata": {"reference_id": "abc-123"}}}}
    assert find_chmaba_reference_id(event) == "abc-123"
    assert find_chmaba_reference_id({"data": {}}) is None
    assert find_chmaba_reference_id({"reference_id": "  "}) is None


def test_chmaba_event_type_reads_header_case_insensitively() -> None:
    assert chmaba_event_type({"X-ChmabaPay-Event": "payment.completed"}) == "payment.completed"
    assert chmaba_event_type({"x-chmabapay-event": "payment.reversed"}) == "payment.reversed"
    assert chmaba_event_type({}) is None


def test_normalize_chmaba_payment_status() -> None:
    assert normalize_chmaba_payment_status("PAID") == "paid"
    assert normalize_chmaba_payment_status("paid") == "paid"
    assert normalize_chmaba_payment_status("FAILED") == "failed"
    assert normalize_chmaba_payment_status("EXPIRED") == "expired"
    assert normalize_chmaba_payment_status("PENDING") == "pending"
    assert normalize_chmaba_payment_status(None) == "pending"


def test_extract_chmaba_qr_string_accepts_khqr_payload() -> None:
    payload = "00020101021229300012D156000000000510A93FO3230Q31280012"
    assert extract_chmaba_qr_string({"qr_string": payload}) == payload
    assert extract_chmaba_qr_string({"data": {"khqr": payload}}) == payload
    assert extract_chmaba_qr_string({"qr_string": "not-a-khqr"}) is None


@pytest.mark.asyncio
async def test_resolve_chmaba_config_prefers_database_over_env() -> None:
    pool = FakePool(
        {
            CHMABA_API_KEY_SETTING: "db-key",
            CHMABA_STORE_ID_KEY: "db-store",
            "billing.chmaba.api_base_url": "https://pay.staging.chmaba.com",
            "billing.chmaba.webhook_secret": "db-whsec",
        }
    )
    config = await resolve_chmaba_config(pool, settings=FakeSettings())  # type: ignore[arg-type]
    assert config.api_key == "db-key"
    assert config.api_key_source == "database"
    assert config.store_id == "db-store"
    assert config.store_source == "database"
    assert config.webhook_secret == "db-whsec"
    assert config.webhook_secret_source == "database"
    assert config.api_base_url == "https://pay.staging.chmaba.com"
    assert config.configured is True


@pytest.mark.asyncio
async def test_resolve_chmaba_config_falls_back_to_env() -> None:
    config = await resolve_chmaba_config(FakePool({}), settings=FakeSettings())  # type: ignore[arg-type]
    assert config.api_key == "env-chmaba-key"
    assert config.api_key_source == "environment"
    assert config.store_id == "env-store"
    assert config.webhook_secret == "env-whsec"
    assert config.api_base_url == "https://pay.chmaba.com"


def test_chmaba_config_requires_key_and_store() -> None:
    base = dict(
        api_base_url="https://pay.chmaba.com",
        api_key_source="environment",
    )
    assert ChmabaConfig(api_key="k", store_id="s", **base).configured is True
    assert ChmabaConfig(api_key="k", store_id="", **base).configured is False
    assert ChmabaConfig(api_key="", store_id="s", **base).configured is False


def test_chmaba_is_opt_in_and_bool_parsing() -> None:
    assert default_provider_enabled("chmaba") is False
    assert parse_bool("on", False) is True
    assert parse_bool("off", True) is False
    assert parse_bool(None, True) is True


def test_checkout_url_allowlists_are_provider_scoped() -> None:
    assert is_allowed_chmaba_checkout_url("https://pay.chmaba.com/pay/abc")
    assert is_allowed_chmaba_checkout_url(
        "https://pay.staging.chmaba.com/pay/abc",
        api_base_url="https://pay.staging.chmaba.com",
    )
    assert not is_allowed_chmaba_checkout_url("https://evil.example/pay/abc")
    assert not is_allowed_chmaba_checkout_url("http://pay.chmaba.com/pay/abc")
    assert not is_allowed_cutluy_checkout_url("https://pay.chmaba.com/pay/abc")


@pytest.mark.asyncio
async def test_service_rejects_missing_credentials_without_network() -> None:
    from platform_api.services.shared.chmaba_service import ChmabaConfigurationError

    service = ChmabaService(
        api_base_url="https://pay.chmaba.com",
        api_key="",
        store_id="",
        webhook_secret="",
    )
    with pytest.raises(ChmabaConfigurationError):
        await service.create_payment(amount_cents=100, reference_id="ref")


def test_fresh_signature_uses_injected_clock() -> None:
    body = b"{}"
    header = _sign(body, "secret", 1_000)
    assert verify_chmaba_webhook_signature(
        raw_body=body,
        signature_header=header,
        secret="secret",
        now=1_000 + 299,
    )
    assert not verify_chmaba_webhook_signature(
        raw_body=body,
        signature_header=header,
        secret="secret",
        now=1_001 + 300,
    )
