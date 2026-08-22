"""Web music checkout uses CutLuy config only and fulfills on status poll."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from platform_api.services.shared.cutluy_service import (
    CutLuyService,
    extract_cutluy_qr_string,
    normalize_cutluy_payment_status,
)
from platform_api.services.v2.subscription_service import SubscriptionService
from platform_api.services.v2.topup_service import TopupService


def test_extract_cutluy_qr_string() -> None:
    payload = "00020101021229300012KHQRFAKEPAYLOAD6304ABCD"
    assert extract_cutluy_qr_string({"qr_string": payload}) == payload
    assert extract_cutluy_qr_string({"qr_string": payload}) == payload
    assert extract_cutluy_qr_string({"data": {"khqr": payload}}) == payload
    assert extract_cutluy_qr_string({"qr_string": "https://cutluy.com/pay/x"}) is None
    assert extract_cutluy_qr_string({}) is None


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
        return {
            "id": "pay_1",
            "checkout_url": "https://cutluy.com/pay/x",
            "expires_at": "",
            "qr_string": "00020101021229300012KHQRFAKEPAYLOAD6304ABCD",
        }


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

    async def get(self, url: str, headers=None):
        self._captured["get_url"] = url
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
    assert result["qr_string"].startswith("000201")
    assert "get_url" not in captured
    assert "payment_link_id" not in captured["json"]
    assert captured["json"]["success_url"] == "https://music.example/create"
    assert captured["json"]["cancel_url"] == "https://music.example/create"
    assert captured["json"]["metadata"]["type"] == "subscription"


class _NestedCutluyResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "data": {
                "id": "pay_nested",
                "checkout_url": "https://cutluy.com/pay/nested",
                "expires_at": None,
                "qr_string": "00020101021229300012KHQRNESTEDPAYLOAD6304ABCD",
            }
        }


class _TimeoutClient:
    async def __aenter__(self) -> "_TimeoutClient":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def post(self, url: str, headers=None, json=None):
        raise httpx.ReadTimeout("CutLuy read timeout")


@pytest.mark.asyncio
async def test_cutluy_nested_payload_and_null_expires_at() -> None:
    captured: dict = {}
    service = CutLuyService.__new__(CutLuyService)
    service._api_key = "ck_test"
    service._webhook_secret = ""
    service._api_url = "https://cutluy.com/v1"

    async def resolve_config(_db=None):
        return "https://cutluy.com", "ck_test", ""

    service._resolve_config = resolve_config  # type: ignore[method-assign]

    class _NestedClient(_FakeClient):
        async def post(self, url: str, headers=None, json=None):
            self._captured["url"] = url
            self._captured["json"] = json
            return _NestedCutluyResponse()

    with patch("httpx.AsyncClient", return_value=_NestedClient(captured)):
        result = await service.create_topup_payment(
            user_id="user-1",
            pack_name="Medium",
            amount_cents=400,
            credits=200,
            success_url="https://music.example/create",
            cancel_url="https://music.example/create",
        )

    assert result["checkout_url"] == "https://cutluy.com/pay/nested"
    assert result["payment_id"] == "pay_nested"
    assert result["expires_at"] == ""
    assert result["qr_string"].startswith("000201")


class _CreateWithoutQrResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"id": "pay_get", "checkout_url": "https://cutluy.com/pay/get", "expires_at": ""}


class _GetQrResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"data": {"qr_string": "00020101021229300012KHQRGETPAYLOAD6304ABCD"}}


@pytest.mark.asyncio
async def test_cutluy_fetches_qr_string_when_create_omits_it() -> None:
    captured: dict = {}
    service = CutLuyService.__new__(CutLuyService)
    service._api_key = "ck_test"
    service._webhook_secret = ""
    service._api_url = "https://cutluy.com/v1"

    async def resolve_config(_db=None):
        return "https://cutluy.com", "ck_test", ""

    service._resolve_config = resolve_config  # type: ignore[method-assign]

    class _FetchQrClient:
        async def __aenter__(self) -> "_FetchQrClient":
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        async def post(self, url: str, headers=None, json=None):
            captured["post_url"] = url
            return _CreateWithoutQrResponse()

        async def get(self, url: str, headers=None):
            captured["get_url"] = url
            return _GetQrResponse()

    with patch("httpx.AsyncClient", return_value=_FetchQrClient()):
        result = await service.create_topup_payment(
            user_id="user-1",
            pack_name="Medium",
            amount_cents=400,
            credits=200,
            success_url="https://music.example/create",
            cancel_url="https://music.example/create",
        )

    assert result["payment_id"] == "pay_get"
    assert result["qr_string"].startswith("000201")
    assert captured["get_url"].endswith("/v1/payments/pay_get")


@pytest.mark.asyncio
async def test_cutluy_timeout_is_retryable_value_error() -> None:
    service = CutLuyService.__new__(CutLuyService)
    service._api_key = "ck_test"
    service._webhook_secret = ""
    service._api_url = "https://cutluy.com/v1"

    async def resolve_config(_db=None):
        return "https://cutluy.com", "ck_test", ""

    service._resolve_config = resolve_config  # type: ignore[method-assign]

    with patch("httpx.AsyncClient", return_value=_TimeoutClient()):
        with pytest.raises(ValueError, match="timed out"):
            await service.create_topup_payment(
                user_id="user-1",
                pack_name="Medium",
                amount_cents=400,
                credits=200,
                success_url="https://music.example/create",
                cancel_url="https://music.example/create",
            )


@pytest.mark.asyncio
async def test_subscription_status_fulfills_when_cutluy_paid() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        return_value={
            "id": "sub-1",
            "status": "pending",
            "monthly_credits_granted": 500,
            "plan_name": "starter_monthly",
            "price_cents": 900,
        }
    )
    db.execute = AsyncMock()
    cutluy = AsyncMock()
    cutluy.get_payment_status = AsyncMock(return_value={"status": "paid", "amount": 9.0})

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
            "qr_string": "00020101021229300012KHQRFAKEPAYLOAD6304ABCD",
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
    assert result["qr_string"].startswith("000201")
    db.fetch_val.assert_not_called()
    assert db.execute.await_count >= 2
    assert any(
        "status = 'pending'" in str(call.args[0])
        for call in db.execute.await_args_list
    )


@pytest.mark.asyncio
async def test_create_subscription_reuses_expired_row() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        side_effect=[
            {"id": "sub-expired", "status": "expired", "plan_id": "plan-old"},
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
    db.fetch_val = AsyncMock()
    cutluy = AsyncMock()
    cutluy.create_subscription_payment = AsyncMock(
        return_value={
            "checkout_url": "https://cutluy.com/pay/x",
            "payment_id": "pay_new",
            "expires_at": "",
            "qr_string": "00020101021229300012KHQRFAKEPAYLOAD6304ABCD",
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
    update_sql = db.execute.await_args_list[0].args[0]
    assert "status = 'pending'" in update_sql
    assert "status <> 'active'" in update_sql


@pytest.mark.asyncio
async def test_topup_status_fulfills_when_cutluy_paid() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        return_value={
            "id": "top-1",
            "payment_status": "pending",
            "credits_purchased": 200,
            "pack_name": "Medium",
            "amount_paid_cents": 400,
        }
    )
    db.execute = AsyncMock()
    cutluy = AsyncMock()
    cutluy.get_payment_status = AsyncMock(return_value={"status": "completed", "amount": 4.0})

    service = TopupService(db, cutluy=cutluy)
    result = await service.get_checkout_status("user-1", "pay_2")

    assert result["status"] == "paid"
    assert result["fulfilled"] is True
    assert result["pack_name"] == "Medium"
    db.execute.assert_awaited()


@pytest.mark.asyncio
async def test_checkout_status_rejects_unsafe_payment_id() -> None:
    db = AsyncMock()
    cutluy = AsyncMock()
    service = SubscriptionService(db, cutluy=cutluy)

    with pytest.raises(LookupError):
        await service.get_checkout_status("user-1", "../etc/passwd")

    db.fetch_one.assert_not_called()
    cutluy.get_payment_status.assert_not_called()


@pytest.mark.asyncio
async def test_subscription_status_refuses_amount_mismatch() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        return_value={
            "id": "sub-1",
            "status": "pending",
            "monthly_credits_granted": 5000,
            "plan_name": "pro_monthly",
            "price_cents": 2900,
        }
    )
    db.execute = AsyncMock()
    cutluy = AsyncMock()
    cutluy.get_payment_status = AsyncMock(return_value={"status": "paid", "amount": 9.0})

    service = SubscriptionService(db, cutluy=cutluy)
    result = await service.get_checkout_status("user-1", "pay_cheap")

    assert result["status"] == "pending"
    assert result["fulfilled"] is False
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_private_plan_cannot_be_purchased() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        return_value={
            "id": "plan-hidden",
            "name": "staff_comp",
            "plan_type": "web_music",
            "price_cents": 100,
            "billing_cycle_days": 30,
            "monthly_credits": 99999,
            "monthly_song_quota": None,
            "features": {},
            "is_public": False,
            "display_order": 99,
        }
    )
    cutluy = AsyncMock()
    service = SubscriptionService(db, cutluy=cutluy)

    with pytest.raises(ValueError, match="not available"):
        await service.create_subscription_by_plan_id(
            user_id="user-1",
            plan_id="plan-hidden",
            success_url="https://evil.example/phish",
            cancel_url="https://evil.example/phish",
        )
    cutluy.create_subscription_payment.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_ignores_stale_payment_after_plan_swap() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)
    db.execute = AsyncMock()
    cutluy = AsyncMock()
    cutluy.verify_webhook_signature_async = AsyncMock(return_value=True)

    service = SubscriptionService(db, cutluy=cutluy)
    result = await service.handle_cutluy_webhook(
        event_type="payment.completed",
        payload={
            "id": "pay_old_cheap",
            "amount": 9.0,
            "metadata": {"subscription_id": "sub-1", "user_id": "user-1", "type": "subscription"},
        },
        signature="t=1,v1=abc",
        raw_body=b"{}",
    )

    assert result["processed"] is True
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_fulfills_only_bound_payment() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        return_value={
            "id": "sub-1",
            "user_id": "user-1",
            "status": "pending",
            "price_cents": 900,
        }
    )
    db.execute = AsyncMock()
    cutluy = AsyncMock()
    cutluy.verify_webhook_signature_async = AsyncMock(return_value=True)

    service = SubscriptionService(db, cutluy=cutluy)
    await service.handle_cutluy_webhook(
        event_type="payment.completed",
        payload={
            "id": "pay_current",
            "amount": 9.0,
            "metadata": {"subscription_id": "sub-1", "user_id": "user-1", "type": "subscription"},
        },
        signature="t=1,v1=abc",
        raw_body=b"{}",
    )

    db.execute.assert_awaited()
    sql = db.execute.await_args.args[0]
    assert "status = 'pending'" in sql
    assert "external_subscription_id" in sql


@pytest.mark.asyncio
async def test_create_subscription_sanitizes_return_urls() -> None:
    db = AsyncMock()
    db.fetch_one = AsyncMock(
        side_effect=[
            None,
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
    db.fetch_val = AsyncMock(return_value="sub-new")
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
    await service.create_subscription(
        user_id="user-1",
        plan_name="starter_monthly",
        billing_cycle="monthly",
        success_url="https://evil.example/steal",
        cancel_url="https://evil.example/steal",
    )

    kwargs = cutluy.create_subscription_payment.await_args.kwargs
    assert kwargs["success_url"] == "https://music.camxora.com/create"
    assert kwargs["cancel_url"] == "https://music.camxora.com/create"
