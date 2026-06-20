from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import glfw
import moderngl
import numpy as np
from PIL import Image

from .audio import AudioAnalyzer
from .automation import apply_automations
from .config import load_template_any, load_template_any_raw
from .effects import BloomConfig, RgbSplitConfig
from .particles import ParticleConfig, ParticleSystem


@dataclass(frozen=True)
class GpuOptions:
    mp3_path: str
    background_path: str
    output_dir: str
    template_path: str
    template_b64: str
    logo_path: str
    ffmpeg_path: str
    fps: int
    width: int
    height: int
    speed_mode: str = "balanced"


def _send(payload: dict) -> None:
    print("MG_EVENT " + json.dumps(payload, ensure_ascii=False), flush=True)


def _load_template(opts: GpuOptions) -> dict:
    if opts.template_b64:
        # Just return the raw dictionary, it's the new Zustand state structure
        return json.loads(base64.b64decode(opts.template_b64).decode("utf-8"))
    return load_template_any(opts.template_path)


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


def _init_glfw_hidden(width: int, height: int) -> None:
    if not glfw.init():
        raise RuntimeError("Failed to init GLFW")
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.SAMPLES, 4)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
    win = glfw.create_window(width, height, "MG_GPU", None, None)
    if not win:
        glfw.terminate()
        raise RuntimeError("Failed to create hidden OpenGL window")
    glfw.make_context_current(win)
    glfw.swap_interval(0)


def _make_ctx() -> moderngl.Context:
    ctx = moderngl.create_context()
    ctx.enable(moderngl.BLEND)
    ctx.enable(moderngl.PROGRAM_POINT_SIZE)
    # moderngl.MULTISAMPLE does not exist in moderngl directly, it's just implicitly enabled if the context has samples
    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
    return ctx


def _compile(ctx: moderngl.Context):
    vs_quad = """
    #version 330
    in vec2 in_pos;
    in vec2 in_uv;
    out vec2 v_uv;
    void main() {
        v_uv = in_uv;
        gl_Position = vec4(in_pos, 0.0, 1.0);
    }
    """

    fs_scene = """
    #version 330
    uniform sampler2D tex_bg;
    uniform float bg_brightness;
    uniform vec2 bg_offset;
    uniform vec2 bg_scale;
    uniform vec2 bg_tex_size;
    uniform int bg_fit_mode;
    uniform vec2 out_size;
    uniform int vignette_enabled;
    uniform float vignette_strength;
    uniform float vignette_feather;
    uniform vec3 vignette_color;
    uniform float vignette_opacity;
    uniform int smoke_enabled;
    uniform float smoke_strength;
    uniform float smoke_blur;
    uniform float smoke_noise;
    uniform float smoke_speed;
    uniform vec3 smoke_color;
    uniform float smoke_opacity;
    uniform float time_sec;
    in vec2 v_uv;
    out vec4 frag;
    float hash(vec2 p) {
        return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
    }
    float noise2(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        float a = hash(i);
        float b = hash(i + vec2(1.0, 0.0));
        float c = hash(i + vec2(0.0, 1.0));
        float d = hash(i + vec2(1.0, 1.0));
        vec2 u = f * f * (3.0 - 2.0 * f);
        return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
    }
    void main() {
        vec2 uv = v_uv;
        float out_aspect = out_size.x / max(1.0, out_size.y);
        float tex_aspect = bg_tex_size.x / max(1.0, bg_tex_size.y);
        vec2 fit_uv = uv;
        if (bg_fit_mode == 2) {
            vec2 px = uv * out_size;
            vec2 p0 = (out_size - bg_tex_size) * 0.5;
            fit_uv = (px - p0) / bg_tex_size;
        } else {
            vec2 fit_scale = vec2(1.0, 1.0);
            if (bg_fit_mode == 0) {
                if (tex_aspect > out_aspect) {
                    fit_scale.x = out_aspect / max(1e-6, tex_aspect);
                } else {
                    fit_scale.y = tex_aspect / max(1e-6, out_aspect);
                }
            } else if (bg_fit_mode == 1) {
                if (tex_aspect > out_aspect) {
                    fit_scale.y = tex_aspect / max(1e-6, out_aspect);
                } else {
                    fit_scale.x = out_aspect / max(1e-6, tex_aspect);
                }
            }
            fit_uv = (uv - vec2(0.5, 0.5)) * fit_scale + vec2(0.5, 0.5);
        }
        uv = (fit_uv - vec2(0.5, 0.5)) / bg_scale + vec2(0.5, 0.5) + bg_offset;
        bool outside = (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0);
        if (outside && (bg_fit_mode == 1 || bg_fit_mode == 2)) {
            frag = vec4(0.0, 0.0, 0.0, 1.0);
            return;
        }
        uv = clamp(uv, vec2(0.0, 0.0), vec2(1.0, 1.0));
        vec4 bg = texture(tex_bg, uv);
        bg.rgb *= bg_brightness;
        float r = length((v_uv - vec2(0.5, 0.5)) / vec2(0.7071, 0.7071));
        float corner = smoothstep(1.0 - max(0.001, vignette_feather), 1.0, r);
        if (vignette_enabled == 1) {
            float v = clamp(corner * vignette_strength, 0.0, 1.0) * vignette_opacity;
            bg.rgb = mix(bg.rgb, vignette_color, v);
        }
        if (smoke_enabled == 1) {
            float scale = mix(2.0, 12.0, clamp(smoke_blur, 0.0, 1.0));
            vec2 p = v_uv * scale + vec2(time_sec * smoke_speed * 0.35, time_sec * smoke_speed * 0.25);
            float n = noise2(p) * 0.65 + noise2(p * 2.1) * 0.35;
            float m = clamp((n - 0.35) * 2.0, 0.0, 1.0);
            float s = clamp(corner * smoke_strength * (0.35 + m * smoke_noise), 0.0, 1.0) * smoke_opacity;
            bg.rgb = mix(bg.rgb, smoke_color, s);
        }
        frag = bg;
    }
    """
    
    fs_logo = """
    #version 330
    uniform sampler2D tex_logo;
    uniform float logo_opacity;
    uniform int logo_circle_mask;
    uniform vec2 logo_px;
    uniform vec2 logo_size_px;
    uniform float logo_rot_rad;
    uniform vec2 out_size;
    in vec2 v_uv;
    out vec4 frag;
    void main() {
        vec2 px = v_uv * out_size;
        vec2 center = out_size * 0.5 + logo_px;
        vec2 p0 = center - logo_size_px * 0.5;
        vec2 p1 = center + logo_size_px * 0.5;
        if (px.x < p0.x || px.y < p0.y || px.x > p1.x || px.y > p1.y) {
            frag = vec4(0.0);
            return;
        }
        vec2 luv = (px - p0) / (p1 - p0);
        vec2 dc0 = luv - vec2(0.5, 0.5);
        float c = cos(logo_rot_rad);
        float s = sin(logo_rot_rad);
        vec2 ruv = vec2(dc0.x * c - dc0.y * s, dc0.x * s + dc0.y * c) + vec2(0.5, 0.5);
        vec4 lg = texture(tex_logo, ruv);
        vec2 dc = ruv - vec2(0.5, 0.5);
        float d = length(dc);
        float mask = logo_circle_mask == 1 ? (1.0 - smoothstep(0.48, 0.50, d)) : 1.0;
        float a = lg.a * mask * logo_opacity;
        frag = vec4(lg.rgb, a);
    }
    """

    fs_text = """
    #version 330
    uniform sampler2D tex_text;
    uniform float text_opacity;
    uniform vec2 text_px;
    uniform vec2 text_size_px;
    uniform vec2 out_size;
    uniform float reveal;
    in vec2 v_uv;
    out vec4 frag;
    void main() {
        vec2 px = v_uv * out_size;
        vec2 center = out_size * 0.5 + text_px;
        vec2 p0 = center - text_size_px * 0.5;
        vec2 p1 = center + text_size_px * 0.5;
        if (px.x < p0.x || px.y < p0.y || px.x > p1.x || px.y > p1.y) {
            frag = vec4(0.0);
            return;
        }
        vec2 luv = (px - p0) / (p1 - p0);
        if (luv.x > clamp(reveal, 0.0, 1.0)) {
            frag = vec4(0.0);
            return;
        }
        vec4 c = texture(tex_text, luv);
        frag = vec4(c.rgb, c.a * text_opacity);
    }
    """

    vs_lines = """
    #version 330
    in vec2 in_pos;
    in vec4 in_col;
    out vec4 v_col;
    void main() {
        v_col = in_col;
        gl_Position = vec4(in_pos, 0.0, 1.0);
    }
    """

    fs_color = """
    #version 330
    in vec4 v_col;
    uniform int clip_enabled;
    uniform vec2 clip_center_px;
    uniform float clip_radius_px;
    out vec4 frag;
    void main() {
        if (clip_enabled == 1) {
            vec2 p = gl_FragCoord.xy;
            vec2 d = p - clip_center_px;
            if (length(d) > clip_radius_px) discard;
        }
        frag = v_col;
    }
    """

    vs_points = """
    #version 330
    in vec2 in_pos;
    in float in_size;
    uniform float pt_size;
    uniform vec4 pt_col;
    out vec4 v_col;
    void main() {
        v_col = pt_col;
        gl_Position = vec4(in_pos, 0.0, 1.0);
        gl_PointSize = max(1.0, pt_size * max(0.2, in_size));
    }
    """

    fs_points = """
    #version 330
    in vec4 v_col;
    uniform int pt_style;
    out vec4 frag;
    float sat(float x) { return clamp(x, 0.0, 1.0); }
    void main() {
        vec2 p = gl_PointCoord * 2.0 - 1.0;
        float r2 = dot(p, p);
        float r = sqrt(max(r2, 0.0));
        if (r > 1.0) discard;
        float a = 1.0;
        if (pt_style == 1) {
            float core = 1.0 - smoothstep(0.55, 1.0, r);
            float halo = 1.0 - smoothstep(0.0, 1.0, r);
            a = max(core, halo * 0.35);
        } else if (pt_style == 2) {
            float inner = smoothstep(0.55, 0.62, r);
            float outer = 1.0 - smoothstep(0.82, 0.90, r);
            a = sat(inner * outer);
        } else if (pt_style == 3) {
            float w = 0.10;
            float ax = 1.0 - smoothstep(w, w + 0.04, abs(p.x));
            float ay = 1.0 - smoothstep(w, w + 0.04, abs(p.y));
            float d1 = abs(p.x - p.y) * 0.70710678;
            float d2 = abs(p.x + p.y) * 0.70710678;
            float ad1 = 1.0 - smoothstep(w, w + 0.04, d1);
            float ad2 = 1.0 - smoothstep(w, w + 0.04, d2);
            float spike = max(max(ax, ay), max(ad1, ad2));
            float core = 1.0 - smoothstep(0.40, 1.0, r);
            float halo = 1.0 - smoothstep(0.0, 1.0, r);
            a = max(core, max(spike * 0.85, halo * 0.25));
        } else if (pt_style == 4) {
            float soft = 1.0 - smoothstep(0.0, 1.0, r);
            a = pow(soft, 1.8);
        }
        frag = vec4(v_col.rgb, v_col.a * a);
    }
    """

    fs_post = """
    #version 330
    uniform sampler2D tex_in;
    uniform vec2 out_size;
    uniform vec2 rgb_r;
    uniform vec2 rgb_g;
    uniform vec2 rgb_b;
    uniform float rgb_opacity;
    uniform float bloom_strength;
    uniform float bloom_threshold;
    in vec2 v_uv;
    out vec4 frag;
    vec4 sample_rgb(vec2 uv) {
        vec2 px = 1.0 / out_size;
        vec4 base = texture(tex_in, uv);
        if (rgb_opacity <= 0.001) return base;
        vec4 c;
        c.r = texture(tex_in, uv + rgb_r * px).r;
        c.g = texture(tex_in, uv + rgb_g * px).g;
        c.b = texture(tex_in, uv + rgb_b * px).b;
        c.a = base.a;
        return mix(base, c, rgb_opacity);
    }
    void main() {
        vec4 col = sample_rgb(v_uv);
        if (bloom_strength <= 0.001) {
            frag = col;
            return;
        }
        float l = dot(col.rgb, vec3(0.2126, 0.7152, 0.0722));
        if (l < bloom_threshold) {
            frag = col;
            return;
        }
        vec2 px = 1.0 / out_size;
        vec4 s = vec4(0.0);
        s += texture(tex_in, v_uv + vec2(-2.0, 0.0) * px);
        s += texture(tex_in, v_uv + vec2(2.0, 0.0) * px);
        s += texture(tex_in, v_uv + vec2(0.0, -2.0) * px);
        s += texture(tex_in, v_uv + vec2(0.0, 2.0) * px);
        s += texture(tex_in, v_uv + vec2(-2.0, -2.0) * px);
        s += texture(tex_in, v_uv + vec2(2.0, 2.0) * px);
        s += texture(tex_in, v_uv + vec2(-2.0, 2.0) * px);
        s += texture(tex_in, v_uv + vec2(2.0, -2.0) * px);
        s *= 0.125;
        frag = vec4(col.rgb + s.rgb * bloom_strength, 1.0);
    }
    """

    prog_scene = ctx.program(vertex_shader=vs_quad, fragment_shader=fs_scene)
    prog_logo = ctx.program(vertex_shader=vs_quad, fragment_shader=fs_logo)
    prog_text = ctx.program(vertex_shader=vs_quad, fragment_shader=fs_text)
    prog_post = ctx.program(vertex_shader=vs_quad, fragment_shader=fs_post)
    prog_lines = ctx.program(vertex_shader=vs_lines, fragment_shader=fs_color)
    prog_points = ctx.program(vertex_shader=vs_points, fragment_shader=fs_points)
    return prog_scene, prog_logo, prog_post, prog_lines, prog_points, prog_text


def _as_rgb(v: any) -> tuple[int, int, int]:
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return (int(v[0]), int(v[1]), int(v[2]))
    if isinstance(v, str) and v.startswith("#") and len(v) == 7:
        return (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
    return (255, 255, 255)

def _render_text_rgba(text: str, size_px: float, color: str, stroke_color: str, stroke_width: float, shadow: float) -> tuple[np.ndarray, int, int]:
    from PIL import Image, ImageDraw, ImageFont
    t = str(text or "").strip()
    if not t:
        arr0 = np.zeros((1, 1, 4), dtype=np.uint8)
        return arr0, 1, 1
    s = int(max(10, min(320, int(round(float(size_px))))))
    try:
        font = ImageFont.truetype("arial.ttf", s)
    except Exception:
        font = ImageFont.load_default()
    sw = int(max(0, min(24, int(round(float(stroke_width))))))
    sh = float(max(0.0, min(1.0, float(shadow))))
    shadow_px = int(round(2.0 * sh))
    tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(tmp)
    bbox = d0.multiline_textbbox((0, 0), t, font=font, stroke_width=sw, spacing=int(round(s * 0.15)))
    w = int(max(1, bbox[2] - bbox[0]))
    h = int(max(1, bbox[3] - bbox[1]))
    pad = int(max(6, round(s * 0.35 + sw * 1.2)))
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0 = pad - int(bbox[0])
    y0 = pad - int(bbox[1])
    if shadow_px > 0:
        d.multiline_text((x0 + shadow_px, y0 + shadow_px), t, font=font, fill=(0, 0, 0, int(255 * sh)), stroke_width=sw, stroke_fill=(0, 0, 0, int(255 * sh)), spacing=int(round(s * 0.15)))
    d.multiline_text((x0, y0), t, font=font, fill=str(color or "#ffffff"), stroke_width=sw, stroke_fill=str(stroke_color or "#000000"), spacing=int(round(s * 0.15)))
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    arr = np.flipud(arr)
    return arr, int(img.width), int(img.height)

def _draw_text_overlays(
    ctx: moderngl.Context,
    prog_text: moderngl.Program,
    vao_quad_text: moderngl.VertexArray,
    overlays: list,
    time_sec: float,
    w: int,
    h: int,
    sf: float,
    cache: dict,
) -> None:
    if not overlays:
        return
    tex_list = cache.get("tex")
    key_list = cache.get("key")
    wh_list = cache.get("wh")
    if not isinstance(tex_list, list) or not isinstance(key_list, list) or not isinstance(wh_list, list):
        return
    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
    for idx, o in enumerate(overlays[:5]):
        if not isinstance(o, dict) or not bool(o.get("enabled", False)):
            continue
        text = str(o.get("text", "") or "").strip()
        if not text:
            continue
        start = float(o.get("startSec", 0.0) or 0.0)
        dur = float(o.get("durationSec", 3.0) or 3.0)
        if dur <= 0:
            continue
        t_rel = float(time_sec) - start
        if t_rel < 0.0 or t_rel > dur:
            continue
        u = float(max(0.0, min(1.0, t_rel / dur)))
        ease = u * u * (3.0 - 2.0 * u)
        anim = str(o.get("animation", "fade") or "fade")
        opacity = 1.0
        dx = 0.0
        dy = 0.0
        scale_t = 1.0
        reveal = 1.0
        fade_in = 0.18
        fade_out = 0.18
        if anim in ("fade", "slide_up", "slide_down", "slide_left", "slide_right", "pop", "typewriter", "glow", "shake"):
            a_in = min(1.0, u / max(0.001, fade_in))
            a_out = min(1.0, (1.0 - u) / max(0.001, fade_out))
            opacity = max(0.0, min(1.0, a_in * a_out))
        if anim == "slide_up":
            dy -= float((1.0 - ease) * 60.0 * sf)
        elif anim == "slide_down":
            dy += float((1.0 - ease) * 60.0 * sf)
        elif anim == "slide_left":
            dx -= float((1.0 - ease) * 70.0 * sf)
        elif anim == "slide_right":
            dx += float((1.0 - ease) * 70.0 * sf)
        elif anim == "pop":
            scale_t = float(max(0.3, min(2.5, 0.85 + ease * 0.2)))
        elif anim == "typewriter":
            reveal = float(max(0.0, min(1.0, u * 1.2)))
        elif anim == "glow":
            import math
            opacity *= float(0.78 + 0.22 * math.sin(u * math.tau * 2.0))
        elif anim == "shake":
            import math
            k = float(max(0.0, min(1.0, u))) * (1.0 - float(max(0.0, min(1.0, u))))
            dx += float(math.sin((start + float(time_sec)) * 38.0 + idx * 7.0) * 10.0 * sf * k)
            dy += float(math.cos((start + float(time_sec)) * 41.0 + idx * 11.0) * 10.0 * sf * k)
        size_px = float(o.get("sizePx", 46.0) if "sizePx" in o else 46.0)
        col = str(o.get("color", "#ffffff") or "#ffffff").strip()
        scol = str(o.get("strokeColor", "#000000") or "#000000").strip()
        sw = float(o.get("strokeWidth", 2.0) if "strokeWidth" in o else 2.0)
        sh = float(o.get("shadow", 0.4) if "shadow" in o else 0.4)
        key = f"{text}|{size_px:.2f}|{col}|{scol}|{sw:.2f}|{sh:.2f}"
        if idx >= len(key_list) or idx >= len(tex_list) or idx >= len(wh_list):
            continue
        if key_list[idx] != key or tex_list[idx] is None:
            arr, tw, th = _render_text_rgba(text, size_px * float(max(0.25, min(4.0, sf))), col, scol, sw * float(max(0.25, min(4.0, sf))), sh)
            if tex_list[idx] is not None:
                try:
                    tex_list[idx].release()
                except Exception:
                    pass
            tx = ctx.texture((tw, th), 4, arr.tobytes())
            tx.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tex_list[idx] = tx
            wh_list[idx] = (int(tw), int(th))
            key_list[idx] = key
        tw, th = wh_list[idx]
        tx = tex_list[idx]
        if not tx or tw <= 0 or th <= 0:
            continue
        anchor_t = str(o.get("anchor", "top-left") or "top-left")
        ox = float(o.get("x", 24.0) if "x" in o else 24.0) * sf
        oy = float(o.get("y", 24.0) if "y" in o else 24.0) * sf
        ax, ay = _get_anchor_coords(anchor_t, ox, oy, w, h)
        prog_text["tex_text"].value = 2
        tx.use(location=2)
        prog_text["out_size"].value = (float(w), float(h))
        prog_text["text_px"].value = (float(ax) - float(w) * 0.5 + dx, float(ay) - float(h) * 0.5 + dy)
        prog_text["text_size_px"].value = (float(tw) * scale_t, float(th) * scale_t)
        prog_text["text_opacity"].value = float(max(0.0, min(1.0, opacity)))
        prog_text["reveal"].value = float(max(0.0, min(1.0, reveal)))
        vao_quad_text.render(mode=moderngl.TRIANGLE_STRIP)

def _quad_vao(ctx: moderngl.Context, prog: moderngl.Program) -> moderngl.VertexArray:
    v = np.array(
        [
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
        ],
        dtype="f4",
    )
    vbo = ctx.buffer(v.tobytes())
    return ctx.vertex_array(prog, [(vbo, "2f 2f", "in_pos", "in_uv")])


import uuid

def _no_window_kwargs() -> dict:
    """Suppress console window on Windows for subprocess calls."""
    if sys.platform != "win32":
        return {}
    kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        kwargs["startupinfo"] = si
    except Exception:
        pass
    return kwargs


def _start_ffmpeg(ffmpeg_path: str, mp3_path: str, out_path: str, w: int, h: int, fps: int, speed_mode: str) -> subprocess.Popen:
    mode = str(speed_mode or "balanced").strip().lower()
    if mode == "very_fast":
        nvenc_preset = "p1"
        nvenc_cq = "27"
        x264_preset = "ultrafast"
        x264_crf = "26"
    elif mode == "fast":
        nvenc_preset = "p3"
        nvenc_cq = "23"
        x264_preset = "superfast"
        x264_crf = "23"
    else:
        nvenc_preset = "p5"
        nvenc_cq = "19"
        x264_preset = "veryfast"
        x264_crf = "20"
    cmd: list[str] = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-y",
        "-fflags",
        "+genpts",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgba",
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-i",
        mp3_path,
        "-af",
        "aresample=async=1000",
        "-vf",
        "vflip,scale=in_range=pc:out_range=pc",
        "-c:v",
        "h264_nvenc",
        "-preset",
        nvenc_preset,
        "-cq",
        nvenc_cq,
        "-color_range",
        "pc",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        out_path,
    ]
    err_file = open(Path(out_path).parent / f"ffmpeg_error_{uuid.uuid4().hex[:8]}.log", "w+", encoding="utf-8")
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err_file, **_no_window_kwargs())
    time.sleep(0.2)
    if enc.poll() is not None:
        err_file.seek(0)
        err_txt = err_file.read()
        cmd2 = cmd[:]
        cmd2[cmd2.index("h264_nvenc")] = "libx264"
        if "-cq" in cmd2:
            i = cmd2.index("-cq")
            del cmd2[i : i + 2]
        if "-preset" in cmd2:
            i = cmd2.index("-preset")
            cmd2[i + 1] = x264_preset
        if "-crf" not in cmd2:
            cmd2.insert(cmd2.index("-pix_fmt"), "-crf")
            cmd2.insert(cmd2.index("-pix_fmt") + 1, x264_crf)
        err_file.seek(0)
        err_file.truncate()
        enc = subprocess.Popen(cmd2, stdin=subprocess.PIPE, stderr=err_file, **_no_window_kwargs())
        time.sleep(0.2)
        if enc.poll() is not None:
            err_file.seek(0)
            err_txt2 = err_file.read()
            raise RuntimeError(err_txt2.strip() or "FFmpeg failed to start")
    
    # attach err_file to enc so we can close/read it later
    enc._err_file = err_file
    return enc


