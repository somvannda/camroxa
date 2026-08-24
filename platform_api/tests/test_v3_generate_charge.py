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

    async def quote(self, *, op: str, user_id, plan_id=None, waive: bool = False):
        self.quotes.append(op)
        return SimpleNamespace(
            op=op,
            amount_units=self.amount_units,
            amount_credits=self.amount_units / 10_000,
        )

    async def charge(self, *, user_id, op: str, ref_id=None, waive: bool = False, plan_id=None):
        self.charges.append({"user_id": user_id, "op": op, "ref_id": ref_id})
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
    assert billing.charges == [{"user_id": USER_ID, "op": "music", "ref_id": None}]


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
