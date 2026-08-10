"""Keep logo / spectrum / lightning drag centers inside the preview frame."""

from __future__ import annotations

from visualizer_video.preview_widget import clamp_template_offset_to_preview


def test_clamp_center_anchor_rejects_far_offsets() -> None:
    ox, oy = clamp_template_offset_to_preview(
        anchor="center",
        offset_x=5000.0,
        offset_y=-4000.0,
        w=800,
        h=450,
        sf=1.0,
        margin_frac=0.0,
    )
    assert abs(ox) <= 800 * 0.5 + 1e-6
    assert abs(oy) <= 450 * 0.5 + 1e-6


def test_clamp_leaves_in_frame_offsets_unchanged() -> None:
    ox, oy = clamp_template_offset_to_preview(
        anchor="center",
        offset_x=12.0,
        offset_y=-8.0,
        w=800,
        h=450,
        sf=1.0,
    )
    assert ox == 12.0
    assert oy == -8.0


def test_clamp_respects_scale_factor() -> None:
    # Template units * sf = pixels; with sf=2, half the template offset reaches the same pixel.
    ox, oy = clamp_template_offset_to_preview(
        anchor="center",
        offset_x=5000.0,
        offset_y=0.0,
        w=800,
        h=450,
        sf=2.0,
        margin_frac=0.0,
    )
    assert abs(ox - 200.0) < 1e-6  # (400px max) / sf=2
    assert abs(oy) < 1e-6