def _stem(p: str) -> str:
    return Path(p).stem or "output"


def _get_anchor_coords(anchor: str, offset_x: float, offset_y: float, w: int, h: int) -> tuple[float, float]:
    anchor = str(anchor).lower().strip()
    
    # X axis
    if "left" in anchor:
        cx = 0.0
    elif "right" in anchor:
        cx = float(w)
    else:
        cx = float(w) * 0.5
        
    # Y axis - Note: OpenGL Y=0 is BOTTOM, but DOM Y=0 is TOP
    # So "top" means Y=h in OpenGL, "bottom" means Y=0 in OpenGL
    if "top" in anchor:
        cy = float(h)
    elif "bottom" in anchor:
        cy = 0.0
    else:
        cy = float(h) * 0.5
        
    # DOM offsetY is positive downwards. In OpenGL, positive is upwards.
    # So we must subtract offsetY to match DOM behavior.
    return (cx + offset_x, cy - offset_y)


def _smooth_env(prev: float, target: float, smoothing: float) -> float:
    s = float(max(0.0, min(0.99, smoothing)))
    t = float(max(0.0, min(1.0, target)))
    return float((float(prev) * s) + (t * (1.0 - s)))

def run_gpu_render(opts: GpuOptions) -> int:
    fps = int(max(1, min(60, int(opts.fps))))
    if fps <= 0:
        fps = 30

    template = _load_template(opts)

    w = int(max(64, min(8192, int(opts.width) if int(opts.width) > 0 else 1920)))
    h = int(max(64, min(8192, int(opts.height) if int(opts.height) > 0 else 1080)))

    base_h = float(template.get("renderBaseHeight", 450.0))
    base_h = float(max(1.0, min(4000.0, base_h)))
    sf = float(h) / base_h

    _send({"status": "running", "message": "Initializing GPU renderer...", "progress": 0.0})
    _init_glfw_hidden(w, h)
    ctx = _make_ctx()

    bg_disable_aspect = False

    if opts.background_path and Path(opts.background_path).exists():
        bg_rgba = _load_image_rgba(opts.background_path, None, disable_aspect=bg_disable_aspect)
    else:
        bg_rgba = np.zeros((h, w, 4), dtype=np.uint8)
        bg_rgba[:, :, 3] = 255
    logo_raw0 = template.get("logoSettings") if isinstance(template.get("logoSettings"), dict) else {}
    logo_enabled0 = bool(logo_raw0.get("enabled", True))
    has_logo = bool(logo_enabled0 and opts.logo_path and Path(opts.logo_path).exists())
    logo_rgba = _load_image_rgba(opts.logo_path) if has_logo else None

    bg_h0 = int(bg_rgba.shape[0]) if hasattr(bg_rgba, "shape") else int(h)
    bg_w0 = int(bg_rgba.shape[1]) if hasattr(bg_rgba, "shape") else int(w)
    bg_h0 = int(max(1, bg_h0))
    bg_w0 = int(max(1, bg_w0))
    bg_tex_size = (float(bg_w0), float(bg_h0))
    tex_bg = ctx.texture((bg_w0, bg_h0), 4, bg_rgba.tobytes())
    tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)

    tex_logo = None
    logo_size_px = (0.0, 0.0)
    if has_logo and logo_rgba is not None:
        # Base logo size in React is 192x192 pixels. Scale it to the video resolution.
        base_size = int(round(192 * sf))
        logo_rgba2 = np.array(Image.fromarray(logo_rgba).resize((base_size, base_size), Image.Resampling.LANCZOS), dtype=np.uint8)
        tex_logo = ctx.texture((base_size, base_size), 4, logo_rgba2.tobytes())
        tex_logo.filter = (moderngl.LINEAR, moderngl.LINEAR)
        logo_size_px = (float(base_size), float(base_size))

    prog_scene, prog_logo, prog_post, prog_lines, prog_points, prog_text = _compile(ctx)
    vao_quad_scene = _quad_vao(ctx, prog_scene)
    vao_quad_logo = _quad_vao(ctx, prog_logo)
    vao_quad_text = _quad_vao(ctx, prog_text)
    vao_quad_post = _quad_vao(ctx, prog_post)
    text_cache = {"tex": [None] * 5, "key": [None] * 5, "wh": [(0, 0)] * 5}
    text_overlays = template.get("textOverlays") if isinstance(template.get("textOverlays"), list) else []
    text_cache = {"tex": [None] * 5, "key": [None] * 5, "wh": [(0, 0)] * 5}

    tex_scene = ctx.texture((w, h), 4)
    tex_scene.filter = (moderngl.LINEAR, moderngl.LINEAR)
    fbo_scene = ctx.framebuffer(color_attachments=[tex_scene])

    tex_out = ctx.texture((w, h), 4)
    tex_out.filter = (moderngl.LINEAR, moderngl.LINEAR)
    fbo_out = ctx.framebuffer(color_attachments=[tex_out])

    line_vbo = ctx.buffer(reserve=4 * 6 * 512)
    vao_lines = ctx.vertex_array(prog_lines, [(line_vbo, "2f 4f", "in_pos", "in_col")])
    prog_lines["clip_enabled"].value = 0
    prog_lines["clip_center_px"].value = (0.0, 0.0)
    prog_lines["clip_radius_px"].value = 0.0

    pt_vbo = ctx.buffer(reserve=4 * 3 * 1024)
    vao_pts = ctx.vertex_array(prog_points, [(pt_vbo, "2f 1f", "in_pos", "in_size")])

    # In the new format, the root template IS the spectrum container
    spectrum_container = template
    point_count = 1024 # Fixed to 1024 for high-res FFT
    
    # We no longer have spec_style or spec_tex for background scale/offset in the spectrum layer.
    # Background scale/offset is now handled via backgroundSettings (if added) or just defaults to 1.0/0.0
    bg_scale = 1.0
    bg_offset = (0.0, 0.0)

    analyzer = AudioAnalyzer(opts.mp3_path, fps=fps, point_count=point_count)
    total_frames = int(analyzer.info.frames)

    particles_cfg_raw = template.get("particlesSettings", {}) if isinstance(template.get("particlesSettings"), dict) else {}
    if not particles_cfg_raw and isinstance(template.get("particles"), dict):
        particles_cfg_raw = template.get("particles")  # legacy fallback
    particles_cfg = ParticleConfig(
        enabled=bool(particles_cfg_raw.get("enabled", False)),
        max_count=int(particles_cfg_raw.get("maxCount", particles_cfg_raw.get("count", 400))),
        spawn_rate=float(particles_cfg_raw.get("spawnRate", particles_cfg_raw.get("spawn_rate", 40.0))),
        lifetime_sec=float(particles_cfg_raw.get("lifetimeSec", particles_cfg_raw.get("lifetime_sec", 1.6))),
        spawn_radius=0.0,
        size=float(particles_cfg_raw.get("size", 2.0)) * sf,
        opacity=float(particles_cfg_raw.get("opacity", 0.35)),
        color=tuple(_as_rgb(particles_cfg_raw.get("color", "#ffffff"))),
        speed=float(particles_cfg_raw.get("speed", 120.0)) * sf,
    )
    particles = ParticleSystem(particles_cfg, width=w, height=h, rng_seed=1)

    effects_raw = template.get("effects") if isinstance(template.get("effects"), dict) else {}
    bloom_raw = effects_raw.get("bloom") if isinstance(effects_raw.get("bloom"), dict) else {}
    rgb_raw = effects_raw.get("rgb_split") if isinstance(effects_raw.get("rgb_split"), dict) else {}
    shake_raw = effects_raw.get("camera_shake") if isinstance(effects_raw.get("camera_shake"), dict) else {}
    bloom_cfg = BloomConfig(
        enabled=bool(bloom_raw.get("enabled", False)),
        strength=float(bloom_raw.get("strength", 1.0)),
        blur_radius=int(bloom_raw.get("blur_radius", 11)),
        threshold=float(bloom_raw.get("threshold", 0.75)),
        opacity=float(bloom_raw.get("opacity", 0.9)),
    )
    rgb_cfg = RgbSplitConfig(
        enabled=bool(rgb_raw.get("enabled", False)),
        red_offset=tuple(rgb_raw.get("red_offset", (2, 0))),
        green_offset=tuple(rgb_raw.get("green_offset", (0, 0))),
        blue_offset=tuple(rgb_raw.get("blue_offset", (-2, 0))),
        opacity=float(rgb_raw.get("opacity", 0.6)),
    )
    shake_enabled = bool(shake_raw.get("enabled", False))
    shake_intensity = float(shake_raw.get("intensity", 8.0))
    shake_smoothing = float(shake_raw.get("smoothing", 0.85))
    autos = template.get("automations") if isinstance(template.get("automations"), list) else []
    
    bg_settings_raw = template.get("backgroundSettings", {})
    bg_brightness = float(bg_settings_raw.get("brightness", 1.0))
    bg_brightness = float(max(0.0, min(3.0, bg_brightness)))
    bg_react_bass = float(bg_settings_raw.get("reactivity", 0.0))
    bg_react_bass = float(max(0.0, min(2.0, bg_react_bass)))
    bg_smoothing = float(max(0.0, min(0.99, bg_settings_raw.get("smoothing", 0.8))))
    bg_motion_mode = str(bg_settings_raw.get("motionMode", "none") or "none")
    if bg_motion_mode not in ("none", "zoom", "vibrate", "both"):
        bg_motion_mode = "none"
    bg_motion_zoom_strength = float(bg_settings_raw.get("motionZoomStrength", 1.0) or 1.0)
    bg_motion_zoom_strength = float(max(0.0, min(2.0, bg_motion_zoom_strength)))
    bg_motion_vibrate_strength = float(bg_settings_raw.get("motionVibrateStrength", 1.0) or 1.0)
    bg_motion_vibrate_strength = float(max(0.0, min(2.0, bg_motion_vibrate_strength)))
    bg_fit_mode = str(bg_settings_raw.get("fitMode", "cover") or "cover")
    if bg_fit_mode not in ("cover", "contain", "original"):
        bg_fit_mode = "cover"
    bg_fit_mode_i = 0 if bg_fit_mode == "cover" else (1 if bg_fit_mode == "contain" else 2)
    bg_user_scale = float(bg_settings_raw.get("userScale", 1.0) or 1.0)
    bg_user_scale = float(max(0.05, min(20.0, bg_user_scale)))
    bg_user_off_x = float(bg_settings_raw.get("userOffsetX", 0.0) or 0.0)
    bg_user_off_y = float(bg_settings_raw.get("userOffsetY", 0.0) or 0.0)
    
    logo_raw = template.get("logoSettings", {})
    logo_enabled = bool(logo_raw.get("enabled", True))
    logo_circle_mask = bool(logo_raw.get("circleMask", True))
    logo_opacity = float(logo_raw.get("opacity", 1.0))
    logo_opacity = float(max(0.0, min(1.0, logo_opacity)))
    logo_size_base = float(logo_raw.get("size", 192.0))
    logo_size_base = float(max(32.0, min(2000.0, logo_size_base)))
    logo_scale_base = float(logo_raw.get("scale", 1.0))
    logo_scale_base = float(max(0.1, min(2.5, logo_scale_base)))
    logo_react_bass = float(logo_raw.get("reactivity", 0.0))
    logo_react_bass = float(max(0.0, min(2.0, logo_react_bass)))
    logo_smoothing = float(max(0.0, min(0.99, logo_raw.get("smoothing", 0.75))))
    logo_base_radius = (logo_size_base * 0.5) * sf
    logo_spin_enabled = bool(logo_raw.get("spinEnabled", False))
    logo_spin_dir = str(logo_raw.get("spinDirection", "cw") or "cw").strip().lower()
    if logo_spin_dir not in ("cw", "ccw"):
        logo_spin_dir = "cw"
    logo_spin_dir_s = 1.0 if logo_spin_dir == "cw" else -1.0
    logo_spin_speed_deg = float(logo_raw.get("spinSpeed", 0.0) or 0.0)
    logo_spin_speed_deg = float(max(0.0, min(720.0, logo_spin_speed_deg)))

    out_dir = Path(opts.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / f"{_stem(opts.mp3_path)}.mp4")

    _send({"status": "running", "message": "Starting encoder...", "progress": 0.0})
    enc = _start_ffmpeg(opts.ffmpeg_path, opts.mp3_path, out_path, w, h, fps, str(getattr(opts, "speed_mode", "balanced")))

    _send({"status": "running", "message": "Encoder started, setting up shaders...", "progress": 0.0})
    try:
        _send({"status": "running", "message": "[DEBUG] Setting tex_bg...", "progress": 0.0})
        prog_scene["tex_bg"].value = 0
        tex_bg.use(location=0)
        
        if tex_logo is not None and logo_enabled:
            prog_logo["tex_logo"].value = 1
            tex_logo.use(location=1)
            
        if "out_size" in prog_scene:
            prog_scene["out_size"].value = (float(w), float(h))
        if "bg_tex_size" in prog_scene:
            prog_scene["bg_tex_size"].value = bg_tex_size
        if "bg_fit_mode" in prog_scene:
            prog_scene["bg_fit_mode"].value = int(bg_fit_mode_i)
        prog_scene["bg_offset"].value = bg_offset
        prog_scene["bg_scale"].value = (bg_scale, bg_scale)
        prog_scene["bg_brightness"].value = float(bg_brightness)

        if tex_logo is not None and logo_enabled:
            if "out_size" in prog_logo:
                prog_logo["out_size"].value = (float(w), float(h))
            prog_logo["logo_px"].value = (0.0, 0.0)
            base_logo_size_px = (float(logo_size_px[0]), float(logo_size_px[1]))
            prog_logo["logo_size_px"].value = base_logo_size_px
            prog_logo["logo_opacity"].value = float(logo_opacity)
            prog_logo["logo_circle_mask"].value = 1 if logo_circle_mask else 0
            if "logo_rot_rad" in prog_logo:
                prog_logo["logo_rot_rad"].value = 0.0

        _send({"status": "running", "message": "[DEBUG] Setting prog_post uniforms...", "progress": 0.0})
        prog_post["tex_in"].value = 0
        prog_post["out_size"].value = (float(w), float(h))
    except Exception as e:
        import traceback
        _send({"status": "failed", "message": f"Shader setup failed: {e}\n{traceback.format_exc()}", "progress": 0.0})
        raise e

    shake_state_x = 0.0
    shake_state_y = 0.0
    bg_shake_state_x = 0.0
    bg_shake_state_y = 0.0

    dt = 1.0 / max(1.0, float(fps))
    p_bass_fast = 0.0
    p_bass_slow = 0.0
    p_kick_env = 0.0
    bg_audio_env = 0.0
    logo_audio_env = 0.0
    particle_audio_env = 0.0
    p_trigger_env = 0.0
    kick_fast_a = 1.0 - float(np.exp(-dt / 0.06))
    kick_slow_a = 1.0 - float(np.exp(-dt / 0.35))
    kick_decay = float(np.exp(-dt / 0.18))

    _send({"status": "running", "message": "Preparing first frame...", "progress": 0.0})

    # --- Pre-compute spectrum mapping (once, outside frame loop) ---
    from ._spectrum_fast import (
        precompute_fft_mapping, fft_to_log_bins, smooth_and_mirror,
        generate_points_curved, generate_points_linear,
        build_waveform_vertices, build_bar_vertices,
    )
    _fft_idx1, _fft_idx2, _fft_frac = precompute_fft_mapping(point_count)
    # Pre-compute frame-invariant template lookups
    _tpl_style_preset = str(template.get("style", "classic-vertical")).lower().strip()
    _tpl_react_gain = float(template.get("audioSettings", {}).get("sensitivity", 1.0))
    _tpl_position = template.get("position", {}) if isinstance(template.get("position"), dict) else {}
    _tpl_anchor_val = _tpl_position.get("anchor", "center")
    _tpl_off_x = float(_tpl_position.get("x", 0.0)) * sf
    _tpl_off_y = float(_tpl_position.get("y", 0.0)) * sf
    _tpl_spectrum_enabled = bool(template.get("spectrumEnabled", True))
    _tpl_raw_layers = spectrum_container.get("layers", [])
    _tpl_spectrum_layers = [x for x in _tpl_raw_layers if isinstance(x, dict)]
    if not _tpl_spectrum_enabled:
        _tpl_spectrum_layers = []

    for i in range(total_frames):
        fft = analyzer.fft_for_frame(i)
        feats = analyzer.features_for_frame(i)
        base_state = {
            "camera_shake.intensity": shake_intensity,
            "spectrum.scale": 1.0,
            "particles.spawn_rate": float(particles_cfg.spawn_rate),
            "effects.bloom.strength": float(bloom_cfg.strength),
            "effects.rgb_split.opacity": float(rgb_cfg.opacity),
        }
        state = apply_automations(base_state, feats, autos)
        bass = float(feats.get("bass", 0.0))
        if tex_logo is not None and logo_enabled:
            base_radius = logo_base_radius
            s_logo = logo_scale_base * (1.0 + bass * logo_react_bass)
            s_logo = max(0.05, min(4.0, s_logo))
            final_logo_size = base_radius * 2.0 * s_logo
            prog_logo["logo_size_px"].value = (final_logo_size, final_logo_size)
            if "logo_rot_rad" in prog_logo:
                angle = 0.0
                if logo_spin_enabled and logo_spin_speed_deg > 0.0:
                    angle = float(logo_spin_dir_s) * float(logo_spin_speed_deg) * 0.017453292519943295 * (float(i) / float(max(1.0, float(fps))))
                prog_logo["logo_rot_rad"].value = float(angle)
            
            logo_anchor = template.get("position", {}).get("anchor", "center")
            logo_off_x = float(template.get("position", {}).get("x", 0.0)) * sf
            logo_off_y = float(template.get("position", {}).get("y", 0.0)) * sf
            
            l_pos = _get_anchor_coords(logo_anchor, logo_off_x, logo_off_y, w, h)
            # Notice the Y-axis calculation:
            # ModernGL / OpenGL has Y=0 at the BOTTOM.
            # `l_pos[1]` is the exact target pixel (e.g. 1080 for Top, 0 for Bottom).
            # The shader expects `logo_px` to be an offset from the CENTER (w/2, h/2).
            prog_logo["logo_px"].value = (l_pos[0] - float(w)*0.5 + float(shake_state_x), l_pos[1] - float(h)*0.5 + float(shake_state_y))

        if shake_enabled:
            target = float(state.get("camera_shake.intensity", shake_intensity)) * (
                0.35 + float(feats.get("bass", 0.0)) * 1.2 + float(feats.get("beat", 0.0)) * 1.5
            )
            jitter_x = (time.time() * 0.9 + i * 0.013) % 1.0
            jitter_y = (time.time() * 0.9 + i * 0.017) % 1.0
            tx = (jitter_x * 2.0 - 1.0) * target
            ty = (jitter_y * 2.0 - 1.0) * target
            s = max(0.0, min(0.99, shake_smoothing))
            shake_state_x = shake_state_x * s + tx * (1.0 - s)
            shake_state_y = shake_state_y * s + ty * (1.0 - s)
        else:
            shake_state_x = 0.0
            shake_state_y = 0.0

        fbo_scene.use()
        ctx.viewport = (0, 0, w, h)
        ctx.clear(0.0, 0.0, 0.0, 1.0)
        
        # RE-BIND background and logo textures because fbo_out overwrites location 0 with tex_scene!
        tex_bg.use(location=0)
        if tex_logo is not None and logo_enabled:
            tex_logo.use(location=1)
        prog_scene["bg_offset"].value = (
            float((-bg_user_off_x / max(1.0, float(w))) + (bg_shake_state_x / max(1.0, float(w)))),
            float((bg_user_off_y / max(1.0, float(h))) + (bg_shake_state_y / max(1.0, float(h)))),
        )
        if bg_motion_mode in ("zoom", "both"):
            bg_scale_live = float(1.0 + bg_audio_env * bg_react_bass * 0.015 * bg_motion_zoom_strength)
        else:
            bg_scale_live = 1.0
        bg_scale_live = float(bg_scale_live) * float(bg_user_scale)
        prog_scene["bg_scale"].value = (bg_scale_live, bg_scale_live)
        fx = template.get("effects") if isinstance(template.get("effects"), dict) else {}
        vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        prog_scene["vignette_enabled"].value = 1 if bool(vig.get("enabled", False)) else 0
        prog_scene["vignette_strength"].value = float(max(0.0, min(1.0, float(vig.get("strength", 0.35) or 0.35))))
        prog_scene["vignette_feather"].value = float(max(0.0, min(1.0, float(vig.get("feather", 0.65) or 0.65))))
        prog_scene["vignette_opacity"].value = float(max(0.0, min(1.0, float(vig.get("opacity", 0.65) or 0.65))))
        vcol = str(vig.get("color", "#000000") or "#000000")
        prog_scene["vignette_color"].value = (
            (int(vcol[1:3], 16) / 255.0, int(vcol[3:5], 16) / 255.0, int(vcol[5:7], 16) / 255.0)
            if vcol.startswith("#") and len(vcol) == 7
            else (0.0, 0.0, 0.0)
        )
        prog_scene["smoke_enabled"].value = 1 if bool(sm.get("enabled", False)) else 0
        prog_scene["smoke_strength"].value = float(max(0.0, min(1.0, float(sm.get("strength", 0.35) or 0.35))))
        prog_scene["smoke_blur"].value = float(max(0.0, min(1.0, float(sm.get("blur", 0.55) or 0.55))))
        prog_scene["smoke_noise"].value = float(max(0.0, min(1.0, float(sm.get("noise", 0.55) or 0.55))))
        prog_scene["smoke_speed"].value = float(max(0.0, min(2.0, float(sm.get("speed", 0.35) or 0.35))))
        prog_scene["smoke_opacity"].value = float(max(0.0, min(1.0, float(sm.get("opacity", 0.55) or 0.55))))
        scol = str(sm.get("color", "#000000") or "#000000")
        prog_scene["smoke_color"].value = (
            (int(scol[1:3], 16) / 255.0, int(scol[3:5], 16) / 255.0, int(scol[5:7], 16) / 255.0)
            if scol.startswith("#") and len(scol) == 7
            else (0.0, 0.0, 0.0)
        )
        prog_scene["time_sec"].value = float(i) / float(max(1.0, float(fps)))
            
        # We already set logo_px above, so we don't overwrite it with just shake_state here
        # prog_scene["logo_px"].value = (float(shake_state_x), float(shake_state_y))
        vao_quad_scene.render(mode=moderngl.TRIANGLE_STRIP)

        scale = float(state.get("spectrum.scale", 1.0))
        rotation_deg = float(spectrum_container.get("rotation_deg", 0.0)) if isinstance(spectrum_container, dict) else 0.0
        
        spectrum_layers = _tpl_spectrum_layers

        style_preset = _tpl_style_preset
        react_gain = _tpl_react_gain
        
        # 1) Logarithmic Mapping to 64 Bins (vectorized)
        BINS = 64
        fft_log = fft_to_log_bins(fft, _fft_idx1, _fft_idx2, _fft_frac)
            
        rg = float(max(0.1, min(8.0, react_gain)))
        rb = 0.0
        bass_feat = float(feats.get("bass", 0.0))
        fft_s = np.clip(fft_log * rg * (1.0 + bass_feat * rb), 0.0, 2.5).astype(np.float32)
        
        c_pos = _get_anchor_coords(_tpl_anchor_val, _tpl_off_x, _tpl_off_y, w, h)
        cx = c_pos[0] + float(shake_state_x)
        cy = c_pos[1] + float(shake_state_y)
        
        for sl in spectrum_layers:
            curved = bool(sl.get("curved", True))
            mirrored = bool(sl.get("mirrored", True))
            bar_width = float(sl.get("barWidth", 4.0)) * sf
            thickness = float(sl.get("thickness", 150.0)) * sf
            gravity = str(sl.get("gravity", "bottom")).lower().strip()
            
            logo_visual_radius = logo_base_radius * logo_scale_base
            radius_offset = float(sl.get("radiusOffset", 0.0)) * sf
            base_radius = logo_visual_radius + (bar_width / 2.0)
            radius = base_radius + radius_offset
            
            color_cfg = sl.get("color", {})
            mode = color_cfg.get("mode", "solid")
            c = color_cfg.get("solidColor", "#ffffff")
            if isinstance(c, str) and c.startswith("#"):
                c = c.lstrip("#")
                c = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            
            op = float(sl.get("opacity", 1.0))
            try:
                spec_col = (
                    float(c[0]) / 255.0,
                    float(c[1]) / 255.0,
                    float(c[2]) / 255.0,
                    float(max(0.0, min(1.0, op))),
                )
            except Exception:
                spec_col = (1.0, 1.0, 1.0, float(max(0.0, min(1.0, op))))

            blend_mode = str(sl.get("blend_mode", "normal")).lower().strip()
            glow_strength = float(max(0.0, min(100.0, float(sl.get("glow", 0.0))))) / 100.0
            glow_softness = float(max(0.0, min(30.0, float(sl.get("blur", 0.0)))))

            # 2) 5-Tap Moving Average Smoothing & Mirroring (vectorized)
            render_fft = smooth_and_mirror(fft_s, mirrored)

            # 3) Generate Points (vectorized)
            n = BINS
            total_length = 0.0
            if curved:
                total_angle = np.pi * 2.0 if mirrored else np.pi
                total_length = radius * total_angle
            else:
                total_length = float(h * 0.8) if gravity in ("left", "right") else float(w * 0.8)
                
            start_angle = np.pi / 2.0
            if gravity == "top": start_angle = -np.pi / 2.0
            elif gravity == "left": start_angle = np.pi
            elif gravity == "right": start_angle = 0.0
            
            if curved:
                px_arr, py_arr, dx_arr, dy_arr = generate_points_curved(n, radius, mirrored, start_angle)
            else:
                px_arr, py_arr, dx_arr, dy_arr = generate_points_linear(n, total_length, gravity)
            base_total_length = total_length
            prog_lines["clip_enabled"].value = 0
            pass_specs: list[dict] = []
            if glow_strength > 0.0:
                pass_specs.append(
                    {
                        "is_glow": True,
                        "alpha": op * (0.14 + glow_strength * 0.22),
                        "bar_width": bar_width + ((glow_softness * 1.8) + (glow_strength * 18.0)) * sf,
                        "thickness": thickness + ((glow_softness * 2.2) + (glow_strength * 22.0)) * sf,
                        "fill_circle": False,
                    }
                )
                pass_specs.append(
                    {
                        "is_glow": True,
                        "alpha": op * (0.08 + glow_strength * 0.15),
                        "bar_width": bar_width + ((glow_softness * 3.0) + (glow_strength * 32.0)) * sf,
                        "thickness": thickness + ((glow_softness * 3.4) + (glow_strength * 34.0)) * sf,
                        "fill_circle": False,
                    }
                )
            pass_specs.append(
                {
                    "is_glow": False,
                    "alpha": op,
                    "bar_width": bar_width,
                    "thickness": thickness,
                    "fill_circle": bool(sl.get("fillCircle", False)),
                }
            )

            for pass_cfg in pass_specs:
                if pass_cfg["is_glow"]:
                    ctx.blend_func = moderngl.ADDITIVE_BLENDING
                elif blend_mode in ("screen", "add", "lighten"):
                    ctx.blend_func = moderngl.ADDITIVE_BLENDING
                else:
                    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

                pass_alpha = float(max(0.0, min(1.0, float(pass_cfg["alpha"]))))
                pass_bar_width = float(pass_cfg["bar_width"])
                pass_thickness = float(pass_cfg["thickness"])
                fill_circle_pass = bool(pass_cfg["fill_circle"])

                val_arr = (render_fft * pass_thickness).astype(np.float32)

                if mode == "gradient" and color_cfg.get("gradientColors") and len(color_cfg.get("gradientColors")) >= 2:
                    gcols = color_cfg.get("gradientColors")
                    c1_hex = gcols[0].lstrip("#")
                    c2_hex = gcols[1].lstrip("#")
                    c1 = np.array([int(c1_hex[i:i+2], 16)/255.0 for i in (0, 2, 4)], dtype=np.float32)
                    c2 = np.array([int(c2_hex[i:i+2], 16)/255.0 for i in (0, 2, 4)], dtype=np.float32)
                    t_arr = (np.arange(n, dtype=np.float32) / float(max(1, n))).reshape((n, 1))
                    rgb = c1 * (1.0 - t_arr) + c2 * t_arr
                    a = np.full((n, 1), pass_alpha, dtype=np.float32)
                    cols = np.concatenate([rgb, a], axis=1)
                else:
                    col = np.array([spec_col[0], spec_col[1], spec_col[2], pass_alpha], dtype=np.float32)
                    cols = np.tile(col[None, :], (n, 1))

                bw = float(max(1.0, (base_total_length / n) * (pass_bar_width / 10.0)))

                if style_preset in ("soft-waveform", "mountain", "liquid", "continuous-waveform"):
                    nn = n
                    val_arr2 = val_arr
                    cols2 = cols
                    px2 = px_arr
                    py2 = py_arr
                    dx2 = dx_arr
                    dy2 = dy_arr
                    if curved and mirrored:
                        px2 = np.concatenate([px_arr, px_arr[:1]])
                        py2 = np.concatenate([py_arr, py_arr[:1]])
                        dx2 = np.concatenate([dx_arr, dx_arr[:1]])
                        dy2 = np.concatenate([dy_arr, dy_arr[:1]])
                        val_arr2 = np.concatenate([val_arr, val_arr[:1]])
                        cols2 = np.concatenate([cols, cols[:1]], axis=0)
                        nn += 1

                    xs_o, ys_o, xs_i, ys_i = build_waveform_vertices(
                        px2, py2, dx2, dy2, val_arr2, cx, cy, w, h, style_preset, pass_bar_width,
                    )

                    if curved and fill_circle_pass:
                        cx_ndc = float(cx) / float(w) * 2.0 - 1.0
                        cy_ndc = float(cy) / float(h) * 2.0 - 1.0
                        pos_fill = np.empty((nn + 1, 2), dtype=np.float32)
                        pos_fill[0, 0] = cx_ndc
                        pos_fill[0, 1] = cy_ndc
                        pos_fill[1:, 0] = xs_o
                        pos_fill[1:, 1] = ys_o
                        cols_edge = cols2[:nn].copy()
                        cols_center = cols_edge[:1].copy()
                        cols_fill = np.concatenate([cols_center, cols_edge], axis=0)
                        verts_fill = np.column_stack([pos_fill, cols_fill]).astype(np.float32)
                        if verts_fill.nbytes > line_vbo.size:
                            line_vbo.orphan(size=verts_fill.nbytes)
                        line_vbo.write(verts_fill.tobytes())
                        vao_lines.render(mode=moderngl.TRIANGLE_FAN, vertices=int(nn + 1))

                    pos = np.empty((2 * nn, 2), dtype=np.float32)
                    pos[0::2, 0] = xs_o
                    pos[0::2, 1] = ys_o
                    pos[1::2, 0] = xs_i
                    pos[1::2, 1] = ys_i
                    colsi = np.repeat(cols2, 2, axis=0)
                    verts = np.column_stack([pos, colsi]).astype(np.float32)
                    if verts.nbytes > line_vbo.size:
                        line_vbo.orphan(size=verts.nbytes)
                    line_vbo.write(verts.tobytes())
                    vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(2 * nn))
                else:
                    pos = build_bar_vertices(
                        px_arr, py_arr, dx_arr, dy_arr, val_arr, cx, cy, w, h,
                        bw, style_preset, sf, logo_audio_env, particle_audio_env,
                    )
                    colsi = np.repeat(cols, 6, axis=0)

                    verts = np.column_stack([pos, colsi]).astype(np.float32)
                    if verts.nbytes > line_vbo.size:
                        line_vbo.orphan(size=verts.nbytes)
                    line_vbo.write(verts.tobytes())
                    vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(n * 6))

        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        spawn_rate = float(particles_cfg_raw.get("spawnRate", particles_cfg_raw.get("spawn_rate", particles_cfg.spawn_rate)))
        lifetime_sec = float(particles_cfg_raw.get("lifetimeSec", particles_cfg_raw.get("lifetime_sec", 1.6)))
        speed_base = float(particles_cfg_raw.get("speed", 120.0))
        prb = float(particles_cfg_raw.get("reactivity", 1.5))
        pt_size = float(particles_cfg_raw.get("size", 2.0))
        pt_color = tuple(_as_rgb(particles_cfg_raw.get("color", "#ffffff")))
        pt_count = int(particles_cfg_raw.get("maxCount", particles_cfg_raw.get("count", 150)))
        pt_opacity = float(particles_cfg_raw.get("opacity", particles_cfg.opacity))

        bass = float(feats.get("bass", 0.0))
        prb = float(max(0.1, min(0.5, prb)))
        
        p_bass_fast = p_bass_fast * (1.0 - kick_fast_a) + bass * kick_fast_a
        p_bass_slow = p_bass_slow * (1.0 - kick_slow_a) + bass * kick_slow_a
        raw_kick = float(max(0.0, p_bass_fast - p_bass_slow))
        kick0 = float(max(0.0, min(1.0, raw_kick * 4.0)))
        p_kick_env = float(max(kick0, p_kick_env * kick_decay))
        kick_pow = float(max(0.0, min(1.0, p_kick_env))) ** 2
        bg_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.6))))
        bg_audio_env = _smooth_env(bg_audio_env, bg_audio_raw, bg_smoothing)
        logo_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.8))))
        logo_audio_env = _smooth_env(logo_audio_env, logo_audio_raw, logo_smoothing)
        if bg_motion_mode in ("vibrate", "both"):
            bg_shake_target = float(max(0.0, bg_react_bass) * bg_audio_env * 18.0 * sf * bg_motion_vibrate_strength)
            bg_jx = (time.time() * 0.81 + i * 0.013) % 1.0
            bg_jy = (time.time() * 0.83 + i * 0.017) % 1.0
            bg_shake_state_x = bg_shake_state_x * bg_smoothing + ((bg_jx * 2.0 - 1.0) * bg_shake_target) * (1.0 - bg_smoothing)
            bg_shake_state_y = bg_shake_state_y * bg_smoothing + ((bg_jy * 2.0 - 1.0) * bg_shake_target) * (1.0 - bg_smoothing)
        else:
            bg_shake_state_x = 0.0
            bg_shake_state_y = 0.0
        prog_scene["bg_brightness"].value = float(max(0.0, min(3.0, bg_brightness * (1.0 + bg_audio_env * bg_react_bass))))
        if tex_logo is not None and logo_enabled:
            base_radius = logo_base_radius
            s_logo = logo_scale_base * (1.0 + logo_audio_env * logo_react_bass)
            s_logo = max(0.05, min(4.0, s_logo))
            final_logo_size = base_radius * 2.0 * s_logo
            prog_logo["logo_size_px"].value = (final_logo_size, final_logo_size)
        ps_smoothing = float(max(0.0, min(0.99, particles_cfg_raw.get("smoothing", 0.65))))
        particle_audio_raw = float(max(0.0, min(1.0, max(kick_pow, bass))))
        particle_audio_env = _smooth_env(particle_audio_env, particle_audio_raw, ps_smoothing)
        
        spawn_mode = str(particles_cfg_raw.get("spawnMode", "always") or "always")
        spawn_trigger = str(particles_cfg_raw.get("spawnTrigger", "both") or "both")
        spawn_threshold = float(particles_cfg_raw.get("spawnThreshold", 0.15) or 0.15)
        spawn_threshold = float(max(0.0, min(1.0, spawn_threshold)))
        if spawn_trigger == "kick":
            trig_raw = kick_pow
        elif spawn_trigger == "bass":
            trig_raw = bass
        else:
            trig_raw = float(max(kick_pow, bass))
        trig_raw = float(max(0.0, min(1.0, trig_raw)))
        p_trigger_env = _smooth_env(p_trigger_env, trig_raw, ps_smoothing)

        if spawn_mode == "reactiveOnly" and p_trigger_env < spawn_threshold:
            spawn_rate = 0.0
        else:
            spawn_rate = spawn_rate * float(0.2 + particle_audio_env * (1.1 + prb * 2.8))
        spawn_rate = float(max(0.0, min(20000.0, spawn_rate)))

        spawn_radius = float(max(0.0, logo_visual_radius + max(2.0 * sf, pt_size * sf)))
        speed_boost = float(18.0 + particle_audio_env * (50.0 + prb * 130.0))
        speed2 = speed_base * speed_boost * sf
        speed2 = float(max(0.0, min(2500.0, speed2)))
        
        particles.update_cfg(
            ParticleConfig(
                enabled=bool(particles_cfg_raw.get("enabled", False)),
                max_count=pt_count,
                spawn_rate=spawn_rate,
                lifetime_sec=lifetime_sec,
                spawn_radius=spawn_radius,
                size=pt_size * sf,
                opacity=pt_opacity,
                color=pt_color,
                speed=speed2,
                size_jitter=float(particles_cfg_raw.get("sizeJitter", 0.0) or 0.0),
                drift=float(particles_cfg_raw.get("drift", 0.0) or 0.0),
                swirl=float(particles_cfg_raw.get("swirl", 0.0) or 0.0),
                spawn_area=str(particles_cfg_raw.get("spawnArea", "centerRing") or "centerRing"),
            )
        )
        particles.update(dt, feats)
        # Draw particles over spectrum
        if particles_cfg_raw.get("enabled", False):
            pos = particles._pos if hasattr(particles, "_pos") else np.zeros((0, 2), dtype=np.float32)
            if pos.shape[0]:
                p = pos.astype(np.float32)
                xs2 = p[:, 0] / float(w) * 2.0 - 1.0
                ys2 = p[:, 1] / float(h) * 2.0 - 1.0
                sz = particles._size.astype(np.float32) if hasattr(particles, "_size") else np.ones((p.shape[0],), dtype=np.float32)
                pts = np.column_stack([xs2, ys2, sz]).astype(np.float32)
                if pts.nbytes > pt_vbo.size:
                    pt_vbo.orphan(size=pts.nbytes)
                pt_vbo.write(pts.tobytes())
                alpha = float(max(0.0, min(1.0, particles_cfg_raw.get("opacity", particles_cfg.opacity))))
                c = _as_rgb(particles_cfg_raw.get("color", particles_cfg.color))
                try:
                    react_strength = float(particles_cfg_raw.get("reactStrength", 0.65) or 0.65)
                    react_strength = float(max(0.0, min(1.0, react_strength)))
                    rc = _as_rgb(particles_cfg_raw.get("reactColor", particles_cfg_raw.get("color", "#ffffff")))
                    mix = float(max(0.0, min(1.0, p_trigger_env))) * react_strength
                    cr = float(c[0]) * (1.0 - mix) + float(rc[0]) * mix
                    cg = float(c[1]) * (1.0 - mix) + float(rc[1]) * mix
                    cb = float(c[2]) * (1.0 - mix) + float(rc[2]) * mix
                    colp = (cr / 255.0, cg / 255.0, cb / 255.0, alpha)
                except Exception:
                    colp = (1.0, 1.0, 1.0, alpha)
                variant = str(particles_cfg_raw.get("variant", "classic") or "classic")
                style = str(particles_cfg_raw.get("style", "dot") or "dot")
                if variant == "bokeh":
                    style = "bokeh"
                elif variant == "soap":
                    style = "ring"
                elif variant == "dust":
                    style = "glow"
                prog_points["pt_size"].value = float(max(1.0, float(particles_cfg_raw.get("size", particles_cfg.size)) * (2.0 if style == "bokeh" else 1.5) * sf))
                prog_points["pt_col"].value = colp
                if style == "glow":
                    prog_points["pt_style"].value = 1
                elif style == "ring":
                    prog_points["pt_style"].value = 2
                elif style == "spark":
                    prog_points["pt_style"].value = 3
                elif style == "bokeh":
                    prog_points["pt_style"].value = 4
                else:
                    prog_points["pt_style"].value = 0
                vao_pts.render(mode=moderngl.POINTS, vertices=int(pts.shape[0]))

        # Draw logo ON TOP of spectrum and particles
        if tex_logo is not None and logo_enabled:
            tex_logo.use(location=1)
            vao_quad_logo.render(mode=moderngl.TRIANGLE_STRIP)

        fbo_out.use()
        ctx.clear(0.0, 0.0, 0.0, 1.0)
        tex_scene.use(location=0)
        rgb_opacity = float(state.get("effects.rgb_split.opacity", rgb_cfg.opacity))
        bloom_strength = float(state.get("effects.bloom.strength", bloom_cfg.strength))
        onset = float(feats.get("onset", 0.0))
        rgb_opacity = rgb_opacity * (1.0 + onset * 0.9)
        bloom_strength = bloom_strength * (1.0 + bass * 0.9)
        if not rgb_cfg.enabled:
            rgb_opacity = 0.0
        if not bloom_cfg.enabled:
            bloom_strength = 0.0
        prog_post["rgb_opacity"].value = float(max(0.0, min(1.0, rgb_opacity)))
        prog_post["rgb_r"].value = (float(rgb_cfg.red_offset[0]), float(rgb_cfg.red_offset[1]))
        prog_post["rgb_g"].value = (float(rgb_cfg.green_offset[0]), float(rgb_cfg.green_offset[1]))
        prog_post["rgb_b"].value = (float(rgb_cfg.blue_offset[0]), float(rgb_cfg.blue_offset[1]))
        prog_post["bloom_strength"].value = float(max(0.0, bloom_strength)) * float(max(0.0, min(1.0, bloom_cfg.opacity)))
        prog_post["bloom_threshold"].value = float(max(0.0, min(1.0, bloom_cfg.threshold)))
        vao_quad_post.render(mode=moderngl.TRIANGLE_STRIP)

        _draw_text_overlays(
            ctx,
            prog_text,
            vao_quad_text,
            text_overlays,
            float(i) / float(max(1.0, float(fps))),
            w,
            h,
            sf,
            text_cache,
        )

        raw = fbo_out.read(components=4, alignment=1)
        if enc.stdin is None:
            raise RuntimeError("FFmpeg stdin is not available")
        try:
            enc.stdin.write(raw)
        except (BrokenPipeError, OSError) as e:
            if hasattr(enc, "_err_file"):
                enc._err_file.seek(0)
                err_txt = enc._err_file.read()
            else:
                err_txt = ""
            raise RuntimeError(f"FFmpeg pipe closed unexpectedly: {err_txt} (OS Error: {e})")

        if i == 0 or (i + 1) % 10 == 0 or i + 1 == total_frames:
            _send(
                {
                    "status": "running",
                    "message": f"Rendering {i + 1}/{total_frames}",
                    "progress": float((i + 1) / max(1, total_frames)),
                    "frame": i + 1,
                    "totalFrames": total_frames,
                }
            )

    _send({"status": "running", "message": "Finalizing MP4...", "progress": 0.99})
    if enc.stdin is not None:
        try:
            enc.stdin.close()
        except Exception:
            pass
    code = enc.wait()
    if code != 0:
        if hasattr(enc, "_err_file"):
            enc._err_file.seek(0)
            err_txt = enc._err_file.read()
        else:
            err_txt = ""
        raise RuntimeError(err_txt.strip() or f"FFmpeg failed (exit code {code})")
        
    if hasattr(enc, "_err_file"):
        enc._err_file.close()

    _send({"status": "done", "message": "Exported MP4", "progress": 1.0, "outputPath": out_path})
    try:
        glfw.terminate()
    except Exception:
        pass
    for tx in text_cache.get("tex", []):
        try:
            if tx is not None:
                tx.release()
        except Exception:
            pass
    return 0


