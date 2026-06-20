from __future__ import annotations

import pytest
from PIL import Image
import numpy as np

from python_app.services.text_overlay_renderer import (
    TextStylePreset,
    render_text_overlay,
    _parse_rgba_hex,
    _calculate_text_block_y,
    _calculate_line_x,
)


def _make_preset(**overrides) -> TextStylePreset:
    """Create a preset with sensible defaults for testing."""
    defaults = dict(
        name="Test Preset",
        font_path="",
        font_size=48,
        primary_color="#FFFFFFFF",
        position="center",
    )
    defaults.update(overrides)
    return TextStylePreset(**defaults)


class TestParseRgbaHex:
    def test_white_opaque(self):
        assert _parse_rgba_hex("#FFFFFFFF") == (255, 255, 255, 255)

    def test_red_opaque(self):
        assert _parse_rgba_hex("#FF0000FF") == (255, 0, 0, 255)

    def test_transparent_black(self):
        assert _parse_rgba_hex("#00000000") == (0, 0, 0, 0)

    def test_half_transparent_blue(self):
        assert _parse_rgba_hex("#0000FF80") == (0, 0, 255, 128)


class TestCalculateTextBlockY:
    def test_top_position(self):
        # Canvas height 1000, text height 100, vertical padding 10%
        # Padding is 100px, so text starts at y=100
        y = _calculate_text_block_y("top", 1000, 100, 10)
        assert y == 100

    def test_bottom_position(self):
        # Canvas height 1000, text height 100, vertical padding 10%
        # Padding is 100px, so text ends at 1000-100=900, starts at 900-100=800
        y = _calculate_text_block_y("bottom", 1000, 100, 10)
        assert y == 800

    def test_center_position(self):
        # Canvas height 1000, text height 100
        # Center: (1000 - 100) // 2 = 450
        y = _calculate_text_block_y("center", 1000, 100, 10)
        assert y == 450


class TestCalculateLineX:
    def test_center_alignment(self):
        # Canvas 1000, line width 200, max_width 800
        # Center: (1000 - 200) // 2 = 400
        x = _calculate_line_x("center", 200, 1000, 800)
        assert x == 400

    def test_left_alignment(self):
        # Canvas 1000, max_width 800
        # Region left: (1000 - 800) // 2 = 100
        x = _calculate_line_x("left", 200, 1000, 800)
        assert x == 100

    def test_right_alignment(self):
        # Canvas 1000, line width 200, max_width 800
        # Region left: (1000 - 800) // 2 = 100
        # Right: 100 + 800 - 200 = 700
        x = _calculate_line_x("right", 200, 1000, 800)
        assert x == 700


