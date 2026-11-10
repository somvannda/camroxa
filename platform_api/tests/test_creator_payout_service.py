"""Tests for creator payout readiness."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.services.creator_payout_service import (
    CreatorPayoutService,
    split_withholding,
    withholding_bps_for,
)


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
        side_effect=[
            _kyc("verified"),
            {"method": "aba"},
            {"withholding_rate_bps": 3000},
            payout,
        ]
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


@pytest.mark.asyncio
async def test_payout_run_creates_one_payout_per_eligible_creator() -> None:
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetch = AsyncMock(
        return_value=[
            {"creator_id": uuid4(), "amount_micros": 30_000_000, "method": "aba"},
            {"creator_id": uuid4(), "amount_micros": 25_000_000, "method": "wing"},
        ]
    )
    service._pool.fetchval = AsyncMock(side_effect=[uuid4(), None])

    result = await service.create_run(
        period_start=date(2026, 10, 1),
        period_end=date(2026, 11, 1),
        created_by=str(uuid4()),
    )

    assert result["eligible_creators"] == 2
    assert result["created"] == 1
    assert result["skipped"] == 1


@pytest.mark.asyncio
async def test_mark_paid_requires_approval() -> None:
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetchrow = AsyncMock(
        return_value={**_payout(uuid4()), "status": "requested", "created_by": uuid4()}
    )

    with pytest.raises(ValidationError) as exc:
        await service.mark_paid(
            str(uuid4()), reference="ABA-123", reviewer_id=str(uuid4())
        )

    assert "status" in (exc.value.details or {}).get("fields", {})


@pytest.mark.asyncio
async def test_maker_checker_blocks_same_approver_marking_paid() -> None:
    reviewer = uuid4()
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetchrow = AsyncMock(
        return_value={
            **_payout(uuid4()),
            "status": "approved",
            "created_by": uuid4(),
            "approved_by": reviewer,
        }
    )

    with pytest.raises(ValidationError) as exc:
        await service.mark_paid(
            str(uuid4()), reference="ABA-123", reviewer_id=str(reviewer)
        )

    assert "payment" in (exc.value.details or {}).get("fields", {})


@pytest.mark.asyncio
async def test_maker_checker_blocks_creator_approving_own_payout() -> None:
    creator = uuid4()
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetchrow = AsyncMock(
        return_value={**_payout(creator), "status": "requested", "created_by": creator}
    )

    with pytest.raises(ValidationError) as exc:
        await service.approve_payout(str(uuid4()), reviewer_id=str(creator))

    assert "approval" in (exc.value.details or {}).get("fields", {})


@pytest.mark.asyncio
async def test_release_available_earnings_promotes_due_rows() -> None:
    service = CreatorPayoutService(AsyncMock())
    service._pool.execute = AsyncMock(return_value="UPDATE 4")

    released = await service.release_available_earnings()

    assert released == 4


@pytest.mark.asyncio
async def test_signed_kyc_document_requires_a_submission() -> None:
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.signed_kyc_document(str(uuid4()), kind="id")


@pytest.mark.asyncio
async def test_signed_kyc_document_passes_legacy_urls_through() -> None:
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetchrow = AsyncMock(
        return_value={
            "id_document_ref": "https://example.com/legacy-id.png",
            "selfie_ref": None,
        }
    )

    payload = await service.signed_kyc_document(str(uuid4()), kind="id")

    assert payload == {
        "url": "https://example.com/legacy-id.png",
        "expires_in": None,
        "signed": False,
    }


@pytest.mark.asyncio
async def test_signed_kyc_document_rejects_a_missing_kind() -> None:
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetchrow = AsyncMock(
        return_value={"id_document_ref": "creator/kyc/x/id.jpg", "selfie_ref": None}
    )

    with pytest.raises(NotFoundError):
        await service.signed_kyc_document(str(uuid4()), kind="selfie")


@pytest.mark.asyncio
async def test_kyc_document_upload_rejects_non_documents() -> None:
    service = CreatorPayoutService(AsyncMock())

    with pytest.raises(ValidationError) as exc:
        await service.upload_kyc_document(
            str(uuid4()), kind="id", content_type="text/plain", data=b"hi"
        )

    assert (exc.value.details or {}).get("fields", {}).get("file")

def test_withholding_rate_follows_tax_status() -> None:
    assert withholding_bps_for("w9", "US") == 0
    assert withholding_bps_for("W9", "us") == 0
    assert withholding_bps_for("w8ben", "KH") == 3000
    assert withholding_bps_for(None, "KH") == 3000
    assert withholding_bps_for("w9", "KH") == 3000


def test_split_withholding_keeps_the_cent() -> None:
    gross, withheld, net = split_withholding(30_000_000, 3000)
    assert (gross, withheld, net) == (30_000_000, 9_000_000, 21_000_000)

    gross, withheld, net = split_withholding(33_333_333, 3000)
    assert gross - withheld == net
    assert withheld == 9_999_999


def test_split_withholding_with_no_rate_is_a_no_op() -> None:
    assert split_withholding(20_000_000, 0) == (20_000_000, 0, 20_000_000)


@pytest.mark.asyncio
async def test_generate_statements_rolls_up_paid_payouts() -> None:
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetch = AsyncMock(
        return_value=[
            {
                "creator_id": uuid4(),
                "gross_micros": 40_000_000,
                "withheld_micros": 12_000_000,
                "net_micros": 28_000_000,
                "payout_count": 2,
            }
        ]
    )
    service._pool.fetchrow = AsyncMock(
        return_value={"tax_form": "w8ben", "tax_country": "KH"}
    )
    service._pool.execute = AsyncMock()

    result = await service.generate_statements(2026)

    assert result == {"year": 2026, "creators": 1, "generated": 1}
    assert "creator_tax_statements" in service._pool.execute.await_args.args[0]



@pytest.mark.asyncio
async def test_reconciliation_flags_drift_and_reports_totals() -> None:
    service = CreatorPayoutService(AsyncMock())
    service._pool.fetch = AsyncMock(
        return_value=[
            {
                "creator_id": uuid4(),
                "earned_micros": 50_000_000,
                "unpaid_micros": 20_000_000,
                "settled_micros": 30_000_000,
                "paid_micros": 29_000_000,
                "in_flight_micros": 0,
                "variance_micros": 1_000_000,
            }
        ]
    )

    result = await service.reconciliation()

    assert result["totals"]["paid_micros"] == 29_000_000
    assert result["totals"]["variance_micros"] == 1_000_000
    assert result["totals"]["balanced"] is False
