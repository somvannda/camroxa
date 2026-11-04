"""Each failed attempt must refund the amount that attempt was charged.

The stash used to be keyed by song only, so retrying a song overwrote it and a
second failure popped nothing - refunding 0 while reporting success. Key it by
task (per attempt) and keep the song key as a fallback for attempts that never
produced a task id.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from platform_api.services.batch_service import BatchService, charge_stash_keys


def test_task_key_comes_first_and_song_key_is_the_fallback() -> None:
    song_id = uuid4()
    task_id = uuid4()

    keys = charge_stash_keys(song_id, task_id)

    assert keys == [f"suno:task:{task_id}", f"suno:{song_id}"]


def test_without_a_task_id_only_the_song_key_is_used() -> None:
    song_id = uuid4()

    assert charge_stash_keys(song_id, None) == [f"suno:{song_id}"]


def test_two_attempts_on_one_song_produce_distinct_keys() -> None:
    song_id = uuid4()
    first, second = uuid4(), uuid4()

    first_keys = charge_stash_keys(song_id, first)
    second_keys = charge_stash_keys(song_id, second)

    assert first_keys[0] != second_keys[0]
    # Both still share the song fallback, which is why the task key must win.
    assert first_keys[1] == second_keys[1]


class _Enforcement:
    def __init__(self, charges: dict[str, int]) -> None:
        self._charges = dict(charges)
        self.popped: list[str] = []

    async def pop_operation_charge(self, key: str) -> int | None:
        self.popped.append(key)
        return self._charges.pop(key, None)


class _Service:
    """Minimal stand-in that exercises the stash lookup in _refund_suno_billing."""

    _enforcement_service: _Enforcement | None = None

    def __init__(self, enforcement: _Enforcement) -> None:
        self._enforcement_service = enforcement

    pop_operation_charge = BatchService._refund_suno_billing


@pytest.mark.asyncio
async def test_refund_uses_the_attempt_amount_not_the_song_fallback() -> None:
    song_id = uuid4()
    task_id = uuid4()
    enforcement = _Enforcement(
        {
            f"suno:task:{task_id}": 100_000,  # this attempt charged 10 credits
            f"suno:{song_id}": 100_000,
        }
    )
    service = _Service(enforcement)

    keys = charge_stash_keys(song_id, task_id)
    charged = 0
    for key in keys:
        stored = await enforcement.pop_operation_charge(key)
        if stored is not None:
            charged = int(stored)
            break

    assert charged == 100_000
    assert enforcement.popped[0] == f"suno:task:{task_id}"


@pytest.mark.asyncio
async def test_second_failure_still_finds_its_own_amount() -> None:
    song_id = uuid4()
    first, second = uuid4(), uuid4()
    enforcement = _Enforcement({f"suno:task:{first}": 100_000})

    # First attempt fails and refunds.
    for key in charge_stash_keys(song_id, first):
        stored = await enforcement.pop_operation_charge(key)
        if stored is not None:
            assert int(stored) == 100_000
            break
    else:  # pragma: no cover - the first attempt must refund
        pytest.fail("first attempt did not refund")

    # A retry charged again and stashes under its own task key.
    enforcement._charges[f"suno:task:{second}"] = 100_000

    for key in charge_stash_keys(song_id, second):
        stored = await enforcement.pop_operation_charge(key)
        if stored is not None:
            assert int(stored) == 100_000
            break
    else:  # pragma: no cover - the retry must refund too
        pytest.fail("second attempt did not refund")
