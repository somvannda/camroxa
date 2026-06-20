"""Unit tests for CanvasCoordinateMapper and CanvasRect."""

from __future__ import annotations

import pytest

from python_app.views.components.canvas_coordinate_mapper import (
    CanvasCoordinateMapper,
    CanvasRect,
)


class TestCanvasRect:
    def test_frozen_dataclass(self):
        rect = CanvasRect(x=10, y=20, width=800, height=450)
        assert rect.x == 10
        assert rect.y == 20
        assert rect.width == 800
        assert rect.height == 450
        with pytest.raises(Exception):
            rect.x = 5  # type: ignore[misc]


class TestComputeCanvasRect:
    def test_matching_aspect_ratio_fills_widget(self):
        """When widget and target have the same aspect ratio, content fills widget."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        rect = mapper.canvas_rect
        assert rect.x == 0
        assert rect.y == 0
        assert rect.width == 1600
        assert rect.height == 900

    def test_pillarboxing_widget_wider_than_target(self):
        """When widget is wider than target, pillarboxing occurs (bars on sides)."""
        # Widget: 1600x900 (16:9), Target: 1080x1080 (1:1)
        mapper = CanvasCoordinateMapper(1600, 900, 1080, 1080)
        rect = mapper.canvas_rect
        # Content should be 900x900 centered horizontally
        assert rect.height == 900
        assert rect.width == 900
        assert rect.y == 0
        assert rect.x == 350  # (1600 - 900) // 2

    def test_letterboxing_widget_taller_than_target(self):
        """When widget is taller than target, letterboxing occurs (bars top/bottom)."""
        # Widget: 800x800 (1:1), Target: 1920x1080 (16:9)
        mapper = CanvasCoordinateMapper(800, 800, 1920, 1080)
        rect = mapper.canvas_rect
        # Content should be 800x450 centered vertically
        assert rect.width == 800
        assert rect.height == 450
        assert rect.x == 0
        assert rect.y == 175  # (800 - 450) // 2

    def test_zero_widget_width(self):
        """Widget width of 0 returns zero-sized canvas rect."""
        mapper = CanvasCoordinateMapper(0, 900, 1920, 1080)
        rect = mapper.canvas_rect
        assert rect.width == 0
        assert rect.height == 0

    def test_zero_widget_height(self):
        """Widget height of 0 returns zero-sized canvas rect."""
        mapper = CanvasCoordinateMapper(1600, 0, 1920, 1080)
        rect = mapper.canvas_rect
        assert rect.width == 0
        assert rect.height == 0

    def test_zero_target_dimensions(self):
        """Zero target dimensions uses full widget area."""
        mapper = CanvasCoordinateMapper(800, 600, 0, 0)
        rect = mapper.canvas_rect
        assert rect.width == 800
        assert rect.height == 600


class TestWidgetToPct:
    def test_center_of_canvas(self):
        """Center of canvas maps to 50%, 50%."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        pct_x, pct_y = mapper.widget_to_pct(800, 450)
        assert abs(pct_x - 50.0) < 0.1
        assert abs(pct_y - 50.0) < 0.1

    def test_top_left_corner(self):
        """Top-left of content rect maps to 0%, 0%."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        pct_x, pct_y = mapper.widget_to_pct(0, 0)
        assert abs(pct_x - 0.0) < 0.1
        assert abs(pct_y - 0.0) < 0.1

    def test_bottom_right_corner(self):
        """Bottom-right of content rect maps to 100%, 100%."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        pct_x, pct_y = mapper.widget_to_pct(1600, 900)
        assert abs(pct_x - 100.0) < 0.1
        assert abs(pct_y - 100.0) < 0.1

    def test_with_pillarboxing_offset(self):
        """Widget position accounts for aspect ratio offset."""
        # Widget: 1600x900 (16:9), Target: 1080x1080 (1:1)
        # Canvas rect: x=350, y=0, w=900, h=900
        mapper = CanvasCoordinateMapper(1600, 900, 1080, 1080)
        # The content left edge is at widget x=350
        pct_x, pct_y = mapper.widget_to_pct(350, 0)
        assert abs(pct_x - 0.0) < 0.1
        assert abs(pct_y - 0.0) < 0.1

    def test_zero_canvas_rect_returns_zero(self):
        """When canvas rect is zero, returns (0, 0)."""
        mapper = CanvasCoordinateMapper(0, 0, 1920, 1080)
        pct_x, pct_y = mapper.widget_to_pct(100, 100)
        assert pct_x == 0.0
        assert pct_y == 0.0


class TestPctToWidget:
    def test_center(self):
        """50%, 50% maps to center of widget when no offset."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        wx, wy = mapper.pct_to_widget(50.0, 50.0)
        assert wx == 800
        assert wy == 450

    def test_origin(self):
        """0%, 0% maps to top-left of content rect."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        wx, wy = mapper.pct_to_widget(0.0, 0.0)
        assert wx == 0
        assert wy == 0

    def test_with_offset(self):
        """0%, 0% accounts for pillarboxing offset."""
        mapper = CanvasCoordinateMapper(1600, 900, 1080, 1080)
        wx, wy = mapper.pct_to_widget(0.0, 0.0)
        assert wx == 350  # The content rect starts at x=350
        assert wy == 0


