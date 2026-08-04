"""Preview HDR bloom post-process (REQ-P4.2).

Flag (default off — visual parity with pre-P4):
  CAMXORA_PREVIEW_HDR_BLOOM=1

Pipeline: scene (offscreen) → threshold → blur pyramid → upsample composite
→ tonemap → Qt Preview_FBO with alpha = 1.0 (translucent frameless window safe).

Interactive scrub (REQ-P2) should skip this path and draw directly to the Qt FBO.
"""

from __future__ import annotations

import os
import struct
from typing import Any

import moderngl

ENV_FLAG = "CAMXORA_PREVIEW_HDR_BLOOM"


def preview_hdr_bloom_enabled() -> bool:
    raw = str(os.environ.get(ENV_FLAG, "0") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


_VS = """
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    v_uv = in_uv;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

_FS_THRESHOLD = """
#version 330
uniform sampler2D tex_in;
uniform float threshold;
uniform float knee;
in vec2 v_uv;
out vec4 frag;
void main() {
    vec3 c = texture(tex_in, v_uv).rgb;
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float soft = clamp(l - threshold + knee, 0.0, 2.0 * knee);
    soft = (soft * soft) / (4.0 * max(knee, 1e-4) + 1e-4);
    float contrib = max(l - threshold, soft);
    float w = contrib / max(l, 1e-4);
    frag = vec4(c * w, 1.0);
}
"""

_FS_BLUR = """
#version 330
uniform sampler2D tex_in;
uniform vec2 direction;
uniform vec2 texel;
in vec2 v_uv;
out vec4 frag;
void main() {
    vec2 off = direction * texel;
    vec3 c = texture(tex_in, v_uv).rgb * 0.227027;
    c += texture(tex_in, v_uv + off).rgb * 0.316216;
    c += texture(tex_in, v_uv - off).rgb * 0.316216;
    c += texture(tex_in, v_uv + off * 2.0).rgb * 0.070270;
    c += texture(tex_in, v_uv - off * 2.0).rgb * 0.070270;
    frag = vec4(c, 1.0);
}
"""

_FS_ADD = """
#version 330
uniform sampler2D tex_a;
uniform sampler2D tex_b;
uniform float mix_b;
in vec2 v_uv;
out vec4 frag;
void main() {
    vec3 a = texture(tex_a, v_uv).rgb;
    vec3 b = texture(tex_b, v_uv).rgb;
    frag = vec4(a + b * mix_b, 1.0);
}
"""

_FS_TONEMAP = """
#version 330
uniform sampler2D tex_scene;
uniform sampler2D tex_bloom;
uniform float bloom_strength;
uniform float exposure;
in vec2 v_uv;
out vec4 frag;
vec3 reinhard(vec3 x) {
    return x / (1.0 + x);
}
void main() {
    vec3 scene = texture(tex_scene, v_uv).rgb;
    vec3 bloom = texture(tex_bloom, v_uv).rgb;
    vec3 hdr = (scene + bloom * bloom_strength) * max(exposure, 0.01);
    vec3 sdr = reinhard(hdr);
    sdr = pow(max(sdr, vec3(0.0)), vec3(1.0 / 2.2));
    frag = vec4(clamp(sdr, 0.0, 1.0), 1.0);
}
"""


def _quad_vao(ctx: moderngl.Context, prog: moderngl.Program) -> moderngl.VertexArray:
    data = struct.pack(
        "16f",
        -1.0,
        -1.0,
        0.0,
        0.0,
        1.0,
        -1.0,
        1.0,
        0.0,
        -1.0,
        1.0,
        0.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
    )
    vbo = ctx.buffer(data)
    return ctx.vertex_array(prog, [(vbo, "2f 2f", "in_pos", "in_uv")])


class PreviewHdrBloomPass:
    """Owns offscreen HDR-ish targets and bloom programs for one ModernGL context."""

    def __init__(self, ctx: moderngl.Context) -> None:
        self.ctx = ctx
        self.prog_threshold = ctx.program(vertex_shader=_VS, fragment_shader=_FS_THRESHOLD)
        self.prog_blur = ctx.program(vertex_shader=_VS, fragment_shader=_FS_BLUR)
        self.prog_add = ctx.program(vertex_shader=_VS, fragment_shader=_FS_ADD)
        self.prog_tonemap = ctx.program(vertex_shader=_VS, fragment_shader=_FS_TONEMAP)
        self.vao_threshold = _quad_vao(ctx, self.prog_threshold)
        self.vao_blur = _quad_vao(ctx, self.prog_blur)
        self.vao_add = _quad_vao(ctx, self.prog_add)
        self.vao_tonemap = _quad_vao(ctx, self.prog_tonemap)
        self._size = (0, 0)
        self.tex_scene: moderngl.Texture | None = None
        self.fbo_scene: moderngl.Framebuffer | None = None
        self._levels: list[dict[str, Any]] = []
        self._dtype = "f2"

    def release(self) -> None:
        for level in self._levels:
            for key in ("tex", "fbo", "tex_b", "fbo_b"):
                obj = level.get(key)
                if obj is not None:
                    try:
                        obj.release()
                    except Exception:
                        pass
        self._levels.clear()
        for name in ("fbo_scene", "tex_scene"):
            obj = getattr(self, name, None)
            if obj is not None:
                try:
                    obj.release()
                except Exception:
                    pass
        self.tex_scene = None
        self.fbo_scene = None
        self._size = (0, 0)

    def _make_tex(self, w: int, h: int) -> moderngl.Texture:
        try:
            tex = self.ctx.texture((w, h), 4, dtype=self._dtype)
        except Exception:
            self._dtype = "f1"
            tex = self.ctx.texture((w, h), 4)
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = False
        tex.repeat_y = False
        return tex

    def ensure(self, width: int, height: int) -> None:
        w = max(2, int(width))
        h = max(2, int(height))
        if (w, h) == self._size and self.fbo_scene is not None:
            return
        self.release()
        self.tex_scene = self._make_tex(w, h)
        self.fbo_scene = self.ctx.framebuffer(color_attachments=[self.tex_scene])
        levels: list[dict[str, Any]] = []
        lw, lh = w, h
        for _ in range(4):
            lw = max(2, lw // 2)
            lh = max(2, lh // 2)
            tex = self._make_tex(lw, lh)
            tex_b = self._make_tex(lw, lh)
            levels.append(
                {
                    "size": (lw, lh),
                    "tex": tex,
                    "fbo": self.ctx.framebuffer(color_attachments=[tex]),
                    "tex_b": tex_b,
                    "fbo_b": self.ctx.framebuffer(color_attachments=[tex_b]),
                }
            )
        self._levels = levels
        self._size = (w, h)

    def begin_scene(self, width: int, height: int) -> moderngl.Framebuffer:
        self.ensure(width, height)
        assert self.fbo_scene is not None
        return self.fbo_scene

    def _blur_into(
        self,
        src: moderngl.Texture,
        level: dict[str, Any],
    ) -> None:
        lw, lh = level["size"]
        texel = (1.0 / float(lw), 1.0 / float(lh))
        level["fbo_b"].use()
        self.ctx.viewport = (0, 0, lw, lh)
        src.use(location=0)
        self.prog_blur["tex_in"].value = 0
        self.prog_blur["direction"].value = (1.0, 0.0)
        self.prog_blur["texel"].value = texel
        self.vao_blur.render(mode=moderngl.TRIANGLE_STRIP)
        level["fbo"].use()
        self.ctx.viewport = (0, 0, lw, lh)
        level["tex_b"].use(location=0)
        self.prog_blur["direction"].value = (0.0, 1.0)
        self.vao_blur.render(mode=moderngl.TRIANGLE_STRIP)

    def resolve(
        self,
        *,
        screen_fbo: Any,
        viewport: tuple[int, int, int, int],
        bloom_strength: float = 0.85,
        threshold: float = 0.65,
        exposure: float = 1.05,
    ) -> None:
        if self.tex_scene is None or not self._levels:
            return
        ctx = self.ctx
        prev_blend = None
        try:
            prev_blend = ctx.blend_func
        except Exception:
            pass
        try:
            ctx.disable(moderngl.BLEND)
        except Exception:
            pass

        # 1) Threshold from scene → level0
        level0 = self._levels[0]
        level0["fbo"].use()
        ctx.viewport = (0, 0, level0["size"][0], level0["size"][1])
        self.tex_scene.use(location=0)
        self.prog_threshold["tex_in"].value = 0
        self.prog_threshold["threshold"].value = float(max(0.0, min(1.0, threshold)))
        self.prog_threshold["knee"].value = 0.12
        self.vao_threshold.render(mode=moderngl.TRIANGLE_STRIP)

        # 2) Blur level0, then downsample+blur into coarser levels
        self._blur_into(level0["tex"], level0)
        for i in range(1, len(self._levels)):
            prev = self._levels[i - 1]["tex"]
            self._blur_into(prev, self._levels[i])

        # 3) Upsample: accumulate coarser into finer (additive)
        for i in range(len(self._levels) - 1, 0, -1):
            coarse = self._levels[i]["tex"]
            fine = self._levels[i - 1]
            fw, fh = fine["size"]
            fine["fbo_b"].use()
            ctx.viewport = (0, 0, fw, fh)
            fine["tex"].use(location=0)
            coarse.use(location=1)
            self.prog_add["tex_a"].value = 0
            self.prog_add["tex_b"].value = 1
            self.prog_add["mix_b"].value = 1.0
            self.vao_add.render(mode=moderngl.TRIANGLE_STRIP)
            # Copy accumulate back into fine.tex
            fine["fbo"].use()
            ctx.viewport = (0, 0, fw, fh)
            fine["tex_b"].use(location=0)
            self.prog_blur["tex_in"].value = 0
            self.prog_blur["direction"].value = (0.0, 0.0)
            self.prog_blur["texel"].value = (1.0 / float(fw), 1.0 / float(fh))
            self.vao_blur.render(mode=moderngl.TRIANGLE_STRIP)

        bloom_tex = self._levels[0]["tex"]

        # 4) Tonemap to Qt screen FBO — alpha always 1
        screen_fbo.use()
        x, y, vw, vh = viewport
        ctx.viewport = (int(x), int(y), int(vw), int(vh))
        self.tex_scene.use(location=0)
        bloom_tex.use(location=1)
        self.prog_tonemap["tex_scene"].value = 0
        self.prog_tonemap["tex_bloom"].value = 1
        self.prog_tonemap["bloom_strength"].value = float(max(0.0, min(3.0, bloom_strength)))
        self.prog_tonemap["exposure"].value = float(max(0.1, min(4.0, exposure)))
        self.vao_tonemap.render(mode=moderngl.TRIANGLE_STRIP)

        try:
            ctx.enable(moderngl.BLEND)
            if prev_blend is not None:
                ctx.blend_func = prev_blend
        except Exception:
            pass
