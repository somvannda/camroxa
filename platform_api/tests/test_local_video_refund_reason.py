"""Local video refund reason clamping for long desktop crash dumps."""

from __future__ import annotations

from platform_api.routers.generation import LocalVideoRefundRequest


def test_local_video_refund_reason_clamps_long_traceback() -> None:
    dump = (
        "Export failed with exit code 1 for track.mp3. (backend=subprocess)\n"
        "File \"run_entry.py\", line 12, in _run_visualizer\n"
        + ("x" * 800)
    )
    req = LocalVideoRefundRequest(operation_type="video", reason=dump)
    assert req.reason == "Export failed with exit code 1 for track.mp3. (backend=subprocess)"
    assert len(req.reason) <= 500


def test_local_video_refund_reason_hard_truncates_single_line() -> None:
    req = LocalVideoRefundRequest(operation_type="video", reason="E" * 700)
    assert len(req.reason) == 500
    assert req.reason.endswith("…")
