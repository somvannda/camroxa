"""Music price settlement after a provider-chain failover."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from platform_api.services.credit_units import credits_to_units
from platform_api.services.usage_enforcement_service import UsageEnforcementService


class FakePricingRepo:
    def __init__(self) -> None:
        self.rows = {
            ("suno", "music", "V6"): {"credits_per_operation": credits_to_units(15)},
            ("camxora_music_api", "music", "V6"): {"credits_per_operation": credits_to_units(10)},
        }

    async def get_by_service_and_operation(
        self, ai_service: str, operation_type: str, sub_model: str = ""
    ):
        return self.rows.get((ai_service, operation_type, sub_model))

    async def get_all(self):
        return list(self.rows.values())


class FakeWallet:
    def __init__(self) -> None:
        self.deducted: list[int] = []
        self.refunded: list[int] = []

    async def get_balance(self, user_id) -> int:  # noqa: ANN001
        return credits_to_units(1_000)

    async def atomic_deduct(
        self, user_id, amount, reason, ref_id=None, metadata=None  # noqa: ANN001
    ) -> bool:
        self.deducted.append(int(amount))
        return True

    async def refund(
        self, user_id, amount, reason, ref_id=None, metadata=None  # noqa: ANN001
    ) -> int:
        self.refunded.append(int(amount))
        return int(amount)


def _service(wallet: FakeWallet, pricing: FakePricingRepo) -> UsageEnforcementService:
    return UsageEnforcementService(
        credit_repo=wallet,
        usage_repo=SimpleNamespace(),
        plan_repo=SimpleNamespace(),
        pricing_repo=pricing,
        redis=None,
        settings_repo=SimpleNamespace(),
    )


@pytest.mark.asyncio
async def test_settle_refunds_when_fallback_is_cheaper() -> None:
    wallet = FakeWallet()
    service = _service(wallet, FakePricingRepo())

    effective = await service.settle_music_price(
        uuid4(),
        charged_units=credits_to_units(15),
        routed_provider="suno",
        executed_provider="camxora_music_api",
        sub_model="V6",
    )

    assert effective == credits_to_units(10)
    assert wallet.refunded == [credits_to_units(5)]
    assert wallet.deducted == []


@pytest.mark.asyncio
async def test_settle_charges_when_fallback_is_pricier() -> None:
    wallet = FakeWallet()
    service = _service(wallet, FakePricingRepo())

    effective = await service.settle_music_price(
        uuid4(),
        charged_units=credits_to_units(10),
        routed_provider="camxora_music_api",
        executed_provider="suno",
        sub_model="V6",
    )

    assert effective == credits_to_units(15)
    assert wallet.deducted == [credits_to_units(5)]
    assert wallet.refunded == []


@pytest.mark.asyncio
async def test_settle_is_noop_for_same_provider() -> None:
    wallet = FakeWallet()
    service = _service(wallet, FakePricingRepo())

    effective = await service.settle_music_price(
        uuid4(),
        charged_units=credits_to_units(15),
        routed_provider="suno",
        executed_provider="suno",
        sub_model="V6",
    )

    assert effective == credits_to_units(15)
    assert wallet.deducted == []
    assert wallet.refunded == []


@pytest.mark.asyncio
async def test_settle_is_noop_when_plan_covered() -> None:
    wallet = FakeWallet()
    service = _service(wallet, FakePricingRepo())

    effective = await service.settle_music_price(
        uuid4(),
        charged_units=0,
        routed_provider="camxora_music_api",
        executed_provider="suno",
        sub_model="V6",
    )

    assert effective == 0
    assert wallet.deducted == []
    assert wallet.refunded == []


@pytest.mark.asyncio
async def test_settle_skips_when_pricing_missing() -> None:
    wallet = FakeWallet()
    service = _service(wallet, FakePricingRepo())

    effective = await service.settle_music_price(
        uuid4(),
        charged_units=credits_to_units(10),
        routed_provider="camxora_music_api",
        executed_provider="suno",
        sub_model="V6_MINI",
    )

    assert effective == credits_to_units(10)
    assert wallet.deducted == []
    assert wallet.refunded == []
