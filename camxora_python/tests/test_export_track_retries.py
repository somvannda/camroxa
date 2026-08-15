"""Per-track export retries then skip, without aborting the album."""

from __future__ import annotations

from features.video.workers.pipeline_export_worker import (
    TRACK_EXPORT_MAX_ATTEMPTS,
    export_one_track_with_retries,
)


def test_export_retries_then_succeeds() -> None:
    attempts = {"n": 0}

    def export_one(_path: str) -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("temporary encoder glitch")
        return "out.mp4"

    result = export_one_track_with_retries("a.mp3", export_one=export_one)
    assert result.skipped is False
    assert result.output_path == "out.mp4"
    assert result.attempts == 3
    assert attempts["n"] == 3


def test_export_skips_after_three_failures() -> None:
    retries: list[int] = []

    def export_one(_path: str) -> str:
        raise RuntimeError("decode hung")

    result = export_one_track_with_retries(
        "a.mp3",
        export_one=export_one,
        on_retry=lambda attempt, _max, _err: retries.append(attempt),
    )
    assert result.skipped is True
    assert result.output_path is None
    assert result.attempts == TRACK_EXPORT_MAX_ATTEMPTS
    assert result.error == "decode hung"
    assert retries == [1, 2]


def test_export_stops_without_counting_as_skip() -> None:
    result = export_one_track_with_retries(
        "a.mp3",
        export_one=lambda _p: (_ for _ in ()).throw(RuntimeError("nope")),
        should_stop=lambda: True,
    )
    assert result.skipped is False
    assert result.error == "Video export stopped."


def test_defer_skips_run_then_expires() -> None:
    from features.video.lib.export_run_defer import (
        clear_export_run_defer,
        defer_export_run,
        deferred_export_run_keys,
    )

    clear_export_run_defer()
    defer_export_run("batch-1:profile-1:OK", seconds=60)
    assert "batch-1:profile-1:OK" in deferred_export_run_keys()
    assert deferred_export_run_keys(now=time_far_future()) == set()
    clear_export_run_defer()


def time_far_future() -> float:
    import time

    return time.time() + 10_000
