"""Plan credit cadence: daily XOR monthly."""

from __future__ import annotations

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.plan_credits import validate_credit_cadence


def test_rejects_both_daily_and_monthly() -> None:
    with pytest.raises(ValidationError):
        validate_credit_cadence(monthly_credits=50, daily_credits=50)


def test_allows_monthly_only() -> None:
    validate_credit_cadence(monthly_credits=50, daily_credits=0)


def test_allows_daily_only() -> None:
    validate_credit_cadence(monthly_credits=0, daily_credits=50)


def test_allows_neither() -> None:
    validate_credit_cadence(monthly_credits=0, daily_credits=0)


def test_allows_nulls() -> None:
    validate_credit_cadence(monthly_credits=None, daily_credits=None)