class TestRenderTextOverlay:
    def test_empty_titles_returns_transparent(self):
        preset = _make_preset()
        img = render_text_overlay([], preset, 800, 600)
        assert img.mode == "RGBA"
        assert img.size == (800, 600)
        # Should be fully transparent
        arr = np.array(img)
        assert arr[:, :, 3].sum() == 0

    def test_returns_correct_dimensions(self):
        preset = _make_preset()
        img = render_text_overlay(["Hello World"], preset, 1920, 1080)
        assert img.mode == "RGBA"
        assert img.size == (1920, 1080)

    def test_single_title_renders_pixels(self):
        preset = _make_preset(primary_color="#FF0000FF")
        img = render_text_overlay(["Track One"], preset, 800, 600)
        arr = np.array(img)
        # Should have some non-transparent pixels
        assert arr[:, :, 3].sum() > 0

    def test_multiple_titles_render_pixels(self):
        preset = _make_preset()
        titles = ["Track One", "Track Two", "Track Three"]
        img = render_text_overlay(titles, preset, 800, 600)
        arr = np.array(img)
        assert arr[:, :, 3].sum() > 0

    def test_center_position_places_text_in_middle(self):
        preset = _make_preset(position="center", font_size=24)
        img = render_text_overlay(["Hello"], preset, 800, 600)
        arr = np.array(img)
        # Find rows with non-transparent pixels
        non_transparent_rows = np.where(arr[:, :, 3].sum(axis=1) > 0)[0]
        assert len(non_transparent_rows) > 0
        center_of_text = (non_transparent_rows[0] + non_transparent_rows[-1]) / 2
        # Should be roughly in the middle third (200-400)
        assert 150 < center_of_text < 450

    def test_top_position_places_text_near_top(self):
        preset = _make_preset(position="top", font_size=24, vertical_padding_pct=5)
        img = render_text_overlay(["Hello"], preset, 800, 600)
        arr = np.array(img)
        non_transparent_rows = np.where(arr[:, :, 3].sum(axis=1) > 0)[0]
        assert len(non_transparent_rows) > 0
        # Text should be in the top region
        assert non_transparent_rows[0] < 200

    def test_bottom_position_places_text_near_bottom(self):
        preset = _make_preset(position="bottom", font_size=24, vertical_padding_pct=5)
        img = render_text_overlay(["Hello"], preset, 800, 600)
        arr = np.array(img)
        non_transparent_rows = np.where(arr[:, :, 3].sum(axis=1) > 0)[0]
        assert len(non_transparent_rows) > 0
        # Text should be in the bottom region
        assert non_transparent_rows[-1] > 400

    def test_font_size_reduction_fits_normal_text(self):
        # Use a moderate title that should fit after size reduction
        preset = _make_preset(
            font_size=100,
            max_text_width_pct=80,
        )
        title = "Moderate Length Title"
        img = render_text_overlay([title], preset, 800, 600)
        arr = np.array(img)
        non_transparent_cols = np.where(arr[:, :, 3].sum(axis=0) > 0)[0]
        if len(non_transparent_cols) > 0:
            text_width = non_transparent_cols[-1] - non_transparent_cols[0] + 1
            max_allowed = int(800 * 80 / 100)
            assert text_width <= max_allowed + 5

    def test_font_size_reduction_clamps_at_minimum(self):
        # Extremely long text that can't fit even at min font size
        # Per design: renderer uses min font size and allows text to overflow
        preset = _make_preset(
            font_size=100,
            max_text_width_pct=20,
        )
        long_title = "A" * 200
        img = render_text_overlay([long_title], preset, 800, 600)
        # Should not crash — renders at minimum font size even if it overflows
        assert img.mode == "RGBA"
        assert img.size == (800, 600)

    def test_primary_color_applied(self):
        preset = _make_preset(primary_color="#FF000080")
        img = render_text_overlay(["Color Test"], preset, 400, 200)
        arr = np.array(img)
        # Find pixels with non-zero alpha
        mask = arr[:, :, 3] > 0
        if mask.any():
            # Red channel should be 255 for rendered pixels
            red_values = arr[:, :, 0][mask]
            assert red_values.mean() > 200  # Mostly red


