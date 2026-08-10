"""GPU smoke: center-image triangle mask must keep opaque interior pixels."""

from __future__ import annotations

import numpy as np


def test_logo_triangle_mask_keeps_center_pixels() -> None:
    import moderngl
    from PIL import Image

    from visualizer_studio.gpu_render import _compile, _quad_vao
    from visualizer_studio.logo_mask import (
        LOGO_MASK_TRIANGLE,
        apply_logo_frame_size_uniform,
        apply_logo_mask_uniform,
    )

    ctx = moderngl.create_standalone_context()
    _prog_scene, prog_logo, *_rest = _compile(ctx)
    assert "logo_mask_mode" in prog_logo
    assert "logo_frame_size_px" in prog_logo

    # Opaque magenta square logo.
    arr = np.zeros((64, 64, 4), dtype=np.uint8)
    arr[:, :, 0] = 255
    arr[:, :, 2] = 255
    arr[:, :, 3] = 255
    tex = ctx.texture((64, 64), 4, arr.tobytes())
    tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

    fbo = ctx.framebuffer(color_attachments=[ctx.texture((128, 128), 4)])
    fbo.use()
    ctx.clear(0.0, 0.0, 0.0, 0.0)
    ctx.enable(moderngl.BLEND)
    ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

    vao = _quad_vao(ctx, prog_logo)
    prog_logo["tex_logo"].value = 0
    tex.use(location=0)
    prog_logo["out_size"].value = (128.0, 128.0)
    prog_logo["logo_px"].value = (0.0, 0.0)
    prog_logo["logo_size_px"].value = (96.0, 96.0)
    apply_logo_frame_size_uniform(prog_logo, 96.0)
    prog_logo["logo_opacity"].value = 1.0
    if "logo_rot_rad" in prog_logo:
        prog_logo["logo_rot_rad"].value = 0.0
    if "logo_mask_rot_rad" in prog_logo:
        prog_logo["logo_mask_rot_rad"].value = 0.0
    apply_logo_mask_uniform(prog_logo, LOGO_MASK_TRIANGLE)
    vao.render(mode=moderngl.TRIANGLE_STRIP)

    raw = fbo.read(components=4)
    img = Image.frombytes("RGBA", fbo.size, raw).transpose(Image.FLIP_TOP_BOTTOM)
    px = np.asarray(img)
    alpha = px[:, :, 3]
    # Center of the logo quad must be opaque (inside triangle).
    assert int(alpha[64, 64]) > 200
    # Far corner of the framebuffer (outside logo quad) must stay empty.
    assert int(alpha[2, 2]) < 10
    # A corner of the logo AABB should be masked out for a triangle crop.
    # Logo quad is centered: roughly x=16..112, y=16..112. Top-left of quad ≈ (20,20).
    assert int(alpha[20, 20]) < 40
    # After FLIP_TOP_BOTTOM, spectrum tip (py=-R / GL bottom) lands at the image
    # bottom — narrow tip there, wide base toward the top.
    tip = int(alpha[64 + 40, 64])
    base_band = int(alpha[64 - 20, 64])
    assert tip > 180, f"triangle tip should be inside, got {tip}"
    assert base_band > 180, f"triangle interior near base should be inside, got {base_band}"


def test_logo_image_larger_than_frame_still_crops_to_frame() -> None:
    """Image size may exceed the shape frame; visible crop stays frame-sized."""
    import moderngl
    from PIL import Image

    from visualizer_studio.gpu_render import _compile, _quad_vao
    from visualizer_studio.logo_mask import (
        LOGO_MASK_CIRCLE,
        apply_logo_frame_size_uniform,
        apply_logo_mask_uniform,
    )

    ctx = moderngl.create_standalone_context()
    _prog_scene, prog_logo, *_rest = _compile(ctx)

    arr = np.full((64, 64, 4), 255, dtype=np.uint8)
    tex = ctx.texture((64, 64), 4, arr.tobytes())
    tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

    fbo = ctx.framebuffer(color_attachments=[ctx.texture((200, 200), 4)])
    fbo.use()
    ctx.clear(0.0, 0.0, 0.0, 0.0)
    ctx.enable(moderngl.BLEND)
    ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

    vao = _quad_vao(ctx, prog_logo)
    prog_logo["tex_logo"].value = 0
    tex.use(location=0)
    prog_logo["out_size"].value = (200.0, 200.0)
    prog_logo["logo_px"].value = (0.0, 0.0)
    # Huge image, small circle frame — silhouette must not grow with image size.
    prog_logo["logo_size_px"].value = (180.0, 180.0)
    apply_logo_frame_size_uniform(prog_logo, 80.0)
    prog_logo["logo_opacity"].value = 1.0
    if "logo_rot_rad" in prog_logo:
        prog_logo["logo_rot_rad"].value = 0.0
    if "logo_mask_rot_rad" in prog_logo:
        prog_logo["logo_mask_rot_rad"].value = 0.0
    apply_logo_mask_uniform(prog_logo, LOGO_MASK_CIRCLE)
    vao.render(mode=moderngl.TRIANGLE_STRIP)

    raw = fbo.read(components=4)
    img = Image.frombytes("RGBA", fbo.size, raw).transpose(Image.FLIP_TOP_BOTTOM)
    alpha = np.asarray(img)[:, :, 3]
    # Center inside the 80px frame.
    assert int(alpha[100, 100]) > 200
    # Just outside the ~80px diameter circle (radius 40) — should be empty.
    # Point ~55px from center on diagonal ≈ outside circle.
    assert int(alpha[100 + 55, 100]) < 40
    # Far outside the large image AABB corner would be filled if mask tracked image size.
    assert int(alpha[20, 20]) < 20
