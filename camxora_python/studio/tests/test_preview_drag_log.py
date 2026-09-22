"""Tests for preview drag diagnostics."""

from studio.core.preview_drag_log import DragShapeWatch, format_norm_rect


def test_format_norm_rect_includes_aspect():
    text = format_norm_rect({"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.5}, canvas_w=1280, canvas_h=720)
    assert "aspect=" in text
    assert "384x360" in text


def test_shape_watch_detects_norm_drift():
    watch = DragShapeWatch()
    watch.reset({"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.5})
    assert watch._drift_warnings == 0
    watch.check_move(
        {"x": 0.12, "y": 0.22, "w": 0.31, "h": 0.5},
        canvas_w=1280,
        canvas_h=720,
    )
    assert watch._drift_warnings == 1


def test_shape_watch_ignores_position_only_move():
    watch = DragShapeWatch()
    watch.reset({"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.5})
    watch.check_move(
        {"x": 0.15, "y": 0.25, "w": 0.3, "h": 0.5},
        canvas_w=1280,
        canvas_h=720,
    )
    assert watch._drift_warnings == 0
