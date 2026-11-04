"""Per-user daily music cap: the shared Suno pool must not be drained by one user."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.exceptions import QuotaExceededError
from platform_api.services.v3.credits_only_billing_service import (
    CreditsOnlyBillingService,
    QuoteResult,
)


def _service(spent_units: int) -> CreditsOnlyBillingService:
    service = CreditsOnlyBillingService.__new__(CreditsOnlyBillingService)
    service._store = MagicMock()
    service._store.music_credits_spent_today = AsyncMock(return_value=spent_units)
    service._store.system_setting = AsyncMock(return_value=None)
    service._credit_repo = MagicMock()
    service._credit_repo.has_transaction = AsyncMock(return_value=False)
    service._credit_repo.atomic_deduct = AsyncMock(return_value=True)
    service._pricing = MagicMock()
    service._enforcement = None
    service._ai_routing = None
    service.quote = AsyncMock(
        return_value=QuoteResult(
            op="music",
            amount_credits=10.0,
            amount_units=100_000,
            source="plan",
            plan_id=None,
        )
    )
    return service


def _settings(cap: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "platform_api.services.v3.credits_only_billing_service.get_settings",
        lambda: SimpleNamespace(music_daily_credit_cap=cap),
    )


@pytest.mark.asyncio
async def test_charge_blocked_when_daily_cap_would_be_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _settings(500, monkeypatch)
    service = _service(spent_units=4_950_000)  # 495 credits already today

    with pytest.raises(QuotaExceededError) as exc:
        await service.charge(user_id=uuid4(), op="music", ref_id="song-1")

    assert exc.value.details["code"] == "music_daily_cap"
    assert exc.value.details["cap_credits"] == 500
    assert service._credit_repo.atomic_deduct.await_count == 0


@pytest.mark.asyncio
async def test_charge_allowed_at_the_cap_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(500, monkeypatch)
    service = _service(spent_units=4_900_000)  # 490 credits already today

    await service._assert_daily_music_cap(
        uuid4(),
        QuoteResult(op="music", amount_credits=10.0, amount_units=100_000, source="plan", plan_id=None),
    )


@pytest.mark.asyncio
async def test_zero_cap_disables_the_check(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(0, monkeypatch)
    service = _service(spent_units=99_000_000)

    await service._assert_daily_music_cap(
        uuid4(),
        QuoteResult(op="music", amount_credits=10.0, amount_units=100_000, source="plan", plan_id=None),
    )
    service._store.music_credits_spent_today.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_operations_are_not_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(500, monkeypatch)
    service = _service(spent_units=99_000_000)

    await service._assert_daily_music_cap(
        uuid4(),
        QuoteResult(op="image", amount_credits=60.0, amount_units=600_000, source="plan", plan_id=None),
    )
    service._store.music_credits_spent_today.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_setting_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The console value must win over MUSIC_DAILY_CREDIT_CAP."""
    _settings(500, monkeypatch)
    service = _service(spent_units=2_450_000)  # 245 credits today
    service._store.system_setting = AsyncMock(return_value="250")

    with pytest.raises(QuotaExceededError) as exc:
        await service._assert_daily_music_cap(
            uuid4(),
            QuoteResult(
                op="music",
                amount_credits=10.0,
                amount_units=100_000,
                source="plan",
                plan_id=None,
            ),
        )

    assert exc.value.details["cap_credits"] == 250
    service._store.system_setting.assert_awaited_with("music_daily_credit_cap")


@pytest.mark.asyncio
async def test_invalid_admin_setting_falls_back_to_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _settings(500, monkeypatch)
    service = _service(spent_units=0)
    service._store.system_setting = AsyncMock(return_value="not-a-number")

    # Env default (500) applies, so a 10-credit song is allowed.
    await service._assert_daily_music_cap(
        uuid4(),
        QuoteResult(
            op="music", amount_credits=10.0, amount_units=100_000, source="plan", plan_id=None
        ),
    )


@pytest.mark.asyncio
async def test_admin_zero_setting_disables_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _settings(500, monkeypatch)
    service = _service(spent_units=99_000_000)
    service._store.system_setting = AsyncMock(return_value="0")

    await service._assert_daily_music_cap(
        uuid4(),
        QuoteResult(
            op="music", amount_credits=10.0, amount_units=100_000, source="plan", plan_id=None
        ),
    )
    service._store.music_credits_spent_today.assert_not_awaited()
