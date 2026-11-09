"""Refunds must never push a wallet lot above what it was granted.

Production hit ``credit_wallet_lots_remaining_check`` because the refund path
added straight onto ``remaining_units``: a full pack lot went to
``remaining_units > amount_units``. The split below caps the refill and sends
the overflow to a fresh lot.
"""

from __future__ import annotations

import pytest

from platform_api.repositories.credit_repo import CreditRepository

CASES = [
    # (amount, remaining, capacity, into_lot, overflow)
    (100, 1_000, 1_000, 0, 100),      # lot already full -> all overflow
    (100, 950, 1_000, 50, 50),        # partial room
    (100, 900, 1_000, 100, 0),        # fits exactly
    (100, 0, 1_000, 100, 0),          # empty lot
    (100, 0, 0, 0, 100),              # zero-capacity lot
    (100, 1_200, 1_000, 0, 100),      # corrupt lot (over capacity) stays safe
]


@pytest.mark.parametrize(("amount", "remaining", "capacity", "into_lot", "overflow"), CASES)
def test_restore_split_never_exceeds_capacity(
    amount: int, remaining: int, capacity: int, into_lot: int, overflow: int
) -> None:
    got_into, got_overflow = CreditRepository._restore_split(amount, remaining, capacity)

    assert (got_into, got_overflow) == (into_lot, overflow)
    # A lot already above capacity (corrupt data) must not grow further.
    assert remaining + got_into <= max(remaining, capacity)
    assert got_into + got_overflow == amount
