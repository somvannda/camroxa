"""Tests for export codec labels and speed mode defaults."""

from __future__ import annotations

from shared.lib.export_codec import (
    DEFAULT_EXPORT_SPEED_MODE,
    export_video_codec_label,
    format_export_status_message,
    normalize_export_speed_mode,
)


def test_normalize_export_speed_mode_defaults_to_fast() -> None:
    assert DEFAULT_EXPORT_SPEED_MODE == "fast"
    assert normalize_export_speed_mode(None) == "fast"
    assert normalize_export_speed_mode("") == "fast"
    assert normalize_export_speed_mode("fast") == "fast"
    assert normalize_export_speed_mode("very_fast") == "very_fast"
    assert normalize_export_speed_mode("invalid") == "fast"


def test_export_video_codec_label() -> None:
    assert export_video_codec_label("h264_nvenc") == "NVENC"
    assert export_video_codec_label("libx264") == "CPU x264"
    assert export_video_codec_label("") == ""


def test_format_export_status_message_appends_codec_once() -> None:
    assert format_export_status_message("Rendering 10/100", video_codec="h264_nvenc") == (
        "Rendering 10/100 · NVENC"
    )
    assert format_export_status_message("Encoder started (NVENC)", video_codec="h264_nvenc") == (
        "Encoder started (NVENC)"
    )
