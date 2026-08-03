"""Tests for ProviderKeyBalanceService normalizers and unsupported paths."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from platform_api.services.provider_key_balance_service import (
    ProviderKeyBalanceService,
    _normalize_deepseek,
    _normalize_fal,
    _normalize_suno,
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
