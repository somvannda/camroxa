"""Tests for ProviderKeyBalanceService normalizers and unsupported paths."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from platform_api.services.provider_key_balance_service import (
    ProviderKeyBalanceService,
    _normalize_deepseek,
    _normalize_fal,
    _normalize_slai,
    _normalize_suno,
    compute_day_usage,
)


def test_normalize_suno_credits() -> None:
    amount, currency, unit = _normalize_suno({"data": {"credits": 42}})
    assert amount == 42
    assert unit == "credits"


def test_normalize_suno_data_is_int() -> None:
    amount, currency, unit = _normalize_suno({"code": 200, "msg": "success", "data": 100})
    assert amount == 100
    assert unit == "credits"
    assert currency is None
    assert currency is None


def test_normalize_deepseek_prefers_usd() -> None:
    amount, currency, unit = _normalize_deepseek(
        {
            "balance_infos": [
                {"currency": "CNY", "total_balance": "10"},
                {"currency": "USD", "total_balance": "8.5"},
            ]
        }
    )
    assert amount == 8.5
    assert currency == "USD"
    assert unit == "currency"


def test_normalize_fal_credits() -> None:
    amount, currency, unit = _normalize_fal(
        {"credits": {"current_balance": 24.5, "currency": "USD"}}
    )
    assert amount == 24.5
    assert currency == "USD"


def test_normalize_slai_available_units() -> None:
    amount, currency, unit = _normalize_slai(
        {
            "balance": {
                "userId": "550e8400-e29b-41d4-a716-446655440000",
                "availableUnits": 271693612,
                "lifetimePurchasedUnits": 7700000000,
                "lifetimeUsedUnits": 7428306388,
                "version": 4,
                "updatedAt": "2026-08-03T08:30:00Z",
            }
        }
    )
    assert amount == pytest.approx(271.693612)
    assert currency is None
    assert unit == "credits"


def test_compute_day_usage_first_read() -> None:
    start, used = compute_day_usage(current=5000.0, start=None, last=None)
    assert start == 5000.0
    assert used == 0.0


def test_compute_day_usage_balance_drop() -> None:
    start, used = compute_day_usage(current=4880.0, start=5000.0, last=5000.0)
    assert start == 5000.0
    assert used == pytest.approx(120.0)


def test_compute_day_usage_top_up_preserves_prior_usage() -> None:
    # Used 120 already (5000 -> 4880), then top-up +1000 to 5880.
    start, used = compute_day_usage(current=5880.0, start=5000.0, last=4880.0)
    assert start == pytest.approx(6000.0)
    assert used == pytest.approx(120.0)


def test_format_display_slai_credits() -> None:
    text = ProviderKeyBalanceService._format_display(
        271.693612, None, "credits", "ok", None
    )
    assert text == "271.69 credits"


@pytest.mark.asyncio
async def test_openai_marked_unsupported_on_403(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        status_code = 403
        text = "session key required"

        def json(self):
            return {}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return _Resp()

    monkeypatch.setattr(
        "platform_api.services.provider_key_balance_service.httpx.AsyncClient",
        lambda *a, **k: _Client(),
    )
    service = ProviderKeyBalanceService(
        redis=None,
        key_pool=None,
        settings=SimpleNamespace(),
    )
    amount, currency, unit, raw, status, error = await service._fetch_openai("sk-test")
    assert amount is None
    assert status == "unsupported"
    assert error is not None


@pytest.mark.asyncio
async def test_fetch_slai_uses_official_balance_api(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_urls: list[str] = []

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "balance": {
                    "userId": "u1",
                    "availableUnits": 271693612,
                    "lifetimePurchasedUnits": 7700000000,
                    "lifetimeUsedUnits": 7428306388,
                    "version": 1,
                    "updatedAt": "2026-08-05T00:00:00Z",
                }
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            seen_urls.append(url)
            assert headers["Authorization"] == "Bearer sk-slai"
            return _Resp()

    monkeypatch.setattr(
        "platform_api.services.provider_key_balance_service.httpx.AsyncClient",
        lambda *a, **k: _Client(),
    )
    service = ProviderKeyBalanceService(
        redis=None,
        key_pool=None,
        settings=SimpleNamespace(slai_api_base_url="https://api.slai.shop"),
    )
    amount, currency, unit, raw, status, error = await service._fetch_slai("sk-slai")
    assert status == "ok"
    assert amount == pytest.approx(271.693612)
    assert unit == "credits"
    assert error is None
    assert seen_urls[0] == "https://slai-api.slai.shop/v1/balance"
    assert isinstance(raw, dict)


@pytest.mark.asyncio
async def test_get_all_balances_lists_keys() -> None:
    key_id = uuid4()

    class _Pool:
        async def list_keys(self, provider: str):
            if provider != "suno":
                return []
            return [
                SimpleNamespace(
                    id=key_id,
                    label="suno-main",
                    status="active",
                    priority=50,
                )
            ]

        async def get_decrypted_key_value(self, kid):
            return "sk-suno"

    class _Service(ProviderKeyBalanceService):
        async def _fetch_provider_balance(self, provider, api_key):
            return 100.0, None, "credits", {"credits": 100}, "ok", None

    service = _Service(redis=None, key_pool=_Pool(), settings=SimpleNamespace())
    data = await service.get_all_balances()
    suno = next(p for p in data["providers"] if p["provider"] == "suno")
    assert len(suno["keys"]) == 1
    assert suno["keys"][0]["label"] == "suno-main"
    assert suno["keys"][0]["balance"] == 100.0
    assert suno["keys"][0]["fetch_status"] == "ok"
