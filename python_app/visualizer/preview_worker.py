from __future__ import annotations

import base64
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import moderngl
import numpy as np
from PIL import Image

from .config import load_template_any
from .gpu_render import (
    AudioAnalyzer,
    BloomConfig,
    GpuOptions,
    ParticleConfig,
    ParticleSystem,
    RgbSplitConfig,
    _compile,
    _init_glfw_hidden,
    _make_ctx,
    _quad_vao,
    apply_automations,
    render_preview_png,
)


def _read_json_lines():
    for line in sys.stdin:
        s = str(line or "").strip()
        if not s:
            continue
        try:
            yield json.loads(s)
        except Exception:
            continue


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _load_image_rgba(path_str: str, size: tuple[int, int] | None = None, disable_aspect: bool = False) -> np.ndarray:
    from PIL import Image, ImageOps
    img = Image.open(path_str).convert("RGBA")
    if size is not None:
        if not disable_aspect:
            img = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
        else:
            img = img.resize(size, Image.Resampling.LANCZOS)
    arr = np.array(img, dtype=np.uint8)
    return np.flipud(arr)


@dataclass
class _PreviewCtx:
    w: int
    h: int
    ctx: any
    prog_scene: any
    prog_logo: any
    prog_post: any
    prog_lines: any
    prog_points: any
    vao_quad_scene: any
    vao_quad_logo: any
    vao_quad_post: any
    tex_scene: any
    fbo_scene: any
    tex_out: any
    fbo_out: any
    line_vbo: any
    vao_lines: any
    pt_vbo: any
    vao_pts: any
    tex_bg: any
    tex_logo: any | None
    bg_path: str
    bg_disable_aspect: bool
    logo_path: str
    logo_size_px: tuple[float, float]


