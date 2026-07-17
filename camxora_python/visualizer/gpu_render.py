from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import glfw
import moderngl
from ._spectrum_fast import resolve_bar_pixel_width

def _audio_bar_height_mult(template: dict) -> float:
    audio = template.get("audioSettings") if isinstance(template.get("audioSettings"), dict) else {}
    try:
        value = float(audio.get("barHeight", 1.0) or 1.0)
    except Exception:
        value = 1.0
    return float(max(0.25, min(8.0, value)))

import numpy as np
from PIL import Image

from .audio import AudioAnalyzer
from .automation import apply_automations
from .config import load_template_any, load_template_any_raw
from .effects import BloomConfig, RgbSplitConfig
from .particles import ParticleConfig, ParticleSystem

try:
    from features.video.lib.particle_color_engine import (
        compute_particle_react_mix,
        build_particle_rgba_rows,
    )
except Exception:  # pragma: no cover - export may run without package path
    def compute_particle_react_mix(
        *,
        reactive_env: float,
        trigger_env: float,
        react_strength: float,
    ) -> float:
        reactive = float(max(0.0, min(1.0, float(reactive_env))))
        trigger = float(max(0.0, min(1.0, float(trigger_env))))
        strength = float(max(0.0, min(1.0, float(react_strength))))
        color_drive = float(max(0.0, min(1.0, max(reactive * 1.3, trigger * 1.85))))
        return float(max(0.0, min(1.0, (color_drive**0.72) * strength)))

    def build_particle_rgba_rows(
        *,
        settings: dict,
        particle_rgbs: np.ndarray | None,
        react_mix: float | None = None,
        reactive_env: float | None = None,
        trigger_env: float | None = None,
    ) -> np.ndarray:
        def _rgb(v) -> tuple[int, int, int]:
            if isinstance(v, (list, tuple)) and len(v) == 3:
                return (int(v[0]), int(v[1]), int(v[2]))
            if isinstance(v, str) and v.startswith("#") and len(v) == 7:
                return (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
            return (255, 255, 255)

        alpha = float(max(0.0, min(1.0, float(settings.get("opacity", 0.35) or 0.35))))
        c = _rgb(settings.get("color", "#ffffff"))
        mix = float(react_mix or 0.0)
        if reactive_env is not None or trigger_env is not None:
            mix = compute_particle_react_mix(
                reactive_env=float(reactive_env or 0.0),
                trigger_env=float(trigger_env or 0.0),
                react_strength=float(settings.get("reactStrength", 0.65) or 0.65),
            )
        rc = _rgb(settings.get("reactColor", settings.get("color", "#ffffff")))
        rgb = (
            (c[0] * (1.0 - mix) + rc[0] * mix) / 255.0,
            (c[1] * (1.0 - mix) + rc[1] * mix) / 255.0,
            (c[2] * (1.0 - mix) + rc[2] * mix) / 255.0,
        )
        n = int(particle_rgbs.shape[0]) if particle_rgbs is not None and particle_rgbs.shape[0] else 1
        return np.tile(np.array([[rgb[0], rgb[1], rgb[2], alpha]], dtype=np.float32), (n, 1))


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
        raw = json.loads(base64.b64decode(opts.template_b64).decode("utf-8"))
    else:
        raw = load_template_any(opts.template_path)
    # Match live preview: clamp particle/spectrum fields the same way paintGL does.
    try:
        from visualizer.template_runtime import normalize_renderer_template

        return normalize_renderer_template(raw if isinstance(raw, dict) else {})
    except Exception:
        return raw if isinstance(raw, dict) else {}


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


def _compute_visible_logo_radius_ratio(logo_rgba: np.ndarray | None, circle_mask: bool) -> float:
    if logo_rgba is None or not isinstance(logo_rgba, np.ndarray) or logo_rgba.ndim < 3:
        return 1.0
    h = int(logo_rgba.shape[0]) if logo_rgba.shape[0] else 0
    w = int(logo_rgba.shape[1]) if logo_rgba.shape[1] else 0
    c = int(logo_rgba.shape[2]) if logo_rgba.ndim >= 3 else 0
    if h < 1 or w < 1 or c < 4:
        return 1.0

    source_size = int(max(1, min(w, h)))
    source_x = int(max(0, (w - source_size) // 2))
    source_y = int(max(0, (h - source_size) // 2))
    alpha = logo_rgba[source_y:source_y + source_size, source_x:source_x + source_size, 3]
    if alpha.size == 0:
        return 1.0

    ys, xs = np.nonzero(alpha >= 10)
    if xs.size == 0 or ys.size == 0:
        return 1.0

    center = float(source_size) / 2.0
    max_allowed_radius = center
    dx = xs.astype(np.float32) + 0.5 - center
    dy = ys.astype(np.float32) + 0.5 - center
    distances = np.sqrt(dx * dx + dy * dy).astype(np.float32)
    if circle_mask:
        distances = distances[distances <= max_allowed_radius]
        if distances.size == 0:
            return 1.0

    max_distance = float(np.max(distances))
    if max_allowed_radius <= 0.0:
        return 1.0
    return float(max(0.2, min(1.0, max_distance / max_allowed_radius)))


def _resolve_attached_layer_base_offset(spectrum_layers: list[dict], sf: float) -> float:
    offsets: list[float] = []
    for layer in spectrum_layers:
        if not isinstance(layer, dict):
            continue
        try:
            offsets.append(max(0.0, float(layer.get("radiusOffset", 0.0) or 0.0) * sf))
        except Exception:
            continue
    return float(min(offsets)) if offsets else 0.0


def _resolve_spectrum_layer_radius(
    *,
    attached_to_logo: bool,
    attached_base_radius: float,
    attached_layer_base_offset: float,
    logo_visual_radius: float,
    bar_width: float = 0.0,
    radius_offset: float,
) -> float:
    """Ring radius from logo + Layer Gap only.

    ``bar_width`` is accepted for call-site compatibility but must not expand
    the circle — Bar Width controls individual bar thickness, not ring size.
    """
    del bar_width  # intentionally unused (legacy callers still pass it)
    if attached_to_logo:
        normalized_offset = max(0.0, max(0.0, radius_offset) - attached_layer_base_offset)
        return float(max(0.0, attached_base_radius + normalized_offset))
    return float(max(0.0, logo_visual_radius + radius_offset))


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
    uniform float bg_contrast;
    uniform float bg_saturation;
    uniform float bg_hue;
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
    vec3 rgb2hsv(vec3 c) {
        vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
        vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
        vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
        float d = q.x - min(q.w, q.y);
        float e = 1.0e-10;
        return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
    }
    vec3 hsv2rgb(vec3 c) {
        vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
        vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
        return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
    }
    vec3 grade_bg(vec3 rgb) {
        // Contrast around mid-gray, then brightness gain, then HSV sat/hue.
        vec3 c = (rgb - vec3(0.5)) * max(0.0, bg_contrast) + vec3(0.5);
        c *= max(0.0, bg_brightness);
        vec3 hsv = rgb2hsv(clamp(c, 0.0, 1.0));
        hsv.x = fract(hsv.x + (bg_hue / 360.0));
        hsv.y = clamp(hsv.y * max(0.0, bg_saturation), 0.0, 1.0);
        return clamp(hsv2rgb(hsv), 0.0, 1.0);
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
        bg.rgb = grade_bg(bg.rgb);
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


def _compile_particle_quads(ctx: moderngl.Context):
    vs_particle_quads = """
    #version 330
    in vec2 in_pos;
    in vec2 in_uv;
    in vec4 in_col;
    out vec2 v_uv;
    out vec4 v_col;
    void main() {
        v_uv = in_uv * 2.0 - 1.0;
        v_col = in_col;
        gl_Position = vec4(in_pos, 0.0, 1.0);
    }
    """
    fs_particle_quads = """
    #version 330
    in vec2 v_uv;
    in vec4 v_col;
    uniform int pt_style;
    out vec4 frag;
    float sat(float x) { return clamp(x, 0.0, 1.0); }
    void main() {
        vec2 p = v_uv;
        float r2 = dot(p, p);
        float r = sqrt(max(r2, 0.0));
        float edge = 1.0 - smoothstep(0.92, 1.0, r);
        if (r > 1.0) discard;
        float a = edge;
        if (pt_style == 1) {
            float core = 1.0 - smoothstep(0.55, 1.0, r);
            float halo = 1.0 - smoothstep(0.0, 1.0, r);
            a = max(core, halo * 0.35) * edge;
        } else if (pt_style == 2) {
            float inner = smoothstep(0.55, 0.62, r);
            float outer = 1.0 - smoothstep(0.82, 0.90, r);
            a = sat(inner * outer) * edge;
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
            a = max(core, max(spike * 0.85, halo * 0.25)) * edge;
        } else if (pt_style == 4) {
            float soft = 1.0 - smoothstep(0.0, 1.0, r);
            a = pow(soft, 1.8) * edge;
        }
        frag = vec4(v_col.rgb, v_col.a * a);
    }
    """
    return ctx.program(vertex_shader=vs_particle_quads, fragment_shader=fs_particle_quads)


def _resolve_particle_style_index(variant: str, style: str) -> int:
    if variant == "bokeh":
        style = "bokeh"
    elif variant == "soap":
        style = "ring"
    elif variant == "dust":
        style = "glow"
    if style == "glow":
        return 1
    if style == "ring":
        return 2
    if style == "spark":
        return 3
    if style == "bokeh":
        return 4
    return 0


def _build_particle_styled_quad_verts(
    *,
    xs: np.ndarray,
    ys: np.ndarray,
    scales: np.ndarray,
    colors_rgba: np.ndarray,
    w: int,
    h: int,
    base_px: float,
) -> np.ndarray:
    hx = (base_px * scales) * 2.0 / max(1.0, float(w))
    hy = (base_px * scales) * 2.0 / max(1.0, float(h))
    x0 = xs - hx
    x1 = xs + hx
    y0 = ys - hy
    y1 = ys + hy
    n = int(xs.shape[0])
    pos = np.empty((n * 6, 2), dtype=np.float32)
    pos[0::6, 0] = x0
    pos[0::6, 1] = y0
    pos[1::6, 0] = x1
    pos[1::6, 1] = y0
    pos[2::6, 0] = x1
    pos[2::6, 1] = y1
    pos[3::6, 0] = x0
    pos[3::6, 1] = y0
    pos[4::6, 0] = x1
    pos[4::6, 1] = y1
    pos[5::6, 0] = x0
    pos[5::6, 1] = y1
    uv_template = np.array(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        dtype=np.float32,
    )
    uv = np.tile(uv_template, (n, 1))
    cols = np.repeat(colors_rgba.astype(np.float32), 6, axis=0)
    return np.column_stack([pos, uv, cols]).astype(np.float32)


def _render_particle_styled_quads(
    ctx: moderngl.Context,
    *,
    prog_particle_quads,
    particle_quad_vbo,
    vao_particle_quads,
    pts: np.ndarray,
    colors_rgba: np.ndarray,
    pt_style: int,
    w: int,
    h: int,
    pt_size: float,
) -> None:
    if pts.shape[0] <= 0:
        return
    if colors_rgba.shape[0] != pts.shape[0]:
        if colors_rgba.shape[0] == 1:
            colors_rgba = np.repeat(colors_rgba, pts.shape[0], axis=0)
        else:
            return
    xs = pts[:, 0].astype(np.float32)
    ys = pts[:, 1].astype(np.float32)
    scales = np.maximum(0.2, pts[:, 2].astype(np.float32))
    verts = _build_particle_styled_quad_verts(
        xs=xs,
        ys=ys,
        scales=scales,
        colors_rgba=colors_rgba,
        w=w,
        h=h,
        base_px=float(pt_size),
    )
    if verts.nbytes > particle_quad_vbo.size:
        particle_quad_vbo.orphan(size=verts.nbytes)
    particle_quad_vbo.write(verts.tobytes())
    prog_particle_quads["pt_style"].value = int(pt_style)
    ctx.enable(moderngl.BLEND)
    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
    vao_particle_quads.render(mode=moderngl.TRIANGLES, vertices=int(pts.shape[0] * 6))


def _as_rgb(v: any) -> tuple[int, int, int]:
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return (int(v[0]), int(v[1]), int(v[2]))
    if isinstance(v, str) and v.startswith("#") and len(v) == 7:
        return (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
    return (255, 255, 255)


def _resolve_export_spectrum_style(style_preset: str, layer: dict | None = None) -> str:
    """Resolve template/pack style ids to Camxora-native renderer keys."""
    from features.video.lib.spectrum_style_registry import normalize_spectrum_preset_key_for_apply
    from features.video.lib.video_template_draft import normalize_spectrum_preset_key

    layer = layer if isinstance(layer, dict) else {}
    fill_circle = bool(layer.get("fillCircle", False))
    raw = str(style_preset or "orbit-spikes").lower().strip()

    # Packs that still ship flying-glow / halo-stack keep fill-aware mapping.
    if raw in ("flying-glow", "halo-stack"):
        return "plasma-bloom" if fill_circle else "magma-ridge"

    normalized = normalize_spectrum_preset_key_for_apply(normalize_spectrum_preset_key(raw))
    camxora_ids = {
        "orbit-spikes",
        "signal-needles",
        "pulse-beads",
        "mirror-blades",
        "aurora-ribbon",
        "magma-ridge",
        "plasma-bloom",
        "grid-steps",
        "ignition-flare",
        "drift-capsules",
    }
    if normalized in camxora_ids:
        return normalized
    return "orbit-spikes"


def _build_spectrum_vertex_colors(
    color_cfg: dict,
    spec_col: tuple[float, float, float, float] | tuple[float, float, float],
    count: int,
    alpha: float,
) -> np.ndarray:
    mode = str(color_cfg.get("mode", "solid") or "solid").lower().strip()
    gradient_colors = color_cfg.get("gradientColors")
    if mode == "gradient" and isinstance(gradient_colors, list):
        stops = [np.array(_as_rgb(value), dtype=np.float32) / 255.0 for value in gradient_colors if isinstance(value, str)]
        if len(stops) >= 2:
            t = np.linspace(0.0, 1.0, int(max(1, count)), dtype=np.float32)
            rgb = np.empty((t.shape[0], 3), dtype=np.float32)
            segment_count = len(stops) - 1
            for idx, step in enumerate(t):
                scaled = float(step) * float(segment_count)
                seg_idx = int(min(segment_count - 1, max(0, int(np.floor(scaled)))))
                local_t = scaled - float(seg_idx)
                c1 = stops[seg_idx]
                c2 = stops[min(seg_idx + 1, len(stops) - 1)]
                rgb[idx] = c1 * (1.0 - local_t) + c2 * local_t
            a = np.full((t.shape[0], 1), float(alpha), dtype=np.float32)
            return np.concatenate([rgb, a], axis=1)

    base_rgb = np.array(spec_col[:3], dtype=np.float32)
    base = np.array([base_rgb[0], base_rgb[1], base_rgb[2], float(alpha)], dtype=np.float32)
    return np.tile(base[None, :], (int(max(1, count)), 1))

def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    raw = str(hex_color or "#ffffff").strip()
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if len(raw) >= 7:
        try:
            return (int(raw[1:3], 16), int(raw[3:5], 16), int(raw[5:7], 16), int(max(0, min(255, alpha))))
        except Exception:
            pass
    return (255, 255, 255, int(max(0, min(255, alpha))))


def _text_letter_spacing_px(size_px: float, letter_spacing: float) -> float:
    # Inspector letterSpacing is tracking in px (CapCut-like; allow tight negative).
    _ = size_px
    return float(max(-40.0, min(80.0, float(letter_spacing or 0.0))))


def _measure_spaced_text(
    draw: Any,
    text: str,
    font: Any,
    *,
    stroke_width: int,
    spacing: int,
    letter_spacing: float,
    align: str = "left",
    box_width: float = 0.0,
) -> tuple[int, int, list[tuple[str, float, float]]]:
    """Return width, height, and per-glyph (char, x, y) layout for letter-spacing."""
    lines = str(text).split("\n")
    layouts: list[tuple[str, float, float]] = []
    line_widths: list[float] = []
    line_layouts: list[list[tuple[str, float, float]]] = []
    y = 0.0
    line_gap = float(spacing)
    align_key = str(align or "left").lower().strip()
    for line_i, line in enumerate(lines):
        x = 0.0
        line_h = float(getattr(font, "size", 16) or 16)
        row: list[tuple[str, float, float]] = []
        if not line:
            line_layouts.append([("\n", 0.0, y)])
            line_widths.append(0.0)
            y += line_h + (line_gap if line_i < len(lines) - 1 else 0.0)
            continue
        for ch in line:
            bbox = draw.textbbox((0, 0), ch, font=font, stroke_width=stroke_width)
            cw = float(max(1, bbox[2] - bbox[0]))
            ch_h = float(max(1, bbox[3] - bbox[1]))
            line_h = max(line_h, ch_h)
            row.append((ch, x, y))
            x += cw + float(letter_spacing)
        width = x - float(letter_spacing) if letter_spacing else x
        line_layouts.append(row)
        line_widths.append(float(max(0.0, width)))
        y += line_h + (line_gap if line_i < len(lines) - 1 else 0.0)

    content_w = max(line_widths) if line_widths else 1.0
    target_w = float(box_width) if float(box_width or 0.0) > 8.0 else content_w
    target_w = max(target_w, content_w)

    for row, width in zip(line_layouts, line_widths):
        if not row:
            continue
        if align_key == "right":
            shift = target_w - width
        elif align_key == "center":
            shift = (target_w - width) * 0.5
        elif align_key == "justify" and len(row) > 1 and width > 1.0 and target_w > width + 0.5:
            # Distribute extra space across inter-glyph gaps (simple justify).
            gaps = len(row) - 1
            extra = (target_w - width) / float(gaps)
            acc = 0.0
            for i, (ch, x, yy) in enumerate(row):
                layouts.append((ch, x + acc, yy))
                if i < gaps:
                    acc += extra
            continue
        else:
            shift = 0.0
        for ch, x, yy in row:
            layouts.append((ch, x + shift, yy))

    return int(max(1, round(target_w))), int(max(1, round(y))), layouts


def _pil_align(align: str) -> str:
    key = str(align or "left").lower().strip()
    if key == "center":
        return "center"
    if key == "right":
        return "right"
    # Pillow has no true justify for multiline_text; left is the fallback.
    return "left"


def _measure_shaped_text(
    draw: Any,
    text: str,
    font: Any,
    *,
    stroke_width: int,
    spacing: int,
    align: str = "left",
    box_width: float = 0.0,
) -> tuple[int, int, list[tuple[str, float, float]]]:
    """Layout complex-script text as whole lines (never per codepoint).

    Returns width, height, and (line, x, y) rows so center/right can honor box width
    while keeping OpenType clusters intact.
    """
    lines = str(text).split("\n")
    line_gap = float(spacing)
    align_key = str(align or "left").lower().strip()
    if align_key == "justify":
        align_key = "left"
    measured: list[tuple[str, float, float, float]] = []  # line, width, y, height
    y = 0.0
    content_w = 1.0
    for line_i, line in enumerate(lines):
        if not line:
            line_h = float(getattr(font, "size", 16) or 16)
            line_w = 0.0
        else:
            bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
            line_w = float(max(1, bbox[2] - bbox[0]))
            line_h = float(max(1, bbox[3] - bbox[1]))
        content_w = max(content_w, line_w)
        measured.append((line, line_w, y, line_h))
        y += line_h + (line_gap if line_i < len(lines) - 1 else 0.0)
    target_w = float(box_width) if float(box_width or 0.0) > 8.0 else content_w
    target_w = max(target_w, content_w)
    layouts: list[tuple[str, float, float]] = []
    for line, line_w, yy, _line_h in measured:
        if align_key == "right":
            shift = target_w - line_w
        elif align_key == "center":
            shift = (target_w - line_w) * 0.5
        else:
            shift = 0.0
        layouts.append((line if line else "\n", shift, yy))
    return int(max(1, round(target_w))), int(max(1, round(y))), layouts


def _draw_spaced_text(
    draw: Any,
    layouts: list[tuple[str, float, float]],
    *,
    origin: tuple[float, float],
    font: Any,
    fill: Any,
    stroke_width: int = 0,
    stroke_fill: Any = None,
) -> None:
    ox, oy = origin
    for ch, x, y in layouts:
        if ch == "\n":
            continue
        draw.text(
            (ox + x, oy + y),
            ch,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )


def _build_text_gradient_fill(
    width: int,
    height: int,
    colors: list[str],
    direction: str,
) -> Any:
    from PIL import Image

    stops = [c for c in colors if c][:5]
    if len(stops) < 2:
        stops = [stops[0] if stops else "#ffffff", "#22d3ee"]
    rgbs = [_hex_to_rgba(c)[:3] for c in stops]
    arr = np.zeros((max(1, height), max(1, width), 4), dtype=np.uint8)
    h = arr.shape[0]
    w = arr.shape[1]
    yy, xx = np.mgrid[0:h, 0:w]
    key = str(direction or "vertical").lower()
    if key == "horizontal":
        t = xx.astype(np.float32) / float(max(1, w - 1))
    elif key == "diagonal":
        t = (xx.astype(np.float32) / float(max(1, w - 1)) + yy.astype(np.float32) / float(max(1, h - 1))) * 0.5
    else:
        t = yy.astype(np.float32) / float(max(1, h - 1))
    scaled = t * float(len(rgbs) - 1)
    left = np.floor(scaled).astype(np.int32)
    right = np.minimum(left + 1, len(rgbs) - 1)
    blend = (scaled - left).astype(np.float32)
    for channel in range(3):
        c0 = np.array([rgb[channel] for rgb in rgbs], dtype=np.float32)[left]
        c1 = np.array([rgb[channel] for rgb in rgbs], dtype=np.float32)[right]
        arr[:, :, channel] = np.clip(c0 * (1.0 - blend) + c1 * blend, 0, 255).astype(np.uint8)
    arr[:, :, 3] = 255
    return Image.fromarray(arr, mode="RGBA")


def _screen_composite(base: Any, overlay: Any) -> Any:
    """Screen-blend ``overlay`` onto ``base`` (additive neon look)."""
    from PIL import Image

    a = np.asarray(base.convert("RGBA"), dtype=np.float32) / 255.0
    b = np.asarray(overlay.convert("RGBA"), dtype=np.float32) / 255.0
    out = np.empty_like(a)
    out[:, :, :3] = 1.0 - (1.0 - a[:, :, :3]) * (1.0 - b[:, :, :3])
    out[:, :, 3] = np.clip(a[:, :, 3] + b[:, :, 3] * (1.0 - a[:, :, 3]), 0.0, 1.0)
    return Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8), mode="RGBA")


def _tint_glow_layer(
    mask: Any,
    *,
    glow_color: str,
    glow_mode: str,
    glow_gradient_colors: list | None,
    glow_gradient_direction: str,
    strength: float,
) -> Any:
    """Colorize an alpha silhouette into a glow layer (solid or gradient)."""
    from PIL import Image

    alpha = mask.split()[-1] if mask.mode == "RGBA" else mask.convert("L")
    # Scale alpha by glow strength.
    a = np.asarray(alpha, dtype=np.float32)
    a = np.clip(a * float(max(0.0, min(1.0, strength))), 0, 255).astype(np.uint8)
    alpha = Image.fromarray(a, mode="L")
    mode = str(glow_mode or "solid").lower().strip()
    stops = [c for c in (glow_gradient_colors or []) if c]
    if mode == "gradient" and len(stops) >= 2:
        grad = _build_text_gradient_fill(
            mask.width,
            mask.height,
            stops,
            str(glow_gradient_direction or "horizontal"),
        )
        layer = Image.new("RGBA", mask.size, (0, 0, 0, 0))
        layer.paste(grad, (0, 0), alpha)
        return layer
    rgba = _hex_to_rgba(str(glow_color or "#ff4fd8"), 255)
    layer = Image.new("RGBA", mask.size, (*rgba[:3], 0))
    layer.putalpha(alpha)
    return layer


def _render_neon_glow(
    paint_fn,
    *,
    img_w: int,
    img_h: int,
    x0: float,
    y0: float,
    glow_amt: float,
    glow_blur_px: float,
    glow_color: str,
    glow_mode: str = "solid",
    glow_gradient_colors: list | None = None,
    glow_gradient_direction: str = "horizontal",
) -> Any:
    """Multi-pass bloom: wide halo + mid bloom + tight core (CapCut-like neon)."""
    from PIL import Image, ImageDraw, ImageFilter

    # Silhouette mask (white text on transparent).
    mask = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    md = ImageDraw.Draw(mask)
    paint_fn(md, x0, y0, (255, 255, 255, 255), (255, 255, 255, 255))

    base_blur = float(max(1.0, glow_blur_px))
    strength = float(max(0.0, min(1.0, glow_amt)))
    # Three bloom radii: outer halo, mid glow, tight rim.
    passes = (
        (base_blur * 2.4, strength * 0.45),
        (base_blur * 1.15, strength * 0.75),
        (max(1.0, base_blur * 0.35), strength * 0.95),
    )
    out = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    for radius, amt in passes:
        blurred = mask.filter(ImageFilter.GaussianBlur(radius=max(1, int(round(radius)))))
        tinted = _tint_glow_layer(
            blurred,
            glow_color=glow_color,
            glow_mode=glow_mode,
            glow_gradient_colors=glow_gradient_colors,
            glow_gradient_direction=glow_gradient_direction,
            strength=amt,
        )
        out = _screen_composite(out, tinted)
    return out


def _render_text_rgba(
    text: str,
    size_px: float,
    color: str,
    stroke_color: str,
    stroke_width: float,
    shadow: float,
    *,
    font_family: str = "arial",
    bold: bool = False,
    italic: bool = False,
    letter_spacing: float = 0.0,
    line_spacing: float = 1.15,
    align: str = "left",
    box_width: float = 0.0,
    fill_mode: str = "solid",
    gradient_colors: list | None = None,
    gradient_direction: str = "vertical",
    glow: float = 0.0,
    glow_color: str = "#ff4fd8",
    glow_blur: float = 8.0,
    glow_mode: str = "solid",
    glow_gradient_colors: list | None = None,
    glow_gradient_direction: str = "horizontal",
    shadow_blur: float = 0.0,
    extrude_depth: float = 0.0,
    extrude_color: str = "#1a1a1a",
) -> tuple[np.ndarray, int, int]:
    from pathlib import Path

    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    t = str(text or "").strip()
    if not t:
        arr0 = np.zeros((1, 1, 4), dtype=np.uint8)
        return arr0, 1, 1
    # Allow large rasters so 1080p/4K stay proportional to the 450-base template.
    s = int(max(5, min(2048, int(round(float(size_px))))))
    family = str(font_family or "arial").strip()
    from features.video.lib.system_fonts import resolve_font_for_text, text_needs_complex_shaping

    font_path = resolve_font_for_text(family, t, bold=bool(bold), italic=bool(italic))
    try:
        font = ImageFont.truetype(font_path, s)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", s)
        except Exception:
            font = ImageFont.load_default()
    # Skip synthetic shear when we already loaded a real italic face.
    face_is_italic = "italic" in Path(str(font_path)).stem.lower() or "oblique" in Path(str(font_path)).stem.lower()

    sw = int(max(0, min(24, int(round(float(stroke_width))))))
    sh = float(max(0.0, min(1.0, float(shadow))))
    shadow_px = int(round(2.0 + 4.0 * sh)) if sh > 0 else 0
    shadow_blur_px = float(max(0.0, min(40.0, float(shadow_blur or 0.0))))
    glow_amt = float(max(0.0, min(1.0, float(glow or 0.0))))
    glow_blur_px = float(max(0.0, min(48.0, float(glow_blur or 8.0))))
    glow_fill_mode = str(glow_mode or "solid").lower().strip()
    if glow_fill_mode not in ("solid", "gradient"):
        glow_fill_mode = "solid"
    glow_stops = list(glow_gradient_colors or []) if isinstance(glow_gradient_colors, list) else []
    glow_dir = str(glow_gradient_direction or "horizontal")
    extrude_n = int(max(0, min(24, int(round(float(extrude_depth or 0.0))))))
    mode = str(fill_mode or "solid").lower().strip()
    if mode not in ("solid", "gradient", "neon"):
        mode = "solid"
    complex_script = text_needs_complex_shaping(t)
    # Per-character tracking breaks OpenType clusters (Khmer, Thai, Arabic, …).
    tracking = 0.0 if complex_script else _text_letter_spacing_px(s, letter_spacing)
    # Preset/inspector lineSpacing is a multiplier (1.0 = tight, 1.15 default).
    # Pillow ``spacing`` is extra pixels between lines beyond the glyph height.
    line_mult = float(max(0.8, min(2.5, float(line_spacing or 1.15))))
    pil_line_spacing = int(round(s * max(0.0, line_mult - 1.0)))
    align_key = str(align or "left").lower().strip()
    box_w = float(max(0.0, box_width or 0.0))
    # Scale authored box width with the same size scale used for glyphs.
    # Callers pass already-scaled letter_spacing/size; box_width is also scaled.
    pil_align = _pil_align("left" if (complex_script and align_key == "justify") else align_key)

    measure = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(measure)
    layouts: list[tuple[str, float, float]] = []
    if complex_script:
        # Keep whole lines shaped; never walk codepoints for layout.
        text_w, text_h, layouts = _measure_shaped_text(
            d0,
            t,
            font,
            stroke_width=sw,
            spacing=pil_line_spacing,
            align=align_key,
            box_width=box_w,
        )
        bbox = (0, 0, text_w, text_h)
    else:
        # Spaced layout when aligning/justifying or tracking is set,
        # so multi-line wraps share one box width.
        use_layout = abs(tracking) > 0.01 or align_key in {"center", "right", "justify"} or box_w > 8.0
        if use_layout:
            text_w, text_h, layouts = _measure_spaced_text(
                d0,
                t,
                font,
                stroke_width=sw,
                spacing=pil_line_spacing,
                letter_spacing=tracking,
                align=align_key,
                box_width=box_w,
            )
            bbox = (0, 0, text_w, text_h)
        else:
            bbox = d0.multiline_textbbox((0, 0), t, font=font, stroke_width=sw, spacing=pil_line_spacing)
            text_w = int(max(1, bbox[2] - bbox[0]))
            text_h = int(max(1, bbox[3] - bbox[1]))

    pad_glow = int(round(glow_blur_px * 2.8)) if glow_amt > 0.01 else 0
    pad_shadow = int(round(shadow_blur_px + shadow_px)) if sh > 0.01 else 0
    # Keep padding tight so the CapCut selection frame matches glyphs.
    # Old ``max(6, size*0.35)`` floor made text look inset / box look offset.
    effect_pad = float(sw) * 1.2 + float(extrude_n) + float(max(pad_glow, pad_shadow))
    pad = int(max(1, round(effect_pad + (2.0 if effect_pad > 0.5 else 1.0))))
    img_w = int(max(1, text_w + pad * 2))
    img_h = int(max(1, text_h + pad * 2))
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0 = float(pad - int(bbox[0]))
    y0 = float(pad - int(bbox[1]))

    def _paint(target_draw: Any, ox: float, oy: float, fill: Any, stroke_fill: Any | None = None) -> None:
        if layouts:
            _draw_spaced_text(
                target_draw,
                layouts,
                origin=(ox, oy),
                font=font,
                fill=fill,
                stroke_width=sw,
                stroke_fill=stroke_fill if stroke_fill is not None else fill,
            )
        else:
            target_draw.multiline_text(
                (ox, oy),
                t,
                font=font,
                fill=fill,
                stroke_width=sw,
                stroke_fill=stroke_fill if stroke_fill is not None else fill,
                spacing=pil_line_spacing,
                align=pil_align,
            )

    # Multi-pass neon bloom (works on any preset when Glow > 0).
    if glow_amt > 0.01:
        glow_layer = _render_neon_glow(
            _paint,
            img_w=img_w,
            img_h=img_h,
            x0=x0,
            y0=y0,
            glow_amt=glow_amt,
            glow_blur_px=glow_blur_px,
            glow_color=str(glow_color or color or "#ff4fd8"),
            glow_mode=glow_fill_mode,
            glow_gradient_colors=glow_stops,
            glow_gradient_direction=glow_dir,
        )
        img = _screen_composite(img, glow_layer)
        d = ImageDraw.Draw(img)

    # Offset shadow (optionally blurred).
    if shadow_px > 0:
        shadow_layer = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        s_rgba = (0, 0, 0, int(255 * sh))
        _paint(sd, x0 + shadow_px, y0 + shadow_px, s_rgba, s_rgba)
        if shadow_blur_px > 0.5:
            shadow_layer = shadow_layer.filter(
                ImageFilter.GaussianBlur(radius=max(1, int(round(shadow_blur_px))))
            )
        img = Image.alpha_composite(img, shadow_layer)
        d = ImageDraw.Draw(img)

    # 3D extrusion: stacked offset silhouettes behind the fill.
    if extrude_n > 0:
        e_rgba = _hex_to_rgba(str(extrude_color or "#1a1a1a"), 255)
        for step in range(extrude_n, 0, -1):
            _paint(d, x0 + step, y0 + step, e_rgba, e_rgba)

    fill_hex = str(color or "#ffffff")
    stroke_hex = str(stroke_color or "#000000")
    use_gradient = mode == "gradient" and isinstance(gradient_colors, list) and len([c for c in gradient_colors if c]) >= 2
    # Neon fill: bright white-hot core over the bloom (reference neon-sign look).
    if mode == "neon" and not use_gradient:
        fill_hex = "#ffffff"

    if use_gradient:
        # Masked gradient fill: draw alpha mask then composite gradient through it.
        mask = Image.new("L", (img_w, img_h), 0)
        md = ImageDraw.Draw(mask)
        if layouts:
            for ch, x, y in layouts:
                if ch == "\n":
                    continue
                md.text((x0 + x, y0 + y), ch, font=font, fill=255, stroke_width=0)
        else:
            md.multiline_text((x0, y0), t, font=font, fill=255, spacing=pil_line_spacing, align=pil_align)
        grad = _build_text_gradient_fill(img_w, img_h, list(gradient_colors or []), str(gradient_direction or "vertical"))
        fill_layer = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        fill_layer.paste(grad, (0, 0), mask)
        if sw > 0:
            stroke_layer = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(stroke_layer)
            _paint(sd, x0, y0, (0, 0, 0, 0), _hex_to_rgba(stroke_hex, 255))
            img = Image.alpha_composite(img, stroke_layer)
        img = Image.alpha_composite(img, fill_layer)
    else:
        # Neon mode still uses solid fill; glow already applied above.
        _paint(d, x0, y0, fill_hex, stroke_hex)

    if italic and not face_is_italic:
        # Simple shear for italic when the face isn't already oblique.
        img = img.transform(
            img.size,
            Image.Transform.AFFINE,
            (1, 0.22, -int(0.1 * img.height), 0, 1, 0),
            resample=Image.Resampling.BICUBIC,
        )
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
    n = int(len(overlays))
    if len(tex_list) > n:
        for tx in tex_list[n:]:
            try:
                if tx is not None:
                    tx.release()
            except Exception:
                pass
        del tex_list[n:]
    if len(key_list) > n:
        del key_list[n:]
    if len(wh_list) > n:
        del wh_list[n:]
    if len(tex_list) < n:
        tex_list.extend([None] * (n - len(tex_list)))
    if len(key_list) < n:
        key_list.extend([None] * (n - len(key_list)))
    if len(wh_list) < n:
        wh_list.extend([(0, 0)] * (n - len(wh_list)))
    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
    for idx, o in enumerate(overlays):
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
        font_family = str(o.get("fontFamily", "arial") or "arial")
        bold = bool(o.get("bold", False))
        italic = bool(o.get("italic", False))
        opacity_mul = float(o.get("opacity", 1.0) if "opacity" in o else 1.0)
        letter_spacing = float(o.get("letterSpacing", 0.0) if "letterSpacing" in o else 0.0)
        line_spacing = float(o.get("lineSpacing", 1.15) if "lineSpacing" in o else 1.15)
        align = str(o.get("align", "left") or "left")
        box_width = float(o.get("boxWidth", 0.0) if "boxWidth" in o else 0.0)
        fill_mode = str(o.get("fillMode", "solid") or "solid")
        gradient_colors = o.get("gradientColors") if isinstance(o.get("gradientColors"), list) else []
        gradient_direction = str(o.get("gradientDirection", "vertical") or "vertical")
        glow_amt = float(o.get("glow", 0.0) if "glow" in o else 0.0)
        glow_color = str(o.get("glowColor", "#ff4fd8") or "#ff4fd8")
        glow_blur = float(o.get("glowBlur", 8.0) if "glowBlur" in o else 8.0)
        glow_mode = str(o.get("glowMode", "solid") or "solid")
        glow_gradient_colors = o.get("glowGradientColors") if isinstance(o.get("glowGradientColors"), list) else []
        glow_gradient_direction = str(o.get("glowGradientDirection", "horizontal") or "horizontal")
        shadow_blur = float(o.get("shadowBlur", 0.0) if "shadowBlur" in o else 0.0)
        extrude_depth = float(o.get("extrudeDepth", 0.0) if "extrudeDepth" in o else 0.0)
        extrude_color = str(o.get("extrudeColor", "#1a1a1a") or "#1a1a1a")
        grad_key = ",".join(str(c) for c in gradient_colors)
        glow_grad_key = ",".join(str(c) for c in glow_gradient_colors)
        # Scale with output height / renderBaseHeight (no 4× cap — preview ↔ export match).
        scale = float(max(0.05, min(16.0, float(sf or 1.0))))
        key = (
            f"{text}|{size_px:.2f}|{col}|{scol}|{sw:.2f}|{sh:.2f}|{font_family}|{int(bold)}|{int(italic)}"
            f"|{letter_spacing:.2f}|{line_spacing:.2f}|{align}|{box_width:.1f}|{fill_mode}|{grad_key}|{gradient_direction}"
            f"|{glow_amt:.2f}|{glow_color}|{glow_blur:.2f}|{glow_mode}|{glow_grad_key}|{glow_gradient_direction}"
            f"|{shadow_blur:.2f}|{extrude_depth:.2f}|{extrude_color}|sf:{scale:.4f}"
        )
        if key_list[idx] != key or tex_list[idx] is None:
            arr, tw, th = _render_text_rgba(
                text,
                size_px * scale,
                col,
                scol,
                sw * scale,
                sh,
                font_family=font_family,
                bold=bold,
                italic=italic,
                letter_spacing=letter_spacing * scale,
                line_spacing=line_spacing,
                align=align,
                box_width=box_width * scale,
                fill_mode=fill_mode,
                gradient_colors=gradient_colors,
                gradient_direction=gradient_direction,
                glow=glow_amt,
                glow_color=glow_color,
                glow_blur=glow_blur * scale,
                glow_mode=glow_mode,
                glow_gradient_colors=glow_gradient_colors,
                glow_gradient_direction=glow_gradient_direction,
                shadow_blur=shadow_blur * scale,
                extrude_depth=extrude_depth * scale,
                extrude_color=extrude_color,
            )
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
        draw_w = float(tw) * scale_t
        draw_h = float(th) * scale_t
        qx, qy = _text_quad_center_offset(anchor_t, draw_w, draw_h)
        prog_text["tex_text"].value = 2
        tx.use(location=2)
        prog_text["out_size"].value = (float(w), float(h))
        prog_text["text_px"].value = (
            float(ax) - float(w) * 0.5 + dx + qx,
            float(ay) - float(h) * 0.5 + dy + qy,
        )
        prog_text["text_size_px"].value = (draw_w, draw_h)
        prog_text["text_opacity"].value = float(max(0.0, min(1.0, opacity * opacity_mul)))
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

from shared.lib.subprocess_utils import popen_hidden


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
    enc = popen_hidden(cmd, stdin=subprocess.PIPE, stderr=err_file)
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
        enc = popen_hidden(cmd2, stdin=subprocess.PIPE, stderr=err_file)
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


def _text_quad_center_offset(anchor: str, tw: float, th: float) -> tuple[float, float]:
    """Shift from anchor point to texture-quad center (shader centers on text_px).

    Left/right pin that edge so title-list numbers share one vertical line.
    Top/bottom pin that edge so list rows stack without vertical drift/overlap.
    """
    a = str(anchor or "").lower().strip()
    half_w = float(tw) * 0.5
    half_h = float(th) * 0.5
    # OpenGL Y-up: top of a centered quad is at cy + half_h.
    if "left" in a:
        ox = half_w
    elif "right" in a:
        ox = -half_w
    else:
        ox = 0.0
    if "top" in a:
        oy = -half_h
    elif "bottom" in a:
        oy = half_h
    else:
        oy = 0.0
    return (ox, oy)


def _smooth_env(
    prev: float,
    target: float,
    smoothing: float,
    *,
    dt: float | None = None,
    ref_fps: float = 60.0,
) -> float:
    """Exponential envelope smooth.

    ``smoothing`` is the per-frame retention coeff as tuned in live preview (60 Hz).
    When ``dt`` is provided (export at 24 fps), convert so wall-clock response matches preview.
    """
    s = float(max(0.0, min(0.99, smoothing)))
    if dt is not None and float(dt) > 0.0 and float(ref_fps) > 0.0:
        s = float(s ** (float(ref_fps) * float(dt)))
        s = float(max(0.0, min(0.99, s)))
    t = float(max(0.0, min(1.0, target)))
    return float((float(prev) * s) + (t * (1.0 - s)))

def run_gpu_render(opts: GpuOptions) -> int:
    fps = int(max(1, min(60, int(opts.fps))))
    if fps <= 0:
        fps = 30
    # Keep encode FPS (24/30/…) for speed, but analyze audio at preview rate so
    # spectrum/particles react identically to paintGL (frame_idx = time * 60).
    ANALYSIS_FPS = 60

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
    text_overlays = template.get("textOverlays") if isinstance(template.get("textOverlays"), list) else []
    text_cache = {"tex": [], "key": [], "wh": []}

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
    # Same styled-quad particle path as live preview (not GL_POINTS).
    prog_particle_quads = _compile_particle_quads(ctx)
    particle_quad_vbo = ctx.buffer(reserve=4 * 8 * 6 * 2048)
    vao_particle_quads = ctx.vertex_array(
        prog_particle_quads,
        [(particle_quad_vbo, "2f 2f 4f", "in_pos", "in_uv", "in_col")],
    )

    # In the new format, the root template IS the spectrum container
    spectrum_container = template
    point_count = 1024 # Fixed to 1024 for high-res FFT
    
    # We no longer have spec_style or spec_tex for background scale/offset in the spectrum layer.
    # Background scale/offset is now handled via backgroundSettings (if added) or just defaults to 1.0/0.0
    bg_scale = 1.0
    bg_offset = (0.0, 0.0)

    analyzer = AudioAnalyzer(opts.mp3_path, fps=ANALYSIS_FPS, point_count=point_count)
    duration_sec = float(analyzer.info.duration_sec)
    # Encode at export fps, but sample audio analysis at preview fps (60).
    total_frames = int(max(1, int(np.ceil(duration_sec * float(fps)))))

    particles_cfg_raw = template.get("particlesSettings", {}) if isinstance(template.get("particlesSettings"), dict) else {}
    if not particles_cfg_raw and isinstance(template.get("particles"), dict):
        particles_cfg_raw = template.get("particles")  # legacy fallback
    particles_cfg = ParticleConfig(
        enabled=bool(particles_cfg_raw.get("enabled", True)),
        max_count=int(particles_cfg_raw.get("maxCount", particles_cfg_raw.get("count", 400))),
        spawn_rate=float(particles_cfg_raw.get("spawnRate", particles_cfg_raw.get("spawn_rate", 40.0))),
        lifetime_sec=float(particles_cfg_raw.get("lifetimeSec", particles_cfg_raw.get("lifetime_sec", 1.6))),
        spawn_radius=0.0,
        size=float(particles_cfg_raw.get("size", 2.0)) * sf,
        opacity=float(particles_cfg_raw.get("opacity", 0.35)),
        color=tuple(_as_rgb(particles_cfg_raw.get("color", "#ffffff"))),
        # Preview default speed is 15 (template_runtime clamp), not 120.
        speed=float(particles_cfg_raw.get("speed", 15.0)) * sf,
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
    bg_contrast = float(max(0.0, min(2.0, float(bg_settings_raw.get("contrast", 1.0) or 1.0))))
    bg_saturation = float(max(0.0, min(2.0, float(bg_settings_raw.get("saturation", 1.0) or 1.0))))
    bg_hue = float(max(-180.0, min(180.0, float(bg_settings_raw.get("hue", 0.0) or 0.0))))
    bg_react_bass = float(bg_settings_raw.get("reactivity", 0.0))
    bg_react_bass = float(max(0.0, min(20.0, bg_react_bass)))
    bg_smoothing = float(max(0.0, min(0.99, bg_settings_raw.get("smoothing", 0.8))))
    bg_motion_mode = str(bg_settings_raw.get("motionMode", "none") or "none")
    if bg_motion_mode not in ("none", "zoom", "vibrate", "both"):
        bg_motion_mode = "none"
    bg_motion_zoom_strength = float(bg_settings_raw.get("motionZoomStrength", 1.0) or 1.0)
    bg_motion_zoom_strength = float(max(0.0, min(20.0, bg_motion_zoom_strength)))
    bg_motion_vibrate_strength = float(bg_settings_raw.get("motionVibrateStrength", 1.0) or 1.0)
    bg_motion_vibrate_strength = float(max(0.0, min(20.0, bg_motion_vibrate_strength)))
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
    preview_bindings = template.get("previewBindings", {}) if isinstance(template.get("previewBindings"), dict) else {}
    spectrum_attach_to_logo = bool(preview_bindings.get("spectrumAttachToLogo", True))
    spectrum_logo_gap = float(max(0.0, float(preview_bindings.get("spectrumLogoGap", 0.0) or 0.0))) * sf
    logo_visible_radius_ratio = (
        _compute_visible_logo_radius_ratio(logo_rgba, logo_circle_mask)
        if spectrum_attach_to_logo and logo_rgba is not None
        else 1.0
    )
    logo_base_radius = (logo_size_base * 0.5) * sf
    logo_spin_enabled = bool(logo_raw.get("spinEnabled", False))
    logo_spin_dir = str(logo_raw.get("spinDirection", "cw") or "cw").strip().lower()
    if logo_spin_dir not in ("cw", "ccw"):
        logo_spin_dir = "cw"
    logo_spin_dir_s = 1.0 if logo_spin_dir == "cw" else -1.0
    logo_spin_speed_deg = float(logo_raw.get("spinSpeed", 0.0) or 0.0)
    logo_spin_speed_deg = float(max(0.0, min(720.0, logo_spin_speed_deg)))
    preview_bindings = template.get("previewBindings", {}) if isinstance(template.get("previewBindings"), dict) else {}
    spectrum_attach_to_logo = bool(preview_bindings.get("spectrumAttachToLogo", True))
    spectrum_logo_gap = float(max(0.0, float(preview_bindings.get("spectrumLogoGap", 0.0) or 0.0))) * sf
    logo_visible_radius_ratio = (
        _compute_visible_logo_radius_ratio(logo_rgba, logo_circle_mask)
        if spectrum_attach_to_logo and logo_rgba is not None
        else 1.0
    )

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
        if "bg_contrast" in prog_scene:
            prog_scene["bg_contrast"].value = float(bg_contrast)
        if "bg_saturation" in prog_scene:
            prog_scene["bg_saturation"].value = float(bg_saturation)
        if "bg_hue" in prog_scene:
            prog_scene["bg_hue"].value = float(bg_hue)

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

    # Encode may be 24 fps while preview paints at 60 Hz.
    # Use encode-frame dt so particle spawn/motion and envelope time constants
    # advance in wall-clock time (same as integrating preview's 1/60 steps).
    encode_dt = 1.0 / max(1.0, float(fps))
    dt = encode_dt
    p_bass_fast = 0.0
    p_bass_slow = 0.0
    p_kick_env = 0.0
    bg_audio_env = 0.0
    logo_audio_env = 0.0
    particle_audio_env = 0.0
    p_trigger_env = 0.0
    kick_fast_a = 1.0 - float(np.exp(-encode_dt / 0.06))
    kick_slow_a = 1.0 - float(np.exp(-encode_dt / 0.35))
    kick_decay = float(np.exp(-encode_dt / 0.18))
    audio_settings = template.get("audioSettings") if isinstance(template.get("audioSettings"), dict) else {}
    aud_smooth = float(max(0.0, min(0.99, float(audio_settings.get("smoothing", 0.8) or 0.8))))
    fft_smoothed = np.zeros(64, dtype=np.float32)
    particles_warmed = False

    _send({"status": "running", "message": "Preparing first frame...", "progress": 0.0})

    # --- Pre-compute spectrum mapping (once, outside frame loop) ---
    from ._spectrum_fast import (
        precompute_fft_mapping, fft_to_log_bins, smooth_and_mirror,
        generate_points_curved, generate_points_linear,
        build_waveform_vertices, build_bar_vertices, resolve_bar_pixel_width,
    )
    _fft_idx1, _fft_idx2, _fft_frac = precompute_fft_mapping(point_count)
    # Pre-compute frame-invariant template lookups
    _tpl_style_preset = str(template.get("style", "orbit-spikes")).lower().strip()
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
    _tpl_attached_to_logo = bool(spectrum_attach_to_logo and logo_rgba is not None)
    _tpl_attached_base_radius = float(max(0.0, (logo_base_radius * logo_scale_base * logo_visible_radius_ratio) + spectrum_logo_gap))
    _tpl_attached_layer_base_offset = _resolve_attached_layer_base_offset(_tpl_spectrum_layers, sf)
    last_analysis_idx = -1

    for i in range(total_frames):
        # Sample analysis at preview rate (60 Hz) for identical FFT/features at wall time T.
        time_sec = float(i) / float(max(1.0, float(fps)))
        analysis_idx = int(max(0, min(int(analyzer.info.frames) - 1, int(time_sec * float(ANALYSIS_FPS)))))
        # Advance temporal FFT smooth through every skipped 60 Hz analysis frame so
        # aud_smooth matches preview (which updates once per 60 Hz paint).
        for aidx in range(max(0, last_analysis_idx + 1), analysis_idx + 1):
            fft_step = analyzer.fft_for_frame(aidx)
            fft_log_step = fft_to_log_bins(fft_step, _fft_idx1, _fft_idx2, _fft_frac)
            fft_smoothed = fft_smoothed * aud_smooth + fft_log_step * (1.0 - aud_smooth)
        last_analysis_idx = analysis_idx
        fft = analyzer.fft_for_frame(analysis_idx)
        feats = analyzer.features_for_frame(analysis_idx)
        base_state = {
            "camera_shake.intensity": shake_intensity,
            "spectrum.scale": 1.0,
            "particles.spawn_rate": float(particles_cfg.spawn_rate),
            "effects.bloom.strength": float(bloom_cfg.strength),
            "effects.rgb_split.opacity": float(rgb_cfg.opacity),
        }
        state = apply_automations(base_state, feats, autos)
        bass = float(feats.get("bass", 0.0))

        # Kick / audio envelopes BEFORE spectrum (matches preview paintGL order).
        p_bass_fast = p_bass_fast * (1.0 - kick_fast_a) + bass * kick_fast_a
        p_bass_slow = p_bass_slow * (1.0 - kick_slow_a) + bass * kick_slow_a
        raw_kick = float(max(0.0, p_bass_fast - p_bass_slow))
        kick0 = float(max(0.0, min(1.0, raw_kick * 4.0)))
        p_kick_env = float(max(kick0, p_kick_env * kick_decay))
        kick_pow = float(max(0.0, min(1.0, p_kick_env))) ** 2
        bg_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.6))))
        bg_audio_env = _smooth_env(bg_audio_env, bg_audio_raw, bg_smoothing, dt=encode_dt)
        logo_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.8))))
        logo_audio_env = _smooth_env(logo_audio_env, logo_audio_raw, logo_smoothing, dt=encode_dt)
        ps_smoothing = float(max(0.0, min(0.99, particles_cfg_raw.get("smoothing", 0.65))))
        onset = float(feats.get("onset", 0.0) or 0.0)
        beat = float(feats.get("beat", 0.0) or 0.0)
        particle_audio_raw = float(
            max(0.0, min(1.0, max(kick_pow, bass, onset * 0.9, beat * 0.95)))
        )
        particle_audio_env = _smooth_env(particle_audio_env, particle_audio_raw, ps_smoothing, dt=encode_dt)
        spawn_trigger = str(particles_cfg_raw.get("spawnTrigger", "both") or "both")
        kick_like = float(max(kick_pow, beat))
        bass_like = float(max(bass, onset * 0.85, particle_audio_raw * 0.65))
        if spawn_trigger == "kick":
            trig_raw = kick_like
        elif spawn_trigger == "bass":
            trig_raw = bass_like
        else:
            trig_raw = float(max(kick_like, bass_like))
        trig_raw = float(max(0.0, min(1.0, trig_raw)))
        p_trigger_env = _smooth_env(p_trigger_env, trig_raw, ps_smoothing, dt=encode_dt)

        if tex_logo is not None and logo_enabled:
            base_radius = logo_base_radius
            s_logo = logo_scale_base * (1.0 + logo_audio_env * logo_react_bass)
            s_logo = max(0.05, min(4.0, s_logo))
            final_logo_size = base_radius * 2.0 * s_logo
            prog_logo["logo_size_px"].value = (final_logo_size, final_logo_size)
            if "logo_rot_rad" in prog_logo:
                angle = 0.0
                if logo_spin_enabled and logo_spin_speed_deg > 0.0:
                    angle = float(logo_spin_dir_s) * float(logo_spin_speed_deg) * 0.017453292519943295 * time_sec
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
        if bg_motion_mode in ("vibrate", "both"):
            bg_shake_target = float(max(0.0, bg_react_bass) * bg_audio_env * 18.0 * sf * bg_motion_vibrate_strength)
            bg_jx = (time.time() * 0.81 + i * 0.013) % 1.0
            bg_jy = (time.time() * 0.83 + i * 0.017) % 1.0
            bg_shake_state_x = bg_shake_state_x * bg_smoothing + ((bg_jx * 2.0 - 1.0) * bg_shake_target) * (1.0 - bg_smoothing)
            bg_shake_state_y = bg_shake_state_y * bg_smoothing + ((bg_jy * 2.0 - 1.0) * bg_shake_target) * (1.0 - bg_smoothing)
        else:
            bg_shake_state_x = 0.0
            bg_shake_state_y = 0.0
        prog_scene["bg_offset"].value = (
            float((-bg_user_off_x / max(1.0, float(w))) + (bg_shake_state_x / max(1.0, float(w)))),
            float((bg_user_off_y / max(1.0, float(h))) + (bg_shake_state_y / max(1.0, float(h)))),
        )
        if bg_motion_mode in ("zoom", "both"):
            bg_scale_live = float(1.0 + min(2.5, max(0.0, bg_audio_env * bg_react_bass * 0.04 * bg_motion_zoom_strength)))
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
        prog_scene["time_sec"].value = float(time_sec)
        prog_scene["bg_brightness"].value = float(max(0.0, min(3.0, bg_brightness * (1.0 + bg_audio_env * bg_react_bass))))
        if "bg_contrast" in prog_scene:
            prog_scene["bg_contrast"].value = float(bg_contrast)
        if "bg_saturation" in prog_scene:
            prog_scene["bg_saturation"].value = float(bg_saturation)
        if "bg_hue" in prog_scene:
            prog_scene["bg_hue"].value = float(bg_hue)
            
        # We already set logo_px above, so we don't overwrite it with just shake_state here
        # prog_scene["logo_px"].value = (float(shake_state_x), float(shake_state_y))
        vao_quad_scene.render(mode=moderngl.TRIANGLE_STRIP)

        scale = float(state.get("spectrum.scale", 1.0))
        rotation_deg = float(spectrum_container.get("rotation_deg", 0.0)) if isinstance(spectrum_container, dict) else 0.0
        
        spectrum_layers = _tpl_spectrum_layers
        if _tpl_spectrum_enabled and not spectrum_layers:
            try:
                from visualizer.template_runtime import default_renderer_template, normalize_renderer_template

                fallback = normalize_renderer_template(default_renderer_template()).get("layers") or []
                spectrum_layers = [dict(x) for x in fallback if isinstance(x, dict)]
            except Exception:
                spectrum_layers = []

        template_style_preset = _tpl_style_preset
        react_gain = _tpl_react_gain
        
        # 1) Logarithmic Mapping already applied via analysis-frame catch-up above.
        BINS = 64
        rg = float(max(0.1, min(8.0, react_gain)))
        fft_s = np.clip(fft_smoothed * rg, 0.0, 2.5).astype(np.float32)
        
        c_pos = _get_anchor_coords(_tpl_anchor_val, _tpl_off_x, _tpl_off_y, w, h)
        cx = c_pos[0] + float(shake_state_x)
        cy = c_pos[1] + float(shake_state_y)
        
        for sl in spectrum_layers:
            style_preset = _resolve_export_spectrum_style(template_style_preset, sl)
            curved = bool(sl.get("curved", False))
            mirrored = bool(sl.get("mirrored", False))
            bar_width = float(sl.get("barWidth", 4.0)) * sf
            bar_height_mult = _audio_bar_height_mult(template)
            # Match preview default thickness (30), not the old export fallback (150).
            thickness = float(sl.get("thickness", 30.0)) * sf * bar_height_mult
            gravity = str(sl.get("gravity", "normal")).lower().strip()
            
            logo_visual_radius = logo_base_radius * logo_scale_base
            radius_offset = float(sl.get("radiusOffset", 0.0)) * sf
            radius = _resolve_spectrum_layer_radius(
                attached_to_logo=_tpl_attached_to_logo,
                attached_base_radius=_tpl_attached_base_radius,
                attached_layer_base_offset=_tpl_attached_layer_base_offset,
                logo_visual_radius=logo_visual_radius,
                bar_width=bar_width,
                radius_offset=radius_offset,
            )
            
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

                cols = _build_spectrum_vertex_colors(color_cfg, spec_col, n, pass_alpha)

                bw = resolve_bar_pixel_width(pass_bar_width, base_total_length / max(1, n))

                if style_preset in ("aurora-ribbon", "magma-ridge", "plasma-bloom", "soft-waveform", "mountain", "liquid", "continuous-waveform"):
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
                    bar_out = build_bar_vertices(
                        px_arr, py_arr, dx_arr, dy_arr, val_arr, cx, cy, w, h,
                        bw, style_preset, sf, logo_audio_env, particle_audio_env,
                        colors=cols,
                    )
                    if isinstance(bar_out, tuple):
                        pos, colsi = bar_out
                    else:
                        pos = bar_out
                        colsi = np.repeat(cols, 6, axis=0)

                    verts = np.column_stack([pos, colsi]).astype(np.float32)
                    if verts.nbytes > line_vbo.size:
                        line_vbo.orphan(size=verts.nbytes)
                    line_vbo.write(verts.tobytes())
                    vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(pos.shape[0]))

        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        spawn_rate = float(particles_cfg_raw.get("spawnRate", particles_cfg_raw.get("spawn_rate", particles_cfg.spawn_rate)))
        lifetime_sec = float(particles_cfg_raw.get("lifetimeSec", particles_cfg_raw.get("lifetime_sec", 1.6)))
        # Preview default / template_runtime clamp uses ~15, not 120.
        speed_base = float(particles_cfg_raw.get("speed", 15.0))
        prb = float(particles_cfg_raw.get("reactivity", 0.5))
        pt_size = float(particles_cfg_raw.get("size", 2.0))
        pt_color = tuple(_as_rgb(particles_cfg_raw.get("color", "#ffffff")))
        pt_count = int(particles_cfg_raw.get("maxCount", particles_cfg_raw.get("count", 400)))
        pt_opacity = float(particles_cfg_raw.get("opacity", particles_cfg.opacity))
        # Match preview reactivity range (0–1), not the old export 0.1–0.5 clamp.
        prb = float(max(0.0, min(1.0, prb)))

        spawn_mode = str(particles_cfg_raw.get("spawnMode", "always") or "always")
        spawn_threshold = float(particles_cfg_raw.get("spawnThreshold", 0.15) or 0.15)
        spawn_threshold = float(max(0.0, min(1.0, spawn_threshold)))
        if spawn_mode == "reactiveOnly" and p_trigger_env < spawn_threshold:
            # Preview never goes fully silent while particles are enabled.
            spawn_rate = float(max(12.0, spawn_rate * 0.12))
        else:
            spawn_rate = spawn_rate * float(0.2 + particle_audio_env * (1.1 + prb * 2.8))
            spawn_rate = float(max(12.0, spawn_rate))
        spawn_rate = float(max(0.0, min(20000.0, spawn_rate)))

        logo_visual_radius = float(logo_base_radius * logo_scale_base)
        if logo_enabled and (tex_logo is not None):
            spawn_radius = float(max(0.0, logo_visual_radius + max(2.0 * sf, pt_size * sf)))
        else:
            spawn_radius = float(max(min(w, h) * 0.22, pt_size * sf * 6.0))
        speed_boost = float(18.0 + particle_audio_env * (50.0 + prb * 130.0))
        speed2 = speed_base * speed_boost * sf
        speed2 = float(max(0.0, min(2500.0, speed2)))

        try:
            from features.video.lib.particle_color_engine import (
                extract_particle_color_model,
                palette_colors_to_rgb_tuple,
            )

            color_model = extract_particle_color_model(particles_cfg_raw)
            palette_rgb = palette_colors_to_rgb_tuple(list(color_model.get("paletteColors") or []))
            color_mode = str(color_model.get("mode") or "solid")
        except Exception:
            palette_rgb = ()
            color_mode = "solid"
        
        particles.update_cfg(
            ParticleConfig(
                enabled=bool(particles_cfg_raw.get("enabled", True)),
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
                travel_mode=str(particles_cfg_raw.get("travelMode", "spawnFlow") or "spawnFlow"),
                color_mode=color_mode,
                palette_colors=palette_rgb,
            )
        )
        particles.update(encode_dt, feats)
        # Draw particles over spectrum (same styled quads as live preview).
        if particles_cfg_raw.get("enabled", True):
            pos = particles._pos if hasattr(particles, "_pos") else np.zeros((0, 2), dtype=np.float32)
            if pos.shape[0] <= 0 and spawn_rate > 0.0 and not particles_warmed:
                particles.update(0.35, feats)
                particles_warmed = True
                pos = particles._pos if hasattr(particles, "_pos") else np.zeros((0, 2), dtype=np.float32)
            if pos.shape[0]:
                p = pos.astype(np.float32)
                xs2 = p[:, 0] / float(w) * 2.0 - 1.0
                ys2 = 1.0 - (p[:, 1] / float(h) * 2.0)
                sz = particles._size.astype(np.float32) if hasattr(particles, "_size") else np.ones((p.shape[0],), dtype=np.float32)
                pts = np.column_stack([xs2, ys2, sz]).astype(np.float32)
                particle_rgbs = particles._rgb if hasattr(particles, "_rgb") else None
                colors_rgba = build_particle_rgba_rows(
                    settings=particles_cfg_raw,
                    particle_rgbs=particle_rgbs,
                    reactive_env=float(particle_audio_env),
                    trigger_env=float(p_trigger_env),
                )
                variant = str(particles_cfg_raw.get("variant", "classic") or "classic")
                style = str(particles_cfg_raw.get("style", "dot") or "dot")
                pt_style = _resolve_particle_style_index(variant, style)
                style_scale = {0: 1.0, 1: 2.0, 2: 1.5, 3: 1.5, 4: 2.0}.get(int(pt_style), 1.0)
                pt_size_px = float(max(1.0, pt_size * (2.0 if style == "bokeh" else 1.5) * sf))
                base_px = float(max(2.5, pt_size_px)) * style_scale
                _render_particle_styled_quads(
                    ctx,
                    prog_particle_quads=prog_particle_quads,
                    particle_quad_vbo=particle_quad_vbo,
                    vao_particle_quads=vao_particle_quads,
                    pts=pts,
                    colors_rgba=colors_rgba,
                    pt_style=int(pt_style),
                    w=w,
                    h=h,
                    pt_size=base_px,
                )

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
    text_cache = {"tex": [], "key": [], "wh": []}

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
    bg_contrast = float(max(0.0, min(2.0, float(bg_settings_raw.get("contrast", 1.0) or 1.0))))
    bg_saturation = float(max(0.0, min(2.0, float(bg_settings_raw.get("saturation", 1.0) or 1.0))))
    bg_hue = float(max(-180.0, min(180.0, float(bg_settings_raw.get("hue", 0.0) or 0.0))))
    bg_react_bass = float(bg_settings_raw.get("reactivity", 0.0))
    bg_react_bass = float(max(0.0, min(20.0, bg_react_bass)))
    bg_smoothing = float(max(0.0, min(0.99, bg_settings_raw.get("smoothing", 0.8))))
    bg_motion_mode = str(bg_settings_raw.get("motionMode", "none") or "none")
    if bg_motion_mode not in ("none", "zoom", "vibrate", "both"):
        bg_motion_mode = "none"
    bg_motion_zoom_strength = float(bg_settings_raw.get("motionZoomStrength", 1.0) or 1.0)
    bg_motion_zoom_strength = float(max(0.0, min(20.0, bg_motion_zoom_strength)))
    bg_motion_vibrate_strength = float(bg_settings_raw.get("motionVibrateStrength", 1.0) or 1.0)
    bg_motion_vibrate_strength = float(max(0.0, min(20.0, bg_motion_vibrate_strength)))

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
    preview_bindings = template.get("previewBindings", {}) if isinstance(template.get("previewBindings"), dict) else {}
    spectrum_attach_to_logo = bool(preview_bindings.get("spectrumAttachToLogo", True))
    spectrum_logo_gap = float(max(0.0, float(preview_bindings.get("spectrumLogoGap", 0.0) or 0.0))) * sf
    logo_visible_radius_ratio = (
        _compute_visible_logo_radius_ratio(logo_rgba, logo_circle_mask)
        if spectrum_attach_to_logo and logo_rgba is not None
        else 1.0
    )

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
        if "bg_contrast" in prog_scene:
            prog_scene["bg_contrast"].value = float(bg_contrast)
        if "bg_saturation" in prog_scene:
            prog_scene["bg_saturation"].value = float(bg_saturation)
        if "bg_hue" in prog_scene:
            prog_scene["bg_hue"].value = float(bg_hue)
        
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
        if "bg_contrast" in prog_scene:
            prog_scene["bg_contrast"].value = float(bg_contrast)
        if "bg_saturation" in prog_scene:
            prog_scene["bg_saturation"].value = float(bg_saturation)
        if "bg_hue" in prog_scene:
            prog_scene["bg_hue"].value = float(bg_hue)
        if tex_logo is not None and logo_enabled:
            base_radius = (float(logo_raw.get("size", 192.0)) * 0.5) * sf
            s_logo = float(logo_scale_base) * (1.0 + logo_audio_env * float(logo_react_bass))
            s_logo = float(max(0.05, min(4.0, s_logo)))
            final_logo_size = base_radius * 2.0 * s_logo
            prog_logo["logo_size_px"].value = (final_logo_size, final_logo_size)
        ps_smoothing = float(max(0.0, min(0.99, particles_cfg_raw.get("smoothing", 0.65))))
        onset = float(feats.get("onset", 0.0) or 0.0)
        beat = float(feats.get("beat", 0.0) or 0.0)
        particle_audio_raw = float(
            max(0.0, min(1.0, max(kick_pow, bass, onset * 0.9, beat * 0.95)))
        )
        particle_audio_env = _smooth_env(particle_audio_env, particle_audio_raw, ps_smoothing)
        
        spawn_mode = str(particles_cfg_raw.get("spawnMode", "always") or "always")
        spawn_trigger = str(particles_cfg_raw.get("spawnTrigger", "both") or "both")
        spawn_threshold = float(particles_cfg_raw.get("spawnThreshold", 0.15) or 0.15)
        spawn_threshold = float(max(0.0, min(1.0, spawn_threshold)))
        kick_like = float(max(kick_pow, beat))
        bass_like = float(max(bass, onset * 0.85, particle_audio_raw * 0.65))
        if spawn_trigger == "kick":
            trig_raw = kick_like
        elif spawn_trigger == "bass":
            trig_raw = bass_like
        else:
            trig_raw = float(max(kick_like, bass_like))
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
                travel_mode=str(particles_cfg_raw.get("travelMode", "spawnFlow") or "spawnFlow"),
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
            bg_scale_live = float(1.0 + min(2.5, max(0.0, bg_audio_env * bg_react_bass * 0.04 * bg_motion_zoom_strength)))
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
        attached_to_logo = bool(spectrum_attach_to_logo and logo_rgba is not None)
        attached_base_radius = float(
            max(0.0, ((float(logo_raw.get("size", 192.0)) * 0.5) * sf * float(logo_scale_base) * logo_visible_radius_ratio) + spectrum_logo_gap)
        )
        attached_layer_base_offset = _resolve_attached_layer_base_offset(spectrum_layers, sf)

        template_style_preset = str(template.get("style", "orbit-spikes")).lower().strip()
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
            style_preset = _resolve_export_spectrum_style(template_style_preset, sl)
            curved = bool(sl.get("curved", False))
            mirrored = bool(sl.get("mirrored", False))
            bar_width = float(sl.get("barWidth", 4.0)) * sf
            bar_height_mult = _audio_bar_height_mult(template)
            thickness = float(sl.get("thickness", 30.0)) * sf * bar_height_mult
            gravity = str(sl.get("gravity", "normal")).lower().strip()
            
            logo_visual_radius = (float(logo_raw.get("size", 192.0)) * 0.5) * sf * float(logo_scale_base)
            radius_offset = float(sl.get("radiusOffset", 0.0)) * sf
            radius = _resolve_spectrum_layer_radius(
                attached_to_logo=attached_to_logo,
                attached_base_radius=attached_base_radius,
                attached_layer_base_offset=attached_layer_base_offset,
                logo_visual_radius=logo_visual_radius,
                bar_width=bar_width,
                radius_offset=radius_offset,
            )
            
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
                    if gravity in ("normal", "top"):
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = offset, 0.0, 0.0, 1.0
                    elif gravity == "bottom":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = offset, 0.0, 0.0, -1.0
                    elif gravity == "left":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = 0.0, offset, 1.0, 0.0
                    elif gravity == "right":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = 0.0, offset, -1.0, 0.0
                val_arr[i] = render_fft[i] * thickness

            cols = _build_spectrum_vertex_colors(color_cfg, spec_col, n, float(spec_col[3]))

            prog_lines["clip_enabled"].value = 0

            # Render Logic
            bw = resolve_bar_pixel_width(bar_width, total_length / max(1, n))
            
            if style_preset in ("aurora-ribbon", "magma-ridge", "plasma-bloom", "soft-waveform", "mountain", "liquid", "continuous-waveform"):
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
                    if style_preset in ("magma-ridge", "mountain"):
                        peak_h = h_val * 1.18
                        xs_o[i] = (cx + px_arr[i] + dx_arr[i] * peak_h) / float(w) * 2.0 - 1.0
                        ys_o[i] = (cy + py_arr[i] + dy_arr[i] * peak_h) / float(h) * 2.0 - 1.0
                        xs_i[i] = (cx + px_arr[i] + dx_arr[i] * (bar_width * 0.10)) / float(w) * 2.0 - 1.0
                        ys_i[i] = (cy + py_arr[i] + dy_arr[i] * (bar_width * 0.10)) / float(h) * 2.0 - 1.0
                    elif style_preset in ("plasma-bloom", "liquid"):
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
                    
                    if style_preset in ("mirror-blades", "symmetrical-bars"):
                        p0x = px_arr[i] - dx_arr[i] * (h_val/2) - wx
                        p0y = py_arr[i] - dy_arr[i] * (h_val/2) - wy
                        p1x = px_arr[i] - dx_arr[i] * (h_val/2) + wx
                        p1y = py_arr[i] - dy_arr[i] * (h_val/2) + wy
                        p2x = px_arr[i] + dx_arr[i] * (h_val/2) + wx
                        p2y = py_arr[i] + dy_arr[i] * (h_val/2) + wy
                        p3x = px_arr[i] + dx_arr[i] * (h_val/2) - wx
                        p3y = py_arr[i] + dy_arr[i] * (h_val/2) - wy
                    elif style_preset in ("drift-capsules", "floating-blocks"):
                        p0x = px_arr[i] + dx_arr[i] * (h_val + 20.0*sf) - wx
                        p0y = py_arr[i] + dy_arr[i] * (h_val + 20.0*sf) - wy
                        p1x = px_arr[i] + dx_arr[i] * (h_val + 20.0*sf) + wx
                        p1y = py_arr[i] + dy_arr[i] * (h_val + 20.0*sf) + wy
                        p2x = px_arr[i] + dx_arr[i] * (h_val + 20.0*sf + 10.0*sf) + wx
                        p2y = py_arr[i] + dy_arr[i] * (h_val + 20.0*sf + 10.0*sf) + wy
                        p3x = px_arr[i] + dx_arr[i] * (h_val + 20.0*sf + 10.0*sf) - wx
                        p3y = py_arr[i] + dy_arr[i] * (h_val + 20.0*sf + 10.0*sf) - wy
                    elif style_preset in ("grid-steps", "pixel-bars"):
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
                    elif style_preset in ("signal-needles", "thin-lines"):
                        needle = float(max(1.0, bw * 0.28))
                        wx = -dy_arr[i] * (needle / 2.0)
                        wy = dx_arr[i] * (needle / 2.0)
                        p0x = px_arr[i] - wx
                        p0y = py_arr[i] - wy
                        p1x = px_arr[i] + wx
                        p1y = py_arr[i] + wy
                        p2x = px_arr[i] + dx_arr[i] * h_val + wx
                        p2y = py_arr[i] + dy_arr[i] * h_val + wy
                        p3x = px_arr[i] + dx_arr[i] * h_val - wx
                        p3y = py_arr[i] + dy_arr[i] * h_val - wy
                    elif style_preset in ("pulse-beads", "dot-matrix"):
                        step = max(10.0 * sf, bw * 1.2)
                        h_val = float(np.ceil(h_val / step) * step)
                        # Keep wx/wy from barWidth (bw); only step the height into beads.
                        p0x = px_arr[i] - wx
                        p0y = py_arr[i] - wy
                        p1x = px_arr[i] + wx
                        p1y = py_arr[i] + wy
                        p2x = px_arr[i] + dx_arr[i] * h_val + wx
                        p2y = py_arr[i] + dy_arr[i] * h_val + wy
                        p3x = px_arr[i] + dx_arr[i] * h_val - wx
                        p3y = py_arr[i] + dy_arr[i] * h_val - wy
                    else:  # orbit-spikes / ignition-flare fallback
                        if style_preset in ("ignition-flare", "neon-pulse"):
                            pulse = 1.0 + logo_audio_env * 0.18 + particle_audio_env * 0.12
                            h_val *= pulse
                            wx *= 1.2
                            wy *= 1.2
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
                ys2 = 1.0 - (p[:, 1] / float(h) * 2.0)
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
                    mix = compute_particle_react_mix(
                        reactive_env=float(particle_audio_env),
                        trigger_env=float(p_trigger_env),
                        react_strength=react_strength,
                    )
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
    import os
    
    fps = int(max(1, min(60, int(opts.fps))))
    if fps <= 0:
        fps = 30

    w = int(max(64, min(8192, int(opts.width) if int(opts.width) > 0 else 1920)))
    h = int(max(64, min(8192, int(opts.height) if int(opts.height) > 0 else 1080)))

    if not glfw.init():
        raise RuntimeError("Failed to init GLFW")
        
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.SAMPLES, 4)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
    glfw.window_hint(glfw.DECORATED, glfw.FALSE)
    win = glfw.create_window(w, h, "MG Live Preview", None, None)
    if not win:
        glfw.terminate()
        raise RuntimeError("Failed to create visible OpenGL window")
    glfw.make_context_current(win)
    glfw.swap_interval(1)

    ctx = _make_ctx()

    native_hwnd = 0
    if sys.platform == "win32":
        try:
            get_win32_window = getattr(glfw, "get_win32_window", None)
            if callable(get_win32_window):
                native_hwnd = int(get_win32_window(win))
        except Exception:
            native_hwnd = 0

    def apply_template_patch(dst: dict, patch: dict) -> dict:
        out = dict(dst) if isinstance(dst, dict) else {}
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = apply_template_patch(out.get(k, {}), v)
            else:
                out[k] = v
        return out

    def try_embed_into_parent(parent_hwnd: int) -> None:
        if sys.platform != "win32":
            return
        if not native_hwnd or not parent_hwnd:
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32
            GWL_STYLE = -16
            GWL_EXSTYLE = -20
            WS_CHILD = 0x40000000
            WS_POPUP = 0x80000000
            WS_CAPTION = 0x00C00000
            WS_THICKFRAME = 0x00040000
            WS_CLIPSIBLINGS = 0x04000000
            WS_CLIPCHILDREN = 0x02000000
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020
            SWP_SHOWWINDOW = 0x0040
            SWP_ASYNCWINDOWPOS = 0x4000

            SetParent = user32.SetParent
            SetParent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            SetParent.restype = ctypes.c_void_p

            GetWindowLongPtrW = getattr(user32, "GetWindowLongPtrW", None)
            SetWindowLongPtrW = getattr(user32, "SetWindowLongPtrW", None)
            if not callable(GetWindowLongPtrW) or not callable(SetWindowLongPtrW):
                GetWindowLongPtrW = user32.GetWindowLongW
                SetWindowLongPtrW = user32.SetWindowLongW

            GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            GetWindowLongPtrW.restype = ctypes.c_void_p
            SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            SetWindowLongPtrW.restype = ctypes.c_void_p

            EnumChildWindows = user32.EnumChildWindows
            EnumChildWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            EnumChildWindows.restype = ctypes.c_int

            GetClassNameW = user32.GetClassNameW
            GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
            GetClassNameW.restype = ctypes.c_int

            IsWindowVisible = user32.IsWindowVisible
            IsWindowVisible.argtypes = [ctypes.c_void_p]
            IsWindowVisible.restype = ctypes.c_int

            SetWindowPos = user32.SetWindowPos
            SetWindowPos.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint,
            ]
            SetWindowPos.restype = ctypes.c_int
            BringWindowToTop = user32.BringWindowToTop
            BringWindowToTop.argtypes = [ctypes.c_void_p]
            BringWindowToTop.restype = ctypes.c_int

            ShowWindow = user32.ShowWindow
            ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
            ShowWindow.restype = ctypes.c_int

            UpdateWindow = user32.UpdateWindow
            UpdateWindow.argtypes = [ctypes.c_void_p]
            UpdateWindow.restype = ctypes.c_int

            HWND_TOPMOST = ctypes.c_void_p(-1)
            SW_SHOWNOACTIVATE = 4

            render_parent_hwnd = int(parent_hwnd)
            child_candidates: list[tuple[int, str]] = []

            @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
            def _enum_child(hwnd, _lparam):
                try:
                    if not IsWindowVisible(hwnd):
                        return 1
                    buf = ctypes.create_unicode_buffer(256)
                    GetClassNameW(hwnd, buf, 255)
                    class_name = str(buf.value or "")
                    if class_name:
                        child_candidates.append((int(hwnd), class_name))
                except Exception:
                    pass
                return 1

            EnumChildWindows(ctypes.c_void_p(int(parent_hwnd)), _enum_child, ctypes.c_void_p(0))
            preferred_classes = (
                "intermediate d3d window",
                "chrome_renderwidgethosthwnd",
                "chrome_widgetwin_0",
            )
            for preferred_class in preferred_classes:
                for candidate_hwnd, candidate_class in child_candidates:
                    if candidate_class.lower() == preferred_class:
                        render_parent_hwnd = int(candidate_hwnd)
                        break
                if render_parent_hwnd != int(parent_hwnd):
                    break

            SetParent(ctypes.c_void_p(native_hwnd), ctypes.c_void_p(int(render_parent_hwnd)))
            style_val = int(GetWindowLongPtrW(ctypes.c_void_p(native_hwnd), GWL_STYLE) or 0)
            style_val = (style_val | WS_CHILD | WS_CLIPSIBLINGS | WS_CLIPCHILDREN) & ~WS_POPUP & ~WS_CAPTION & ~WS_THICKFRAME
            SetWindowLongPtrW(ctypes.c_void_p(native_hwnd), GWL_STYLE, ctypes.c_void_p(style_val))
            ex_style_val = int(GetWindowLongPtrW(ctypes.c_void_p(native_hwnd), GWL_EXSTYLE) or 0)
            ex_style_val = (ex_style_val & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
            SetWindowLongPtrW(ctypes.c_void_p(native_hwnd), GWL_EXSTYLE, ctypes.c_void_p(ex_style_val))
            SetWindowPos(
                ctypes.c_void_p(native_hwnd),
                HWND_TOPMOST,
                0,
                0,
                int(w),
                int(h),
                SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW | SWP_ASYNCWINDOWPOS,
            )
            ShowWindow(ctypes.c_void_p(native_hwnd), SW_SHOWNOACTIVATE)
            BringWindowToTop(ctypes.c_void_p(native_hwnd))
            UpdateWindow(ctypes.c_void_p(native_hwnd))
            try:
                glfw.show_window(win)
            except Exception:
                pass
        except Exception:
            pass

    def try_set_bounds(x: int, y: int, width: int, height: int) -> None:
        if sys.platform != "win32" or not native_hwnd:
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            SWP_ASYNCWINDOWPOS = 0x4000

            SetWindowPos = user32.SetWindowPos
            SetWindowPos.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint,
            ]
            SetWindowPos.restype = ctypes.c_int
            BringWindowToTop = user32.BringWindowToTop
            BringWindowToTop.argtypes = [ctypes.c_void_p]
            BringWindowToTop.restype = ctypes.c_int

            ShowWindow = user32.ShowWindow
            ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
            ShowWindow.restype = ctypes.c_int

            UpdateWindow = user32.UpdateWindow
            UpdateWindow.argtypes = [ctypes.c_void_p]
            UpdateWindow.restype = ctypes.c_int

            HWND_TOPMOST = ctypes.c_void_p(-1)
            SW_SHOWNOACTIVATE = 4

            SetWindowPos(
                ctypes.c_void_p(native_hwnd),
                HWND_TOPMOST,
                int(x),
                int(y),
                int(width),
                int(height),
                SWP_NOACTIVATE | SWP_SHOWWINDOW | SWP_ASYNCWINDOWPOS,
            )
            ShowWindow(ctypes.c_void_p(native_hwnd), SW_SHOWNOACTIVATE)
            BringWindowToTop(ctypes.c_void_p(native_hwnd))
            UpdateWindow(ctypes.c_void_p(native_hwnd))
            try:
                glfw.show_window(win)
            except Exception:
                pass
        except Exception:
            pass

    resize_state = {"pending": False, "w": w, "h": h}

    def request_resize(next_w: int, next_h: int) -> None:
        nw = int(max(64, min(8192, int(next_w))))
        nh = int(max(64, min(8192, int(next_h))))
        if nw == resize_state["w"] and nh == resize_state["h"]:
            return
        resize_state["pending"] = True
        resize_state["w"] = nw
        resize_state["h"] = nh

    shared_state = {
        "template": _load_template(opts),
        "time": 0.0,
        "bg_path": opts.background_path,
        "logo_path": opts.logo_path,
        "audio_path": opts.mp3_path,
        "quit": False,
    }

    def stdin_reader():
        for line in sys.stdin:
            try:
                msg = json.loads(line)
                if "time" in msg:
                    shared_state["time"] = float(msg["time"])
                if "templateB64" in msg:
                    shared_state["template"] = json.loads(base64.b64decode(msg["templateB64"]).decode("utf-8"))
                if "templatePatch" in msg and isinstance(msg["templatePatch"], dict) and isinstance(shared_state.get("template"), dict):
                    shared_state["template"] = apply_template_patch(shared_state["template"], msg["templatePatch"])
                if "backgroundPath" in msg:
                    shared_state["bg_path"] = msg["backgroundPath"]
                if "logoPath" in msg:
                    shared_state["logo_path"] = msg["logoPath"]
                if "audioPath" in msg:
                    shared_state["audio_path"] = msg["audioPath"]
                if msg.get("cmd") == "embed":
                    parent_hwnd = int(msg.get("parentHwnd") or 0)
                    try_embed_into_parent(parent_hwnd)
                if msg.get("cmd") == "setBounds":
                    x = int(msg.get("x") or 0)
                    y = int(msg.get("y") or 0)
                    bw = int(msg.get("width") or 0)
                    bh = int(msg.get("height") or 0)
                    if bw > 0 and bh > 0:
                        request_resize(bw, bh)
                        try_set_bounds(x, y, bw, bh)
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
    text_cache = {"tex": [], "key": [], "wh": []}

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

    particles = ParticleSystem(
        ParticleConfig(enabled=False, max_count=1, spawn_rate=1, lifetime_sec=1, size=1, opacity=1, color=(255,255,255), speed=1, spawn_radius=0),
        width=w,
        height=h,
        rng_seed=1,
    )
    
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

    _send(
        {
            "status": "ready",
            "message": "Live preview started",
            "preview": {
                "pid": int(os.getpid()),
                "hwnd": int(native_hwnd),
                "platform": sys.platform,
            },
        }
    )

    while not glfw.window_should_close(win) and not shared_state["quit"]:
        glfw.poll_events()

        if resize_state["pending"]:
            resize_state["pending"] = False
            w = int(resize_state["w"])
            h = int(resize_state["h"])
            try:
                glfw.set_window_size(win, int(w), int(h))
            except Exception:
                pass
            try:
                fbo_scene.release()
            except Exception:
                pass
            try:
                tex_scene.release()
            except Exception:
                pass
            tex_scene = ctx.texture((w, h), 4)
            tex_scene.filter = (moderngl.LINEAR, moderngl.LINEAR)
            fbo_scene = ctx.framebuffer(color_attachments=[tex_scene])
            current_bg_path = None
            current_logo_path = None
            current_audio_path = None
            try:
                particles = ParticleSystem(
                    ParticleConfig(enabled=False, max_count=1, spawn_rate=1, lifetime_sec=1, size=1, opacity=1, color=(255,255,255), speed=1, spawn_radius=0),
                    width=w,
                    height=h,
                    rng_seed=1,
                )
            except Exception:
                pass

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
            except Exception as error:
                _ = error
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
        bg_contrast = float(max(0.0, min(2.0, float(bg_settings_raw.get("contrast", 1.0) or 1.0))))
        bg_saturation = float(max(0.0, min(2.0, float(bg_settings_raw.get("saturation", 1.0) or 1.0))))
        bg_hue = float(max(-180.0, min(180.0, float(bg_settings_raw.get("hue", 0.0) or 0.0))))
        bg_react_bass = float(bg_settings_raw.get("reactivity", 0.0))
        bg_react_bass = float(max(0.0, min(20.0, bg_react_bass)))
        bg_smoothing = float(max(0.0, min(0.99, bg_settings_raw.get("smoothing", 0.8))))
        bg_motion_mode = str(bg_settings_raw.get("motionMode", "none") or "none")
        if bg_motion_mode not in ("none", "zoom", "vibrate", "both"):
            bg_motion_mode = "none"
        bg_motion_zoom_strength = float(bg_settings_raw.get("motionZoomStrength", 1.0) or 1.0)
        bg_motion_zoom_strength = float(max(0.0, min(20.0, bg_motion_zoom_strength)))
        bg_motion_vibrate_strength = float(bg_settings_raw.get("motionVibrateStrength", 1.0) or 1.0)
        bg_motion_vibrate_strength = float(max(0.0, min(20.0, bg_motion_vibrate_strength)))

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
        preview_bindings = template.get("previewBindings", {}) if isinstance(template.get("previewBindings"), dict) else {}
        spectrum_attach_to_logo = bool(preview_bindings.get("spectrumAttachToLogo", True))
        spectrum_logo_gap = float(max(0.0, float(preview_bindings.get("spectrumLogoGap", 0.0) or 0.0))) * sf
        logo_visible_radius_ratio = (
            _compute_visible_logo_radius_ratio(logo_rgba, logo_circle_mask)
            if spectrum_attach_to_logo and logo_rgba is not None
            else 1.0
        )

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
            bg_scale_live = float(1.0 + min(2.5, max(0.0, bg_audio_env * bg_react_bass * 0.04 * bg_motion_zoom_strength)))
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
        if "bg_contrast" in prog_scene:
            prog_scene["bg_contrast"].value = float(bg_contrast)
        if "bg_saturation" in prog_scene:
            prog_scene["bg_saturation"].value = float(bg_saturation)
        if "bg_hue" in prog_scene:
            prog_scene["bg_hue"].value = float(bg_hue)
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

        template_style_preset = str(template.get("style", "orbit-spikes")).lower().strip()
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
        attached_to_logo = bool(spectrum_attach_to_logo and logo_rgba is not None)
        attached_base_radius = float(
            max(0.0, ((float(logo_raw.get("size", 192.0)) * 0.5) * sf * float(logo_scale_base) * logo_visible_radius_ratio) + spectrum_logo_gap)
        )
        attached_layer_base_offset = _resolve_attached_layer_base_offset(spectrum_layers, sf)
        
        for sl in spectrum_layers:
            style_preset = _resolve_export_spectrum_style(template_style_preset, sl)
            curved = bool(sl.get("curved", False))
            mirrored = bool(sl.get("mirrored", False))
            bar_width = float(sl.get("barWidth", 4.0)) * sf
            bar_height_mult = _audio_bar_height_mult(template)
            thickness = float(sl.get("thickness", 30.0)) * sf * bar_height_mult
            gravity = str(sl.get("gravity", "normal")).lower().strip()
            
            logo_visual_radius = (float(logo_raw.get("size", 192.0)) * 0.5) * sf * float(logo_scale_base)
            radius = _resolve_spectrum_layer_radius(
                attached_to_logo=attached_to_logo,
                attached_base_radius=attached_base_radius,
                attached_layer_base_offset=attached_layer_base_offset,
                logo_visual_radius=logo_visual_radius,
                bar_width=bar_width,
                radius_offset=0.0,
            )
            
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
                    if gravity in ("normal", "top"):
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = offset, 0.0, 0.0, 1.0
                    elif gravity == "bottom":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = offset, 0.0, 0.0, -1.0
                    elif gravity == "left":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = 0.0, offset, 1.0, 0.0
                    elif gravity == "right":
                        px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = 0.0, offset, -1.0, 0.0
                val_arr[i] = render_fft[i] * thickness

            cols = _build_spectrum_vertex_colors(color_cfg, spec_col, n, float(spec_col[3]))

            prog_lines["clip_enabled"].value = 0
            
            bw = resolve_bar_pixel_width(bar_width, total_length / max(1, n))
            
            if style_preset in ("aurora-ribbon", "magma-ridge", "plasma-bloom", "soft-waveform", "mountain", "liquid", "continuous-waveform"):
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
                    if style_preset in ("magma-ridge", "mountain"):
                        peak_h = h_val * 1.18
                        xs_o[i] = (cx + px_arr[i] + dx_arr[i] * peak_h) / float(w) * 2.0 - 1.0
                        ys_o[i] = (cy + py_arr[i] + dy_arr[i] * peak_h) / float(h) * 2.0 - 1.0
                        xs_i[i] = (cx + px_arr[i] + dx_arr[i] * (bar_width * 0.10)) / float(w) * 2.0 - 1.0
                        ys_i[i] = (cy + py_arr[i] + dy_arr[i] * (bar_width * 0.10)) / float(h) * 2.0 - 1.0
                    elif style_preset in ("plasma-bloom", "liquid"):
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
                    
                    if style_preset in ("mirror-blades", "symmetrical-bars"):
                        p0x = px_arr[i] - dx_arr[i] * (h_val/2) - wx
                        p0y = py_arr[i] - dy_arr[i] * (h_val/2) - wy
                        p1x = px_arr[i] - dx_arr[i] * (h_val/2) + wx
                        p1y = py_arr[i] - dy_arr[i] * (h_val/2) + wy
                        p2x = px_arr[i] + dx_arr[i] * (h_val/2) + wx
                        p2y = py_arr[i] + dy_arr[i] * (h_val/2) + wy
                        p3x = px_arr[i] + dx_arr[i] * (h_val/2) - wx
                        p3y = py_arr[i] + dy_arr[i] * (h_val/2) - wy
                    elif style_preset in ("drift-capsules", "floating-blocks"):
                        p0x = px_arr[i] + dx_arr[i] * (h_val + 20.0 * sf) - wx
                        p0y = py_arr[i] + dy_arr[i] * (h_val + 20.0 * sf) - wy
                        p1x = px_arr[i] + dx_arr[i] * (h_val + 20.0 * sf) + wx
                        p1y = py_arr[i] + dy_arr[i] * (h_val + 20.0 * sf) + wy
                        p2x = px_arr[i] + dx_arr[i] * (h_val + 30.0 * sf) + wx
                        p2y = py_arr[i] + dy_arr[i] * (h_val + 30.0 * sf) + wy
                        p3x = px_arr[i] + dx_arr[i] * (h_val + 30.0 * sf) - wx
                        p3y = py_arr[i] + dy_arr[i] * (h_val + 30.0 * sf) - wy
                    elif style_preset in ("grid-steps", "pixel-bars"):
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
                    elif style_preset in ("signal-needles", "thin-lines"):
                        needle = float(max(1.0, bw * 0.28))
                        wx = -dy_arr[i] * (needle / 2.0)
                        wy = dx_arr[i] * (needle / 2.0)
                        p0x = px_arr[i] - wx
                        p0y = py_arr[i] - wy
                        p1x = px_arr[i] + wx
                        p1y = py_arr[i] + wy
                        p2x = px_arr[i] + dx_arr[i] * h_val + wx
                        p2y = py_arr[i] + dy_arr[i] * h_val + wy
                        p3x = px_arr[i] + dx_arr[i] * h_val - wx
                        p3y = py_arr[i] + dy_arr[i] * h_val - wy
                    elif style_preset in ("pulse-beads", "dot-matrix"):
                        step = max(10.0 * sf, bw * 1.2)
                        h_val = float(np.ceil(h_val / step) * step)
                        # Keep wx/wy from barWidth (bw); only step the height into beads.
                        p0x = px_arr[i] - wx
                        p0y = py_arr[i] - wy
                        p1x = px_arr[i] + wx
                        p1y = py_arr[i] + wy
                        p2x = px_arr[i] + dx_arr[i] * h_val + wx
                        p2y = py_arr[i] + dy_arr[i] * h_val + wy
                        p3x = px_arr[i] + dx_arr[i] * h_val - wx
                        p3y = py_arr[i] + dy_arr[i] * h_val - wy
                    else:
                        if style_preset in ("ignition-flare", "neon-pulse"):
                            pulse = 1.0 + logo_audio_env * 0.18 + particle_audio_env * 0.12
                            h_val *= pulse
                            wx *= 1.2
                            wy *= 1.2
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
        onset = float(feats.get("onset", 0.0) or 0.0)
        beat = float(feats.get("beat", 0.0) or 0.0)
        particle_audio_raw = float(
            max(0.0, min(1.0, max(kick_pow, bass, onset * 0.9, beat * 0.95)))
        )
        particle_audio_env = _smooth_env(particle_audio_env, particle_audio_raw, ps_smoothing)
        
        spawn_mode = str(particles_cfg_raw.get("spawnMode", "always") or "always")
        spawn_trigger = str(particles_cfg_raw.get("spawnTrigger", "both") or "both")
        spawn_threshold = float(particles_cfg_raw.get("spawnThreshold", 0.15) or 0.15)
        spawn_threshold = float(max(0.0, min(1.0, spawn_threshold)))
        kick_like = float(max(kick_pow, beat))
        bass_like = float(max(bass, onset * 0.85, particle_audio_raw * 0.65))
        if spawn_trigger == "kick":
            trig_raw = kick_like
        elif spawn_trigger == "bass":
            trig_raw = bass_like
        else:
            trig_raw = float(max(kick_like, bass_like))
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
                travel_mode=str(particles_cfg_raw.get("travelMode", "spawnFlow") or "spawnFlow"),
            )
        )
        particles.update(dt, feats)

        if particles_cfg_raw.get("enabled", False):
            pos = particles._pos if hasattr(particles, "_pos") else np.zeros((0, 2), dtype=np.float32)
            if pos.shape[0]:
                p = pos.astype(np.float32)
                xs2 = p[:, 0] / float(w) * 2.0 - 1.0
                ys2 = 1.0 - (p[:, 1] / float(h) * 2.0)
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
                    mix = compute_particle_react_mix(
                        reactive_env=float(particle_audio_env),
                        trigger_env=float(p_trigger_env),
                        react_strength=react_strength,
                    )
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
