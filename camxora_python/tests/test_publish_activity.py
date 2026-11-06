"""Live upload activity shown on each Progress row."""

from __future__ import annotations

from shared.lib import publish_activity as activity


def _key() -> str:
    return activity.slot_key("batch-1", "profile-1", "ok")


def test_slot_key_is_stable_and_upper_cases_the_role() -> None:
    assert _key() == "batch-1:profile-1:OK"
    assert _key() == activity.slot_key(" batch-1 ", "profile-1", "OK")


def test_storage_stage_reports_a_real_percentage() -> None:
    key = _key()
    activity.begin(key, label="MERGED_OK.mp4", total=1000)
    activity.progress(key, 420, 1000)

    assert activity.describe(key) == "Storage 42%"
    assert activity.snapshot(key).label == "MERGED_OK.mp4"

    activity.finish(key)
    assert activity.describe(key) == ""


def test_provider_stage_reports_elapsed_instead_of_a_fake_percentage() -> None:
    key = _key()
    activity.begin(key, total=1000)
    activity.progress(key, 1000, 1000)
    activity.mark_provider(key)

    text = activity.describe(key)
    assert text.startswith("Uploading ")
    assert "%" not in text

    activity.finish(key)


def test_cancel_asks_the_worker_that_owns_the_slot() -> None:
    class _Worker:
        def __init__(self) -> None:
            self.called = False

        def requestInterruption(self) -> None:
            self.called = True

    key = _key()
    worker = _Worker()
    activity.begin(key, total=1, worker=worker)

    assert activity.cancel(key) is True
    assert worker.called is True

    activity.finish(key)


def test_unknown_slots_are_silent() -> None:
    assert activity.describe("b:p:OK") == ""
    assert activity.cancel("b:p:OK") is False
    assert activity.snapshot("b:p:OK") is None


def test_active_lists_only_slots_that_are_still_moving() -> None:
    first, second = _key(), activity.slot_key("batch-2", "profile-1", "ALT")
    activity.begin(first, total=10)
    activity.begin(second, total=10)

    assert {item.key for item in activity.active()} == {first, second}

    activity.finish(first)
    assert [item.key for item in activity.active()] == [second]
    activity.finish(second)
