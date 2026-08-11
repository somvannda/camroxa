"""Spectrum Glow Strength/Softness preview↔export parity."""

from __future__ import annotations

from pathlib import Path

import moderngl

from visualizer._spectrum_fast import build_spectrum_glow_pass_specs
from visualizer.gpu_render import apply_spectrum_pass_blend, blend_rgb_additive_opaque_alpha


def test_spectrum_glow_pass_specs_shared_math() -> None:
    specs = build_spectrum_glow_pass_specs(
        glow_strength=1.0,
        glow_softness=30.0,
        layer_opacity=1.0,
        bar_width_px=10.0,
        spike_height_px=100.0,
        sf=2.0,
        fill_circle=True,
        glow_pass_limit=2,
    )
    assert len(specs) == 3
    assert specs[0]["is_glow"] is True
    assert specs[1]["is_glow"] is True
    assert specs[2]["is_glow"] is False
    # Outer glow tip = spike + (soft*3.4 + strength*34) * sf
    assert specs[1]["spike_height"] == specs[1]["thickness"]
    assert abs(float(specs[1]["spike_height"]) - (100.0 + (30.0 * 3.4 + 34.0) * 2.0)) < 1e-6
    assert specs[2]["fill_circle"] is True
    assert specs[2]["spike_height"] == 100.0


def test_spectrum_glow_pass_specs_zero_glow_is_main_only() -> None:
    specs = build_spectrum_glow_pass_specs(
        glow_strength=0.0,
        glow_softness=30.0,
        layer_opacity=1.0,
        bar_width_px=4.0,
        spike_height_px=41.0,
        sf=3.5,
        fill_circle=False,
        glow_pass_limit=2,
    )
    assert len(specs) == 1
    assert specs[0]["is_glow"] is False
    assert specs[0]["spike_height"] == 41.0


def test_apply_spectrum_pass_blend_matches_preview_alpha_weighted_additive() -> None:
    class _Ctx:
        blend_func = None

    ctx = _Ctx()
    apply_spectrum_pass_blend(ctx, is_glow=True)  # type: ignore[arg-type]
    assert ctx.blend_func == (
        moderngl.SRC_ALPHA,
        moderngl.ONE,
        moderngl.ZERO,
        moderngl.ONE,
    )
    # Must NOT be moderngl.ADDITIVE_BLENDING (ONE, ONE) — that ignored glow alpha.
    assert ctx.blend_func != moderngl.ADDITIVE_BLENDING


def test_export_spectrum_glow_blend_uses_helper_not_one_one() -> None:
    src = Path(__file__).resolve().parents[1] / "visualizer" / "gpu_render.py"
    text = src.read_text(encoding="utf-8")
    marker = "WYSIWYG: same alpha-weighted additive as preview"
    idx = text.find(marker)
    assert idx > 0
    snippet = text[idx : idx + 220]
    assert "apply_spectrum_pass_blend" in snippet
    assert "moderngl.ADDITIVE_BLENDING" not in snippet


def test_preview_and_export_share_glow_pass_builder() -> None:
    preview = (
        Path(__file__).resolve().parents[1] / "visualizer" / "preview_widget.py"
    ).read_text(encoding="utf-8")
    export = (
        Path(__file__).resolve().parents[1] / "visualizer" / "gpu_render.py"
    ).read_text(encoding="utf-8")
    assert "build_spectrum_glow_pass_specs(" in preview
    assert "build_spectrum_glow_pass_specs(" in export
    assert blend_rgb_additive_opaque_alpha is not None
