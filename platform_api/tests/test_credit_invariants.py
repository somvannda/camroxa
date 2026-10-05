"""Credit-grant invariant check: violation detection + alert formatting."""

from __future__ import annotations

from platform_api.services.credit_invariants import (
    format_credit_invariants_message,
    has_credit_violations,
)


def _empty() -> dict:
    return {
        "multi_lot_users": [],
        "multi_grant_user_days": [],
        "daily_volume": [],
        "volume_threshold": 50000,
    }


def test_no_violations_on_clean_state() -> None:
    assert has_credit_violations(_empty()) is False


def test_multiple_live_lots_is_violation() -> None:
    inv = _empty()
    inv["multi_lot_users"] = [{"email": "a@b.c", "lots": 2, "credits": 100}]
    assert has_credit_violations(inv) is True


def test_multiple_grants_in_a_day_is_violation() -> None:
    inv = _empty()
    inv["multi_grant_user_days"] = [
        {"email": "a@b.c", "grants": 2, "day": "2026-10-05", "credits": 100}
    ]
    assert has_credit_violations(inv) is True


def test_daily_volume_spike_is_violation() -> None:
    inv = _empty()
    inv["daily_volume"] = [{"day": "2026-10-05", "grants": 5, "credits": 60000}]
    assert has_credit_violations(inv) is True


def test_daily_volume_within_threshold_is_ok() -> None:
    inv = _empty()
    inv["daily_volume"] = [{"day": "2026-10-05", "grants": 5, "credits": 100}]
    assert has_credit_violations(inv) is False


def test_message_includes_details() -> None:
    inv = _empty()
    inv["multi_lot_users"] = [{"email": "a@b.c", "lots": 2, "credits": 100}]
    inv["multi_grant_user_days"] = [
        {"email": "a@b.c", "grants": 2, "day": "2026-10-05", "credits": 100}
    ]
    message = format_credit_invariants_message(inv, "Sandbox")
    assert "a@b.c" in message
    assert "2026-10-05" in message
    assert "Sandbox" in message
