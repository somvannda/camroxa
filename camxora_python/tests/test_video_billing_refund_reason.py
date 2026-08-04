"""Refund reason must stay within API max_length=500."""

from __future__ import annotations

from features.video.lib.video_billing import _REFUND_REASON_MAX_LEN, _clamp_refund_reason


def test_clamp_refund_reason_keeps_short_message() -> None:
    assert _clamp_refund_reason("Export failed.") == "Export failed."


def test_clamp_refund_reason_uses_first_line_of_traceback() -> None:
    dump = (
        "Export failed with exit code 1 for track.mp3. (backend=subprocess)\n"
        "File \"run_entry.py\", line 12, in _run_visualizer\n"
        + ("x" * 600)
    )
    clamped = _clamp_refund_reason(dump)
    assert clamped == "Export failed with exit code 1 for track.mp3. (backend=subprocess)"
    assert len(clamped) <= _REFUND_REASON_MAX_LEN


def test_clamp_refund_reason_hard_truncates_long_single_line() -> None:
    long_line = "E" * 700
    clamped = _clamp_refund_reason(long_line)
    assert len(clamped) == _REFUND_REASON_MAX_LEN
    assert clamped.endswith("…")