class TestTextEffects:
    """Tests for text effects rendering (shadow, glow, stroke, gradient)."""

    def test_shadow_renders_duplicate_at_offset(self):
        """Shadow should create pixels offset from main text."""
        # Render without shadow
        preset_no_shadow = _make_preset(primary_color="#FFFFFFFF", font_size=36)
        img_no_shadow = render_text_overlay(["Test"], preset_no_shadow, 400, 200)

        # Render with shadow
        preset_shadow = _make_preset(
            primary_color="#FFFFFFFF",
            font_size=36,
            shadow_offset_x=5,
            shadow_offset_y=5,
            shadow_color="#000000FF",
        )
        img_shadow = render_text_overlay(["Test"], preset_shadow, 400, 200)

        arr_no_shadow = np.array(img_no_shadow)
        arr_shadow = np.array(img_shadow)

        # Shadow version should have more non-transparent pixels (shadow + fill)
        no_shadow_pixels = (arr_no_shadow[:, :, 3] > 0).sum()
        shadow_pixels = (arr_shadow[:, :, 3] > 0).sum()
        assert shadow_pixels > no_shadow_pixels

    def test_glow_expands_non_transparent_region(self):
        """Glow (Gaussian blur) should widen the non-transparent pixel region."""
        # Render without glow
        preset_no_glow = _make_preset(primary_color="#FFFFFFFF", font_size=36)
        img_no_glow = render_text_overlay(["Test"], preset_no_glow, 400, 200)

        # Render with glow
        preset_glow = _make_preset(
            primary_color="#FFFFFFFF",
            font_size=36,
            glow_color="#00FFFFFF",
            glow_radius=10,
        )
        img_glow = render_text_overlay(["Test"], preset_glow, 400, 200)

        arr_no_glow = np.array(img_no_glow)
        arr_glow = np.array(img_glow)

        # Glow version should have more non-transparent pixels
        no_glow_pixels = (arr_no_glow[:, :, 3] > 0).sum()
        glow_pixels = (arr_glow[:, :, 3] > 0).sum()
        assert glow_pixels > no_glow_pixels

    def test_stroke_widens_text_footprint(self):
        """Stroke should widen the text footprint by stroke_width."""
        # Render without stroke
        preset_no_stroke = _make_preset(primary_color="#FFFFFFFF", font_size=36)
        img_no_stroke = render_text_overlay(["Test"], preset_no_stroke, 400, 200)

        # Render with stroke
        preset_stroke = _make_preset(
            primary_color="#FFFFFFFF",
            font_size=36,
            stroke_width=3,
            stroke_color="#FF0000FF",
        )
        img_stroke = render_text_overlay(["Test"], preset_stroke, 400, 200)

        arr_no_stroke = np.array(img_no_stroke)
        arr_stroke = np.array(img_stroke)

        # Stroke version should have more non-transparent pixels
        no_stroke_pixels = (arr_no_stroke[:, :, 3] > 0).sum()
        stroke_pixels = (arr_stroke[:, :, 3] > 0).sum()
        assert stroke_pixels > no_stroke_pixels

    def test_gradient_produces_color_variation(self):
        """Gradient fill should produce different colors at top and bottom of text."""
        preset = _make_preset(
            font_size=72,
            position="center",
            gradient_enabled=True,
            gradient_start_color="#FF0000FF",  # Red at top
            gradient_end_color="#0000FFFF",    # Blue at bottom
        )
        img = render_text_overlay(["Hello World"], preset, 600, 400)
        arr = np.array(img)

        # Find rows with non-transparent pixels
        non_transparent_rows = np.where(arr[:, :, 3].sum(axis=1) > 0)[0]
        assert len(non_transparent_rows) > 0

        # Get the top and bottom rows of the text
        top_row = non_transparent_rows[0]
        bottom_row = non_transparent_rows[-1]

        # Top pixels should be more red, bottom pixels should be more blue
        top_pixels = arr[top_row][arr[top_row, :, 3] > 0]
        bottom_pixels = arr[bottom_row][arr[bottom_row, :, 3] > 0]

        if len(top_pixels) > 0 and len(bottom_pixels) > 0:
            # Top should have higher red channel average
            assert top_pixels[:, 0].mean() > bottom_pixels[:, 0].mean()
            # Bottom should have higher blue channel average
            assert bottom_pixels[:, 2].mean() > top_pixels[:, 2].mean()

    def test_gradient_disabled_uses_solid_color(self):
        """When gradient_enabled is False, text should be solid primary_color."""
        preset = _make_preset(
            primary_color="#00FF00FF",
            font_size=36,
            gradient_enabled=False,
        )
        img = render_text_overlay(["Test"], preset, 400, 200)
        arr = np.array(img)

        # Find pixels with non-zero alpha
        mask = arr[:, :, 3] > 0
        if mask.any():
            # Green channel should be 255 for rendered pixels (solid green)
            green_values = arr[:, :, 1][mask]
            assert green_values.mean() > 200

    def test_layer_ordering_shadow_behind_fill(self):
        """Shadow should be behind the fill layer (composited first)."""
        # Use contrasting colors to verify ordering
        preset = _make_preset(
            primary_color="#FF0000FF",  # Red fill
            font_size=36,
            shadow_offset_x=0,
            shadow_offset_y=3,
            shadow_color="#0000FFFF",  # Blue shadow below
        )
        img = render_text_overlay(["Test"], preset, 400, 200)
        arr = np.array(img)

        # Should have both red and blue pixels
        mask = arr[:, :, 3] > 0
        assert mask.any()
        # Should have pixels that are predominantly red (fill on top)
        red_dominant = (arr[:, :, 0] > 200) & (arr[:, :, 2] < 50) & mask
        assert red_dominant.any()

    def test_no_effects_renders_plain_text(self):
        """When all effects are at zero/disabled, should render plain text."""
        preset = _make_preset(
            primary_color="#FFFFFFFF",
            font_size=36,
            glow_radius=0,
            stroke_width=0,
            shadow_offset_x=0,
            shadow_offset_y=0,
            gradient_enabled=False,
        )
        img = render_text_overlay(["Test"], preset, 400, 200)
        arr = np.array(img)
        # Should still have visible text
        assert (arr[:, :, 3] > 0).sum() > 0

    def test_all_effects_combined(self):
        """All effects enabled simultaneously should not crash and produce output."""
        preset = _make_preset(
            primary_color="#FFFFFFFF",
            font_size=36,
            glow_color="#00FFFFFF",
            glow_radius=5,
            shadow_offset_x=3,
            shadow_offset_y=3,
            shadow_color="#000000FF",
            stroke_width=2,
            stroke_color="#FF0000FF",
            gradient_enabled=True,
            gradient_start_color="#FFFFFFFF",
            gradient_end_color="#00FF00FF",
        )
        img = render_text_overlay(["Full Effects"], preset, 600, 300)
        assert img.mode == "RGBA"
        assert img.size == (600, 300)
        arr = np.array(img)
        assert (arr[:, :, 3] > 0).sum() > 0
