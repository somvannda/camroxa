"""Export failure / milestone logging helpers."""

from __future__ import annotations

from features.video.lib.export_failure_log import (
    append_export_event_line,
    format_export_failure_message,
    is_export_milestone_message,
    tail_export_error_detail,
)


def test_format_export_failure_includes_detail_and_backend() -> None:
    message = format_export_failure_message(
        exit_code=1,
        mp3_path=r"D:\runs\1. Electric Desert Downtown Call_OK.mp3",
        detail="moderngl.Error: cannot create context\nTraceback (most recent call last):",
        backend_used="subprocess",
    )
    assert "exit code 1" in message
    assert "Electric Desert Downtown Call_OK.mp3" in message
    assert "backend=subprocess" in message
    assert "cannot create context" in message


def test_append_export_event_line_keeps_failed_and_log_tail() -> None:
    lines: list[str] = []
    append_export_event_line(lines, {"status": "running", "message": "Analyzing audio..."})
    append_export_event_line(lines, {"status": "log", "message": "Traceback (most recent call last):"})
    append_export_event_line(lines, {"status": "failed", "message": "OpenGL error"})
    assert lines == [
        "Traceback (most recent call last):",
        "OpenGL error",
    ]
    assert "OpenGL error" in tail_export_error_detail(lines)


def test_is_export_milestone_message() -> None:
    assert is_export_milestone_message("Analyzing audio (first track can take a minute)…")
    assert is_export_milestone_message("Audio analysis loaded from cache")
    assert is_export_milestone_message("Preparing encoder...")
    assert not is_export_milestone_message("Rendering 120/1800")
