"""End-to-end unit coverage for the provider-switched top-up flow.

These tests pin the two behaviours that produced the October 2026 production
outage and the ChmabaPay migration:

* a non-subscriber checkout must insert ``web_subscription_id = NULL`` (the
  database may not reject it), and
* a settled ChmabaPay webhook must credit exactly once.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from platform_api.services.v2.topup_service import TopupService

PACK_ROW = {
    "id": "pack-small",
    "slug": "small",
    "name": "Small Pack",
    "pack_type": "web_music",
    "total_credits": 1000,
    "price_cents": 500,
    "display_order": 1,
    "is_active": True,
}


class ProviderPool:
    """Minimal asyncpg-pool stand-in for ``system_settings`` lookups."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    async def fetchrow(self, query: str, key: str):
        if key not in self.values:
            return None
        return {"value": self.values[key]}


def chmaba_pool(**overrides: str) -> ProviderPool:
    values = {
        "billing.active_provider": "chmaba",
        "billing.provider.chmaba.enabled": "true",
        "billing.chmaba.api_key": "ck_live_test",
        "billing.chmaba.store_id": "st_test",
        "billing.chmaba.webhook_secret": "whsec_test",
    }
    values.update(overrides)
    return ProviderPool(values)


@pytest.mark.asyncio
async def test_topup_purchase_allows_null_subscription_and_uses_chmaba(monkeypatch) -> None:
    db = AsyncMock()
    db._pool = chmaba_pool()
    # 1) pack lookup, 2) active-subscription lookup (none), 3) v3 sync row.
    db.fetch_one = AsyncMock(side_effect=[PACK_ROW, None, None])
    db.fetch_val = AsyncMock(side_effect=[0, "topup-1"])
    db.execute = AsyncMock()

    from platform_api.services.shared.chmaba_service import ChmabaService

    created: dict[str, Any] = {}

    async def fake_create(self, **kwargs):
        created.update(kwargs)
        return {
            "checkout_url": "https://pay.chmaba.com/pay/abc",
            "payment_id": "pay_abc",
            "expires_at": "",
            "qr_string": "00020101021229300012D156000000000510A93FO3230Q31280012",
            "provider": "chmaba",
        }

    monkeypatch.setattr(ChmabaService, "create_payment", fake_create)

    service = TopupService(db)
    result = await service.purchase_topup(
        user_id="user-1",
        pack_slug="small",
        success_url="https://music.camxora.com/create",
        cancel_url="https://music.camxora.com/create",
    )

    assert result["provider"] == "chmaba"
    # The local top-up id is the provider reference, so the webhook can bind
    # straight back to this row without trusting client metadata.
    assert created["reference_id"] == "topup-1"
    assert created["amount_cents"] == 500

    insert_call = next(
        call
        for call in db.fetch_val.await_args_list
        if "INSERT INTO topup_purchases" in call.args[0]
    )
    assert insert_call.args[2] is None, "non-subscriber must insert NULL subscription id"

    provider_update = next(
        call
        for call in db.execute.await_args_list
        if "payment_provider" in call.args[0]
    )
    assert provider_update.args[1] == "pay_abc"
    assert provider_update.args[2] == "chmaba"


@pytest.mark.asyncio
async def test_topup_purchase_falls_back_to_cutluy_when_settings_missing(monkeypatch) -> None:
    db = AsyncMock()
    db._pool = ProviderPool({})
    db.fetch_one = AsyncMock(side_effect=[PACK_ROW, None])
    db.fetch_val = AsyncMock(side_effect=[0, "topup-2"])
    db.execute = AsyncMock()

    cutluy = AsyncMock()
    cutluy.create_topup_payment = AsyncMock(
        return_value={
            "checkout_url": "https://cutluy.com/pay/abc",
            "payment_id": "pay_cutluy",
            "expires_at": "",
            "qr_string": "00020101021229300012D156000000000510A93FO3230Q31280012",
        }
    )

    service = TopupService(db, cutluy=cutluy)
    result = await service.purchase_topup(
        user_id="user-2",
        pack_slug="small",
        success_url="https://music.camxora.com/create",
        cancel_url="https://music.camxora.com/create",
    )

    assert result["provider"] == "cutluy"
    cutluy.create_topup_payment.assert_awaited_once()


@pytest.mark.asyncio
async def test_topup_status_polls_the_provider_stored_on_the_row(monkeypatch) -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        return_value={
            "id": "topup-3",
            "payment_status": "pending",
            "credits_purchased": 1000,
            "amount_paid_cents": 500,
            "payment_provider": "chmaba",
            "pack_name": "Small Pack",
        }
    )
    db.execute = AsyncMock()

    from platform_api.services.shared.chmaba_service import ChmabaService

    async def fake_status(self, payment_id, db=None):
        assert payment_id == "pay_chmaba"
        return {"status": "PAID", "amount": 5.0}

    monkeypatch.setattr(ChmabaService, "get_payment_status", fake_status)
    monkeypatch.setattr(TopupService, "_sync_v3_pack", AsyncMock())

    cutluy = AsyncMock()
    service = TopupService(db, cutluy=cutluy)
    result = await service.get_checkout_status("user-3", "pay_chmaba")

    assert result["status"] == "paid"
    assert result["fulfilled"] is True
    cutluy.get_payment_status.assert_not_called()


@pytest.mark.asyncio
async def test_settle_chmaba_topup_credits_once(monkeypatch) -> None:
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch_one = AsyncMock(
        side_effect=[
            {"id": "11111111-1111-1111-1111-111111111111", "payment_status": "pending"},
            {"id": "11111111-1111-1111-1111-111111111111", "payment_status": "completed"},
        ]
    )
    monkeypatch.setattr(TopupService, "_sync_v3_pack", AsyncMock())

    service = TopupService(db, cutluy=AsyncMock())

    first = await service.settle_chmaba_topup(
        event_type="payment.completed", topup_id="11111111-1111-1111-1111-111111111111"
    )
    second = await service.settle_chmaba_topup(
        event_type="payment.completed", topup_id="11111111-1111-1111-1111-111111111111"
    )

    assert first["processed"] is True
    assert second["processed"] is True
    assert "already" in second["message"].lower()
    status_updates = [
        call for call in db.execute.await_args_list if "payment_status = 'completed'" in call.args[0]
    ]
    assert len(status_updates) == 1


@pytest.mark.asyncio
async def test_settle_chmaba_topup_marks_reversal_refunded(monkeypatch) -> None:
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch_one = AsyncMock(return_value={"id": "22222222-2222-2222-2222-222222222222", "payment_status": "completed"})
    monkeypatch.setattr(TopupService, "_sync_v3_pack", AsyncMock())

    service = TopupService(db, cutluy=AsyncMock())
    result = await service.settle_chmaba_topup(
        event_type="payment.reversed", topup_id="22222222-2222-2222-2222-222222222222"
    )

    assert result["processed"] is True
    refund_call = next(
        call for call in db.execute.await_args_list if "payment_status = $2" in call.args[0]
    )
    assert refund_call.args[1] == "22222222-2222-2222-2222-222222222222"
    assert refund_call.args[2] == "refunded"


@pytest.mark.asyncio
async def test_settle_chmaba_topup_rejects_non_uuid_reference() -> None:
    db = AsyncMock()
    service = TopupService(db, cutluy=AsyncMock())

    result = await service.settle_chmaba_topup(
        event_type="payment.completed", topup_id="camxora:user:plan:abc"
    )

    assert result["processed"] is False
    db.fetch_one.assert_not_called()
