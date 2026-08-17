"""Web music checkout uses CutLuy config only and fulfills on status poll."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from platform_api.services.shared.cutluy_service import (
    CutLuyService,
    normalize_cutluy_payment_status,
)
from platform_api.services.v2.subscription_service import SubscriptionService
from platform_api.services.v2.topup_service import TopupService


def test_normalize_cutluy_payment_status() -> None:
    assert normalize_cutluy_payment_status("paid") == "paid"
    assert normalize_cutluy_payment_status("COMPLETED") == "paid"
    assert normalize_cutluy_payment_status("failed") == "failed"
    assert normalize_cutluy_payment_status("expired") == "expired"
    assert normalize_cutluy_payment_status("pending") == "pending"
    assert normalize_cutluy_payment_status(None) == "pending"


class _FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"id": "pay_1", "checkout_url": "https://cutluy.com/pay/x", "expires_at": ""}


class _FakeClient:
    def __init__(self, captured: dict) -> None:
        self._captured = captured

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def post(self, url: str, headers=None, json=None):
        self._captured["url"] = url
        self._captured["json"] = json
        return _FakeResponse()


@pytest.mark.asyncio
async def test_web_music_payment_omits_portal_payment_link() -> None:
    captured: dict = {}
    service = CutLuyService.__new__(CutLuyService)
    service._api_key = "ck_test"
    service._webhook_secret = ""
    service._api_url = "https://cutluy.com/v1"

    async def resolve_config(_db=None):
        return "https://cutluy.com", "ck_test", "portal-link-should-not-be-sent"

    service._resolve_config = resolve_config  # type: ignore[method-assign]

    with patch("httpx.AsyncClient", return_value=_FakeClient(captured)):
        result = await service.create_subscription_payment(
            user_id="user-1",
            plan_name="starter_monthly",
            amount_cents=900,
            billing_cycle="monthly",
            success_url="https://music.example/create",
            cancel_url="https://music.example/create",
        )

    assert result["checkout_url"] == "https://cutluy.com/pay/x"
    assert "payment_link_id" not in captured["json"]
    assert captured["json"]["success_url"] == "https://music.example/create"
    assert captured["json"]["cancel_url"] == "https://music.example/create"
    assert captured["json"]["metadata"]["type"] == "subscription"


@pytest.mark.asyncio
async def test_subscription_status_fulfills_when_cutluy_paid() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        return_value={
            "id": "sub-1",
            "status": "pending",
            "monthly_credits_granted": 500,
            "plan_name": "starter_monthly",
        }
    )
    db.execute = AsyncMock()
    cutluy = AsyncMock()
    cutluy.get_payment_status = AsyncMock(return_value={"status": "paid"})

    service = SubscriptionService(db, cutluy=cutluy)
    result = await service.get_checkout_status("user-1", "pay_1")

    assert result["status"] == "paid"
    assert result["fulfilled"] is True
    assert result["credits"] == 500
    db.execute.assert_awaited()


@pytest.mark.asyncio
async def test_subscription_status_is_idempotent_when_already_active() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        return_value={
            "id": "sub-1",
            "status": "active",
            "monthly_credits_granted": 500,
            "plan_name": "starter_monthly",
        }
    )
    cutluy = AsyncMock()
    service = SubscriptionService(db, cutluy=cutluy)

    result = await service.get_checkout_status("user-1", "pay_1")

    assert result["status"] == "paid"
    assert result["fulfilled"] is True
    cutluy.get_payment_status.assert_not_called()


@pytest.mark.asyncio
async def test_create_subscription_reuses_pending_row() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        side_effect=[
            {"id": "sub-pending", "status": "pending", "plan_id": "plan-old"},
            {
                "id": "plan-1",
                "name": "starter_monthly",
                "plan_type": "web_music",
                "price_cents": 900,
                "billing_cycle_days": 30,
                "monthly_credits": 500,
                "monthly_song_quota": None,
                "features": {},
                "is_public": True,
                "display_order": 1,
            },
        ]
    )
    db.execute = AsyncMock()
    cutluy = AsyncMock()
    cutluy.create_subscription_payment = AsyncMock(
        return_value={
            "checkout_url": "https://cutluy.com/pay/x",
            "payment_id": "pay_new",
            "expires_at": "",
        }
    )

    service = SubscriptionService(db, cutluy=cutluy)
    result = await service.create_subscription(
        user_id="user-1",
        plan_name="starter_monthly",
        billing_cycle="monthly",
        success_url="https://music.example/create",
        cancel_url="https://music.example/create",
    )

    assert result["payment_id"] == "pay_new"
    db.fetch_val.assert_not_called()
    assert db.execute.await_count >= 2


@pytest.mark.asyncio
async def test_topup_status_fulfills_when_cutluy_paid() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        return_value={
            "id": "top-1",
            "payment_status": "pending",
            "credits_purchased": 200,
            "pack_name": "Medium",
        }
    )
    db.execute = AsyncMock()
    cutluy = AsyncMock()
    cutluy.get_payment_status = AsyncMock(return_value={"status": "completed"})

    service = TopupService(db, cutluy=cutluy)
    result = await service.get_checkout_status("user-1", "pay_2")

    assert result["status"] == "paid"
    assert result["fulfilled"] is True
    assert result["pack_name"] == "Medium"
    db.execute.assert_awaited()
