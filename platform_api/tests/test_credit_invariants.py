"""Credit-grant invariant check: violation detection + alert formatting."""

from __future__ import annotations

from platform_api.services.credit_invariants import (
    _MULTI_LOT_SQL,
    _NON_EXPIRING_GRANT_SQL,
    format_credit_invariants_message,
    has_credit_violations,
)


def _empty() -> dict:
    return {
        "multi_lot_users": [],
        "non_expiring_grants": [],
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


def test_non_expiring_grant_lots_is_violation() -> None:
    inv = _empty()
    inv["non_expiring_grants"] = [{"email": "a@b.c", "lots": 60, "credits": 600}]
    assert has_credit_violations(inv) is True


def test_multi_lot_query_only_counts_period_grants() -> None:
    """Refund-created grant lots must not look like stacked period grants."""
    assert "period_start IS NOT NULL" in _MULTI_LOT_SQL
    assert "tag = 'grant'" in _MULTI_LOT_SQL


def test_non_expiring_query_targets_grant_lots() -> None:
    assert "expires_at IS NULL" in _NON_EXPIRING_GRANT_SQL
    assert "tag = 'grant'" in _NON_EXPIRING_GRANT_SQL


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
    inv["non_expiring_grants"] = [{"email": "a@b.c", "lots": 60, "credits": 600}]
    inv["multi_grant_user_days"] = [
        {"email": "a@b.c", "grants": 2, "day": "2026-10-05", "credits": 100}
    ]
    message = format_credit_invariants_message(inv, "Sandbox")
    assert "a@b.c" in message
    assert "2026-10-05" in message
    assert "no expiry" in message
    assert "Sandbox" in message
