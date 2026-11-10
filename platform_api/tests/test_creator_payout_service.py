"""Tests for creator payout readiness."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.creator_payout_service import CreatorPayoutService


def _kyc(status="pending"):
    return {
        "user_id": uuid4(),
        "legal_name": "Sokha Chan",
        "date_of_birth": date(1998, 5, 1),
        "country_code": "KH",
        "id_type": "national_id",
        "id_last4": "1234",
        "id_document_ref": "kyc/doc-1",
        "selfie_ref": None,
        "tax_id": None,
        "status": status,
    }


def _payout(creator_id):
    return {
        "id": uuid4(),
        "creator_id": creator_id,
        "amount_micros": 30_000_000,
        "currency": "USD",
        "method": "aba",
        "status": "requested",
    }


@pytest.mark.asyncio
async def test_kyc_rejects_under_18() -> None:
    service = CreatorPayoutService(AsyncMock())
    with pytest.raises(ValidationError) as exc:
        await service.submit_kyc(
            str(uuid4()),
            {
                "legal_name": "Young Creator",
                "date_of_birth": "2012-01-01",
                "country_code": "KH",
                "id_type": "national_id",
                "id_last4": "1234",
                "id_document_ref": "kyc/doc",
            },
        )
    assert "date_of_birth" in (exc.value.details or {}).get("fields", {})


@pytest.mark.asyncio
async def test_kyc_submit_creates_pending_record() -> None:
    user_id = uuid4()
    row = {**_kyc(), "user_id": user_id}
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetchrow = AsyncMock(side_effect=[None, row])

    result = await service.submit_kyc(
        str(user_id),
        {
            "legal_name": "Sokha Chan",
            "date_of_birth": "1998-05-01",
            "country_code": "KH",
            "id_type": "national_id",
            "id_last4": "1234",
            "id_document_ref": "kyc/doc",
        },
    )

    assert result["kyc"]["status"] == "pending"


@pytest.mark.asyncio
async def test_payout_request_requires_minimum_balance() -> None:
    user_id = uuid4()
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetchrow = AsyncMock(
        side_effect=[_kyc("verified"), {"method": "aba"}]
    )
    service._pool.fetchval = AsyncMock(side_effect=[5_000_000, None])

    with pytest.raises(ValidationError) as exc:
        await service.request_payout(str(user_id))

    assert "balance" in (exc.value.details or {}).get("fields", {})


@pytest.mark.asyncio
async def test_payout_request_creates_requested_payout() -> None:
    user_id = uuid4()
    payout = _payout(user_id)
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetchrow = AsyncMock(
        side_effect=[_kyc("verified"), {"method": "aba"}, payout]
    )
    service._pool.fetchval = AsyncMock(side_effect=[50_000_000, None])

    result = await service.request_payout(str(user_id))

    assert result["payout"]["status"] == "requested"


@pytest.mark.asyncio
async def test_kyc_approval_moves_eligible_tracks_to_earning() -> None:
    user_id = uuid4()
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetchrow = AsyncMock(return_value=_kyc("verified"))
    service._pool.execute = AsyncMock()

    await service.decide_kyc(
        str(user_id), decision="approve", reviewer_id=str(uuid4())
    )

    assert service._pool.execute.await_count == 2
    assert "creator_earning_eligibility" in service._pool.execute.await_args_list[0].args[0]
    assert "notification_queue" in service._pool.execute.await_args_list[1].args[0]
