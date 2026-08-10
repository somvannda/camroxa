from __future__ import annotations

from visualizer_video.gpu_render import _smooth_env


def test_smooth_env_dt_scales_retention_for_lower_export_fps() -> None:
    """24 fps export should reach the same target in similar wall time as 60 Hz preview."""
    target = 1.0
    prev = 0.0
    preview_s = 0.8
    encode_dt = 1.0 / 24.0

    preview_after_one_sec = prev
    for _ in range(60):
        preview_after_one_sec = _smooth_env(preview_after_one_sec, target, preview_s)

    export_after_one_sec = prev
    for _ in range(24):
        export_after_one_sec = _smooth_env(export_after_one_sec, target, preview_s, dt=encode_dt)

    assert abs(preview_after_one_sec - export_after_one_sec) < 0.08


def test_smooth_env_without_dt_differs_at_same_frame_count() -> None:
    target = 1.0
    prev = 0.0
    smoothing = 0.8
    encode_dt = 1.0 / 24.0

    scaled = prev
    raw = prev
    for _ in range(24):
        scaled = _smooth_env(scaled, target, smoothing, dt=encode_dt)
        raw = _smooth_env(raw, target, smoothing)

    assert scaled > raw
