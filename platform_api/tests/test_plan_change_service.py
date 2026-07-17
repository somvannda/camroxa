"""Tests for plan change validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.models.domain import Plan
from platform_api.services.plan_change_service import (
    is_plan_downgrade,
    resolve_plan_change_checkout,
    validate_mid_cycle_plan_change,
)


def _plan(*, channels: int, price: int, cycle: int = 30) -> Plan:
    return Plan(
        id=uuid4(),
        name=f"{channels}ch",
        price_cents=price,
        billing_cycle_days=cycle,
        profile_allowance=channels,
    )


def test_downgrade_blocked_mid_cycle() -> None:
    current = _plan(channels=6, price=15900)
    target = _plan(channels=2, price=7900)
    expires = datetime.now(timezone.utc) + timedelta(days=10)
    with pytest.raises(ValidationError) as exc:
        validate_mid_cycle_plan_change(
            current_plan=current,
            target_plan=target,
            license_expires_at=expires,
        )
    assert exc.value.details["error_code"] == "DOWNGRADE_AT_RENEWAL_ONLY"


def test_upgrade_uses_proration() -> None:
    current = _plan(channels=2, price=7900)
    target = _plan(channels=6, price=15900)
    expires = datetime.now(timezone.utc) + timedelta(days=20)
    amount, meta = resolve_plan_change_checkout(
        current_plan=current,
        target_plan=target,
        license_expires_at=expires,
        list_price_cents=15900,
    )
    assert meta["plan_change"] == "upgrade"
    assert amount > 0
    assert amount <= 15900


def test_is_plan_downgrade() -> None:
    assert is_plan_downgrade(_plan(channels=6, price=1), _plan(channels=2, price=1))
