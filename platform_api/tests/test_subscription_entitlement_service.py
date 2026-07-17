"""Tests for profile add-on entitlement validation."""

from __future__ import annotations

import pytest

from platform_api.models.domain import Plan
from platform_api.services.subscription_entitlement_service import (
    validate_profile_addon_reduction,
)


def _plan(profile_allowance: int = 2) -> Plan:
    return Plan(
        id="00000000-0000-0000-0000-000000000001",
        name="Monthly - 2-channel",
        price_cents=7900,
        profile_allowance=profile_allowance,
        is_active=True,
    )


def test_pending_reduction_blocked_when_profiles_exceed_new_allowance() -> None:
    with pytest.raises(ValueError, match="new profile allowance would be 4"):
        validate_profile_addon_reduction(
            plan=_plan(),
            profile_count=5,
            current_addon_slots=0,
            current_addon_pending=4,
            new_addon_pending=2,
        )


def test_pending_reduction_allowed_when_profiles_fit() -> None:
    validate_profile_addon_reduction(
        plan=_plan(),
        profile_count=4,
        current_addon_slots=0,
        current_addon_pending=4,
        new_addon_pending=2,
    )


def test_active_reduction_blocked_when_profiles_exceed_quota_channels() -> None:
    with pytest.raises(ValueError, match="monthly quotas would scale to 2"):
        validate_profile_addon_reduction(
            plan=_plan(),
            profile_count=4,
            current_addon_slots=2,
            current_addon_pending=2,
            new_addon_slots=0,
        )


def test_active_reduction_allowed_when_profiles_fit_quota() -> None:
    validate_profile_addon_reduction(
        plan=_plan(),
        profile_count=2,
        current_addon_slots=2,
        current_addon_pending=0,
        new_addon_slots=0,
    )
