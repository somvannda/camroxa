"""Guards for the local-video refund endpoint (Phase 0 billing hardening).

The refund amount must come from the charge stashed at consume time, never from
the request body, so a client cannot refund more than it was charged or refund
an operation it never ran.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.routers import generation as gen


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(user_id=str(uuid4()))


@pytest.mark.asyncio
async def test_video_refund_uses_stashed_charge_not_client_amount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gen, "enforce_rate_limit", AsyncMock())
    monkeypatch.setattr(gen, "_assert_owned_channel_profile", AsyncMock())

    enforcement = AsyncMock()
    enforcement.pop_operation_charge = AsyncMock(return_value=10)
    enforcement.refund_failed_operation = AsyncMock()

    request = gen.LocalVideoRefundRequest(
        operation_type="video",
        ref_id="video:ref-1",
        charged_credit_units=99999,
    )
    out = await gen.refund_local_video_operation(
        request, SimpleNamespace(), _ctx(), enforcement, AsyncMock()
    )

    assert out["status"] == "refunded"
    assert (
        enforcement.refund_failed_operation.await_args.kwargs["charged_credit_units"]
        == 10
    )


@pytest.mark.asyncio
async def test_video_refund_noop_when_no_stashed_charge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gen, "enforce_rate_limit", AsyncMock())
    monkeypatch.setattr(gen, "_assert_owned_channel_profile", AsyncMock())

    enforcement = AsyncMock()
    enforcement.pop_operation_charge = AsyncMock(return_value=None)
    enforcement.refund_failed_operation = AsyncMock()

    request = gen.LocalVideoRefundRequest(
        operation_type="video",
        ref_id="video:never-charged",
        charged_credit_units=50,
    )
    out = await gen.refund_local_video_operation(
        request, SimpleNamespace(), _ctx(), enforcement, AsyncMock()
    )

    assert out["status"] == "noop"
    enforcement.refund_failed_operation.assert_not_awaited()


@pytest.mark.asyncio
async def test_video_refund_requires_ref_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gen, "enforce_rate_limit", AsyncMock())
    monkeypatch.setattr(gen, "_assert_owned_channel_profile", AsyncMock())

    request = gen.LocalVideoRefundRequest(operation_type="video", ref_id=None)
    with pytest.raises(Exception):
        await gen.refund_local_video_operation(
            request, SimpleNamespace(), _ctx(), AsyncMock(), AsyncMock()
        )
