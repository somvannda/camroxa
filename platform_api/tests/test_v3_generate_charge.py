"""Flagged v3 generate charge: off keeps quota-first, on debits the shared wallet."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from platform_api.exceptions import InsufficientCreditsError
from platform_api.services.credit_units import credits_to_units
from platform_api.services.usage_enforcement_service import UsageEnforcementService
from platform_api.services.v3.generate_charge import (
    CREDITS_ONLY_V3_CHARGE_SETTING_KEY,
    credits_only_v3_charge_enabled,
    map_v1_op_to_v3,
    parse_bool_flag,
)


USER_ID = uuid4()


class FakeSettingsRepo:
    def __init__(self, enabled: bool | None) -> None:
        self.enabled = enabled

    async def get_system_setting(self, key: str):
        if key != CREDITS_ONLY_V3_CHARGE_SETTING_KEY:
            return None
        return self.enabled


class FakeV3Billing:
    def __init__(self, amount_units: int = 0, *, fail: bool = False) -> None:
        self.amount_units = amount_units
        self.fail = fail
        self.charges: list[dict] = []
        self.quotes: list[str] = []

    async def quote(
        self, *, op: str, user_id, plan_id=None, waive: bool = False, operation=None
    ):
        self.quotes.append(op)
        return SimpleNamespace(
            op=op,
            amount_units=self.amount_units,
            amount_credits=self.amount_units / 10_000,
        )

    async def charge(
        self,
        *,
        user_id,
        op: str,
        ref_id=None,
        waive: bool = False,
        plan_id=None,
        product=None,
        model=None,
        operation=None,
        provider=None,
    ):
        self.charges.append(
            {
                "user_id": user_id,
                "op": op,
                "ref_id": ref_id,
                "product": product,
                "model": model,
                "operation": operation,
                "provider": provider,
            }
        )
        if self.fail:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation.",
                details={"required_credits": 10, "current_balance": 0},
            )
        return {"amount_units": self.amount_units, "charged": self.amount_units > 0, "op": op}


class _Unused:
    pass


class FakeRedis:
    async def get(self, key: str):
        return None


def _service(settings_enabled: bool | None, billing: FakeV3Billing) -> UsageEnforcementService:
    return UsageEnforcementService(
        credit_repo=SimpleNamespace(get_balance=lambda _user_id: 0),
        usage_repo=_Unused(),
        plan_repo=_Unused(),
        pricing_repo=_Unused(),
        redis=FakeRedis(),
        settings_repo=FakeSettingsRepo(settings_enabled),
        v3_billing=billing,
    )


def test_map_v1_ops() -> None:
    assert map_v1_op_to_v3("music") == "music"
    assert map_v1_op_to_v3("lyric") == "lyric"
    assert map_v1_op_to_v3("web_music_lyrics") == "lyric"
    assert map_v1_op_to_v3("web_music_style") == "style"
    assert map_v1_op_to_v3("title") == "title"
    assert map_v1_op_to_v3("album") == "album"
    assert map_v1_op_to_v3("background_image") == "image"
    assert map_v1_op_to_v3("video_manual") == "video"
    assert map_v1_op_to_v3("video_merge") == "merge"
    assert map_v1_op_to_v3("channel_setup") is None


def test_parse_bool_flag() -> None:
    assert parse_bool_flag(True) is True
    assert parse_bool_flag("false") is False
    assert parse_bool_flag("1") is True
    assert parse_bool_flag(None) is None


@pytest.mark.asyncio
async def test_admin_setting_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "platform_api.services.v3.generate_charge.env_v3_charge_enabled",
        lambda: True,
    )
    assert await credits_only_v3_charge_enabled(FakeSettingsRepo(False)) is False
    assert await credits_only_v3_charge_enabled(FakeSettingsRepo(True)) is True
    assert await credits_only_v3_charge_enabled(FakeSettingsRepo(None)) is True


@pytest.mark.asyncio
async def test_check_and_deduct_uses_v3_when_flag_on() -> None:
    billing = FakeV3Billing(amount_units=credits_to_units(10))
    service = _service(True, billing)
    charged = await service.check_and_deduct(USER_ID, None, "music", "suno")
    assert charged == credits_to_units(10)
    assert billing.charges == [
        {
            "user_id": USER_ID,
            "op": "music",
            "ref_id": None,
            "product": "desktop",
            "model": None,
            "operation": "music",
            "provider": "suno",
        }
    ]


@pytest.mark.asyncio
async def test_deduct_for_operation_uses_v3_when_flag_on() -> None:
    billing = FakeV3Billing(amount_units=credits_to_units(5))
    service = _service(True, billing)
    charged = await service.deduct_for_operation(USER_ID, None, "lyric", "openai")
    assert charged == credits_to_units(5)
    assert billing.charges[0]["op"] == "lyric"


@pytest.mark.asyncio
async def test_flag_off_does_not_call_v3(monkeypatch: pytest.MonkeyPatch) -> None:
    billing = FakeV3Billing(amount_units=credits_to_units(10))
    service = _service(False, billing)

    async def _boom(*_args, **_kwargs):
        raise AssertionError("v1 path should run, not v3")

    monkeypatch.setattr(service, "_charge_via_v3", _boom)
    with pytest.raises(Exception):
        # Fake repos are stubs; v1 path fails when it tries to look up pricing.
        await service.check_and_deduct(USER_ID, None, "music", "suno")
    assert billing.charges == []


@pytest.mark.asyncio
async def test_v3_charge_insufficient_is_402() -> None:
    billing = FakeV3Billing(fail=True)
    service = _service(True, billing)
    with pytest.raises(InsufficientCreditsError) as exc:
        await service.check_and_deduct(USER_ID, None, "music", "suno")
    assert exc.value.status_code == 402


@pytest.mark.asyncio
async def test_reserve_hold_and_finalize_skip_quota_when_v3_on() -> None:
    billing = FakeV3Billing(amount_units=credits_to_units(4))
    service = _service(True, billing)
    hold = await service.reserve_and_hold_before_provider(
        USER_ID,
        None,
        "background_image",
        hold_credit_units=99,
        ai_service="fal",
    )
    assert hold.source == "v3"
    assert hold.v3_op == "image"
    assert hold.held_units == credits_to_units(4)
    settled = await service.finalize_held_operation(
        USER_ID,
        "background_image",
        "fal",
        hold=hold,
    )
    assert settled == credits_to_units(4)
    assert billing.charges[0]["op"] == "image"


class FakePricingRepo:
    """Minimal pricing repo: exact (service, operation, model) rows only."""

    def __init__(self, rows: dict[tuple[str, str, str], dict]) -> None:
        self.rows = rows

    async def get_by_service_and_operation(self, service, operation, model):
        return self.rows.get((service, operation, model))


class FakeCreditRepo:
    def __init__(self, *, cover_delta: bool = True) -> None:
        self.cover_delta = cover_delta
        self.deducts: list[dict] = []
        self.refunds: list[dict] = []

    async def get_balance(self, _user_id):
        return 10**9

    async def atomic_deduct(self, user_id, amount, reason, metadata=None, **_kwargs):
        self.deducts.append(
            {"amount": amount, "reason": reason, "metadata": metadata or {}}
        )
        return self.cover_delta

    async def refund(self, user_id, amount, reason, ref_id=None, metadata=None, **_kwargs):
        self.refunds.append(
            {"amount": amount, "reason": reason, "metadata": metadata or {}}
        )
        return True


def _settle_service(
    *,
    rows: dict[tuple[str, str, str], dict],
    credit_repo: FakeCreditRepo,
) -> UsageEnforcementService:
    return UsageEnforcementService(
        credit_repo=credit_repo,
        usage_repo=_Unused(),
        plan_repo=_Unused(),
        pricing_repo=FakePricingRepo(rows),
        redis=FakeRedis(),
        settings_repo=FakeSettingsRepo(True),
        v3_billing=FakeV3Billing(amount_units=0),
    )


@pytest.mark.asyncio
async def test_v3_settle_collects_delta_when_fallback_costs_more() -> None:
    """Quoted SLAI (6) then kie ran (8): collect the 2-credit difference."""
    from platform_api.services.usage_enforcement_service import OperationHold

    credit_repo = FakeCreditRepo()
    service = _settle_service(
        rows={
            ("kie", "background_image", "grok-imagine-image-2-0/text-to-image"): {
                "credits_per_operation": credits_to_units(8)
            }
        },
        credit_repo=credit_repo,
    )
    hold = OperationHold(
        held_units=credits_to_units(6), plan_covered=False, source="v3", v3_op="image"
    )

    settled = await service.finalize_held_operation(
        USER_ID,
        "background_image",
        "kie",
        sub_model="grok-imagine-image-2-0/text-to-image",
        hold=hold,
        routed_provider="slai",
        routed_model="cx/gpt-image-2.5",
        executed_provider="kie",
        executed_model="grok-imagine-image-2-0/text-to-image",
    )

    assert settled == credits_to_units(8)
    assert len(credit_repo.deducts) == 1
    assert credit_repo.deducts[0]["amount"] == credits_to_units(2)
    meta = credit_repo.deducts[0]["metadata"]
    assert meta["provider"] == "kie"
    assert meta["model"] == "grok-imagine-image-2-0/text-to-image"
    assert meta["routed_provider"] == "slai"
    assert meta["executed_provider"] == "kie"


@pytest.mark.asyncio
async def test_v3_settle_refunds_delta_when_fallback_is_cheaper() -> None:
    """Quoted kie (8) then SLAI ran (6): refund the 2-credit difference."""
    from platform_api.services.usage_enforcement_service import OperationHold

    credit_repo = FakeCreditRepo()
    service = _settle_service(
        rows={
            ("slai", "background_image", "cx/gpt-image-2.5"): {
                "credits_per_operation": credits_to_units(6)
            }
        },
        credit_repo=credit_repo,
    )
    hold = OperationHold(
        held_units=credits_to_units(8), plan_covered=False, source="v3", v3_op="image"
    )

    settled = await service.finalize_held_operation(
        USER_ID,
        "background_image",
        "slai",
        sub_model="cx/gpt-image-2.5",
        hold=hold,
        routed_provider="kie",
        routed_model="grok-imagine-image-2-0/text-to-image",
        executed_provider="slai",
        executed_model="cx/gpt-image-2.5",
    )

    assert settled == credits_to_units(6)
    assert credit_repo.deducts == []
    assert len(credit_repo.refunds) == 1
    assert credit_repo.refunds[0]["amount"] == credits_to_units(2)


@pytest.mark.asyncio
async def test_v3_settle_keeps_charge_when_wallet_cannot_cover_delta() -> None:
    """A produced image must not fail because the delta charge is refused."""
    from platform_api.services.usage_enforcement_service import OperationHold

    credit_repo = FakeCreditRepo(cover_delta=False)
    service = _settle_service(
        rows={
            ("kie", "background_image", "grok-imagine-image-2-0/text-to-image"): {
                "credits_per_operation": credits_to_units(8)
            }
        },
        credit_repo=credit_repo,
    )
    hold = OperationHold(
        held_units=credits_to_units(6), plan_covered=False, source="v3", v3_op="image"
    )

    settled = await service.finalize_held_operation(
        USER_ID,
        "background_image",
        "kie",
        sub_model="grok-imagine-image-2-0/text-to-image",
        hold=hold,
        executed_provider="kie",
        executed_model="grok-imagine-image-2-0/text-to-image",
    )

    assert settled == credits_to_units(6)
    assert credit_repo.refunds == []


@pytest.mark.asyncio
async def test_v3_settle_works_for_any_fallback_provider() -> None:
    """Settlement is generic: fal keeps its own list price after a fallback."""
    from platform_api.services.usage_enforcement_service import OperationHold

    credit_repo = FakeCreditRepo()
    service = _settle_service(
        rows={
            ("fal", "background_image", "flux-pro"): {
                "credits_per_operation": credits_to_units(40)
            }
        },
        credit_repo=credit_repo,
    )
    hold = OperationHold(
        held_units=credits_to_units(6), plan_covered=False, source="v3", v3_op="image"
    )

    settled = await service.finalize_held_operation(
        USER_ID,
        "background_image",
        "fal",
        sub_model="flux-pro",
        hold=hold,
        routed_provider="slai",
        routed_model="cx/gpt-image-2.5",
        executed_provider="fal",
        executed_model="flux-pro",
    )

    assert settled == credits_to_units(40)
    assert credit_repo.deducts[0]["amount"] == credits_to_units(34)
    assert credit_repo.deducts[0]["metadata"]["provider"] == "fal"
    assert credit_repo.deducts[0]["metadata"]["model"] == "flux-pro"


@pytest.mark.asyncio
async def test_v3_settle_keeps_held_when_executed_model_has_no_pricing() -> None:
    """An unconfigured fallback model cannot be priced; keep the quoted charge."""
    from platform_api.services.usage_enforcement_service import OperationHold

    credit_repo = FakeCreditRepo()
    service = _settle_service(rows={}, credit_repo=credit_repo)
    hold = OperationHold(
        held_units=credits_to_units(6), plan_covered=False, source="v3", v3_op="image"
    )

    settled = await service.finalize_held_operation(
        USER_ID,
        "background_image",
        "cala",
        sub_model=None,
        hold=hold,
        routed_provider="slai",
        routed_model="cx/gpt-image-2.5",
        executed_provider="cala",
        executed_model=None,
    )

    assert settled == credits_to_units(6)
    assert credit_repo.deducts == []
    assert credit_repo.refunds == []