class TestPctToOutput:
    def test_center(self):
        """50%, 50% maps to center of output resolution."""
        mapper = CanvasCoordinateMapper(800, 600, 1920, 1080)
        ox, oy = mapper.pct_to_output(50.0, 50.0)
        assert ox == 960
        assert oy == 540

    def test_origin(self):
        """0%, 0% maps to (0, 0) in output."""
        mapper = CanvasCoordinateMapper(800, 600, 1920, 1080)
        ox, oy = mapper.pct_to_output(0.0, 0.0)
        assert ox == 0
        assert oy == 0

    def test_full_extent(self):
        """100%, 100% maps to full output dimensions."""
        mapper = CanvasCoordinateMapper(800, 600, 1920, 1080)
        ox, oy = mapper.pct_to_output(100.0, 100.0)
        assert ox == 1920
        assert oy == 1080

    def test_zero_target_returns_zero(self):
        """Zero target dimensions returns (0, 0)."""
        mapper = CanvasCoordinateMapper(800, 600, 0, 0)
        ox, oy = mapper.pct_to_output(50.0, 50.0)
        assert ox == 0
        assert oy == 0


class TestOutputToPct:
    def test_center(self):
        """Center of output maps to 50%, 50%."""
        mapper = CanvasCoordinateMapper(800, 600, 1920, 1080)
        pct_x, pct_y = mapper.output_to_pct(960, 540)
        assert abs(pct_x - 50.0) < 0.1
        assert abs(pct_y - 50.0) < 0.1

    def test_origin(self):
        """(0, 0) in output maps to 0%, 0%."""
        mapper = CanvasCoordinateMapper(800, 600, 1920, 1080)
        pct_x, pct_y = mapper.output_to_pct(0, 0)
        assert pct_x == 0.0
        assert pct_y == 0.0

    def test_zero_target_returns_zero(self):
        """Zero target dimensions returns (0, 0)."""
        mapper = CanvasCoordinateMapper(800, 600, 0, 0)
        pct_x, pct_y = mapper.output_to_pct(500, 300)
        assert pct_x == 0.0
        assert pct_y == 0.0


class TestWidgetDeltaToPctDelta:
    def test_full_width_delta(self):
        """Moving the full canvas width equals 100% delta."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        dpct_x, dpct_y = mapper.widget_delta_to_pct_delta(1600, 900)
        assert abs(dpct_x - 100.0) < 0.1
        assert abs(dpct_y - 100.0) < 0.1

    def test_zero_delta(self):
        """Zero pixel delta equals 0% delta."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        dpct_x, dpct_y = mapper.widget_delta_to_pct_delta(0, 0)
        assert dpct_x == 0.0
        assert dpct_y == 0.0

    def test_with_pillarboxing(self):
        """Delta uses canvas rect width, not full widget width."""
        # Widget: 1600x900, Target: 1:1 => canvas rect 900x900
        mapper = CanvasCoordinateMapper(1600, 900, 1080, 1080)
        dpct_x, dpct_y = mapper.widget_delta_to_pct_delta(90, 90)
        assert abs(dpct_x - 10.0) < 0.1  # 90/900 * 100 = 10%
        assert abs(dpct_y - 10.0) < 0.1

    def test_zero_canvas_returns_zero(self):
        """When canvas is zero, returns (0, 0)."""
        mapper = CanvasCoordinateMapper(0, 0, 1920, 1080)
        dpct_x, dpct_y = mapper.widget_delta_to_pct_delta(100, 100)
        assert dpct_x == 0.0
        assert dpct_y == 0.0


class TestUpdate:
    def test_update_recalculates_canvas_rect(self):
        """update() recalculates canvas rect with new dimensions."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        assert mapper.canvas_rect.width == 1600
        assert mapper.canvas_rect.height == 900

        mapper.update(800, 800, 1920, 1080)
        rect = mapper.canvas_rect
        # Now widget is 1:1, target is 16:9 -> letterboxing
        assert rect.width == 800
        assert rect.height == 450
        assert rect.x == 0
        assert rect.y == 175

    def test_update_to_zero_widget(self):
        """update() with zero widget dimensions produces zero canvas rect."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        mapper.update(0, 0, 1920, 1080)
        assert mapper.canvas_rect.width == 0
        assert mapper.canvas_rect.height == 0

    def test_update_resolution_change(self):
        """update() with new target resolution recalculates correctly."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        # Change to 1:1 target
        mapper.update(1600, 900, 1080, 1080)
        rect = mapper.canvas_rect
        assert rect.width == 900
        assert rect.height == 900


class TestRoundTrip:
    """Integration tests verifying round-trip conversions within tolerance."""

    def test_pct_to_widget_and_back(self):
        """pct -> widget -> pct round-trip within 0.5% tolerance."""
        mapper = CanvasCoordinateMapper(1600, 900, 1920, 1080)
        original_x, original_y = 33.3, 66.7
        wx, wy = mapper.pct_to_widget(original_x, original_y)
        result_x, result_y = mapper.widget_to_pct(wx, wy)
        assert abs(result_x - original_x) < 0.5
        assert abs(result_y - original_y) < 0.5

    def test_pct_to_output_and_back(self):
        """pct -> output -> pct round-trip within 0.5% tolerance."""
        mapper = CanvasCoordinateMapper(800, 600, 1920, 1080)
        original_x, original_y = 25.0, 75.0
        ox, oy = mapper.pct_to_output(original_x, original_y)
        result_x, result_y = mapper.output_to_pct(ox, oy)
        assert abs(result_x - original_x) < 0.5
        assert abs(result_y - original_y) < 0.5

    def test_round_trip_with_aspect_mismatch(self):
        """Round-trip works correctly even with letterboxing/pillarboxing."""
        # Widget 1600x900 (16:9), target 1080x1080 (1:1) -> pillarboxing
        mapper = CanvasCoordinateMapper(1600, 900, 1080, 1080)
        original_x, original_y = 42.5, 87.3
        wx, wy = mapper.pct_to_widget(original_x, original_y)
        result_x, result_y = mapper.widget_to_pct(wx, wy)
        assert abs(result_x - original_x) < 0.5
        assert abs(result_y - original_y) < 0.5