def render_preview_png(opts: GpuOptions, out_png_path: str, preview_frame: int = 150) -> str:
    fps = int(max(1, min(60, int(opts.fps))))
    if fps <= 0:
        fps = 30

    template = _load_template(opts)

    w = int(max(64, min(8192, int(opts.width) if int(opts.width) > 0 else 1920)))
    h = int(max(64, min(8192, int(opts.height) if int(opts.height) > 0 else 1080)))

    base_h = float(template.get("renderBaseHeight", 450.0))
    base_h = float(max(1.0, min(4000.0, base_h)))
    sf = float(h) / base_h

    _send({"status": "running", "message": "Initializing GPU preview...", "progress": 0.0})
    _init_glfw_hidden(w, h)
    ctx = _make_ctx()

    bg_rgba = _load_image_rgba(opts.background_path, (w, h))
    logo_raw0 = template.get("logoSettings") if isinstance(template.get("logoSettings"), dict) else {}
    logo_enabled0 = bool(logo_raw0.get("enabled", True))
    has_logo = bool(logo_enabled0 and opts.logo_path and Path(opts.logo_path).exists())
    logo_rgba = _load_image_rgba(opts.logo_path) if has_logo else None

    tex_bg = ctx.texture((w, h), 4, bg_rgba.tobytes())
    tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)

    tex_logo = None
    logo_size_px = (0.0, 0.0)
    if has_logo and logo_rgba is not None:
        lh, lw = int(logo_rgba.shape[0]), int(logo_rgba.shape[1])
        max_w = int(w * 0.22)
        scale = min(1.0, max_w / max(1, lw))
        nlw = max(1, int(round(lw * scale)))
        nlh = max(1, int(round(lh * scale)))
        logo_rgba2 = np.array(Image.fromarray(logo_rgba).resize((nlw, nlh), Image.Resampling.LANCZOS), dtype=np.uint8)
        tex_logo = ctx.texture((nlw, nlh), 4, logo_rgba2.tobytes())
        tex_logo.filter = (moderngl.LINEAR, moderngl.LINEAR)
        logo_size_px = (float(nlw), float(nlh))

    prog_scene, prog_logo, prog_post, prog_lines, prog_points, prog_text = _compile(ctx)
    vao_quad_scene = _quad_vao(ctx, prog_scene)
    vao_quad_logo = _quad_vao(ctx, prog_logo)
    vao_quad_text = _quad_vao(ctx, prog_text)
    vao_quad_post = _quad_vao(ctx, prog_post)
    text_overlays = template.get("textOverlays") if isinstance(template.get("textOverlays"), list) else []
    text_cache = {"tex": [None] * 5, "key": [None] * 5, "wh": [(0, 0)] * 5}

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

    # In the new format, the root template IS the spectrum container
    spectrum_container = template
    point_count = 1024 # Fixed to 1024 for high-res FFT
    
    # We no longer have spec_style or spec_tex for background scale/offset in the spectrum layer.
    bg_scale = 1.0
    bg_offset = (0.0, 0.0)

    has_audio = bool(opts.mp3_path and Path(opts.mp3_path).exists())
    analyzer = AudioAnalyzer(opts.mp3_path, fps=fps, point_count=point_count) if has_audio else None
    total_frames = int(analyzer.info.frames) if analyzer is not None else int(max(1, int(preview_frame) + 1))
    tgt = int(max(0, min(total_frames - 1, int(preview_frame))))

    particles_cfg_raw = template.get("particlesSettings", {}) if isinstance(template.get("particlesSettings"), dict) else {}
    if not particles_cfg_raw and isinstance(template.get("particles"), dict):
        particles_cfg_raw = template.get("particles")
    particles_cfg = ParticleConfig(
        enabled=bool(particles_cfg_raw.get("enabled", False)),
        max_count=int(particles_cfg_raw.get("maxCount", particles_cfg_raw.get("max_count", particles_cfg_raw.get("count", 400)))),
        spawn_rate=float(particles_cfg_raw.get("spawnRate", particles_cfg_raw.get("spawn_rate", 40.0))),
        lifetime_sec=float(particles_cfg_raw.get("lifetimeSec", particles_cfg_raw.get("lifetime_sec", 1.6))),
        spawn_radius=0.0,
        size=float(particles_cfg_raw.get("size", 2.0)) * sf,
        opacity=float(particles_cfg_raw.get("opacity", 0.35)),
        color=tuple(_as_rgb(particles_cfg_raw.get("color", "#ffffff"))),
        speed=float(particles_cfg_raw.get("speed", 120.0)) * sf,
    )
    particles = ParticleSystem(particles_cfg, width=w, height=h, rng_seed=1)

    effects_raw = template.get("effects") if isinstance(template.get("effects"), dict) else {}
    bloom_raw = effects_raw.get("bloom") if isinstance(effects_raw.get("bloom"), dict) else {}
    rgb_raw = effects_raw.get("rgb_split") if isinstance(effects_raw.get("rgb_split"), dict) else {}
    shake_raw = effects_raw.get("camera_shake") if isinstance(effects_raw.get("camera_shake"), dict) else {}
    bloom_cfg = BloomConfig(
        enabled=bool(bloom_raw.get("enabled", False)),
        strength=float(bloom_raw.get("strength", 1.0)),
        blur_radius=int(bloom_raw.get("blur_radius", 11)),
        threshold=float(bloom_raw.get("threshold", 0.75)),
        opacity=float(bloom_raw.get("opacity", 0.9)),
    )
    rgb_cfg = RgbSplitConfig(
        enabled=bool(rgb_raw.get("enabled", False)),
        red_offset=tuple(rgb_raw.get("red_offset", (2, 0))),
        green_offset=tuple(rgb_raw.get("green_offset", (0, 0))),
        blue_offset=tuple(rgb_raw.get("blue_offset", (-2, 0))),
        opacity=float(rgb_raw.get("opacity", 0.6)),
    )
    shake_enabled = bool(shake_raw.get("enabled", False))
    shake_intensity = float(shake_raw.get("intensity", 8.0))
    shake_smoothing = float(shake_raw.get("smoothing", 0.85))
    autos = template.get("automations") if isinstance(template.get("automations"), list) else []

    bg_settings_raw = template.get("backgroundSettings", {}) if isinstance(template.get("backgroundSettings"), dict) else {}
    bg_brightness = float(bg_settings_raw.get("brightness", 1.0))
    bg_brightness = float(max(0.0, min(3.0, bg_brightness)))
    bg_react_bass = float(bg_settings_raw.get("reactivity", 0.0))
    bg_react_bass = float(max(0.0, min(2.0, bg_react_bass)))
    bg_smoothing = float(max(0.0, min(0.99, bg_settings_raw.get("smoothing", 0.8))))
    bg_motion_mode = str(bg_settings_raw.get("motionMode", "none") or "none")
    if bg_motion_mode not in ("none", "zoom", "vibrate", "both"):
        bg_motion_mode = "none"
    bg_motion_zoom_strength = float(bg_settings_raw.get("motionZoomStrength", 1.0) or 1.0)
    bg_motion_zoom_strength = float(max(0.0, min(2.0, bg_motion_zoom_strength)))
    bg_motion_vibrate_strength = float(bg_settings_raw.get("motionVibrateStrength", 1.0) or 1.0)
    bg_motion_vibrate_strength = float(max(0.0, min(2.0, bg_motion_vibrate_strength)))

    logo_raw = template.get("logoSettings", {}) if isinstance(template.get("logoSettings"), dict) else {}
    logo_enabled = bool(logo_raw.get("enabled", True))
    logo_circle_mask = bool(logo_raw.get("circleMask", True))
    logo_opacity = float(logo_raw.get("opacity", 1.0))
    logo_opacity = float(max(0.0, min(1.0, logo_opacity)))
    logo_scale_base = float(logo_raw.get("scale", 1.0))
    logo_scale_base = float(max(0.1, min(2.5, logo_scale_base)))
    logo_react_bass = float(logo_raw.get("reactivity", 0.0))
    logo_react_bass = float(max(0.0, min(2.0, logo_react_bass)))
    logo_smoothing = float(max(0.0, min(0.99, logo_raw.get("smoothing", 0.75))))

    try:
        prog_scene["tex_bg"].value = 0
        tex_bg.use(location=0)
        if tex_logo is not None and logo_enabled:
            prog_logo["tex_logo"].value = 1
            tex_logo.use(location=1)
        if "out_size" in prog_scene:
            prog_scene["out_size"].value = (float(w), float(h))
        if "bg_tex_size" in prog_scene:
            prog_scene["bg_tex_size"].value = (float(w), float(h))
        if "bg_fit_mode" in prog_scene:
            prog_scene["bg_fit_mode"].value = 0
        prog_scene["bg_offset"].value = bg_offset
        prog_scene["bg_scale"].value = (bg_scale, bg_scale)
        prog_scene["bg_brightness"].value = float(bg_brightness)
        
        if tex_logo is not None and logo_enabled:
            if "out_size" in prog_logo:
                prog_logo["out_size"].value = (float(w), float(h))
            prog_logo["logo_px"].value = (0.0, 0.0)
            base_logo_size_px = (float(logo_size_px[0]), float(logo_size_px[1]))
            prog_logo["logo_size_px"].value = base_logo_size_px
            prog_logo["logo_opacity"].value = float(logo_opacity)
            prog_logo["logo_circle_mask"].value = 1 if logo_circle_mask else 0
            if "logo_rot_rad" in prog_logo:
                prog_logo["logo_rot_rad"].value = 0.0

        prog_post["tex_in"].value = 0
        prog_post["out_size"].value = (float(w), float(h))
    except Exception as e:
        import traceback
        _send({"status": "failed", "message": f"Shader setup failed: {e}\n{traceback.format_exc()}", "progress": 0.0})
        raise e

    dt = 1.0 / max(1.0, float(fps))
    shake_state_x = 0.0
    shake_state_y = 0.0
    bg_shake_state_x = 0.0
    bg_shake_state_y = 0.0
    p_bass_fast = 0.0
    p_bass_slow = 0.0
    p_kick_env = 0.0
    bg_audio_env = 0.0
    logo_audio_env = 0.0
    particle_audio_env = 0.0
    p_trigger_env = 0.0
    kick_fast_a = 1.0 - float(np.exp(-dt / 0.06))
    kick_slow_a = 1.0 - float(np.exp(-dt / 0.35))
    kick_decay = float(np.exp(-dt / 0.18))

    def synth_fft(i: int) -> np.ndarray:
        n = int(point_count)
        t = float(i) / float(max(1, fps))
        a = 0.35 + 0.25 * np.sin(t * 2.2) + 0.15 * np.sin(t * 6.1)
        phase = t * 0.7
        x = np.linspace(0.0, 1.0, num=n, dtype=np.float32)
        y = (a * (0.5 + 0.5 * np.sin((x * 12.0 + phase) * np.pi * 2.0))).astype(np.float32)
        return np.clip(y, 0.0, 1.0)

    def synth_feats(i: int) -> dict:
        t = float(i) / float(max(1, fps))
        beat = 1.0 if int(t * 2.0) % 2 == 0 and (t * 2.0 - int(t * 2.0)) < 0.05 else 0.0
        onset = max(0.0, float(np.sin(t * 3.1)) * 0.5 + 0.5)
        bass = max(0.0, float(np.sin(t * 1.9)) * 0.5 + 0.5)
        return {"bass": bass, "mid": 0.5, "treble": 0.5, "energy": 0.6, "onset": onset, "beat": beat}

    for i in range(tgt + 1):
        fft = analyzer.fft_for_frame(i) if analyzer is not None else synth_fft(i)
        feats = analyzer.features_for_frame(i) if analyzer is not None else synth_feats(i)
        base_state = {
            "camera_shake.intensity": shake_intensity,
            "spectrum.scale": 1.0,
            "particles.spawn_rate": float(particles_cfg.spawn_rate),
            "effects.bloom.strength": float(bloom_cfg.strength),
            "effects.rgb_split.opacity": float(rgb_cfg.opacity),
        }
        state = apply_automations(base_state, feats, autos)
        bass = float(feats.get("bass", 0.0))
        if tex_logo is not None and logo_enabled:
            base_radius = (float(logo_raw.get("size", 192.0)) * 0.5) * sf
            s_logo = float(logo_scale_base) * (1.0 + bass * float(logo_react_bass))
            s_logo = float(max(0.05, min(4.0, s_logo)))
            final_logo_size = base_radius * 2.0 * s_logo
            prog_logo["logo_size_px"].value = (final_logo_size, final_logo_size)
            
            logo_anchor = template.get("position", {}).get("anchor", "center")
            logo_off_x = float(template.get("position", {}).get("x", 0.0)) * sf
            logo_off_y = float(template.get("position", {}).get("y", 0.0)) * sf
            
            l_pos = _get_anchor_coords(logo_anchor, logo_off_x, logo_off_y, w, h)
            prog_logo["logo_px"].value = (l_pos[0] - float(w)*0.5 + float(shake_state_x), l_pos[1] - float(h)*0.5 + float(shake_state_y))

        # Ensure particles use new schema properties
        spawn_rate = float(particles_cfg_raw.get("spawnRate", particles_cfg_raw.get("spawn_rate", 40.0)))
        lifetime_sec = float(particles_cfg_raw.get("lifetimeSec", particles_cfg_raw.get("lifetime_sec", 1.6)))
        speed_base = float(particles_cfg_raw.get("speed", 120.0))
        prb = float(particles_cfg_raw.get("reactivity", 1.5))
        pt_size = float(particles_cfg_raw.get("size", 2.0))
        pt_color = tuple(_as_rgb(particles_cfg_raw.get("color", "#ffffff")))
        pt_count = int(particles_cfg_raw.get("maxCount", particles_cfg_raw.get("count", 150)))
        pt_opacity = float(particles_cfg_raw.get("opacity", particles_cfg.opacity))

        bass = float(feats.get("bass", 0.0))
        prb = float(max(0.1, min(0.5, prb)))
        
        p_bass_fast = p_bass_fast * (1.0 - kick_fast_a) + bass * kick_fast_a
        p_bass_slow = p_bass_slow * (1.0 - kick_slow_a) + bass * kick_slow_a
        raw_kick = float(max(0.0, p_bass_fast - p_bass_slow))
        kick0 = float(max(0.0, min(1.0, raw_kick * 4.0)))
        p_kick_env = float(max(kick0, p_kick_env * kick_decay))
        kick_pow = float(max(0.0, min(1.0, p_kick_env))) ** 2
        bg_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.6))))
        bg_audio_env = _smooth_env(bg_audio_env, bg_audio_raw, bg_smoothing)
        logo_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.8))))
        logo_audio_env = _smooth_env(logo_audio_env, logo_audio_raw, logo_smoothing)
        if bg_motion_mode in ("vibrate", "both"):
            bg_shake_target = float(max(0.0, bg_react_bass) * bg_audio_env * 18.0 * sf * bg_motion_vibrate_strength)
            bg_jx = (time.time() * 0.81 + i * 0.013) % 1.0
            bg_jy = (time.time() * 0.83 + i * 0.017) % 1.0
            bg_shake_state_x = bg_shake_state_x * bg_smoothing + ((bg_jx * 2.0 - 1.0) * bg_shake_target) * (1.0 - bg_smoothing)
            bg_shake_state_y = bg_shake_state_y * bg_smoothing + ((bg_jy * 2.0 - 1.0) * bg_shake_target) * (1.0 - bg_smoothing)
        else:
            bg_shake_state_x = 0.0
            bg_shake_state_y = 0.0
        prog_scene["bg_brightness"].value = float(max(0.0, min(3.0, bg_brightness * (1.0 + bg_audio_env * bg_react_bass))))
        if tex_logo is not None and logo_enabled:
            base_radius = (float(logo_raw.get("size", 192.0)) * 0.5) * sf
            s_logo = float(logo_scale_base) * (1.0 + logo_audio_env * float(logo_react_bass))
            s_logo = float(max(0.05, min(4.0, s_logo)))
            final_logo_size = base_radius * 2.0 * s_logo
            prog_logo["logo_size_px"].value = (final_logo_size, final_logo_size)
        ps_smoothing = float(max(0.0, min(0.99, particles_cfg_raw.get("smoothing", 0.65))))
        particle_audio_raw = float(max(0.0, min(1.0, max(kick_pow, bass))))
        particle_audio_env = _smooth_env(particle_audio_env, particle_audio_raw, ps_smoothing)
        
        spawn_mode = str(particles_cfg_raw.get("spawnMode", "always") or "always")
        spawn_trigger = str(particles_cfg_raw.get("spawnTrigger", "both") or "both")
        spawn_threshold = float(particles_cfg_raw.get("spawnThreshold", 0.15) or 0.15)
        spawn_threshold = float(max(0.0, min(1.0, spawn_threshold)))
        if spawn_trigger == "kick":
            trig_raw = kick_pow
        elif spawn_trigger == "bass":
            trig_raw = bass
        else:
            trig_raw = float(max(kick_pow, bass))
        trig_raw = float(max(0.0, min(1.0, trig_raw)))
        p_trigger_env = _smooth_env(p_trigger_env, trig_raw, ps_smoothing)

        if spawn_mode == "reactiveOnly" and p_trigger_env < spawn_threshold:
            spawn_rate = 0.0
        else:
            spawn_rate = spawn_rate * float(0.2 + particle_audio_env * (1.1 + prb * 2.8))
        spawn_rate = float(max(0.0, min(20000.0, spawn_rate)))

        logo_visual_radius = (float(logo_raw.get("size", 192.0)) * 0.5) * sf * float(logo_scale_base)
        spawn_radius = float(max(0.0, logo_visual_radius + max(2.0 * sf, pt_size * sf)))
        speed_boost = float(18.0 + particle_audio_env * (50.0 + prb * 130.0))
        speed2 = speed_base * speed_boost * sf
        speed2 = float(max(0.0, min(2500.0, speed2)))
        
        particles.update_cfg(
            ParticleConfig(
                enabled=bool(particles_cfg_raw.get("enabled", False)),
                max_count=pt_count,
                spawn_rate=spawn_rate,
                lifetime_sec=lifetime_sec,
                spawn_radius=spawn_radius,
                size=pt_size * sf,
                opacity=pt_opacity,
                color=pt_color,
                speed=speed2,
                size_jitter=float(particles_cfg_raw.get("sizeJitter", 0.0) or 0.0),
                drift=float(particles_cfg_raw.get("drift", 0.0) or 0.0),
                swirl=float(particles_cfg_raw.get("swirl", 0.0) or 0.0),
                spawn_area=str(particles_cfg_raw.get("spawnArea", "centerRing") or "centerRing"),
            )
        )
        particles.update(dt, feats)

        if i != tgt:
            continue

        if shake_enabled:
            target = float(state.get("camera_shake.intensity", shake_intensity)) * (
                0.35 + float(feats.get("bass", 0.0)) * 1.2 + float(feats.get("beat", 0.0)) * 1.5
            )
            jitter_x = (time.time() * 0.9 + i * 0.013) % 1.0
            jitter_y = (time.time() * 0.9 + i * 0.017) % 1.0
            tx = (jitter_x * 2.0 - 1.0) * target
            ty = (jitter_y * 2.0 - 1.0) * target
            s = max(0.0, min(0.99, shake_smoothing))
            shake_state_x = shake_state_x * s + tx * (1.0 - s)
            shake_state_y = shake_state_y * s + ty * (1.0 - s)
        else:
            shake_state_x = 0.0
            shake_state_y = 0.0

        fbo_scene.use()
        ctx.viewport = (0, 0, w, h)
        ctx.clear(0.0, 0.0, 0.0, 1.0)
        
        # Draw background
        if bg_motion_mode in ("zoom", "both"):
            bg_scale_live = float(1.0 + bg_audio_env * bg_react_bass * 0.015 * bg_motion_zoom_strength)
        else:
            bg_scale_live = 1.0
        prog_scene["bg_scale"].value = (bg_scale_live, bg_scale_live)
        if bg_motion_mode in ("vibrate", "both"):
            prog_scene["bg_offset"].value = (
                float(bg_shake_state_x / max(1.0, float(w))),
                float(bg_shake_state_y / max(1.0, float(h))),
            )
        else:
            prog_scene["bg_offset"].value = (0.0, 0.0)
        tex_bg.use(location=0)
        fx = template.get("effects") if isinstance(template.get("effects"), dict) else {}
        vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        prog_scene["vignette_enabled"].value = 1 if bool(vig.get("enabled", False)) else 0
        prog_scene["vignette_strength"].value = float(max(0.0, min(1.0, float(vig.get("strength", 0.35) or 0.35))))
        prog_scene["vignette_feather"].value = float(max(0.0, min(1.0, float(vig.get("feather", 0.65) or 0.65))))
        prog_scene["vignette_opacity"].value = float(max(0.0, min(1.0, float(vig.get("opacity", 0.65) or 0.65))))
        vcol = str(vig.get("color", "#000000") or "#000000")
        prog_scene["vignette_color"].value = (
            (int(vcol[1:3], 16) / 255.0, int(vcol[3:5], 16) / 255.0, int(vcol[5:7], 16) / 255.0)
            if vcol.startswith("#") and len(vcol) == 7
            else (0.0, 0.0, 0.0)
        )
        prog_scene["smoke_enabled"].value = 1 if bool(sm.get("enabled", False)) else 0
        prog_scene["smoke_strength"].value = float(max(0.0, min(1.0, float(sm.get("strength", 0.35) or 0.35))))
        prog_scene["smoke_blur"].value = float(max(0.0, min(1.0, float(sm.get("blur", 0.55) or 0.55))))
        prog_scene["smoke_noise"].value = float(max(0.0, min(1.0, float(sm.get("noise", 0.55) or 0.55))))
        prog_scene["smoke_speed"].value = float(max(0.0, min(2.0, float(sm.get("speed", 0.35) or 0.35))))
        prog_scene["smoke_opacity"].value = float(max(0.0, min(1.0, float(sm.get("opacity", 0.55) or 0.55))))
        scol = str(sm.get("color", "#000000") or "#000000")
        prog_scene["smoke_color"].value = (
            (int(scol[1:3], 16) / 255.0, int(scol[3:5], 16) / 255.0, int(scol[5:7], 16) / 255.0)
            if scol.startswith("#") and len(scol) == 7
            else (0.0, 0.0, 0.0)
        )
        prog_scene["time_sec"].value = float(i) / float(max(1.0, float(fps)))
        vao_quad_scene.render(mode=moderngl.TRIANGLE_STRIP)

        scale = float(state.get("spectrum.scale", 1.0))
        cx = float(w) * 0.5 + float(shake_state_x)
        cy = float(h) * 0.5 + float(shake_state_y)

        raw_layers = spectrum_container.get("layers", [])
        spectrum_layers: list[dict] = [x for x in raw_layers if isinstance(x, dict)]

        style_preset = str(template.get("style", "classic-vertical")).lower().strip()
        react_gain = float(template.get("audioSettings", {}).get("sensitivity", 1.0))
        
        # 1) Logarithmic Mapping to 64 Bins
        BINS = 64
        fft_log = np.zeros(BINS, dtype=np.float32)
        sample_rate = 44100.0
        nyquist = sample_rate / 2.0
        min_freq = 20.0
        max_freq = 12000.0
        min_log = np.log10(min_freq)
        max_log = np.log10(max_freq)
        
        n0 = int(min(point_count, fft.shape[0]))
        fft_size_half = float(point_count)
        
        for b_idx in range(BINS):
            log_freq = min_log + (b_idx / float(BINS)) * (max_log - min_log)
            freq = 10.0 ** log_freq
            linear_index = (freq / nyquist) * fft_size_half
            idx1 = int(np.floor(linear_index))
            idx2 = int(min(np.ceil(linear_index), fft_size_half - 1))
            frac = linear_index - float(idx1)
            
            val1 = float(fft[idx1]) if idx1 < n0 else 0.0
            val2 = float(fft[idx2]) if idx2 < n0 else 0.0
            raw_val = val1 * (1.0 - frac) + val2 * frac
            
            freq_boost = 1.0 + ((b_idx / float(BINS)) ** 2) * 2.0
            val = raw_val * freq_boost
            fft_log[b_idx] = float(max(0.01, min(1.0, val)))
            
        rg = float(max(0.1, min(8.0, react_gain)))
        rb = 0.0
        bass_feat = float(feats.get("bass", 0.0))
        fft_s = np.clip(fft_log * rg * (1.0 + bass_feat * rb), 0.0, 2.5).astype(np.float32)
        
        anchor_val = template.get("position", {}).get("anchor", "center") if isinstance(template.get("position"), dict) else "center"
        off_x = float(template.get("position", {}).get("x", 0.0)) * sf if isinstance(template.get("position"), dict) else 0.0
        off_y = float(template.get("position", {}).get("y", 0.0)) * sf if isinstance(template.get("position"), dict) else 0.0
        
        c_pos = _get_anchor_coords(anchor_val, off_x, off_y, w, h)
        cx = c_pos[0] + float(shake_state_x)
        cy = c_pos[1] + float(shake_state_y)
        
        for sl in spectrum_layers:
            curved = bool(sl.get("curved", True))
            mirrored = bool(sl.get("mirrored", True))
            bar_width = float(sl.get("barWidth", 4.0)) * sf
            thickness = float(sl.get("thickness", 150.0)) * sf
            gravity = str(sl.get("gravity", "bottom")).lower().strip()
            
            logo_visual_radius = (float(logo_raw.get("size", 192.0)) * 0.5) * sf * float(logo_scale_base)
            radius_offset = float(sl.get("radiusOffset", 0.0)) * sf
            base_radius = logo_visual_radius + (bar_width / 2.0)
            radius = base_radius + radius_offset
            
            color_cfg = sl.get("color", {})
            mode = color_cfg.get("mode", "solid")
            c = color_cfg.get("solidColor", "#ffffff")
            if isinstance(c, str) and c.startswith("#"):
                c = c.lstrip("#")
                c = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            
            op = float(sl.get("opacity", 1.0))
            try:
                spec_col = (
                    float(c[0]) / 255.0,
                    float(c[1]) / 255.0,
                    float(c[2]) / 255.0,
                    float(max(0.0, min(1.0, op))),
                )
            except Exception:
                spec_col = (1.0, 1.0, 1.0, float(max(0.0, min(1.0, op))))

            blend_mode = str(sl.get("blend_mode", "normal")).lower().strip()
            if blend_mode in ("screen", "add", "lighten"):
                ctx.blend_func = moderngl.ADDITIVE_BLENDING
            else:
                ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

            # 2) 5-Tap Moving Average Smoothing & Mirroring
            render_fft = np.zeros(BINS, dtype=np.float32)
            if mirrored:
                half = BINS // 2
                for i in range(half):
                    smoothed = fft_s[i]
                    if 1 < i < half - 2:
                        smoothed = (fft_s[i-2]*0.1 + fft_s[i-1]*0.2 + fft_s[i]*0.4 + fft_s[i+1]*0.2 + fft_s[i+2]*0.1)
                    render_fft[half - 1 - i] = smoothed
                    render_fft[half + i] = smoothed
            else:
                for i in range(BINS):
                    smoothed = fft_s[i]
                    if 1 < i < BINS - 2:
                        smoothed = (fft_s[i-2]*0.1 + fft_s[i-1]*0.2 + fft_s[i]*0.4 + fft_s[i+1]*0.2 + fft_s[i+2]*0.1)
                    render_fft[i] = smoothed

            react_mult = rg * thickness
            
            # 3) Generate Points
            n = BINS
            total_length = 0.0
            if curved:
                total_angle = np.pi * 2.0 if mirrored else np.pi
                total_length = radius * total_angle
            else:
                total_length = float(h * 0.8) if gravity in ("left", "right") else float(w * 0.8)
                
            start_angle = np.pi / 2.0
            if gravity == "top": start_angle = -np.pi / 2.0
            elif gravity == "left": start_angle = np.pi
            elif gravity == "right": start_angle = 0.0
            
            start_x = -total_length / 2.0
            
            px_arr = np.zeros(n, dtype=np.float32)
            py_arr = np.zeros(n, dtype=np.float32)
            dx_arr = np.zeros(n, dtype=np.float32)
            dy_arr = np.zeros(n, dtype=np.float32)
            val_arr = np.zeros(n, dtype=np.float32)
            
            for i in range(n):
                t = float(i) / float(n - 1) if n > 1 else 0.0
                if curved:
                    total_angle = np.pi * 2.0 if mirrored else np.pi
                    angle = start_angle - (total_angle / 2.0) + (t * total_angle)
                    px_arr[i] = np.cos(angle) * radius
                    py_arr[i] = np.sin(angle) * radius
                    dx_arr[i] = np.cos(angle)
                    dy_arr[i] = np.sin(angle)
                else:
                    offset = start_x + (t * total_length)
                    if gravity == "bottom":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = offset, 0.0, 0.0, -1.0
                    elif gravity == "top":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = offset, 0.0, 0.0, 1.0
                    elif gravity == "left":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = 0.0, offset, 1.0, 0.0
                    elif gravity == "right":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = 0.0, offset, -1.0, 0.0
                val_arr[i] = render_fft[i] * thickness

            if mode == "gradient" and color_cfg.get("gradientColors") and len(color_cfg.get("gradientColors")) >= 2:
                gcols = color_cfg.get("gradientColors")
                c1_hex = gcols[0].lstrip("#")
                c2_hex = gcols[1].lstrip("#")
                c1 = np.array([int(c1_hex[i:i+2], 16)/255.0 for i in (0, 2, 4)], dtype=np.float32)
                c2 = np.array([int(c2_hex[i:i+2], 16)/255.0 for i in (0, 2, 4)], dtype=np.float32)
                t_arr = (np.arange(n, dtype=np.float32) / float(max(1, n))).reshape((n, 1))
                rgb = c1 * (1.0 - t_arr) + c2 * t_arr
                a = np.full((n, 1), float(spec_col[3]), dtype=np.float32)
                cols = np.concatenate([rgb, a], axis=1)
            else:
                col = np.array(spec_col, dtype=np.float32)
                cols = np.tile(col[None, :], (n, 1))

            prog_lines["clip_enabled"].value = 0

            # Render Logic
            bw = float(max(1.0, (total_length / n) * (bar_width / 10.0)))
            
            if style_preset in ("soft-waveform", "mountain", "liquid", "continuous-waveform"):
                # Render as triangle strip
                nn = n
                if curved and mirrored:
                    # Connect start and end
                    px_arr = np.concatenate([px_arr, px_arr[:1]])
                    py_arr = np.concatenate([py_arr, py_arr[:1]])
                    dx_arr = np.concatenate([dx_arr, dx_arr[:1]])
                    dy_arr = np.concatenate([dy_arr, dy_arr[:1]])
                    val_arr = np.concatenate([val_arr, val_arr[:1]])
                    cols = np.concatenate([cols, cols[:1]], axis=0)
                    nn += 1

                xs_o = np.zeros(nn, dtype=np.float32)
                ys_o = np.zeros(nn, dtype=np.float32)
                xs_i = np.zeros(nn, dtype=np.float32)
                ys_i = np.zeros(nn, dtype=np.float32)
                
                for i in range(nn):
                    h_val = float(max(2.0, val_arr[i]))
                    if style_preset == "mountain":
                        peak_h = h_val * 1.18
                        xs_o[i] = (cx + px_arr[i] + dx_arr[i] * peak_h) / float(w) * 2.0 - 1.0
                        ys_o[i] = (cy + py_arr[i] + dy_arr[i] * peak_h) / float(h) * 2.0 - 1.0
                        xs_i[i] = (cx + px_arr[i] + dx_arr[i] * (bar_width * 0.10)) / float(w) * 2.0 - 1.0
                        ys_i[i] = (cy + py_arr[i] + dy_arr[i] * (bar_width * 0.10)) / float(h) * 2.0 - 1.0
                    elif style_preset == "liquid":
                        liquid_h = h_val * 0.92
                        inner_pull = bar_width * 0.68
                        xs_o[i] = (cx + px_arr[i] + dx_arr[i] * liquid_h) / float(w) * 2.0 - 1.0
                        ys_o[i] = (cy + py_arr[i] + dy_arr[i] * liquid_h) / float(h) * 2.0 - 1.0
                        xs_i[i] = (cx + px_arr[i] - dx_arr[i] * inner_pull) / float(w) * 2.0 - 1.0
                        ys_i[i] = (cy + py_arr[i] - dy_arr[i] * inner_pull) / float(h) * 2.0 - 1.0
                    else:
                        # Stroke
                        half_t = bar_width * 0.5
                        xs_o[i] = (cx + px_arr[i] + dx_arr[i] * (h_val + half_t)) / float(w) * 2.0 - 1.0
                        ys_o[i] = (cy + py_arr[i] + dy_arr[i] * (h_val + half_t)) / float(h) * 2.0 - 1.0
                        xs_i[i] = (cx + px_arr[i] + dx_arr[i] * (h_val - half_t)) / float(w) * 2.0 - 1.0
                        ys_i[i] = (cy + py_arr[i] + dy_arr[i] * (h_val - half_t)) / float(h) * 2.0 - 1.0

                if curved and bool(sl.get("fillCircle", False)):
                    cx_ndc = float(cx) / float(w) * 2.0 - 1.0
                    cy_ndc = float(cy) / float(h) * 2.0 - 1.0
                    pos_fill = np.empty((nn + 1, 2), dtype=np.float32)
                    pos_fill[0, 0] = cx_ndc
                    pos_fill[0, 1] = cy_ndc
                    pos_fill[1:, 0] = xs_o
                    pos_fill[1:, 1] = ys_o
                    cols_edge = cols[:nn].copy()
                    cols_center = cols_edge[:1].copy()
                    cols_fill = np.concatenate([cols_center, cols_edge], axis=0)
                    verts_fill = np.column_stack([pos_fill, cols_fill]).astype(np.float32)
                    if verts_fill.nbytes > line_vbo.size:
                        line_vbo.orphan(size=verts_fill.nbytes)
                    line_vbo.write(verts_fill.tobytes())
                    vao_lines.render(mode=moderngl.TRIANGLE_FAN, vertices=int(nn + 1))

                pos = np.empty((2 * nn, 2), dtype=np.float32)
                pos[0::2, 0] = xs_o
                pos[0::2, 1] = ys_o
                pos[1::2, 0] = xs_i
                pos[1::2, 1] = ys_i
                colsi = np.repeat(cols, 2, axis=0)
                verts = np.column_stack([pos, colsi]).astype(np.float32)
                if verts.nbytes > line_vbo.size:
                    line_vbo.orphan(size=verts.nbytes)
                line_vbo.write(verts.tobytes())
                vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(2 * nn))
                
            else:
                # Bar Styles (Render as individual quads)
                # Build pos array for triangles
                # 6 vertices per bar
                pos = np.zeros((n * 6, 2), dtype=np.float32)
                colsi = np.repeat(cols, 6, axis=0)
                
                for i in range(n):
                    h_val = float(max(2.0, val_arr[i]))
                    # Base anchor is px, py. Direction is dx, dy.
                    # Perpendicular vector (for width):
                    wx = -dy_arr[i] * (bw / 2.0)
                    wy = dx_arr[i] * (bw / 2.0)
                    
                    if style_preset == "symmetrical-bars":
                        p0x = px_arr[i] - dx_arr[i] * (h_val/2) - wx
                        p0y = py_arr[i] - dy_arr[i] * (h_val/2) - wy
                        p1x = px_arr[i] - dx_arr[i] * (h_val/2) + wx
                        p1y = py_arr[i] - dy_arr[i] * (h_val/2) + wy
                        p2x = px_arr[i] + dx_arr[i] * (h_val/2) + wx
                        p2y = py_arr[i] + dy_arr[i] * (h_val/2) + wy
                        p3x = px_arr[i] + dx_arr[i] * (h_val/2) - wx
                        p3y = py_arr[i] + dy_arr[i] * (h_val/2) - wy
                    elif style_preset == "floating-blocks":
                        p0x = px_arr[i] + dx_arr[i] * (h_val + 20.0*sf) - wx
                        p0y = py_arr[i] + dy_arr[i] * (h_val + 20.0*sf) - wy
                        p1x = px_arr[i] + dx_arr[i] * (h_val + 20.0*sf) + wx
                        p1y = py_arr[i] + dy_arr[i] * (h_val + 20.0*sf) + wy
                        p2x = px_arr[i] + dx_arr[i] * (h_val + 20.0*sf + 10.0*sf) + wx
                        p2y = py_arr[i] + dy_arr[i] * (h_val + 20.0*sf + 10.0*sf) + wy
                        p3x = px_arr[i] + dx_arr[i] * (h_val + 20.0*sf + 10.0*sf) - wx
                        p3y = py_arr[i] + dy_arr[i] * (h_val + 20.0*sf + 10.0*sf) - wy
                    elif style_preset == "pixel-bars":
                        step = 20.0 * sf
                        h_val = float(np.ceil(h_val / step) * step)
                        p0x = px_arr[i] - wx
                        p0y = py_arr[i] - wy
                        p1x = px_arr[i] + wx
                        p1y = py_arr[i] + wy
                        p2x = px_arr[i] + dx_arr[i] * h_val + wx
                        p2y = py_arr[i] + dy_arr[i] * h_val + wy
                        p3x = px_arr[i] + dx_arr[i] * h_val - wx
                        p3y = py_arr[i] + dy_arr[i] * h_val - wy
                    elif style_preset == "thin-lines":
                        wx = -dy_arr[i] * (1.0 * sf)
                        wy = dx_arr[i] * (1.0 * sf)
                        p0x = px_arr[i] - wx
                        p0y = py_arr[i] - wy
                        p1x = px_arr[i] + wx
                        p1y = py_arr[i] + wy
                        p2x = px_arr[i] + dx_arr[i] * h_val + wx
                        p2y = py_arr[i] + dy_arr[i] * h_val + wy
                        p3x = px_arr[i] + dx_arr[i] * h_val - wx
                        p3y = py_arr[i] + dy_arr[i] * h_val - wy
                    else: # classic-vertical, neon-pulse
                        p0x = px_arr[i] - wx
                        p0y = py_arr[i] - wy
                        p1x = px_arr[i] + wx
                        p1y = py_arr[i] + wy
                        p2x = px_arr[i] + dx_arr[i] * h_val + wx
                        p2y = py_arr[i] + dy_arr[i] * h_val + wy
                        p3x = px_arr[i] + dx_arr[i] * h_val - wx
                        p3y = py_arr[i] + dy_arr[i] * h_val - wy

                    idx = i * 6
                    pos[idx+0] = [(cx + p0x) / float(w) * 2.0 - 1.0, (cy + p0y) / float(h) * 2.0 - 1.0]
                    pos[idx+1] = [(cx + p1x) / float(w) * 2.0 - 1.0, (cy + p1y) / float(h) * 2.0 - 1.0]
                    pos[idx+2] = [(cx + p2x) / float(w) * 2.0 - 1.0, (cy + p2y) / float(h) * 2.0 - 1.0]
                    pos[idx+3] = [(cx + p0x) / float(w) * 2.0 - 1.0, (cy + p0y) / float(h) * 2.0 - 1.0]
                    pos[idx+4] = [(cx + p2x) / float(w) * 2.0 - 1.0, (cy + p2y) / float(h) * 2.0 - 1.0]
                    pos[idx+5] = [(cx + p3x) / float(w) * 2.0 - 1.0, (cy + p3y) / float(h) * 2.0 - 1.0]

                verts = np.column_stack([pos, colsi]).astype(np.float32)
                if verts.nbytes > line_vbo.size:
                    line_vbo.orphan(size=verts.nbytes)
                line_vbo.write(verts.tobytes())
                vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(n * 6))

        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        if particles_cfg_raw.get("enabled", False):
            pos = particles._pos if hasattr(particles, "_pos") else np.zeros((0, 2), dtype=np.float32)
            if pos.shape[0]:
                p = pos.astype(np.float32)
                xs2 = p[:, 0] / float(w) * 2.0 - 1.0
                ys2 = p[:, 1] / float(h) * 2.0 - 1.0
                sz = particles._size.astype(np.float32) if hasattr(particles, "_size") else np.ones((p.shape[0],), dtype=np.float32)
                pts = np.column_stack([xs2, ys2, sz]).astype(np.float32)
                if pts.nbytes > pt_vbo.size:
                    pt_vbo.orphan(size=pts.nbytes)
                pt_vbo.write(pts.tobytes())
                alpha = float(max(0.0, min(1.0, particles_cfg_raw.get("opacity", particles_cfg.opacity))))
                c = _as_rgb(particles_cfg_raw.get("color", particles_cfg.color))
                try:
                    react_strength = float(particles_cfg_raw.get("reactStrength", 0.65) or 0.65)
                    react_strength = float(max(0.0, min(1.0, react_strength)))
                    rc = _as_rgb(particles_cfg_raw.get("reactColor", particles_cfg_raw.get("color", "#ffffff")))
                    mix = float(max(0.0, min(1.0, p_trigger_env))) * react_strength
                    cr = float(c[0]) * (1.0 - mix) + float(rc[0]) * mix
                    cg = float(c[1]) * (1.0 - mix) + float(rc[1]) * mix
                    cb = float(c[2]) * (1.0 - mix) + float(rc[2]) * mix
                    colp = (cr / 255.0, cg / 255.0, cb / 255.0, alpha)
                except Exception:
                    colp = (1.0, 1.0, 1.0, alpha)
                variant = str(particles_cfg_raw.get("variant", "classic") or "classic")
                style = str(particles_cfg_raw.get("style", "dot") or "dot")
                if variant == "bokeh":
                    style = "bokeh"
                elif variant == "soap":
                    style = "ring"
                elif variant == "dust":
                    style = "glow"
                prog_points["pt_size"].value = float(max(1.0, float(particles_cfg_raw.get("size", particles_cfg.size)) * (2.0 if style == "bokeh" else 1.5) * sf))
                prog_points["pt_col"].value = colp
                if style == "glow":
                    prog_points["pt_style"].value = 1
                elif style == "ring":
                    prog_points["pt_style"].value = 2
                elif style == "spark":
                    prog_points["pt_style"].value = 3
                elif style == "bokeh":
                    prog_points["pt_style"].value = 4
                else:
                    prog_points["pt_style"].value = 0
                vao_pts.render(mode=moderngl.POINTS, vertices=int(pts.shape[0]))

        if tex_logo is not None and logo_enabled:
            tex_logo.use(location=1)
            vao_quad_logo.render(mode=moderngl.TRIANGLE_STRIP)

        fbo_out.use()
        ctx.clear(0.0, 0.0, 0.0, 1.0)
        tex_scene.use(location=0)
        rgb_opacity = float(state.get("effects.rgb_split.opacity", rgb_cfg.opacity))
        bloom_strength = float(state.get("effects.bloom.strength", bloom_cfg.strength))
        onset = float(feats.get("onset", 0.0))
        rgb_opacity = rgb_opacity * (1.0 + onset * 0.9)
        bloom_strength = bloom_strength * (1.0 + bass * 0.9)
        if not rgb_cfg.enabled:
            rgb_opacity = 0.0
        if not bloom_cfg.enabled:
            bloom_strength = 0.0
        prog_post["rgb_opacity"].value = float(max(0.0, min(1.0, rgb_opacity)))
        prog_post["rgb_r"].value = (float(rgb_cfg.red_offset[0]), float(rgb_cfg.red_offset[1]))
        prog_post["rgb_g"].value = (float(rgb_cfg.green_offset[0]), float(rgb_cfg.green_offset[1]))
        prog_post["rgb_b"].value = (float(rgb_cfg.blue_offset[0]), float(rgb_cfg.blue_offset[1]))
        prog_post["bloom_strength"].value = float(max(0.0, bloom_strength)) * float(max(0.0, min(1.0, bloom_cfg.opacity)))
        prog_post["bloom_threshold"].value = float(max(0.0, min(1.0, bloom_cfg.threshold)))
        vao_quad_post.render(mode=moderngl.TRIANGLE_STRIP)

        _draw_text_overlays(
            ctx,
            prog_text,
            vao_quad_text,
            text_overlays,
            float(i) / float(max(1.0, float(fps))),
            w,
            h,
            sf,
            text_cache,
        )

        raw = fbo_out.read(components=4, alignment=1)
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 4))
        arr = np.flipud(arr)
        img = Image.fromarray(arr, mode="RGBA")
        Path(out_png_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(out_png_path)

    try:
        glfw.terminate()
    except Exception:
        pass
    for tx in text_cache.get("tex", []):
        try:
            if tx is not None:
                tx.release()
        except Exception:
            pass
    return out_png_path

def run_live_preview(opts: GpuOptions) -> int:
    import threading
    import sys
    import json
    
    fps = int(max(1, min(60, int(opts.fps))))
    if fps <= 0:
        fps = 30

    w = int(max(64, min(8192, int(opts.width) if int(opts.width) > 0 else 1920)))
    h = int(max(64, min(8192, int(opts.height) if int(opts.height) > 0 else 1080)))

    if not glfw.init():
        raise RuntimeError("Failed to init GLFW")
        
    glfw.window_hint(glfw.VISIBLE, glfw.TRUE)
    glfw.window_hint(glfw.SAMPLES, 4)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
    glfw.window_hint(glfw.DECORATED, glfw.TRUE)
    win = glfw.create_window(w, h, "MG Live Preview", None, None)
    if not win:
        glfw.terminate()
        raise RuntimeError("Failed to create visible OpenGL window")
    glfw.make_context_current(win)
    glfw.swap_interval(1)

    ctx = _make_ctx()

    shared_state = {
        "template": _load_template(opts),
        "time": 0.0,
        "bg_path": opts.background_path,
        "logo_path": opts.logo_path,
        "audio_path": opts.mp3_path,
        "quit": False
    }

    def stdin_reader():
        for line in sys.stdin:
            try:
                msg = json.loads(line)
                if "time" in msg:
                    shared_state["time"] = float(msg["time"])
                if "templateB64" in msg:
                    shared_state["template"] = json.loads(base64.b64decode(msg["templateB64"]).decode("utf-8"))
                if "backgroundPath" in msg:
                    shared_state["bg_path"] = msg["backgroundPath"]
                if "logoPath" in msg:
                    shared_state["logo_path"] = msg["logoPath"]
                if "audioPath" in msg:
                    shared_state["audio_path"] = msg["audioPath"]
                if msg.get("cmd") == "exit":
                    shared_state["quit"] = True
                    break
            except Exception:
                pass
        shared_state["quit"] = True

    t = threading.Thread(target=stdin_reader, daemon=True)
    t.start()

    prog_scene, prog_logo, prog_post, prog_lines, prog_points, prog_text = _compile(ctx)
    vao_quad_scene = _quad_vao(ctx, prog_scene)
    vao_quad_logo = _quad_vao(ctx, prog_logo)
    vao_quad_text = _quad_vao(ctx, prog_text)
    vao_quad_post = _quad_vao(ctx, prog_post)

    tex_scene = ctx.texture((w, h), 4)
    tex_scene.filter = (moderngl.LINEAR, moderngl.LINEAR)
    fbo_scene = ctx.framebuffer(color_attachments=[tex_scene])

    line_vbo = ctx.buffer(reserve=4 * 6 * 1024)
    vao_lines = ctx.vertex_array(prog_lines, [(line_vbo, "2f 4f", "in_pos", "in_col")])
    prog_lines["clip_enabled"].value = 0
    prog_lines["clip_center_px"].value = (0.0, 0.0)
    prog_lines["clip_radius_px"].value = 0.0

    pt_vbo = ctx.buffer(reserve=4 * 3 * 2048)
    vao_pts = ctx.vertex_array(prog_points, [(pt_vbo, "2f 1f", "in_pos", "in_size")])

    current_bg_path = None
    tex_bg = None

    current_logo_path = None
    tex_logo = None
    logo_size_px = (0.0, 0.0)

    current_audio_path = None
    analyzer = None
    point_count = 1024

    particles = ParticleSystem(ParticleConfig(enabled=False, max_count=1, spawn_rate=1, lifetime_sec=1, size=1, opacity=1, color=(255,255,255), speed=1, spawn_radius=0), width=w, height=h, rng_seed=1)
    
    dt = 1.0 / float(fps)
    shake_state_x = 0.0
    shake_state_y = 0.0
    bg_shake_state_x = 0.0
    bg_shake_state_y = 0.0
    p_bass_fast = 0.0
    p_bass_slow = 0.0
    p_kick_env = 0.0
    bg_audio_env = 0.0
    logo_audio_env = 0.0
    particle_audio_env = 0.0
    p_trigger_env = 0.0
    kick_fast_a = 1.0 - float(np.exp(-dt / 0.06))
    kick_slow_a = 1.0 - float(np.exp(-dt / 0.35))
    kick_decay = float(np.exp(-dt / 0.18))
    
    def synth_fft(i: int) -> np.ndarray:
        n = int(point_count)
        t = float(i) / float(max(1, fps))
        a = 0.35 + 0.25 * np.sin(t * 2.2) + 0.15 * np.sin(t * 6.1)
        phase = t * 0.7
        x = np.linspace(0.0, 1.0, num=n, dtype=np.float32)
        y = (a * (0.5 + 0.5 * np.sin((x * 12.0 + phase) * np.pi * 2.0))).astype(np.float32)
        return np.clip(y, 0.0, 1.0)

    def synth_feats(i: int) -> dict:
        t = float(i) / float(max(1, fps))
        beat = 1.0 if int(t * 2.0) % 2 == 0 and (t * 2.0 - int(t * 2.0)) < 0.05 else 0.0
        onset = max(0.0, float(np.sin(t * 3.1)) * 0.5 + 0.5)
        bass = max(0.0, float(np.sin(t * 1.9)) * 0.5 + 0.5)
        return {"bass": bass, "mid": 0.5, "treble": 0.5, "energy": 0.6, "onset": onset, "beat": beat}

    _send({"status": "ready", "message": "Live preview started"})

    while not glfw.window_should_close(win) and not shared_state["quit"]:
        glfw.poll_events()

        template = shared_state["template"]
        bg_path = shared_state["bg_path"]
        logo_path = shared_state["logo_path"]
        audio_path = shared_state["audio_path"]
        c_time = shared_state["time"]
        logo0 = template.get("logoSettings") if isinstance(template.get("logoSettings"), dict) else {}
        logo_enabled0 = bool(logo0.get("enabled", True))
        if not logo_enabled0:
            logo_path = ""

        base_h = float(template.get("renderBaseHeight", 450.0))
        base_h = float(max(1.0, min(4000.0, base_h)))
        sf = float(h) / base_h

        if bg_path != current_bg_path:
            if tex_bg: tex_bg.release()
            try:
                bg_rgba = _load_image_rgba(bg_path, (w, h))
            except:
                bg_rgba = np.zeros((h, w, 4), dtype=np.uint8)
            tex_bg = ctx.texture((w, h), 4, bg_rgba.tobytes())
            tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
            current_bg_path = bg_path

        if logo_path != current_logo_path:
            if tex_logo: tex_logo.release()
            tex_logo = None
            if logo_path and Path(logo_path).exists():
                try:
                    logo_rgba = _load_image_rgba(logo_path)
                    lh, lw = int(logo_rgba.shape[0]), int(logo_rgba.shape[1])
                    max_w = int(w * 0.22)
                    scale = min(1.0, max_w / max(1, lw))
                    nlw = max(1, int(round(lw * scale)))
                    nlh = max(1, int(round(lh * scale)))
                    logo_rgba2 = np.array(Image.fromarray(logo_rgba).resize((nlw, nlh), Image.Resampling.LANCZOS), dtype=np.uint8)
                    tex_logo = ctx.texture((nlw, nlh), 4, logo_rgba2.tobytes())
                    tex_logo.filter = (moderngl.LINEAR, moderngl.LINEAR)
                    logo_size_px = (float(nlw), float(nlh))
                except:
                    pass
            current_logo_path = logo_path

        if audio_path != current_audio_path:
            if audio_path and Path(audio_path).exists() and audio_path != "synthetic":
                analyzer = AudioAnalyzer(audio_path, fps=fps, point_count=point_count)
            else:
                analyzer = None
            current_audio_path = audio_path

        frame_idx = int(c_time * fps)
        
        fft = analyzer.fft_for_frame(frame_idx) if analyzer is not None else synth_fft(frame_idx)
        feats = analyzer.features_for_frame(frame_idx) if analyzer is not None else synth_feats(frame_idx)

        spectrum_container = template

        effects_raw = template.get("effects") if isinstance(template.get("effects"), dict) else {}
        bloom_raw = effects_raw.get("bloom") if isinstance(effects_raw.get("bloom"), dict) else {}
        rgb_raw = effects_raw.get("rgb_split") if isinstance(effects_raw.get("rgb_split"), dict) else {}
        shake_raw = effects_raw.get("camera_shake") if isinstance(effects_raw.get("camera_shake"), dict) else {}
        bloom_cfg = BloomConfig(
            enabled=bool(bloom_raw.get("enabled", False)),
            strength=float(bloom_raw.get("strength", 1.0)),
            blur_radius=int(bloom_raw.get("blur_radius", 11)),
            threshold=float(bloom_raw.get("threshold", 0.75)),
            opacity=float(bloom_raw.get("opacity", 0.9)),
        )
        rgb_cfg = RgbSplitConfig(
            enabled=bool(rgb_raw.get("enabled", False)),
            red_offset=tuple(rgb_raw.get("red_offset", (2, 0))),
            green_offset=tuple(rgb_raw.get("green_offset", (0, 0))),
            blue_offset=tuple(rgb_raw.get("blue_offset", (-2, 0))),
            opacity=float(rgb_raw.get("opacity", 0.6)),
        )
        shake_enabled = bool(shake_raw.get("enabled", False))
        shake_intensity = float(shake_raw.get("intensity", 8.0))
        shake_smoothing = float(shake_raw.get("smoothing", 0.85))
        autos = template.get("automations") if isinstance(template.get("automations"), list) else []

        bg_settings_raw = template.get("backgroundSettings", {}) if isinstance(template.get("backgroundSettings"), dict) else {}
        bg_brightness = float(bg_settings_raw.get("brightness", 1.0))
        bg_brightness = float(max(0.0, min(3.0, bg_brightness)))
        bg_react_bass = float(bg_settings_raw.get("reactivity", 0.0))
        bg_react_bass = float(max(0.0, min(2.0, bg_react_bass)))
        bg_smoothing = float(max(0.0, min(0.99, bg_settings_raw.get("smoothing", 0.8))))
        bg_motion_mode = str(bg_settings_raw.get("motionMode", "none") or "none")
        if bg_motion_mode not in ("none", "zoom", "vibrate", "both"):
            bg_motion_mode = "none"
        bg_motion_zoom_strength = float(bg_settings_raw.get("motionZoomStrength", 1.0) or 1.0)
        bg_motion_zoom_strength = float(max(0.0, min(2.0, bg_motion_zoom_strength)))
        bg_motion_vibrate_strength = float(bg_settings_raw.get("motionVibrateStrength", 1.0) or 1.0)
        bg_motion_vibrate_strength = float(max(0.0, min(2.0, bg_motion_vibrate_strength)))

        logo_raw = template.get("logoSettings", {}) if isinstance(template.get("logoSettings"), dict) else {}
        logo_enabled = bool(logo_raw.get("enabled", True))
        logo_circle_mask = bool(logo_raw.get("circleMask", True))
        logo_opacity = float(logo_raw.get("opacity", 1.0))
        logo_opacity = float(max(0.0, min(1.0, logo_opacity)))
        logo_scale_base = float(logo_raw.get("scale", 1.0))
        logo_scale_base = float(max(0.1, min(2.5, logo_scale_base)))
        logo_react_bass = float(logo_raw.get("reactivity", 0.0))
        logo_react_bass = float(max(0.0, min(2.0, logo_react_bass)))
        logo_smoothing = float(max(0.0, min(0.99, logo_raw.get("smoothing", 0.75))))

        base_state = {
            "camera_shake.intensity": shake_intensity,
            "spectrum.scale": 1.0,
            "effects.bloom.strength": float(bloom_cfg.strength),
            "effects.rgb_split.opacity": float(rgb_cfg.opacity),
        }
        state = apply_automations(base_state, feats, autos)
        bass = float(feats.get("bass", 0.0))
        p_bass_fast = p_bass_fast * (1.0 - kick_fast_a) + bass * kick_fast_a
        p_bass_slow = p_bass_slow * (1.0 - kick_slow_a) + bass * kick_slow_a
        raw_kick = float(max(0.0, p_bass_fast - p_bass_slow))
        kick0 = float(max(0.0, min(1.0, raw_kick * 4.0)))
        p_kick_env = float(max(kick0, p_kick_env * kick_decay))
        kick_pow = float(max(0.0, min(1.0, p_kick_env))) ** 2

        bg_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.6))))
        bg_audio_env = _smooth_env(bg_audio_env, bg_audio_raw, bg_smoothing)
        logo_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.8))))
        logo_audio_env = _smooth_env(logo_audio_env, logo_audio_raw, logo_smoothing)

        if bg_motion_mode in ("vibrate", "both"):
            bg_shake_target = float(max(0.0, bg_react_bass) * bg_audio_env * 18.0 * sf * bg_motion_vibrate_strength)
            bg_jx = (time.time() * 0.81 + frame_idx * 0.013) % 1.0
            bg_jy = (time.time() * 0.83 + frame_idx * 0.017) % 1.0
            bg_shake_state_x = bg_shake_state_x * bg_smoothing + ((bg_jx * 2.0 - 1.0) * bg_shake_target) * (1.0 - bg_smoothing)
            bg_shake_state_y = bg_shake_state_y * bg_smoothing + ((bg_jy * 2.0 - 1.0) * bg_shake_target) * (1.0 - bg_smoothing)
        else:
            bg_shake_state_x = 0.0
            bg_shake_state_y = 0.0

        if bg_motion_mode in ("zoom", "both"):
            bg_scale_live = float(1.0 + bg_audio_env * bg_react_bass * 0.015 * bg_motion_zoom_strength)
        else:
            bg_scale_live = 1.0
        bg_offset_uv = (
            float(bg_shake_state_x / max(1.0, float(w))),
            float(bg_shake_state_y / max(1.0, float(h))),
        )

        prog_scene["tex_bg"].value = 0
        tex_bg.use(location=0)
        if tex_logo is not None and logo_enabled:
            prog_logo["tex_logo"].value = 1
            tex_logo.use(location=1)
        if "out_size" in prog_scene:
            prog_scene["out_size"].value = (float(w), float(h))
        if "bg_tex_size" in prog_scene:
            prog_scene["bg_tex_size"].value = (float(w), float(h))
        if "bg_fit_mode" in prog_scene:
            prog_scene["bg_fit_mode"].value = 0
        if bg_motion_mode in ("vibrate", "both"):
            prog_scene["bg_offset"].value = bg_offset_uv
        else:
            prog_scene["bg_offset"].value = (0.0, 0.0)
        prog_scene["bg_scale"].value = (bg_scale_live, bg_scale_live)
        prog_scene["bg_brightness"].value = float(max(0.0, min(3.0, bg_brightness * (1.0 + bg_audio_env * bg_react_bass))))
        fx = template.get("effects") if isinstance(template.get("effects"), dict) else {}
        vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        prog_scene["vignette_enabled"].value = 1 if bool(vig.get("enabled", False)) else 0
        prog_scene["vignette_strength"].value = float(max(0.0, min(1.0, float(vig.get("strength", 0.35) or 0.35))))
        prog_scene["vignette_feather"].value = float(max(0.0, min(1.0, float(vig.get("feather", 0.65) or 0.65))))
        prog_scene["vignette_opacity"].value = float(max(0.0, min(1.0, float(vig.get("opacity", 0.65) or 0.65))))
        vcol = str(vig.get("color", "#000000") or "#000000")
        prog_scene["vignette_color"].value = (
            (int(vcol[1:3], 16) / 255.0, int(vcol[3:5], 16) / 255.0, int(vcol[5:7], 16) / 255.0)
            if vcol.startswith("#") and len(vcol) == 7
            else (0.0, 0.0, 0.0)
        )
        prog_scene["smoke_enabled"].value = 1 if bool(sm.get("enabled", False)) else 0
        prog_scene["smoke_strength"].value = float(max(0.0, min(1.0, float(sm.get("strength", 0.35) or 0.35))))
        prog_scene["smoke_blur"].value = float(max(0.0, min(1.0, float(sm.get("blur", 0.55) or 0.55))))
        prog_scene["smoke_noise"].value = float(max(0.0, min(1.0, float(sm.get("noise", 0.55) or 0.55))))
        prog_scene["smoke_speed"].value = float(max(0.0, min(2.0, float(sm.get("speed", 0.35) or 0.35))))
        prog_scene["smoke_opacity"].value = float(max(0.0, min(1.0, float(sm.get("opacity", 0.55) or 0.55))))
        scol = str(sm.get("color", "#000000") or "#000000")
        prog_scene["smoke_color"].value = (
            (int(scol[1:3], 16) / 255.0, int(scol[3:5], 16) / 255.0, int(scol[5:7], 16) / 255.0)
            if scol.startswith("#") and len(scol) == 7
            else (0.0, 0.0, 0.0)
        )
        prog_scene["time_sec"].value = float(c_time)
        
        if tex_logo is not None and logo_enabled:
            if "out_size" in prog_logo:
                prog_logo["out_size"].value = (float(w), float(h))
            prog_logo["logo_px"].value = (0.0, 0.0)
            base_logo_size_px = (float(logo_size_px[0]), float(logo_size_px[1]))
            prog_logo["logo_size_px"].value = base_logo_size_px
            prog_logo["logo_opacity"].value = float(logo_opacity)
            prog_logo["logo_circle_mask"].value = 1 if logo_circle_mask else 0

        prog_post["tex_in"].value = 0
        prog_post["out_size"].value = (float(w), float(h))

        if shake_enabled:
            target = float(state.get("camera_shake.intensity", shake_intensity)) * (
                0.35 + float(feats.get("bass", 0.0)) * 1.2 + float(feats.get("beat", 0.0)) * 1.5
            )
            jitter_x = (time.time() * 0.9 + frame_idx * 0.013) % 1.0
            jitter_y = (time.time() * 0.9 + frame_idx * 0.017) % 1.0
            tx = (jitter_x * 2.0 - 1.0) * target
            ty = (jitter_y * 2.0 - 1.0) * target
            s = max(0.0, min(0.99, shake_smoothing))
            shake_state_x = shake_state_x * s + tx * (1.0 - s)
            shake_state_y = shake_state_y * s + ty * (1.0 - s)
        else:
            shake_state_x = 0.0
            shake_state_y = 0.0

        fbo_scene.use()
        ctx.viewport = (0, 0, w, h)
        ctx.clear(0.0, 0.0, 0.0, 1.0)
        tex_bg.use(location=0)
        vao_quad_scene.render(mode=moderngl.TRIANGLE_STRIP)

        scale = float(state.get("spectrum.scale", 1.0))
        raw_layers = spectrum_container.get("layers", [])
        spectrum_layers: list[dict] = [x for x in raw_layers if isinstance(x, dict)]

        style_preset = str(template.get("style", "classic-vertical")).lower().strip()
        react_gain = float(template.get("audioSettings", {}).get("sensitivity", 1.0))
        
        BINS = 64
        fft_log = np.zeros(BINS, dtype=np.float32)
        sample_rate = 44100.0
        nyquist = sample_rate / 2.0
        min_freq = 20.0
        max_freq = 12000.0
        min_log = np.log10(min_freq)
        max_log = np.log10(max_freq)
        n0 = int(min(point_count, fft.shape[0]))
        fft_size_half = float(point_count)
        
        for b_idx in range(BINS):
            log_freq = min_log + (b_idx / float(BINS)) * (max_log - min_log)
            freq = 10.0 ** log_freq
            linear_index = (freq / nyquist) * fft_size_half
            idx1 = int(np.floor(linear_index))
            idx2 = int(min(np.ceil(linear_index), fft_size_half - 1))
            frac = linear_index - float(idx1)
            val1 = float(fft[idx1]) if idx1 < n0 else 0.0
            val2 = float(fft[idx2]) if idx2 < n0 else 0.0
            raw_val = val1 * (1.0 - frac) + val2 * frac
            freq_boost = 1.0 + ((b_idx / float(BINS)) ** 2) * 2.0
            val = raw_val * freq_boost
            fft_log[b_idx] = float(max(0.01, min(1.0, val)))
            
        rg = float(max(0.1, min(8.0, react_gain)))
        rb = 0.0
        fft_s = np.clip(fft_log * rg * (1.0 + bass * rb), 0.0, 2.5).astype(np.float32)
        
        anchor_val = template.get("position", {}).get("anchor", "center") if isinstance(template.get("position"), dict) else "center"
        off_x = float(template.get("position", {}).get("x", 0.0)) * sf if isinstance(template.get("position"), dict) else 0.0
        off_y = float(template.get("position", {}).get("y", 0.0)) * sf if isinstance(template.get("position"), dict) else 0.0
        
        c_pos = _get_anchor_coords(anchor_val, off_x, off_y, w, h)
        cx = c_pos[0] + float(shake_state_x)
        cy = c_pos[1] + float(shake_state_y)
        
        for sl in spectrum_layers:
            curved = bool(sl.get("curved", True))
            mirrored = bool(sl.get("mirrored", True))
            bar_width = float(sl.get("barWidth", 4.0)) * sf
            thickness = float(sl.get("thickness", 150.0)) * sf
            gravity = str(sl.get("gravity", "bottom")).lower().strip()
            
            logo_visual_radius = (float(logo_raw.get("size", 192.0)) * 0.5) * sf * float(logo_scale_base)
            base_radius = logo_visual_radius + (bar_width / 2.0)
            radius = base_radius
            
            color_cfg = sl.get("color", {})
            mode = color_cfg.get("mode", "solid")
            c = color_cfg.get("solidColor", "#ffffff")
            if isinstance(c, str) and c.startswith("#"):
                c = c.lstrip("#")
                c = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            
            op = float(sl.get("opacity", 1.0))
            try:
                spec_col = (float(c[0]) / 255.0, float(c[1]) / 255.0, float(c[2]) / 255.0, float(max(0.0, min(1.0, op))))
            except Exception:
                spec_col = (1.0, 1.0, 1.0, float(max(0.0, min(1.0, op))))

            blend_mode = str(sl.get("blend_mode", "normal")).lower().strip()
            if blend_mode in ("screen", "add", "lighten"):
                ctx.blend_func = moderngl.ADDITIVE_BLENDING
            else:
                ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

            render_fft = np.zeros(BINS, dtype=np.float32)
            if mirrored:
                half = BINS // 2
                for i in range(half):
                    smoothed = fft_s[i]
                    if 1 < i < half - 2:
                        smoothed = (fft_s[i-2]*0.1 + fft_s[i-1]*0.2 + fft_s[i]*0.4 + fft_s[i+1]*0.2 + fft_s[i+2]*0.1)
                    render_fft[half - 1 - i] = smoothed
                    render_fft[half + i] = smoothed
            else:
                for i in range(BINS):
                    smoothed = fft_s[i]
                    if 1 < i < BINS - 2:
                        smoothed = (fft_s[i-2]*0.1 + fft_s[i-1]*0.2 + fft_s[i]*0.4 + fft_s[i+1]*0.2 + fft_s[i+2]*0.1)
                    render_fft[i] = smoothed

            n = BINS
            total_length = 0.0
            if curved:
                total_angle = np.pi * 2.0 if mirrored else np.pi
                total_length = radius * total_angle
            else:
                total_length = float(h * 0.8) if gravity in ("left", "right") else float(w * 0.8)
                
            start_angle = np.pi / 2.0
            if gravity == "top": start_angle = -np.pi / 2.0
            elif gravity == "left": start_angle = np.pi
            elif gravity == "right": start_angle = 0.0
            
            start_x = -total_length / 2.0
            
            px_arr = np.zeros(n, dtype=np.float32)
            py_arr = np.zeros(n, dtype=np.float32)
            dx_arr = np.zeros(n, dtype=np.float32)
            dy_arr = np.zeros(n, dtype=np.float32)
            val_arr = np.zeros(n, dtype=np.float32)
            
            for i in range(n):
                t = float(i) / float(n - 1) if n > 1 else 0.0
                if curved:
                    total_angle = np.pi * 2.0 if mirrored else np.pi
                    angle = start_angle - (total_angle / 2.0) + (t * total_angle)
                    px_arr[i] = np.cos(angle) * radius
                    py_arr[i] = np.sin(angle) * radius
                    dx_arr[i] = np.cos(angle)
                    dy_arr[i] = np.sin(angle)
                else:
                    offset = start_x + (t * total_length)
                    if gravity == "bottom":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = offset, 0.0, 0.0, -1.0
                    elif gravity == "top":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = offset, 0.0, 0.0, 1.0
                    elif gravity == "left":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = 0.0, offset, 1.0, 0.0
                    elif gravity == "right":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = 0.0, offset, -1.0, 0.0
                val_arr[i] = render_fft[i] * thickness

            if mode == "gradient" and color_cfg.get("gradientColors") and len(color_cfg.get("gradientColors")) >= 2:
                gcols = color_cfg.get("gradientColors")
                c1_hex = gcols[0].lstrip("#")
                c2_hex = gcols[1].lstrip("#")
                c1 = np.array([int(c1_hex[i:i+2], 16)/255.0 for i in (0, 2, 4)], dtype=np.float32)
                c2 = np.array([int(c2_hex[i:i+2], 16)/255.0 for i in (0, 2, 4)], dtype=np.float32)
                t_arr = (np.arange(n, dtype=np.float32) / float(max(1, n))).reshape((n, 1))
                rgb = c1 * (1.0 - t_arr) + c2 * t_arr
                a = np.full((n, 1), float(spec_col[3]), dtype=np.float32)
                cols = np.concatenate([rgb, a], axis=1)
            else:
                col = np.array(spec_col, dtype=np.float32)
                cols = np.tile(col[None, :], (n, 1))

            prog_lines["clip_enabled"].value = 0
            
            bw = float(max(1.0, (total_length / n) * (bar_width / 10.0)))
            
            if style_preset in ("soft-waveform", "mountain", "liquid", "continuous-waveform"):
                nn = n
                if curved and mirrored:
                    px_arr = np.concatenate([px_arr, px_arr[:1]])
                    py_arr = np.concatenate([py_arr, py_arr[:1]])
                    dx_arr = np.concatenate([dx_arr, dx_arr[:1]])
                    dy_arr = np.concatenate([dy_arr, dy_arr[:1]])
                    val_arr = np.concatenate([val_arr, val_arr[:1]])
                    cols = np.concatenate([cols, cols[:1]], axis=0)
                    nn += 1

                xs_o = np.zeros(nn, dtype=np.float32)
                ys_o = np.zeros(nn, dtype=np.float32)
                xs_i = np.zeros(nn, dtype=np.float32)
                ys_i = np.zeros(nn, dtype=np.float32)
                
                for i in range(nn):
                    h_val = float(max(2.0, val_arr[i]))
                    if style_preset == "mountain":
                        peak_h = h_val * 1.18
                        xs_o[i] = (cx + px_arr[i] + dx_arr[i] * peak_h) / float(w) * 2.0 - 1.0
                        ys_o[i] = (cy + py_arr[i] + dy_arr[i] * peak_h) / float(h) * 2.0 - 1.0
                        xs_i[i] = (cx + px_arr[i] + dx_arr[i] * (bar_width * 0.10)) / float(w) * 2.0 - 1.0
                        ys_i[i] = (cy + py_arr[i] + dy_arr[i] * (bar_width * 0.10)) / float(h) * 2.0 - 1.0
                    elif style_preset == "liquid":
                        liquid_h = h_val * 0.92
                        inner_pull = bar_width * 0.68
                        xs_o[i] = (cx + px_arr[i] + dx_arr[i] * liquid_h) / float(w) * 2.0 - 1.0
                        ys_o[i] = (cy + py_arr[i] + dy_arr[i] * liquid_h) / float(h) * 2.0 - 1.0
                        xs_i[i] = (cx + px_arr[i] - dx_arr[i] * inner_pull) / float(w) * 2.0 - 1.0
                        ys_i[i] = (cy + py_arr[i] - dy_arr[i] * inner_pull) / float(h) * 2.0 - 1.0
                    else:
                        half_t = bar_width * 0.5
                        xs_o[i] = (cx + px_arr[i] + dx_arr[i] * (h_val + half_t)) / float(w) * 2.0 - 1.0
                        ys_o[i] = (cy + py_arr[i] + dy_arr[i] * (h_val + half_t)) / float(h) * 2.0 - 1.0
                        xs_i[i] = (cx + px_arr[i] + dx_arr[i] * (h_val - half_t)) / float(w) * 2.0 - 1.0
                        ys_i[i] = (cy + py_arr[i] + dy_arr[i] * (h_val - half_t)) / float(h) * 2.0 - 1.0

                pos = np.empty((2 * nn, 2), dtype=np.float32)
                pos[0::2, 0] = xs_o
                pos[0::2, 1] = ys_o
                pos[1::2, 0] = xs_i
                pos[1::2, 1] = ys_i
                colsi = np.repeat(cols, 2, axis=0)
                verts = np.column_stack([pos, colsi]).astype(np.float32)
                if verts.nbytes > line_vbo.size:
                    line_vbo.orphan(size=verts.nbytes)
                line_vbo.write(verts.tobytes())
                vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(2 * nn))
                
            else:
                pos = np.zeros((n * 6, 2), dtype=np.float32)
                colsi = np.repeat(cols, 6, axis=0)
                
                for i in range(n):
                    h_val = float(max(2.0, val_arr[i]))
                    wx = -dy_arr[i] * (bw / 2.0)
                    wy = dx_arr[i] * (bw / 2.0)
                    
                    if style_preset == "symmetrical-bars":
                        p0x = px_arr[i] - dx_arr[i] * (h_val/2) - wx
                        p0y = py_arr[i] - dy_arr[i] * (h_val/2) - wy
                        p1x = px_arr[i] - dx_arr[i] * (h_val/2) + wx
                        p1y = py_arr[i] - dy_arr[i] * (h_val/2) + wy
                        p2x = px_arr[i] + dx_arr[i] * (h_val/2) + wx
                        p2y = py_arr[i] + dy_arr[i] * (h_val/2) + wy
                        p3x = px_arr[i] + dx_arr[i] * (h_val/2) - wx
                        p3y = py_arr[i] + dy_arr[i] * (h_val/2) - wy
                    else:
                        p0x = px_arr[i] - wx
                        p0y = py_arr[i] - wy
                        p1x = px_arr[i] + wx
                        p1y = py_arr[i] + wy
                        p2x = px_arr[i] + dx_arr[i] * h_val + wx
                        p2y = py_arr[i] + dy_arr[i] * h_val + wy
                        p3x = px_arr[i] + dx_arr[i] * h_val - wx
                        p3y = py_arr[i] + dy_arr[i] * h_val - wy

                    idx = i * 6
                    pos[idx+0] = [(cx + p0x) / float(w) * 2.0 - 1.0, (cy + p0y) / float(h) * 2.0 - 1.0]
                    pos[idx+1] = [(cx + p1x) / float(w) * 2.0 - 1.0, (cy + p1y) / float(h) * 2.0 - 1.0]
                    pos[idx+2] = [(cx + p2x) / float(w) * 2.0 - 1.0, (cy + p2y) / float(h) * 2.0 - 1.0]
                    pos[idx+3] = [(cx + p0x) / float(w) * 2.0 - 1.0, (cy + p0y) / float(h) * 2.0 - 1.0]
                    pos[idx+4] = [(cx + p2x) / float(w) * 2.0 - 1.0, (cy + p2y) / float(h) * 2.0 - 1.0]
                    pos[idx+5] = [(cx + p3x) / float(w) * 2.0 - 1.0, (cy + p3y) / float(h) * 2.0 - 1.0]

                verts = np.column_stack([pos, colsi]).astype(np.float32)
                if verts.nbytes > line_vbo.size:
                    line_vbo.orphan(size=verts.nbytes)
                line_vbo.write(verts.tobytes())
                vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(n * 6))

        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        particles_cfg_raw = template.get("particlesSettings", {}) if isinstance(template.get("particlesSettings"), dict) else {}
        if not particles_cfg_raw and isinstance(template.get("particles"), dict):
            particles_cfg_raw = template.get("particles")
            
        spawn_rate = float(particles_cfg_raw.get("spawnRate", particles_cfg_raw.get("spawn_rate", 40.0)))
        lifetime_sec = float(particles_cfg_raw.get("lifetimeSec", particles_cfg_raw.get("lifetime_sec", 1.6)))
        speed_base = float(particles_cfg_raw.get("speed", 120.0))
        prb = float(particles_cfg_raw.get("reactivity", 1.5))
        pt_size = float(particles_cfg_raw.get("size", 2.0))
        pt_color = tuple(_as_rgb(particles_cfg_raw.get("color", "#ffffff")))
        pt_count = int(particles_cfg_raw.get("maxCount", particles_cfg_raw.get("max_count", particles_cfg_raw.get("count", 150))))
        pt_opacity = float(particles_cfg_raw.get("opacity", 0.35))

        prb = float(max(0.0, min(6.0, prb)))
        prb = float(max(0.1, min(0.5, prb)))
        ps_smoothing = float(max(0.0, min(0.99, particles_cfg_raw.get("smoothing", 0.65))))
        particle_audio_raw = float(max(0.0, min(1.0, max(kick_pow, bass))))
        particle_audio_env = _smooth_env(particle_audio_env, particle_audio_raw, ps_smoothing)
        
        spawn_mode = str(particles_cfg_raw.get("spawnMode", "always") or "always")
        spawn_trigger = str(particles_cfg_raw.get("spawnTrigger", "both") or "both")
        spawn_threshold = float(particles_cfg_raw.get("spawnThreshold", 0.15) or 0.15)
        spawn_threshold = float(max(0.0, min(1.0, spawn_threshold)))
        if spawn_trigger == "kick":
            trig_raw = kick_pow
        elif spawn_trigger == "bass":
            trig_raw = bass
        else:
            trig_raw = float(max(kick_pow, bass))
        trig_raw = float(max(0.0, min(1.0, trig_raw)))
        p_trigger_env = _smooth_env(p_trigger_env, trig_raw, ps_smoothing)

        if spawn_mode == "reactiveOnly" and p_trigger_env < spawn_threshold:
            spawn_rate = 0.0
        else:
            spawn_rate = spawn_rate * float(0.2 + particle_audio_env * (1.1 + prb * 2.8))
        spawn_rate = float(max(0.0, min(20000.0, spawn_rate)))

        logo_visual_radius = (float(logo_raw.get("size", 192.0)) * 0.5) * sf * float(logo_scale_base)
        spawn_radius = float(max(0.0, logo_visual_radius + (2.0 * sf)))
        speed2 = speed_base * float(18.0 + particle_audio_env * (50.0 + prb * 130.0)) * sf
        speed2 = float(max(0.0, min(2500.0, speed2)))
        
        particles.update_cfg(
            ParticleConfig(
                enabled=bool(particles_cfg_raw.get("enabled", False)),
                max_count=pt_count,
                spawn_rate=spawn_rate,
                lifetime_sec=lifetime_sec,
                spawn_radius=spawn_radius,
                size=pt_size * sf,
                opacity=pt_opacity,
                color=pt_color,
                speed=speed2,
                size_jitter=float(particles_cfg_raw.get("sizeJitter", 0.0) or 0.0),
                drift=float(particles_cfg_raw.get("drift", 0.0) or 0.0),
                swirl=float(particles_cfg_raw.get("swirl", 0.0) or 0.0),
                spawn_area=str(particles_cfg_raw.get("spawnArea", "centerRing") or "centerRing"),
            )
        )
        particles.update(dt, feats)

        if particles_cfg_raw.get("enabled", False):
            pos = particles._pos if hasattr(particles, "_pos") else np.zeros((0, 2), dtype=np.float32)
            if pos.shape[0]:
                p = pos.astype(np.float32)
                xs2 = p[:, 0] / float(w) * 2.0 - 1.0
                ys2 = p[:, 1] / float(h) * 2.0 - 1.0
                sz = particles._size.astype(np.float32) if hasattr(particles, "_size") else np.ones((p.shape[0],), dtype=np.float32)
                pts = np.column_stack([xs2, ys2, sz]).astype(np.float32)
                if pts.nbytes > pt_vbo.size:
                    pt_vbo.orphan(size=pts.nbytes)
                pt_vbo.write(pts.tobytes())
                alpha = float(max(0.0, min(1.0, pt_opacity)))
                c = pt_color
                try:
                    react_strength = float(particles_cfg_raw.get("reactStrength", 0.65) or 0.65)
                    react_strength = float(max(0.0, min(1.0, react_strength)))
                    rc = _as_rgb(particles_cfg_raw.get("reactColor", particles_cfg_raw.get("color", "#ffffff")))
                    mix = float(max(0.0, min(1.0, p_trigger_env))) * react_strength
                    cr = float(c[0]) * (1.0 - mix) + float(rc[0]) * mix
                    cg = float(c[1]) * (1.0 - mix) + float(rc[1]) * mix
                    cb = float(c[2]) * (1.0 - mix) + float(rc[2]) * mix
                    colp = (cr / 255.0, cg / 255.0, cb / 255.0, alpha)
                except Exception:
                    colp = (1.0, 1.0, 1.0, alpha)
                variant = str(particles_cfg_raw.get("variant", "classic") or "classic")
                style = str(particles_cfg_raw.get("style", "dot") or "dot")
                if variant == "bokeh":
                    style = "bokeh"
                elif variant == "soap":
                    style = "ring"
                elif variant == "dust":
                    style = "glow"
                prog_points["pt_size"].value = float(max(1.0, pt_size * (2.0 if style == "bokeh" else 1.5) * sf))
                prog_points["pt_col"].value = colp
                if style == "glow":
                    prog_points["pt_style"].value = 1
                elif style == "ring":
                    prog_points["pt_style"].value = 2
                elif style == "spark":
                    prog_points["pt_style"].value = 3
                elif style == "bokeh":
                    prog_points["pt_style"].value = 4
                else:
                    prog_points["pt_style"].value = 0
                vao_pts.render(mode=moderngl.POINTS, vertices=int(pts.shape[0]))

        if tex_logo is not None and logo_enabled:
            if "logo_size_px" in prog_logo:
                base_radius = (float(logo_raw.get("size", 192.0)) * 0.5) * sf
                s_logo = float(logo_scale_base) * (1.0 + logo_audio_env * float(logo_react_bass))
                s_logo = float(max(0.05, min(4.0, s_logo)))
                final_logo_size = base_radius * 2.0 * s_logo
                prog_logo["logo_size_px"].value = (final_logo_size, final_logo_size)
                
                logo_anchor = template.get("position", {}).get("anchor", "center")
                logo_off_x = float(template.get("position", {}).get("x", 0.0)) * sf
                logo_off_y = float(template.get("position", {}).get("y", 0.0)) * sf
                
                l_pos = _get_anchor_coords(logo_anchor, logo_off_x, logo_off_y, w, h)
                prog_logo["logo_px"].value = (l_pos[0] - float(w)*0.5 + float(shake_state_x), l_pos[1] - float(h)*0.5 + float(shake_state_y))
            tex_logo.use(location=1)
            vao_quad_logo.render(mode=moderngl.TRIANGLE_STRIP)

        text_overlays = template.get("textOverlays") if isinstance(template.get("textOverlays"), list) else []
        _draw_text_overlays(ctx, prog_text, vao_quad_text, text_overlays, float(c_time), w, h, sf, text_cache)

        ctx.viewport = (0, 0, w, h)
        glfw.swap_buffers(win)

    try:
        glfw.terminate()
    except Exception:
        pass
    for tx in text_cache.get("tex", []):
        try:
            if tx is not None:
                tx.release()
        except Exception:
            pass
    return 0
