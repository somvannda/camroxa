"""Ensure unverified credit pack purchase stays closed (Phase 3 / C1)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from platform_api.exceptions import ForbiddenError
from platform_api.routers.credits import PurchaseRequest, purchase_pack


@pytest.mark.asyncio
async def test_credit_purchase_remains_disabled() -> None:
    with pytest.raises(ForbiddenError) as exc:
        await purchase_pack(
            request=PurchaseRequest(pack_id="00000000-0000-0000-0000-000000000001", payment_ref="fake"),
            ctx=MagicMock(),
            credit_service=MagicMock(),
            pack_repo=MagicMock(),
        )
    assert exc.value.details["error_code"] == "CREDIT_PURCHASE_USE_BILLING_CHECKOUT"
