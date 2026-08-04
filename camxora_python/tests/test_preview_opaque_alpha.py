"""REQ-P0: preview Alpha_Lock helpers and spectrum call-site guards."""

from __future__ import annotations

from pathlib import Path

import moderngl

from features.video.lib.lightning_render import (
    _blend_rgb_additive_opaque_alpha,
    _blend_rgb_normal_opaque_alpha,
)
from visualizer.gpu_render import (
    blend_rgb_additive_opaque_alpha,
    blend_rgb_normal_opaque_alpha,
)


def test_blend_rgb_helpers_use_opaque_alpha_factors() -> None:
    class _Ctx:
        blend_func = None

    ctx = _Ctx()
    blend_rgb_normal_opaque_alpha(ctx)  # type: ignore[arg-type]
    assert ctx.blend_func == (
        moderngl.SRC_ALPHA,
        moderngl.ONE_MINUS_SRC_ALPHA,
        moderngl.ZERO,
        moderngl.ONE,
    )
    blend_rgb_additive_opaque_alpha(ctx)  # type: ignore[arg-type]
    assert ctx.blend_func == (
        moderngl.SRC_ALPHA,
        moderngl.ONE,
        moderngl.ZERO,
        moderngl.ONE,
    )


def test_lightning_blend_helpers_match_preview_alpha_lock() -> None:
    class _Ctx:
        blend_func = None

    ctx = _Ctx()
    _blend_rgb_normal_opaque_alpha(ctx)  # type: ignore[arg-type]
    assert ctx.blend_func[2:] == (moderngl.ZERO, moderngl.ONE)
    _blend_rgb_additive_opaque_alpha(ctx)  # type: ignore[arg-type]
    assert ctx.blend_func[2:] == (moderngl.ZERO, moderngl.ONE)


def test_preview_spectrum_paint_uses_blend_helpers_not_raw_additive() -> None:
    """REQ-P0.1: spectrum glow call sites must not assign ADDITIVE_BLENDING."""
    src = Path(__file__).resolve().parents[1] / "visualizer" / "preview_widget.py"
    text = src.read_text(encoding="utf-8")
    # Narrow to the spectrum pass blend selection block.
    marker = "if pass_cfg['is_glow']:"
    idx = text.find(marker)
    assert idx > 0
    snippet = text[idx : idx + 280]
    assert "self._blend_additive()" in snippet
    assert "self._blend_normal()" in snippet
    assert "moderngl.ADDITIVE_BLENDING" not in snippet


def test_particle_quad_path_uses_opaque_alpha_helpers() -> None:
    src = Path(__file__).resolve().parents[1] / "visualizer" / "gpu_render.py"
    text = src.read_text(encoding="utf-8")
    # Particle styled quads section.
    idx = text.find("Neon bloom reads better with additive when glow is on.")
    assert idx > 0
    snippet = text[idx : idx + 350]
    assert "blend_rgb_additive_opaque_alpha" in snippet
    assert "blend_rgb_normal_opaque_alpha" in snippet
    assert "moderngl.ADDITIVE_BLENDING" not in snippet
