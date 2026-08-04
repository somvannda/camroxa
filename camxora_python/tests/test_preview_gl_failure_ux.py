"""REQ-P1.2 / P1.3: opaque GL failure overlay helpers (no Qt event loop required)."""

from __future__ import annotations

from visualizer.preview_diag import preview_gl_diag_log_path


def test_preview_gl_diag_path_documented_for_support() -> None:
    path = preview_gl_diag_log_path()
    assert path.name == "preview-gl-diag.log"
    assert "Camxora" in str(path)
    assert "logs" in str(path)


def test_gl_failure_user_message_points_at_diag_log() -> None:
    # Lightweight stand-in: same copy as VideoSpectrumPreview._gl_failure_user_message
    detail = "initializeGL failed: boom"
    lines = [
        "GPU preview failed to start on this PC.",
        "The Video page stays usable; try Remount Preview or restart Camxora.",
        "Send support: %LOCALAPPDATA%\\Camxora\\logs\\preview-gl-diag.log",
        "and the daily camxora-*.log from the same folder.",
        f"Detail: {detail}",
    ]
    text = "\n\n".join(lines)
    assert "preview-gl-diag.log" in text
    assert "boom" in text
    assert "GPU preview failed" in text
