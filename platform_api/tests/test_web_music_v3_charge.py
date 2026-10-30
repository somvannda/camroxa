"""Web Create uses the credits-only charge model when the v3 flag is On."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import InsufficientCreditsError, QuotaExceededError
from platform_api.services.credit_units import credits_to_units, units_to_credits
from platform_api.services.v3.web_music_charge import WebMusicChargeBridge
from platform_api.services.web_music_service import WebMusicService


USER_ID = uuid4()
FREE_PLAN_ID = uuid4()
PAID_PLAN_ID = uuid4()


class FakeQuote:
    def __init__(self, amount_credits: float, *, included: bool = False) -> None:
        self.amount_credits = amount_credits
        self.included = included
        self.amount_units = credits_to_units(amount_credits)
        self.op = "music"
        self.source = "plan"
        self.plan_id = None


class FakeV3Billing:
    def __init__(self, amount_credits: float = 10, *, fail: bool = False) -> None:
        self.amount_credits = amount_credits
        self.fail = fail
        self.charges: list[dict] = []
        self.refunds: list[dict] = []

    async def quote(self, *, op: str, user_id, plan_id=None, waive: bool = False):
        return FakeQuote(self.amount_credits)

    async def charge(self, *, user_id, op: str, ref_id=None, waive: bool = False, plan_id=None, product=None, model=None):
        self.charges.append({"user_id": user_id, "op": op, "ref_id": ref_id, "product": product, "model": model})
        if self.fail:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation.",
                details={"required_credits": self.amount_credits, "current_balance": 0},
            )
        return {"amount_units": credits_to_units(self.amount_credits), "op": op}

    async def refund(self, *, user_id, op: str, amount_credits=None, ref_id=None, absorb: bool = False, product=None):
        self.refunds.append({"user_id": user_id, "op": op, "amount_credits": amount_credits, "ref_id": ref_id, "product": product})
        return {}


class FakeGrant:
    def __init__(self) -> None:
        self.calls = 0

    async def ensure_daily_grant(self, user_id: UUID) -> dict:
        self.calls += 1
        return {"granted": False, "reason": "already_granted"}

    async def ensure_period_grant(self, user_id: UUID) -> dict:
        return {"granted": False, "reason": "already_granted"}


class FakeStore:
    def __init__(self, plan: dict | None = None) -> None:
        self.plan = plan or {
            "id": str(PAID_PLAN_ID),
            "name": "Monthly",
            "price_cents": 7900,
            "music_credits": 10,
            "lyric_credits": 5,
            "style_credits": 2,
            "daily_credits": 0,
        }

    async def resolve_charge_plan(self, user_id: UUID) -> dict | None:
        return self.plan

    async def live_pack_expiry(self, user_id: UUID):
        # A paid plan in this double stands in for a live pack lot.
        if int((self.plan or {}).get("price_cents") or 0) > 0:
            return datetime.now(timezone.utc)
        return None

    async def get_active_free_plan(self) -> dict | None:
        return {
            "id": str(FREE_PLAN_ID),
            "daily_credits": 50,
            "music_credits": 10,
        }


class FakeWallet:
    def __init__(self, credits: float) -> None:
        self.balance = credits_to_units(credits)

    async def get_balance(self, user_id: UUID | str) -> int:
        return self.balance


class FakeV2Credits:
    def __init__(self, remaining: int) -> None:
        self.remaining = remaining
        self.consumed: list[dict] = []
        self.refunds: list[dict] = []

    async def get_detailed_balance(self, user_id: str):
        return SimpleNamespace(total_available=self.remaining)

    async def consume_credits(self, user_id: str, amount: int, source: str, reference_id=None, **kwargs):
        self.consumed.append({"amount": amount, "source": source, "ref_id": reference_id})
        self.remaining -= amount
        return True

    async def refund_credits(self, user_id: str, amount: int, source: str, reference_id=None):
        self.refunds.append({"amount": amount, "source": source})
        self.remaining += amount
        return True


def _bridge(
    *,
    wallet_credits: float,
    paid_web: bool,
    fail: bool = False,
    v2_remaining: int = 0,
) -> tuple[WebMusicChargeBridge, FakeV3Billing, FakeV2Credits, FakeGrant]:
    billing = FakeV3Billing(fail=fail)
    grant = FakeGrant()
    v2 = FakeV2Credits(v2_remaining)

    async def has_paid_web(_user_id: UUID) -> bool:
        return paid_web

    bridge = WebMusicChargeBridge(
        v3_billing=billing,
        v3_grant=grant,
        v3_store=FakeStore(),
        credit_repo=FakeWallet(wallet_credits),
        credit_service=v2,
        has_paid_web_subscription=has_paid_web,
    )
    return bridge, billing, v2, grant


@pytest.mark.asyncio
async def test_desktop_pro_wallet_is_charged_ten() -> None:
    bridge, billing, v2, grant = _bridge(wallet_credits=5200, paid_web=False)
    charged = await bridge.charge(USER_ID, "music", ref_id="res-1")
    assert charged.path == "v3"
    assert charged.amount_credits == 10
    assert billing.charges == [{"user_id": USER_ID, "op": "music", "ref_id": "res-1", "product": "web_music", "model": None}]
    assert v2.consumed == []
    assert grant.calls == 1


@pytest.mark.asyncio
async def test_empty_pro_wallet_is_not_skipped() -> None:
    bridge, billing, _v2, _grant = _bridge(wallet_credits=0, paid_web=False, fail=True)
    with pytest.raises(QuotaExceededError, match="Insufficient credits"):
        await bridge.charge(USER_ID, "music")
    assert billing.charges


@pytest.mark.asyncio
async def test_paid_web_subscription_uses_v3_wallet() -> None:
    bridge, billing, v2, _grant = _bridge(wallet_credits=100, paid_web=True, v2_remaining=1000)
    charged = await bridge.charge(USER_ID, "music", ref_id="cutluy")
    assert charged.path == "v3"
    assert charged.amount_credits == 10
    assert billing.charges == [{"user_id": USER_ID, "op": "music", "ref_id": "cutluy", "product": "web_music", "model": None}]
    assert v2.consumed == []


@pytest.mark.asyncio
async def test_empty_v3_wallet_does_not_fall_back_to_v2() -> None:
    bridge, billing, v2, _grant = _bridge(wallet_credits=0, paid_web=True, fail=True, v2_remaining=1000)
    with pytest.raises(QuotaExceededError, match="Insufficient credits"):
        await bridge.charge(USER_ID, "music", ref_id="cutluy")
    assert billing.charges
    assert v2.consumed == []


@pytest.mark.asyncio
async def test_lyrics_assist_maps_to_lyric() -> None:
    billing = FakeV3Billing(amount_credits=5)
    grant = FakeGrant()

    async def has_paid_web(_user_id: UUID) -> bool:
        return False

    bridge = WebMusicChargeBridge(
        v3_billing=billing,
        v3_grant=grant,
        v3_store=FakeStore(),
        credit_repo=FakeWallet(50),
        credit_service=FakeV2Credits(0),
        has_paid_web_subscription=has_paid_web,
    )
    charged = await bridge.charge(USER_ID, "web_music_lyrics")
    assert charged.op == "lyric"
    assert charged.amount_credits == 5
    assert billing.charges[0]["op"] == "lyric"


@pytest.mark.asyncio
async def test_failed_generate_refunds_v3() -> None:
    bridge, billing, _v2, _grant = _bridge(wallet_credits=100, paid_web=False)
    charged = await bridge.charge(USER_ID, "music", ref_id="fail-1")
    await bridge.refund(USER_ID, charged)
    assert billing.refunds == [
        {"user_id": USER_ID, "op": "music", "amount_credits": 10.0, "ref_id": "fail-1", "product": "web_music"}
    ]


@pytest.mark.asyncio
async def test_usage_today_does_not_treat_pro_as_unlimited() -> None:
    billing = FakeV3Billing()
    grant = FakeGrant()
    store = FakeStore()
    wallet = FakeWallet(25)
    settings = SimpleNamespace(get_system_setting=AsyncMock(return_value=True))
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"value": True})
    service = WebMusicService(
        pool,
        AsyncMock(),
        credit_service=FakeV2Credits(0),
        v3_billing=billing,
        v3_grant=grant,
        v3_store=store,
        credit_repo=wallet,
        settings_repo=settings,
    )
    service._has_pro = AsyncMock(return_value=True)
    service._has_web_subscription = AsyncMock(return_value=False)
    service._has_paid_web_subscription = AsyncMock(return_value=False)

    payload = await service.usage_today(USER_ID)
    assert payload["credits_remaining"] == 25
    assert payload["credits_per_song"] == 10
    assert payload["requires_upgrade"] is False
    assert payload["is_pro"] is True
    assert payload["remaining"] == 2


@pytest.mark.asyncio
async def test_reserve_charges_pro_when_flag_on() -> None:
    billing = FakeV3Billing()
    grant = FakeGrant()
    service = WebMusicService(
        AsyncMock(),
        AsyncMock(),
        credit_service=FakeV2Credits(0),
        v3_billing=billing,
        v3_grant=grant,
        v3_store=FakeStore(),
        credit_repo=FakeWallet(100),
        settings_repo=SimpleNamespace(get_system_setting=AsyncMock(return_value=True)),
    )
    service._has_pro = AsyncMock(return_value=True)
    service._has_web_subscription = AsyncMock(return_value=False)
    service._has_paid_web_subscription = AsyncMock(return_value=False)

    quota = await service._reserve_daily_slot(USER_ID, reservation_id="r1")
    assert billing.charges == [{"user_id": USER_ID, "op": "music", "ref_id": "r1", "product": "web_music", "model": None}]
    assert quota["requires_upgrade"] is False
    assert service._open_charges["r1"].path == "v3"


@pytest.mark.asyncio
async def test_release_refunds_recorded_debit_when_memory_charge_missing() -> None:
    """The worker has no in-memory charge; the recorded debit must be reversed."""
    debit_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"id": debit_id, "amount": credits_to_units(15)})
    service = WebMusicService(
        pool,
        AsyncMock(),
        credit_service=FakeV2Credits(0),
        settings_repo=SimpleNamespace(get_system_setting=AsyncMock(return_value=True)),
    )
    billing = SimpleNamespace(refund=AsyncMock())
    service._v3_refund_billing = lambda: billing  # type: ignore[method-assign]

    await service._release_daily_slot(USER_ID, reference_id="res-1", task_id="task-1")

    billing.refund.assert_awaited_once()
    kwargs = billing.refund.await_args.kwargs
    assert kwargs["op"] == "music"
    assert kwargs["amount_credits"] == 15.0
    # Keyed on the debit row id so worker re-attempts are no-ops.
    assert kwargs["ref_id"] == str(debit_id)
    # Lookup matches the reservation id and the linked task id.
    assert pool.fetchrow.await_args.args[2] == ["res-1", "task-1"]


@pytest.mark.asyncio
async def test_release_does_not_refund_when_no_debit_recorded() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    service = WebMusicService(
        pool,
        AsyncMock(),
        credit_service=FakeV2Credits(0),
        settings_repo=SimpleNamespace(get_system_setting=AsyncMock(return_value=True)),
    )
    billing = SimpleNamespace(refund=AsyncMock())
    service._v3_refund_billing = lambda: billing  # type: ignore[method-assign]

    await service._release_daily_slot(USER_ID, reference_id="res-1", task_id="task-1")

    billing.refund.assert_not_awaited()


def test_units_round_trip() -> None:
    assert units_to_credits(credits_to_units(10)) == 10.0
