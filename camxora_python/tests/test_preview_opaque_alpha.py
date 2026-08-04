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


def test_force_opaque_alpha_does_not_use_moderngl_masked_clear() -> None:
    """moderngl Context.clear ignores color_mask and wiped RGB → black preview."""
    src = Path(__file__).resolve().parents[1] / "visualizer" / "preview_widget.py"
    text = src.read_text(encoding="utf-8")
    start = text.find("def _force_framebuffer_opaque_alpha")
    assert start > 0
    end = text.find("\n    def ", start + 1)
    body = text[start:end]
    assert "glColorMask" in body
    assert "glClear(GL.GL_COLOR_BUFFER_BIT)" in body or "glClear(GL_COLOR_BUFFER_BIT)" in body
    assert "self.ctx.clear(" not in body


def test_moderngl_masked_clear_wipes_rgb_regression_guard() -> None:
    """Document driver/library behavior that caused black live preview."""
    import numpy as np
    from OpenGL import GL

    ctx = moderngl.create_standalone_context()
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((2, 2), 4)])
    fbo.use()
    ctx.clear(1.0, 0.0, 0.0, 0.25)
    before = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(2, 2, 4)[0, 0]

    ctx.color_mask = (False, False, False, True)
    ctx.clear(0.0, 0.0, 0.0, 1.0)
    ctx.color_mask = (True, True, True, True)
    after_mgl = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(2, 2, 4)[0, 0]
    # ModernGL clear does not honor the mask — RGB becomes clear color.
    assert list(after_mgl[:3]) != list(before[:3])

    ctx.clear(1.0, 0.0, 0.0, 0.25)
    GL.glColorMask(GL.GL_FALSE, GL.GL_FALSE, GL.GL_FALSE, GL.GL_TRUE)
    GL.glClearColor(0.0, 0.0, 0.0, 1.0)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT)
    GL.glColorMask(GL.GL_TRUE, GL.GL_TRUE, GL.GL_TRUE, GL.GL_TRUE)
    after_gl = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(2, 2, 4)[0, 0]
    assert after_gl[0] == 255 and after_gl[1] == 0 and after_gl[2] == 0
    assert after_gl[3] == 255
