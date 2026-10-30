"""Free-plan model scoping for web-music charges.

The Free plan's monthly 50 credits sit in the shared wallet. V6-Pro / V6-Wild
must stay locked until the user buys a credit pack in the same calendar month;
V6-Mini is always allowed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from platform_api.exceptions import QuotaExceededError
from platform_api.services.v3.web_music_charge import (
    WebMusicChargeBridge,
    model_allows_free_grant,
)

USER_ID = uuid4()
FREE_PLAN = {"name": "Free", "price_cents": 0}
PRO_PLAN = {"name": "Pro", "price_cents": 1000}
_NOW = datetime.now(timezone.utc)


class FakeStore:
    def __init__(self, plan: dict | None, has_pack: bool) -> None:
        self.plan = plan
        self.has_pack = has_pack

    async def live_pack_expiry(self, user_id):  # noqa: ANN001
        # Paid plans in this test double stand in for a live pack lot.
        if self.plan and int(self.plan.get("price_cents") or 0) > 0:
            return _NOW
        return None

    async def has_completed_topup_this_month(self, user_id):  # noqa: ANN001
        return self.has_pack


def bridge(store: FakeStore) -> WebMusicChargeBridge:
    return WebMusicChargeBridge(
        v3_billing=None,
        v3_grant=None,
        v3_store=store,
        credit_repo=None,
        credit_service=None,
        has_paid_web_subscription=None,
    )


def test_model_allows_free_grant_for_free_plan() -> None:
    assert model_allows_free_grant("V6-MINI", is_free_plan=True, has_pack_this_month=False)
    assert model_allows_free_grant("V6_MINI", is_free_plan=True, has_pack_this_month=False)
    assert model_allows_free_grant("v6 mini", is_free_plan=True, has_pack_this_month=False)
    assert model_allows_free_grant("chirp-goose", is_free_plan=True, has_pack_this_month=False)
    assert not model_allows_free_grant("V6", is_free_plan=True, has_pack_this_month=False)
    assert not model_allows_free_grant("V6-WILD", is_free_plan=True, has_pack_this_month=False)
    # A pack purchase in the same month unlocks the remaining grant.
    assert model_allows_free_grant("V6", is_free_plan=True, has_pack_this_month=True)
    # Paid plans are unrestricted.
    assert model_allows_free_grant("V6", is_free_plan=False, has_pack_this_month=False)
    # Missing model (non-generation operations) is not blocked here.
    assert model_allows_free_grant(None, is_free_plan=True, has_pack_this_month=False)


@pytest.mark.asyncio
async def test_free_plan_premium_is_blocked_without_a_pack() -> None:
    with pytest.raises(QuotaExceededError) as exc:
        await bridge(FakeStore(FREE_PLAN, False))._enforce_free_model_scope(USER_ID, "V6")
    assert "V6-Pro requires purchased credits" in str(exc.value)

    with pytest.raises(QuotaExceededError) as exc:
        await bridge(FakeStore(FREE_PLAN, False))._enforce_free_model_scope(USER_ID, "V6-WILD")
    assert "V6-Wild requires purchased credits" in str(exc.value)


@pytest.mark.asyncio
async def test_free_plan_mini_and_pack_unlock_pass() -> None:
    await bridge(FakeStore(FREE_PLAN, False))._enforce_free_model_scope(USER_ID, "V6-MINI")
    await bridge(FakeStore(FREE_PLAN, True))._enforce_free_model_scope(USER_ID, "V6")
    await bridge(FakeStore(FREE_PLAN, True))._enforce_free_model_scope(USER_ID, "V6-WILD")
    # Paid plans never hit the Free-plan restriction.
    await bridge(FakeStore(PRO_PLAN, False))._enforce_free_model_scope(USER_ID, "V6")