class PreviewRenderer:
    def __init__(self) -> None:
        self._c: _PreviewCtx | None = None
        self._analyzer: AudioAnalyzer | None = None
        self._analyzer_path: str = ""
        self._particles: ParticleSystem | None = None
        self._cfg_key: str = ""
        self._last_frame: int = -1
        self._shake_state_x: float = 0.0
        self._shake_state_y: float = 0.0

    def _ensure(self, w: int, h: int) -> _PreviewCtx:
        if self._c is not None and self._c.w == w and self._c.h == h:
            return self._c
        _init_glfw_hidden(w, h)
        ctx = _make_ctx()
        prog_scene, prog_logo, prog_post, prog_lines, prog_points, prog_text = _compile(ctx)
        vao_quad_scene = _quad_vao(ctx, prog_scene)
        vao_quad_logo = _quad_vao(ctx, prog_logo)
        vao_quad_post = _quad_vao(ctx, prog_post)
        tex_scene = ctx.texture((w, h), 4)
        tex_scene.filter = (moderngl.LINEAR, moderngl.LINEAR)
        fbo_scene = ctx.framebuffer(color_attachments=[tex_scene])
        tex_out = ctx.texture((w, h), 4)
        tex_out.filter = (moderngl.LINEAR, moderngl.LINEAR)
        fbo_out = ctx.framebuffer(color_attachments=[tex_out])
        line_vbo = ctx.buffer(reserve=4 * 6 * 1024)
        vao_lines = ctx.vertex_array(prog_lines, [(line_vbo, "2f 4f", "in_pos", "in_col")])
        prog_lines["clip_enabled"].value = 0
        prog_lines["clip_center_px"].value = (0.0, 0.0)
        prog_lines["clip_radius_px"].value = 0.0
        pt_vbo = ctx.buffer(reserve=4 * 3 * 2048)
        vao_pts = ctx.vertex_array(prog_points, [(pt_vbo, "2f 1f", "in_pos", "in_size")])
        tex_bg = ctx.texture((w, h), 4, b"\x00\x00\x00\xff" * (w * h))
        tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._c = _PreviewCtx(
            w=w,
            h=h,
            ctx=ctx,
            prog_scene=prog_scene,
            prog_logo=prog_logo,
            prog_post=prog_post,
            prog_lines=prog_lines,
            prog_points=prog_points,
            vao_quad_scene=vao_quad_scene,
            vao_quad_logo=vao_quad_logo,
            vao_quad_post=vao_quad_post,
            tex_scene=tex_scene,
            fbo_scene=fbo_scene,
            tex_out=tex_out,
            fbo_out=fbo_out,
            line_vbo=line_vbo,
            vao_lines=vao_lines,
            pt_vbo=pt_vbo,
            vao_pts=vao_pts,
            tex_bg=tex_bg,
            tex_logo=None,
            bg_path="",
            bg_disable_aspect=False,
            logo_path="",
            logo_size_px=(0.0, 0.0),
        )
        return self._c

    def _set_bg(self, c: _PreviewCtx, background_path: str, disable_aspect: bool) -> None:
        p = str(background_path or "").strip()
        if not p:
            if c.bg_path == "":
                return
            c.tex_bg.release()
            c.tex_bg = c.ctx.texture((c.w, c.h), 4, b"\x00\x00\x00\xff" * (c.w * c.h))
            c.tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
            c.bg_path = ""
            c.bg_disable_aspect = disable_aspect
            return
        if c.bg_path == p and c.bg_disable_aspect == disable_aspect:
            return
        bg_rgba = _load_image_rgba(p, (c.w, c.h), disable_aspect=disable_aspect)
        c.tex_bg.release()
        c.tex_bg = c.ctx.texture((c.w, c.h), 4, bg_rgba.tobytes())
        c.tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
        c.bg_path = p
        c.bg_disable_aspect = disable_aspect

    def _set_logo(self, c: _PreviewCtx, logo_path: str) -> None:
        p = str(logo_path or "").strip()
        if c.logo_path == p:
            return
        if c.tex_logo is not None:
            try:
                c.tex_logo.release()
            except Exception:
                pass
        c.tex_logo = None
        c.logo_size_px = (0.0, 0.0)
        c.logo_path = p
        if not p or not Path(p).exists():
            return
        logo_rgba = _load_image_rgba(p)
        lh, lw = int(logo_rgba.shape[0]), int(logo_rgba.shape[1])
        max_w = int(c.w * 0.22)
        scale = min(1.0, max_w / max(1, lw))
        nlw = max(1, int(round(lw * scale)))
        nlh = max(1, int(round(lh * scale)))
        logo_rgba2 = np.array(Image.fromarray(logo_rgba).resize((nlw, nlh), Image.Resampling.LANCZOS), dtype=np.uint8)
        c.tex_logo = c.ctx.texture((nlw, nlh), 4, logo_rgba2.tobytes())
        c.tex_logo.filter = (moderngl.LINEAR, moderngl.LINEAR)
        c.logo_size_px = (float(nlw), float(nlh))

    def _ensure_analyzer(self, mp3_path: str, fps: int, point_count: int) -> AudioAnalyzer | None:
        p = str(mp3_path or "").strip()
        if not p or p == "synthetic" or not Path(p).exists():
            self._analyzer = None
            self._analyzer_path = ""
            return None
        if self._analyzer is not None and self._analyzer_path == p and int(self._analyzer.fps) == int(fps):
            if int(self._analyzer.point_count) != int(point_count):
                self._analyzer.point_count = int(point_count)
            return self._analyzer
        self._analyzer = AudioAnalyzer(p, fps=int(fps), point_count=int(point_count))
        self._analyzer_path = p
        return self._analyzer

    def render(self, payload: dict) -> dict:
        w = int(max(64, min(1280, int(payload.get("width") or 480))))
        h = int(max(64, min(1280, int(payload.get("height") or 270))))
        fps = int(max(1, min(60, int(payload.get("fps") or 30))))
        frame = int(max(0, int(payload.get("frame") or 8)))
        out_png = str(payload.get("outPngPath") or "").strip()
        if not out_png:
            return {"ok": False, "message": "Missing outPngPath"}
        background_path = str(payload.get("backgroundPath") or "").strip()
        if background_path and not Path(background_path).exists():
            return {"ok": False, "message": "Background file does not exist"}
        template_b64 = str(payload.get("templateJsonB64") or "").strip()
        template_path = str(payload.get("templatePath") or "").strip()
        opts = GpuOptions(
            mp3_path=str(payload.get("mp3Path") or "").strip() or "synthetic",
            background_path=background_path,
            output_dir=str(Path(out_png).parent),
            template_path=template_path,
            template_b64=template_b64,
            logo_path=str(payload.get("logoPath") or "").strip(),
            ffmpeg_path="",
            fps=fps,
            width=w,
            height=h,
        )
        render_preview_png(opts, out_png, preview_frame=frame)
        return {"ok": True, "filePath": out_png}


def main() -> int:
    r = PreviewRenderer()
    _write({"type": "ready"})
    for msg in _read_json_lines():
        rid = str(msg.get("id") or "")
        cmd = str(msg.get("cmd") or "")
        if cmd == "exit":
            _write({"id": rid, "ok": True})
            return 0
        if cmd != "render":
            _write({"id": rid, "ok": False, "message": "Unknown cmd"})
            continue
        try:
            out = r.render(msg)
            _write({"id": rid, **out})
        except Exception as e:
            _write({"id": rid, "ok": False, "message": str(e)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
