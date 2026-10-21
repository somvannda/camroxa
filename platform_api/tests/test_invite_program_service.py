from __future__ import annotations

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.invite_program_service import (
    DEFAULT_INVITE_SETTINGS,
    InviteSettings,
    RewardRule,
    coerce_invite_settings,
    invite_reward_credits,
    mask_email,
    merge_invite_settings,
    normalize_referral_code,
    serialize_invite_settings,
)


def test_normalize_referral_code() -> None:
    assert normalize_referral_code(" abcd-2345 ") == "ABCD2345"
    assert normalize_referral_code("a") is None
    assert normalize_referral_code(1234) is None


def test_coerce_defaults_and_clamps() -> None:
    defaults = coerce_invite_settings(None)
    assert defaults == DEFAULT_INVITE_SETTINGS

    clamped = coerce_invite_settings(
        {
            "enabled": False,
            "inviter": {"mode": "percent", "value": 250},
            "invitee": {"mode": "fixed", "value": 40},
        }
    )
    assert clamped.enabled is False
    assert clamped.inviter == RewardRule(mode="percent", value=100.0)
    assert clamped.invitee == RewardRule(mode="fixed", value=40.0)


def test_percent_reward_rounds_down_but_pays_at_least_one() -> None:
    assert invite_reward_credits(RewardRule("percent", 15), 1000) == 150
    assert invite_reward_credits(RewardRule("percent", 15), 50) == 7
    assert invite_reward_credits(RewardRule("percent", 15), 1) == 1
    assert invite_reward_credits(RewardRule("percent", 0), 1000) == 0
    assert invite_reward_credits(RewardRule("percent", 15), 0) == 0


def test_fixed_reward_is_independent_of_purchase_size() -> None:
    assert invite_reward_credits(RewardRule("fixed", 75), 5) == 75
    assert invite_reward_credits(RewardRule("fixed", 75), 10_000) == 75


def test_merge_validates_modes_and_bounds() -> None:
    current = coerce_invite_settings(None)

    merged = merge_invite_settings(
        current,
        {
            "inviter": {"mode": "fixed", "value": 100},
            "invitee": {"mode": "percent", "value": 20},
        },
    )
    assert merged.inviter == RewardRule("fixed", 100.0)
    assert merged.invitee == RewardRule("percent", 20.0)

    with pytest.raises(ValidationError):
        merge_invite_settings(current, {"inviter": {"mode": "bogus"}})
    with pytest.raises(ValidationError):
        merge_invite_settings(current, {"inviter": {"value": -1}})
    with pytest.raises(ValidationError):
        merge_invite_settings(current, {"inviter": {"mode": "percent", "value": 101}})
    with pytest.raises(ValidationError):
        merge_invite_settings(current, {"enabled": "yes"})


def test_serialize_round_trips() -> None:
    settings = InviteSettings(
        enabled=True,
        inviter=RewardRule("percent", 15),
        invitee=RewardRule("fixed", 50),
    )
    payload = serialize_invite_settings(settings)
    assert payload == {
        "enabled": True,
        "inviter": {"mode": "percent", "value": 15},
        "invitee": {"mode": "fixed", "value": 50},
    }


def test_mask_email() -> None:
    assert mask_email("jane@example.com") == "j***@example.com"
    assert mask_email("a@example.com") == "a*@example.com"
    assert mask_email("not-an-email") == "***"
