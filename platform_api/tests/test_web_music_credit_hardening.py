"""Tests for web music credit hardening (P0 + P1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from platform_api.services.v2.credit_service import CreditService


class _FakeDb:
    def __init__(self) -> None:
        self.fetch_val = AsyncMock(return_value=None)
        self.fetch_one = AsyncMock(return_value=None)
        self.execute = AsyncMock()
        self.transaction = lambda: _FakeTxn()


class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def test_fallback_refund_split_when_monthly_pool_was_exhausted() -> None:
    restore_monthly, restore_topup = CreditService._fallback_refund_split(
        10,
        monthly_used=500,
        monthly_granted=500,
    )
    assert restore_monthly == 0
    assert restore_topup == 10


def test_fallback_refund_split_when_monthly_was_available() -> None:
    restore_monthly, restore_topup = CreditService._fallback_refund_split(
        10,
        monthly_used=40,
        monthly_granted=500,
    )
    assert restore_monthly == 10
    assert restore_topup == 0


@pytest.mark.asyncio
async def test_refund_credits_is_idempotent_with_reference_id() -> None:
    db = _FakeDb()
    service = CreditService(db)
    user_id = "11111111-1111-1111-1111-111111111111"
    task_id = "22222222-2222-2222-2222-222222222222"

    db.fetch_val.side_effect = [None, 1]
    db.fetch_one.side_effect = [
        {
            "id": "sub-1",
            "monthly_credits_granted": 500,
            "monthly_credits_used": 10,
            "topup_credits_balance": 0,
        },
        {"metadata": {"monthly": 10, "topup": 0}},
    ]

    with patch.object(service, "_refresh_subscription_state", AsyncMock()), patch.object(
        service,
        "_refund_subscription_credits",
        AsyncMock(return_value=True),
    ) as refund_mock:
        first = await service.refund_credits(
            user_id,
            10,
            "web_music_generation",
            reference_id=task_id,
        )
        second = await service.refund_credits(
            user_id,
            10,
            "web_music_generation",
            reference_id=task_id,
        )

    assert first is True
    assert second is True
    refund_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_refund_subscription_restores_monthly_from_debit_metadata() -> None:
    db = _FakeDb()
    service = CreditService(db)
    user_id = "11111111-1111-1111-1111-111111111111"
    task_id = "22222222-2222-2222-2222-222222222222"
    subscription = {
        "id": "sub-1",
        "monthly_credits_granted": 500,
        "monthly_credits_used": 20,
        "topup_credits_balance": 5,
    }

    with patch.object(
        service,
        "_lookup_debit_split",
        AsyncMock(return_value=(10, 0)),
    ):
        db.fetch_val = AsyncMock(return_value=None)
        db.fetch_one.return_value = {
            "id": "sub-1",
            "monthly_credits_used": 20,
            "topup_credits_balance": 5,
        }
        ok = await service._refund_subscription_credits(
            user_id=user_id,
            amount=10,
            source="web_music_generation",
            reference_id=task_id,
            subscription=subscription,
        )

    assert ok is True
    assert db.execute.await_count >= 1


@pytest.mark.asyncio
async def test_consume_credits_falls_back_to_daily_when_no_active_subscription() -> None:
    db = _FakeDb()
    service = CreditService(db)
    user_id = "33333333-3333-3333-3333-333333333333"

    with patch.object(service, "_refresh_subscription_state", AsyncMock()), patch.object(
        service,
        "daily_free_limit",
        AsyncMock(return_value=50),
    ), patch.object(service, "_consume_daily_free_credits", AsyncMock(return_value=True)) as daily_mock:
        db.fetch_one.return_value = None
        ok = await service.consume_credits(user_id, 10, "web_music_generation")

    assert ok is True
    daily_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_daily_free_limit_reads_the_free_plan_row() -> None:
    db = _FakeDb()
    service = CreditService(db)
    db.fetch_one = AsyncMock(return_value={"daily_credits": 50})

    assert await service.daily_free_limit() == 50
    db.fetch_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_daily_free_limit_is_zero_without_a_free_plan_row() -> None:
    """The retired web_music_free_daily_credits setting is no longer a fallback."""
    db = _FakeDb()
    service = CreditService(db)
    db.fetch_one = AsyncMock(return_value=None)

    assert await service.daily_free_limit() == 0
    db.fetch_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_refund_skips_desktop_pro() -> None:
    from platform_api.routers.callbacks import _refund_web_music_generation_on_failure

    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"?column?": 1})
    credit_mock = AsyncMock()
    with patch(
        "platform_api.services.v2.credit_service.get_credit_service",
        return_value=credit_mock,
    ):
        await _refund_web_music_generation_on_failure(
            pool,
            user_id=str(UUID("44444444-4444-4444-4444-444444444444")),
            task_id=UUID("55555555-5555-5555-5555-555555555555"),
            prior_status="PENDING",
        )

    credit_mock.refund_credits.assert_not_called()
