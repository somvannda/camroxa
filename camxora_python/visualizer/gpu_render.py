from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import glfw
import moderngl
from ._spectrum_fast import (
    normalize_spectrum_gravity,
    resolve_bar_pixel_width,
    scroll_spectrum_heights,
)

def _audio_bar_height_mult(template: dict) -> float:
    audio = template.get("audioSettings") if isinstance(template.get("audioSettings"), dict) else {}
    try:
        value = float(audio.get("barHeight", 1.0) or 1.0)
    except Exception:
        value = 1.0
    return float(max(0.25, min(12.0, value)))

import numpy as np
from PIL import Image

from .audio import AudioAnalyzer
from .automation import apply_automations
from .config import load_template_any, load_template_any_raw
from .frame_integrator import (
    BgVibrateConfig,
    BgVibrateState,
    BgVibrateStepInput,
    CameraShakeConfig,
    CameraShakeState,
    CameraShakeStepInput,
    KickBassEnvelopeConfig,
    KickBassEnvelopeState,
    KickBassEnvelopeStepInput,
    integrate_bg_vibrate,
    integrate_camera_shake,
    integrate_kick_bass_envelopes,
    integrate_particle_audio,
    ParticleAudioConfig,
    ParticleAudioState,
    ParticleAudioStepInput,
    smooth_env,
)
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


def _init_glfw_hidden(width: int, height: int, *, samples: int = 4) -> None:
    if not glfw.init():
        raise RuntimeError("Failed to init GLFW")
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.SAMPLES, max(0, int(samples)))
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
    try:
        glfw.window_hint(glfw.FOCUSED, glfw.FALSE)
    except Exception:
        pass
    win = glfw.create_window(width, height, "MG_GPU", None, None)
    if not win:
        glfw.terminate()
        raise RuntimeError("Failed to create hidden OpenGL window")
    glfw.make_context_current(win)
    glfw.swap_interval(0)
    # Invisible HWND still defaults to an app-window taskbar slot on Windows;
    # exclude it so export does not replace Camxora's branded taskbar icon.
    try:
        from shared.lib.win32_window import exclude_glfw_window_from_taskbar

        exclude_glfw_window_from_taskbar(win)
    except Exception:
        pass


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


def _compile_readback_flip(ctx: moderngl.Context):
    """Final export blit — flip Y so OpenGL readback row order matches video top-down."""
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
    fs_readback_flip = """
    #version 330
    uniform sampler2D tex_in;
    in vec2 v_uv;
    out vec4 frag;
    void main() {
        frag = texture(tex_in, vec2(v_uv.x, 1.0 - v_uv.y));
    }
    """
    return ctx.program(vertex_shader=vs_quad, fragment_shader=fs_readback_flip)


def _blit_readback_oriented(
    *,
    src_tex: moderngl.Texture,
    fbo_readback: moderngl.Framebuffer,
    prog: moderngl.Program,
    vao: moderngl.VertexArray,
) -> None:
    fbo_readback.use()
    src_tex.use(location=0)
    prog["tex_in"].value = 0
    vao.render(mode=moderngl.TRIANGLE_STRIP)


def _compile_particle_quads(ctx: moderngl.Context):
    vs_particle_quads = """
    #version 330
    in vec2 in_pos;
    in vec2 in_uv;
    in vec4 in_col;
    in vec2 in_meta;
    out vec2 v_uv;
    out vec4 v_col;
    out vec2 v_meta;
    void main() {
        v_uv = in_uv;
        v_col = in_col;
        v_meta = in_meta;
        gl_Position = vec4(in_pos, 0.0, 1.0);
    }
    """
    fs_particle_quads = """
    #version 330
    in vec2 v_uv;
    in vec4 v_col;
    in vec2 v_meta;
    uniform int pt_style;
    uniform float glow_amount;
    uniform sampler2D icon_atlas;
    uniform int atlas_cols;
    out vec4 frag;
    float sat(float x) { return clamp(x, 0.0, 1.0); }
    void main() {
        vec2 p = v_uv * 2.0 - 1.0;
        float r2 = dot(p, p);
        float r = sqrt(max(r2, 0.0));
        float edge = 1.0 - smoothstep(0.92, 1.0, r);
        float a = 0.0;
        vec3 rgb = v_col.rgb;

        if (pt_style == 5) {
            // Music icon atlas sample with per-particle rotation.
            float cols = float(max(1, atlas_cols));
            float icon = floor(mod(max(v_meta.x, 0.0), cols));
            float ang = v_meta.y;
            float ca = cos(ang);
            float sa = sin(ang);
            vec2 q = v_uv - 0.5;
            vec2 rq = vec2(ca * q.x - sa * q.y, sa * q.x + ca * q.y);
            vec2 local = rq + 0.5;
            if (local.x < 0.0 || local.x > 1.0 || local.y < 0.0 || local.y > 1.0) discard;
            vec2 atlas_uv = vec2((icon + local.x) / cols, local.y);
            float icon_a = texture(icon_atlas, atlas_uv).a;
            a = icon_a;
            float core = smoothstep(0.15, 0.85, icon_a);
            rgb = mix(v_col.rgb, vec3(1.0), glow_amount * 0.55 * core);
        } else {
            if (r > 1.0) discard;
            a = edge;
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
            float core_w = 1.0 - smoothstep(0.0, 0.55, r);
            rgb = mix(v_col.rgb, vec3(1.0), glow_amount * 0.5 * core_w);
        }

        float g = clamp(glow_amount, 0.0, 1.0);
        if (g > 0.001) {
            float halo = 1.0 - smoothstep(0.0, 1.0, r);
            if (pt_style == 5) {
                halo = a * (1.0 - smoothstep(0.35, 1.0, a));
            }
            a = max(a, halo * (0.22 + g * 0.55));
            a = sat(a * (1.0 + g * 0.35));
        }
        if (a <= 0.001) discard;
        frag = vec4(rgb, v_col.a * a);
    }
    """
    prog = ctx.program(vertex_shader=vs_particle_quads, fragment_shader=fs_particle_quads)
    if "icon_atlas" in prog:
        prog["icon_atlas"].value = 3
    if "atlas_cols" in prog:
        prog["atlas_cols"].value = 4
    if "glow_amount" in prog:
        prog["glow_amount"].value = 0.0
    return prog


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
    if style in ("music", "musicNotes", "notes"):
        return 5
    return 0


def _particle_style_size_scale(pt_style: int) -> float:
    return {0: 1.0, 1: 2.0, 2: 1.5, 3: 1.5, 4: 2.0, 5: 2.4}.get(int(pt_style), 1.0)


def _build_particle_styled_quad_verts(
    *,
    xs: np.ndarray,
    ys: np.ndarray,
    scales: np.ndarray,
    colors_rgba: np.ndarray,
    w: int,
    h: int,
    base_px: float,
    icons: np.ndarray | None = None,
    angles: np.ndarray | None = None,
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
    if icons is None or int(getattr(icons, "shape", [0])[0]) != n:
        icon_f = np.zeros((n,), dtype=np.float32)
    else:
        icon_f = icons.astype(np.float32).reshape(n)
    if angles is None or int(getattr(angles, "shape", [0])[0]) != n:
        ang_f = np.zeros((n,), dtype=np.float32)
    else:
        ang_f = angles.astype(np.float32).reshape(n)
    meta = np.column_stack([icon_f, ang_f]).astype(np.float32)
    meta = np.repeat(meta, 6, axis=0)
    return np.column_stack([pos, uv, cols, meta]).astype(np.float32)


def _ensure_music_icon_texture(ctx: moderngl.Context, holder: dict | None = None):
    """Upload / reuse music-icon atlas on texture unit-ready Moderngl texture."""
    store = holder if isinstance(holder, dict) else {}
    tex = store.get("tex")
    cols = int(store.get("cols") or 0)
    if tex is not None and cols > 0:
        return tex, cols
    from features.video.lib.particle_music_icons import build_music_icon_atlas

    atlas, cols = build_music_icon_atlas()
    h, w = int(atlas.shape[0]), int(atlas.shape[1])
    tex = ctx.texture((w, h), 4, atlas.tobytes())
    tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
    tex.repeat_x = False
    tex.repeat_y = False
    store["tex"] = tex
    store["cols"] = int(cols)
    return tex, int(cols)


def _particle_trail_cfg_from_settings(ps: dict) -> tuple[bool, int, float, float]:
    enabled = bool(ps.get("trailEnabled", False))
    try:
        length = int(round(float(ps.get("trailLength", 8) or 8)))
    except (TypeError, ValueError):
        length = 8
    length = int(max(2, min(24, length)))
    try:
        fade = float(ps.get("trailFade", 0.65) or 0.65)
    except (TypeError, ValueError):
        fade = 0.65
    fade = float(max(0.05, min(0.98, fade)))
    try:
        width = float(ps.get("trailWidth", 0.45) or 0.45)
    except (TypeError, ValueError):
        width = 0.45
    width = float(max(0.1, min(1.0, width)))
    return enabled, length, fade, width


def _clamp_particle_glow(value) -> float:
    try:
        return float(max(0.0, min(1.0, float(value if value is not None else 0.0))))
    except (TypeError, ValueError):
        return 0.0


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
    glow_amount: float = 0.0,
    icons: np.ndarray | None = None,
    angles: np.ndarray | None = None,
    music_tex_holder: dict | None = None,
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
    glow = _clamp_particle_glow(glow_amount)
    size_boost = 1.0 + glow * 1.75
    if int(pt_style) == 5:
        size_boost *= 1.15
    verts = _build_particle_styled_quad_verts(
        xs=xs,
        ys=ys,
        scales=scales,
        colors_rgba=colors_rgba,
        w=w,
        h=h,
        base_px=float(pt_size) * size_boost,
        icons=icons,
        angles=angles,
    )
    if verts.nbytes > particle_quad_vbo.size:
        particle_quad_vbo.orphan(size=verts.nbytes)
    particle_quad_vbo.write(np.ascontiguousarray(verts, dtype=np.float32))
    prog_particle_quads["pt_style"].value = int(pt_style)
    if "glow_amount" in prog_particle_quads:
        prog_particle_quads["glow_amount"].value = float(glow)
    if int(pt_style) == 5:
        tex, cols = _ensure_music_icon_texture(ctx, music_tex_holder)
        tex.use(location=3)
        if "icon_atlas" in prog_particle_quads:
            prog_particle_quads["icon_atlas"].value = 3
        if "atlas_cols" in prog_particle_quads:
            prog_particle_quads["atlas_cols"].value = int(cols)
    ctx.enable(moderngl.BLEND)
    # Neon bloom reads better with additive when glow is on.
    if glow > 0.08:
        ctx.blend_func = moderngl.ADDITIVE_BLENDING
    else:
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
    vao_particle_quads.render(mode=moderngl.TRIANGLES, vertices=int(pts.shape[0] * 6))
    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

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
        "contour-waves",
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
    *,
    glow: bool = False,
) -> np.ndarray:
    from features.video.lib.spectrum_color_engine import (
        build_spectrum_vertex_rgba,
        dampen_spectrum_glow_rgba,
    )

    mode = str(color_cfg.get("mode", "solid") or "solid").lower().strip()
    solid = color_cfg.get("solidColor")
    if not isinstance(solid, str) or not solid.strip():
        # Fall back to the already-resolved solid RGB float tuple.
        solid = "#{:02x}{:02x}{:02x}".format(
            int(max(0, min(255, round(float(spec_col[0]) * 255.0)))),
            int(max(0, min(255, round(float(spec_col[1]) * 255.0)))),
            int(max(0, min(255, round(float(spec_col[2]) * 255.0)))),
        )
    gradient_colors = color_cfg.get("gradientColors") if isinstance(color_cfg.get("gradientColors"), list) else None
    colors = build_spectrum_vertex_rgba(
        mode=mode,
        solid_color=str(solid),
        gradient_colors=gradient_colors,
        count=count,
        alpha=alpha,
    )
    if glow:
        return dampen_spectrum_glow_rgba(colors, strength=0.38)
    return colors


def _build_spectrum_bar_quad_colors(
    color_cfg: dict,
    spec_col: tuple[float, float, float, float] | tuple[float, float, float],
    count: int,
    alpha: float,
) -> np.ndarray:
    from features.video.lib.spectrum_color_engine import build_spectrum_bar_quad_rgba

    mode = str(color_cfg.get("mode", "solid") or "solid").lower().strip()
    solid = color_cfg.get("solidColor")
    if not isinstance(solid, str) or not solid.strip():
        solid = "#{:02x}{:02x}{:02x}".format(
            int(max(0, min(255, round(float(spec_col[0]) * 255.0)))),
            int(max(0, min(255, round(float(spec_col[1]) * 255.0)))),
            int(max(0, min(255, round(float(spec_col[2]) * 255.0)))),
        )
    gradient_colors = color_cfg.get("gradientColors") if isinstance(color_cfg.get("gradientColors"), list) else None
    gradient_direction = str(color_cfg.get("gradientDirection", "left-to-right") or "left-to-right")
    return build_spectrum_bar_quad_rgba(
        mode=mode,
        solid_color=str(solid),
        gradient_colors=gradient_colors,
        count=count,
        alpha=alpha,
        gradient_direction=gradient_direction,
    )

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


def _render_panel_rgba(
    width_px: float,
    height_px: float,
    *,
    fill: str = "#0f172a",
    opacity: float = 0.45,
    border_color: str = "#94a3b8",
    border_width: float = 1.0,
    radius: float = 12.0,
    frost: float = 0.4,
    specular: float = 0.5,
    label: str = "",
    label_size_px: float = 0.0,
    label_font_family: str = "montserrat",
    label_bold: bool = True,
) -> tuple[np.ndarray, int, int]:
    """Rasterize a rounded glass plate (optional centered label for NOW PLAYING pills)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    from features.video.lib.system_fonts import resolve_font_file

    w = int(max(4, min(4096, round(float(width_px)))))
    h = int(max(4, min(4096, round(float(height_px)))))
    rad = float(max(0.0, min(min(w, h) * 0.5, float(radius))))
    op = float(max(0.0, min(1.0, float(opacity))))
    frost_amt = float(max(0.0, min(1.0, float(frost))))
    spec_amt = float(max(0.0, min(1.0, float(specular))))
    bw = float(max(0.0, min(24.0, float(border_width))))
    pad = int(max(2, round(bw + 4.0 + frost_amt * 6.0)))
    img_w = w + pad * 2
    img_h = h + pad * 2
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    box = (pad, pad, pad + w - 1, pad + h - 1)
    # Keep plate readable on dark video backgrounds (floor alpha).
    fill_a = int(round(255 * max(0.35, op * (0.65 + frost_amt * 0.3))))
    fill_rgba = _hex_to_rgba(fill, fill_a)
    border_rgba = _hex_to_rgba(border_color, 255)
    # Soft outer neon glow for the frame edge.
    if bw > 0.05:
        glow = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        glow_box = (pad - 2, pad - 2, pad + w + 1, pad + h + 1)
        gd.rounded_rectangle(
            glow_box,
            radius=rad + 2,
            outline=(border_rgba[0], border_rgba[1], border_rgba[2], 180),
            width=max(2, int(round(bw + 2))),
        )
        glow = glow.filter(ImageFilter.GaussianBlur(radius=max(2, int(round(2 + frost_amt * 3)))))
        img = Image.alpha_composite(img, glow)
        draw = ImageDraw.Draw(img)
    # Soft drop shadow.
    shadow = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(box, radius=rad, fill=(0, 0, 0, int(110 * (0.4 + frost_amt * 0.5))))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(1, int(round(3 + frost_amt * 5)))))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)
    # Reliable border ring: outer accent fill, then punch inner plate fill.
    # (Pillow outline width is inconsistent across versions.)
    inset = max(1, int(round(max(bw, 1.5))))
    if bw > 0.05:
        draw.rounded_rectangle(box, radius=rad, fill=border_rgba)
        inner = (pad + inset, pad + inset, pad + w - 1 - inset, pad + h - 1 - inset)
        inner_rad = max(0.0, rad - float(inset))
        draw.rounded_rectangle(inner, radius=inner_rad, fill=fill_rgba)
        plate_box = inner
        plate_rad = inner_rad
    else:
        draw.rounded_rectangle(box, radius=rad, fill=fill_rgba)
        plate_box = box
        plate_rad = rad
    # Frost veil: soft white wash stronger at the top (fake glass, no scene blur).
    if frost_amt > 0.04:
        veil = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        vd = ImageDraw.Draw(veil)
        bands = max(4, min(24, int(round(8 + frost_amt * 10))))
        px0, py0, px1, py1 = plate_box
        ph = max(1, py1 - py0)
        for i in range(bands):
            t0 = i / bands
            t1 = (i + 1) / bands
            y0 = py0 + int(round(ph * t0))
            y1 = py0 + int(round(ph * t1))
            a = int(round(150 * frost_amt * (1.0 - t0 * 0.9)))
            if a <= 0 or y1 <= y0:
                continue
            vd.rectangle((px0, y0, px1, y1), fill=(220, 235, 255, a))
        mask = Image.new("L", (img_w, img_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(plate_box, radius=plate_rad, fill=255)
        r, g, b, a_ch = veil.split()
        from PIL import ImageChops

        veil = Image.merge("RGBA", (r, g, b, ImageChops.multiply(a_ch, mask)))
        veil = veil.filter(ImageFilter.GaussianBlur(radius=max(1, int(round(1 + frost_amt * 2.5)))))
        img = Image.alpha_composite(img, veil)
        draw = ImageDraw.Draw(img)
    if spec_amt > 0.05:
        # Specular edge along the top of the plate.
        highlight = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        hd = ImageDraw.Draw(highlight)
        hy1 = pad + max(1, int(round(h * 0.08)))
        hd.rounded_rectangle(
            (pad + 2, pad + 1, pad + w - 3, hy1),
            radius=max(2.0, rad * 0.35),
            fill=(255, 255, 255, int(round(160 * spec_amt))),
        )
        highlight = highlight.filter(ImageFilter.GaussianBlur(radius=max(1, int(round(1.5 + spec_amt * 2)))))
        img = Image.alpha_composite(img, highlight)
        draw = ImageDraw.Draw(img)
    label_text = str(label or "").strip()
    if label_text:
        size = int(max(6, min(128, round(float(label_size_px or max(8.0, h * 0.42))))))
        try:
            font = ImageFont.truetype(resolve_font_file(label_font_family, bold=bool(label_bold)), size)
        except Exception:
            try:
                font = ImageFont.truetype("arial.ttf", size)
            except Exception:
                font = ImageFont.load_default()
        # Dark text on bright pill, light text on dark plate.
        r, g, b, _a = fill_rgba
        luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        ink = (15, 23, 42, 255) if luminance > 0.55 else (248, 250, 252, 255)
        if "\n" in label_text:
            tb = draw.multiline_textbbox((0, 0), label_text, font=font, align="center", spacing=2)
            tw = float(tb[2] - tb[0])
            th = float(tb[3] - tb[1])
            tx = pad + (w - tw) * 0.5 - tb[0]
            ty = pad + (h - th) * 0.5 - tb[1]
            draw.multiline_text((tx, ty), label_text, font=font, fill=ink, align="center", spacing=2)
        else:
            tb = draw.textbbox((0, 0), label_text, font=font)
            tw = float(tb[2] - tb[0])
            th = float(tb[3] - tb[1])
            tx = pad + (w - tw) * 0.5 - tb[0]
            ty = pad + (h - th) * 0.5 - tb[1]
            draw.text((tx, ty), label_text, font=font, fill=ink)
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    arr = np.flipud(arr)
    return arr, int(img.width), int(img.height)


def _render_stage_art_rgba(
    width_px: float,
    height_px: float,
    *,
    logo_path: str = "",
    ring_color: str = "#e879f9",
    ring_count: int = 4,
    border_width: float = 2.0,
    fill: str = "#12041c",
) -> tuple[np.ndarray, int, int]:
    """Circular cover art with concentric neon rings (Playlist Stage)."""
    from PIL import Image, ImageDraw, ImageFilter

    w = int(max(8, min(2048, round(float(width_px)))))
    h = int(max(8, min(2048, round(float(height_px)))))
    size = min(w, h)
    pad = int(max(8, round(size * 0.18)))
    canvas = size + pad * 2
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = canvas * 0.5
    r = size * 0.5
    accent = _hex_to_rgba(ring_color, 255)
    # Concentric rings outside the disc
    rings = max(1, min(8, int(ring_count)))
    for i in range(rings, 0, -1):
        rr = r + (pad * 0.55) * (i / rings)
        a = int(max(40, 200 - i * 28))
        draw.ellipse(
            (cx - rr, cy - rr, cx + rr, cy + rr),
            outline=(accent[0], accent[1], accent[2], a),
            width=max(1, int(round(1.0 + (rings - i) * 0.35))),
        )
    # Disc fill / photo
    disc = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    dd = ImageDraw.Draw(disc)
    fill_rgba = _hex_to_rgba(fill, 230)
    dd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill_rgba)
    path = str(logo_path or "").strip()
    if path:
        try:
            from pathlib import Path

            if Path(path).is_file():
                cover = Image.open(path).convert("RGBA")
                side = int(max(8, round(r * 2)))
                cover = cover.resize((side, side), Image.Resampling.LANCZOS)
                mask = Image.new("L", (side, side), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, side - 1, side - 1), fill=255)
                ox = int(round(cx - r))
                oy = int(round(cy - r))
                disc.paste(cover, (ox, oy), mask)
        except Exception:
            pass
    # Neon rim
    bw = max(1, int(round(float(border_width))))
    dd = ImageDraw.Draw(disc)
    dd.ellipse((cx - r, cy - r, cx + r, cy + r), outline=accent, width=bw)
    glow = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2), outline=(accent[0], accent[1], accent[2], 160), width=3)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(2, int(round(size * 0.04)))))
    img = Image.alpha_composite(img, glow)
    img = Image.alpha_composite(img, disc)
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    arr = np.flipud(arr)
    return arr, int(img.width), int(img.height)


def _render_overlay_rgba(overlay: dict, scale: float) -> tuple[np.ndarray, int, int]:
    """Dispatch text vs panel/pill/stage-art rasters for preview + export."""
    kind = str((overlay or {}).get("overlayKind") or "text").strip().lower()
    scale = float(max(0.05, min(16.0, float(scale or 1.0))))
    if kind == "stage_art":
        return _render_stage_art_rgba(
            float((overlay or {}).get("panelWidth") or 120.0) * scale,
            float((overlay or {}).get("panelHeight") or 120.0) * scale,
            logo_path=str((overlay or {}).get("logoPath") or ""),
            ring_color=str((overlay or {}).get("ringColor") or (overlay or {}).get("strokeColor") or "#e879f9"),
            ring_count=int((overlay or {}).get("ringCount") or 4),
            border_width=float((overlay or {}).get("strokeWidth") or 2.0) * scale,
            fill=str((overlay or {}).get("color") or "#12041c"),
        )
    if kind in {"panel", "pill"}:
        return _render_panel_rgba(
            float((overlay or {}).get("panelWidth") or 120.0) * scale,
            float((overlay or {}).get("panelHeight") or 40.0) * scale,
            fill=str((overlay or {}).get("color") or "#0f172a"),
            opacity=float((overlay or {}).get("opacity") if "opacity" in (overlay or {}) else 0.45),
            border_color=str((overlay or {}).get("strokeColor") or "#94a3b8"),
            border_width=float((overlay or {}).get("strokeWidth") or 0.0) * scale,
            radius=float((overlay or {}).get("panelRadius") or 12.0) * scale,
            frost=float((overlay or {}).get("panelFrost") or 0.0),
            specular=float((overlay or {}).get("panelSpecular") or 0.0),
            label=str((overlay or {}).get("text") or "") if kind == "pill" else "",
            label_size_px=float((overlay or {}).get("sizePx") or 0.0) * scale,
            label_font_family=str((overlay or {}).get("fontFamily") or "montserrat"),
            label_bold=bool((overlay or {}).get("bold", True)),
        )
    text = str((overlay or {}).get("text", "") or "").strip()
    size_px = float((overlay or {}).get("sizePx", 46.0) if "sizePx" in (overlay or {}) else 46.0)
    return _render_text_rgba(
        text,
        size_px * scale,
        str((overlay or {}).get("color", "#ffffff") or "#ffffff"),
        str((overlay or {}).get("strokeColor", "#000000") or "#000000"),
        float((overlay or {}).get("strokeWidth", 2.0) if "strokeWidth" in (overlay or {}) else 2.0) * scale,
        float((overlay or {}).get("shadow", 0.4) if "shadow" in (overlay or {}) else 0.4),
        font_family=str((overlay or {}).get("fontFamily", "arial") or "arial"),
        bold=bool((overlay or {}).get("bold", False)),
        italic=bool((overlay or {}).get("italic", False)),
        letter_spacing=float((overlay or {}).get("letterSpacing", 0.0) if "letterSpacing" in (overlay or {}) else 0.0)
        * scale,
        line_spacing=float((overlay or {}).get("lineSpacing", 1.15) if "lineSpacing" in (overlay or {}) else 1.15),
        align=str((overlay or {}).get("align", "left") or "left"),
        box_width=float((overlay or {}).get("boxWidth", 0.0) if "boxWidth" in (overlay or {}) else 0.0) * scale,
        fill_mode=str((overlay or {}).get("fillMode", "solid") or "solid"),
        gradient_colors=(overlay or {}).get("gradientColors")
        if isinstance((overlay or {}).get("gradientColors"), list)
        else [],
        gradient_direction=str((overlay or {}).get("gradientDirection", "vertical") or "vertical"),
        glow=float((overlay or {}).get("glow", 0.0) if "glow" in (overlay or {}) else 0.0),
        glow_color=str((overlay or {}).get("glowColor", "#ff4fd8") or "#ff4fd8"),
        glow_blur=float((overlay or {}).get("glowBlur", 8.0) if "glowBlur" in (overlay or {}) else 8.0) * scale,
        glow_mode=str((overlay or {}).get("glowMode", "solid") or "solid"),
        glow_gradient_colors=(overlay or {}).get("glowGradientColors")
        if isinstance((overlay or {}).get("glowGradientColors"), list)
        else [],
        glow_gradient_direction=str(
            (overlay or {}).get("glowGradientDirection", "horizontal") or "horizontal"
        ),
        shadow_blur=float((overlay or {}).get("shadowBlur", 0.0) if "shadowBlur" in (overlay or {}) else 0.0)
        * scale,
        extrude_depth=float((overlay or {}).get("extrudeDepth", 0.0) if "extrudeDepth" in (overlay or {}) else 0.0)
        * scale,
        extrude_color=str((overlay or {}).get("extrudeColor", "#1a1a1a") or "#1a1a1a"),
    )


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
        kind = str(o.get("overlayKind") or "text").strip().lower()
        text = str(o.get("text", "") or "").strip()
        if kind not in {"panel", "pill", "stage_art"} and not text:
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
        opacity_mul = float(o.get("opacity", 1.0) if "opacity" in o else 1.0)
        # Scale with output height / renderBaseHeight (no 4× cap — preview ↔ export match).
        scale = float(max(0.05, min(16.0, float(sf or 1.0))))
        if kind in {"panel", "pill", "stage_art"}:
            key = (
                f"shape:{kind}|{float(o.get('panelWidth') or 0):.1f}|{float(o.get('panelHeight') or 0):.1f}"
                f"|{o.get('color')}|{opacity_mul:.3f}|{o.get('strokeColor')}|{float(o.get('strokeWidth') or 0):.2f}"
                f"|{float(o.get('panelRadius') or 0):.2f}|{float(o.get('panelFrost') or 0):.2f}"
                f"|{float(o.get('panelSpecular') or 0):.2f}|{text}|{float(o.get('sizePx') or 0):.2f}"
                f"|{o.get('fontFamily')}|{o.get('logoPath')}|sf:{scale:.4f}"
            )
        else:
            size_px = float(o.get("sizePx", 46.0) if "sizePx" in o else 46.0)
            col = str(o.get("color", "#ffffff") or "#ffffff").strip()
            scol = str(o.get("strokeColor", "#000000") or "#000000").strip()
            sw = float(o.get("strokeWidth", 2.0) if "strokeWidth" in o else 2.0)
            sh = float(o.get("shadow", 0.4) if "shadow" in o else 0.4)
            font_family = str(o.get("fontFamily", "arial") or "arial")
            bold = bool(o.get("bold", False))
            italic = bool(o.get("italic", False))
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
            key = (
                f"{text}|{size_px:.2f}|{col}|{scol}|{sw:.2f}|{sh:.2f}|{font_family}|{int(bold)}|{int(italic)}"
                f"|{letter_spacing:.2f}|{line_spacing:.2f}|{align}|{box_width:.1f}|{fill_mode}|{grad_key}|{gradient_direction}"
                f"|{glow_amt:.2f}|{glow_color}|{glow_blur:.2f}|{glow_mode}|{glow_grad_key}|{glow_gradient_direction}"
                f"|{shadow_blur:.2f}|{extrude_depth:.2f}|{extrude_color}|sf:{scale:.4f}"
            )
        if key_list[idx] != key or tex_list[idx] is None:
            arr, tw, th = _render_overlay_rgba(o, scale)
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
        # Panel opacity is baked into the raster; avoid double-multiplying fill alpha.
        draw_opacity = float(opacity if kind in {"panel", "pill", "stage_art"} else opacity * opacity_mul)
        prog_text["tex_text"].value = 2
        tx.use(location=2)
        prog_text["out_size"].value = (float(w), float(h))
        prog_text["text_px"].value = (
            float(ax) - float(w) * 0.5 + dx + qx,
            float(ay) - float(h) * 0.5 + dy + qy,
        )
        prog_text["text_size_px"].value = (draw_w, draw_h)
        prog_text["text_opacity"].value = float(max(0.0, min(1.0, draw_opacity)))
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
from shared.lib.export_codec import export_video_codec_label


_EXPORT_INIT_PROGRESS_MAX = 0.12
_EXPORT_RENDER_PROGRESS_SPAN = 0.88


def _encode_frame_progress(frame_index: int, total_frames: int) -> float:
    total = max(1, int(total_frames))
    idx = max(0, min(int(frame_index), total - 1))
    return _EXPORT_INIT_PROGRESS_MAX + _EXPORT_RENDER_PROGRESS_SPAN * ((idx + 1) / total)


_EXPORT_PROFILE_SAMPLE_EVERY = 60


def _export_profile_enabled() -> bool:
    raw = str(os.environ.get("CAMXORA_EXPORT_PROFILE", "0") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


class _ExportFrameProfiler:
    """Rolling per-phase frame timings (optional ``CAMXORA_EXPORT_PROFILE=1``)."""

    def __init__(self, *, emit: Callable[[dict], None], sample_every: int = _EXPORT_PROFILE_SAMPLE_EVERY) -> None:
        self._emit = emit
        self._sample_every = max(1, int(sample_every))
        self._audio_ms: list[float] = []
        self._gl_ms: list[float] = []
        self._readback_ms: list[float] = []
        self._encode_ms: list[float] = []
        self._since_emit = 0

    def record(self, *, audio_ms: float, gl_ms: float, readback_ms: float, encode_ms: float) -> None:
        self._audio_ms.append(float(audio_ms))
        self._gl_ms.append(float(gl_ms))
        self._readback_ms.append(float(readback_ms))
        self._encode_ms.append(float(encode_ms))
        self._since_emit += 1
        if self._since_emit >= self._sample_every:
            self._emit_rolling()
            self._since_emit = 0

    def flush(self) -> None:
        if self._audio_ms and self._since_emit > 0:
            self._emit_rolling()

    @staticmethod
    def _avg(values: list[float]) -> float | None:
        if not values:
            return None
        return float(sum(values) / len(values))

    def _emit_rolling(self) -> None:
        profile = {
            "sampleFrames": len(self._audio_ms),
            "audioStepAvgMs": self._avg(self._audio_ms),
            "glRenderAvgMs": self._avg(self._gl_ms),
            "readbackAvgMs": self._avg(self._readback_ms),
            "encodeWriteAvgMs": self._avg(self._encode_ms),
        }
        parts: list[str] = []
        for label, key in (
            ("audio", "audioStepAvgMs"),
            ("gl", "glRenderAvgMs"),
            ("readback", "readbackAvgMs"),
            ("encode", "encodeWriteAvgMs"),
        ):
            value = profile.get(key)
            if isinstance(value, (int, float)):
                parts.append(f"{label}={value:.2f} ms")
        self._emit(
            {
                "status": "running",
                "message": "Export frame profile (rolling avg): " + ", ".join(parts),
                "exportFrameProfile": profile,
            }
        )
        self._audio_ms.clear()
        self._gl_ms.clear()
        self._readback_ms.clear()
        self._encode_ms.clear()


def normalize_export_speed_mode(speed_mode: str | None) -> str:
    mode = str(speed_mode or "balanced").strip().lower()
    if mode in {"very_fast", "draft", "fast", "balanced", "quality", "master"}:
        return mode
    return "balanced"


def export_glow_pass_limit(speed_mode: str | None) -> int:
    """How many spectrum bloom/glow passes to draw during export.

    Preview always draws up to two additive glow layers under the main pass.
    Heavy templates (e.g. Bass Drive liquid + glow=100) pay that cost every
    frame on the CPU waveform path. Speed tiers trade glow for throughput:

    - ``very_fast`` / ``draft`` / ``fast`` / ``balanced``: skip glow (0)
    - ``quality`` / ``master``: full dual glow (2)

    On ``low`` GPU tier (GTX 1050 Ti-class), Balanced already skips glow; Master
    stays full so high-end quality is unchanged.
    """
    mode = normalize_export_speed_mode(speed_mode)
    if mode in {"very_fast", "draft", "fast", "balanced"}:
        return 0
    return 2


def export_particle_caps(speed_mode: str | None, *, max_count: int, spawn_rate: float) -> tuple[int, float]:
    """Cap particle count/spawn for export speed modes (preview unchanged).

    Bass Drive ships ~1200 max / 400 spawn vs Beattok ~475 / 100 — the gap is
    mostly particle load. Caps leave light templates alone and tame heavy ones.

    ``low`` GPU tier (``CAMXORA_GPU_TIER=low`` or auto <6GB / 1050-class) uses
    tighter Draft/Fast/Balanced caps. Master/quality stay uncapped.
    """
    from visualizer.export_gpu_tier import detect_export_gpu_tier

    mode = normalize_export_speed_mode(speed_mode)
    count = int(max(0, max_count))
    rate = float(max(0.0, spawn_rate))
    low_gpu = detect_export_gpu_tier() == "low"
    if mode in {"very_fast", "draft"}:
        cap_count, cap_rate = (150, 50.0) if low_gpu else (250, 80.0)
        return min(count, cap_count), min(rate, cap_rate)
    if mode == "fast":
        cap_count, cap_rate = (250, 80.0) if low_gpu else (400, 120.0)
        return min(count, cap_count), min(rate, cap_rate)
    if mode == "balanced":
        cap_count, cap_rate = (350, 100.0) if low_gpu else (600, 200.0)
        return min(count, cap_count), min(rate, cap_rate)
    return count, rate


def build_nvenc_export_args(speed_mode: str, *, pipe_pix_fmt: str = "rgba", color_range: str = "pc") -> list[str]:
    """NVENC output flags by speed mode (REQ-2.x encode throughput).

    Presets/CQ match pre-throughput baselines so file size stays predictable.
    Low-latency / ``-bf 0`` are opt-in via ``CAMXORA_NVENC_LL=1`` — they inflate
    bitrate and often feel slower on desktop exports.
    """
    import os

    mode = normalize_export_speed_mode(speed_mode)
    range_tag = str(color_range or "pc").strip().lower()
    if range_tag not in {"pc", "tv"}:
        range_tag = "pc"
    _ = pipe_pix_fmt  # API reserved for pipe-specific codec flags
    if mode in {"very_fast", "draft"}:
        nvenc_preset = "p1"
        nvenc_cq = "27"
    elif mode == "fast":
        nvenc_preset = "p3"
        nvenc_cq = "23"
    elif mode in {"quality", "master"}:
        nvenc_preset = "p5"
        nvenc_cq = "19"
    else:
        # balanced / Standard default
        nvenc_preset = "p3"
        nvenc_cq = "23"
    args: list[str] = [
        "-c:v",
        "h264_nvenc",
        "-preset",
        nvenc_preset,
        "-rc",
        "constqp",
        "-cq",
        nvenc_cq,
        "-color_range",
        range_tag,
        "-pix_fmt",
        "yuv420p",
    ]
    ll_raw = str(os.environ.get("CAMXORA_NVENC_LL", "0") or "0").strip().lower()
    if ll_raw in {"1", "true", "yes", "on"}:
        args += ["-tune", "ll", "-zerolatency", "1", "-bf", "0"]
    return args


def _start_ffmpeg(
    ffmpeg_path: str,
    mp3_path: str,
    out_path: str,
    w: int,
    h: int,
    fps: int,
    speed_mode: str,
    *,
    pipe_pix_fmt: str = "rgba",
) -> tuple[subprocess.Popen, str]:
    mode = str(speed_mode or "balanced").strip().lower()
    pipe_fmt = str(pipe_pix_fmt or "rgba").strip().lower()
    if pipe_fmt not in {"rgba", "nv12", "yuv420p"}:
        pipe_fmt = "rgba"
    if pipe_fmt in {"nv12", "yuv420p"} and (int(w) % 2 != 0 or int(h) % 2 != 0):
        pipe_fmt = "rgba"
    if mode == "very_fast":
        x264_preset = "ultrafast"
        x264_crf = "26"
    elif mode == "fast":
        x264_preset = "superfast"
        x264_crf = "23"
    else:
        x264_preset = "veryfast"
        x264_crf = "20"
    from visualizer.readback import pipe_frame_byte_size, pipe_needs_cpu_pack, yuv_pipe_color_range

    color_range = yuv_pipe_color_range() if pipe_needs_cpu_pack(pipe_fmt) else "pc"
    # Deeper demux queue reduces stdin back-pressure when pack/write outpaces NVENC briefly.
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
        pipe_fmt,
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-thread_queue_size",
        "64",
        "-i",
        "pipe:0",
        "-thread_queue_size",
        "64",
        "-i",
        mp3_path,
        "-af",
        "aresample=async=1000",
    ]
    if pipe_fmt == "rgba":
        cmd += ["-vf", "scale=in_range=pc:out_range=pc"]
    cmd += build_nvenc_export_args(mode, pipe_pix_fmt=pipe_fmt, color_range=color_range)
    cmd += [
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        out_path,
    ]
    err_file = open(Path(out_path).parent / f"ffmpeg_error_{uuid.uuid4().hex[:8]}.log", "w+", encoding="utf-8")
    # One-frame stdin buffer (~3 MiB yuv420p / ~8 MiB rgba) avoids 8 KiB default churn.
    _stdin_buf = max(1024 * 1024, pipe_frame_byte_size(w, h, pipe_fmt))
    enc = popen_hidden(cmd, stdin=subprocess.PIPE, stderr=err_file, bufsize=_stdin_buf)
    time.sleep(0.2)
    video_codec = "h264_nvenc"
    if enc.poll() is not None:
        err_file.seek(0)
        err_txt = err_file.read()
        cmd2 = cmd[:]
        cmd2[cmd2.index("h264_nvenc")] = "libx264"
        for flag in ("-cq", "-rc", "-tune", "-zerolatency", "-bf"):
            while flag in cmd2:
                i = cmd2.index(flag)
                del cmd2[i : i + 2]
        if "-preset" in cmd2:
            i = cmd2.index("-preset")
            cmd2[i + 1] = x264_preset
        if "-crf" not in cmd2:
            cmd2.insert(cmd2.index("-pix_fmt"), "-crf")
            cmd2.insert(cmd2.index("-pix_fmt") + 1, x264_crf)
        err_file.seek(0)
        err_file.truncate()
        enc = popen_hidden(cmd2, stdin=subprocess.PIPE, stderr=err_file, bufsize=_stdin_buf)
        video_codec = "libx264"
        time.sleep(0.2)
        if enc.poll() is not None:
            err_file.seek(0)
            err_txt2 = err_file.read()
            raise RuntimeError(err_txt2.strip() or "FFmpeg failed to start")
    
    # attach err_file to enc so we can close/read it later
    enc._err_file = err_file
    enc._pipe_pix_fmt = pipe_fmt
    return enc, video_codec


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


def _resolve_spectrum_logo_centers(
    *,
    w: int,
    h: int,
    sf: float,
    position: dict | None,
    spectrum_attach_to_logo: bool,
    logo_position: dict | None = None,
    template: dict | None = None,
) -> tuple[tuple[float, float], tuple[float, float]]:
    from features.video.lib.logo_spectrum_bindings import resolve_spectrum_logo_centers

    logo_pos = logo_position
    if logo_pos is None and isinstance(template, dict):
        ls = template.get("logoSettings")
        if isinstance(ls, dict) and isinstance(ls.get("position"), dict):
            logo_pos = ls.get("position")

    return resolve_spectrum_logo_centers(
        _get_anchor_coords,
        w=w,
        h=h,
        sf=sf,
        position=position if isinstance(position, dict) else {},
        spectrum_attach_to_logo=bool(spectrum_attach_to_logo),
        logo_position=logo_pos if isinstance(logo_pos, dict) else {},
    )


def _spectrum_draw_jobs(template: dict) -> list[dict]:
    """Return enabled spectrum instances for export; legacy templates → one job."""
    from features.video.lib.spectrum_instance_registry import iter_render_spectrum_instances
    jobs = iter_render_spectrum_instances(template if isinstance(template, dict) else {})
    if jobs:
        return jobs
    layers = template.get("layers") if isinstance(template, dict) and isinstance(template.get("layers"), list) else []
    layers = [sl for sl in layers if isinstance(sl, dict)]
    if not layers:
        return []
    pos = template.get("position") if isinstance(template.get("position"), dict) else {}
    pb = template.get("previewBindings") if isinstance(template.get("previewBindings"), dict) else {}
    audio = template.get("audioSettings") if isinstance(template.get("audioSettings"), dict) else {}
    return [{
        "style": str(template.get("style") or "orbit-spikes"),
        "anchor": str(pos.get("anchor") or "center"),
        "x": float(pos.get("x", 0.0) or 0.0),
        "y": float(pos.get("y", 0.0) or 0.0),
        "spectrumAttachToLogo": bool(pb.get("spectrumAttachToLogo", True)),
        "spectrumLogoGap": float(pb.get("spectrumLogoGap", 0.0) or 0.0),
        "audioSettings": dict(audio),
        "layers": layers,
        "enabled": True,
    }]



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
    """Backward-compatible alias; see ``frame_integrator.smooth_env``."""
    return smooth_env(prev, target, smoothing, dt=dt, ref_fps=ref_fps)

def run_gpu_render(
    opts: GpuOptions,
    *,
    single_frame_png: str | None = None,
    single_frame_index: int | None = None,
    on_event: Callable[[dict], None] | None = None,
    existing_analyzer: Any | None = None,
    ctx_factory: Callable[[], moderngl.Context] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    cancel_hooks: dict[str, Any] | None = None,
) -> int:
    fps = int(max(1, min(60, int(opts.fps))))
    if fps <= 0:
        fps = 30
    # Keep encode FPS (24/30/…) for speed, but analyze audio at preview rate so
    # spectrum/particles react identically to paintGL (frame_idx = time * 60).
    ANALYSIS_FPS = 60
    export_speed_mode = normalize_export_speed_mode(getattr(opts, "speed_mode", "balanced"))
    glow_pass_limit = export_glow_pass_limit(export_speed_mode)

    def _emit_event(payload: dict) -> None:
        if on_event is not None:
            on_event(payload)
        else:
            _send(payload)

    template = _load_template(opts)

    w = int(max(64, min(8192, int(opts.width) if int(opts.width) > 0 else 1920)))
    h = int(max(64, min(8192, int(opts.height) if int(opts.height) > 0 else 1080)))

    base_h = float(template.get("renderBaseHeight", 450.0))
    base_h = float(max(1.0, min(4000.0, base_h)))
    sf = float(h) / base_h

    _emit_event({"status": "running", "message": "Initializing GPU renderer...", "progress": 0.0})
    if ctx_factory is not None:
        _emit_event({"status": "running", "message": "Using shared OpenGL context...", "progress": 0.02})
        ctx = ctx_factory()
    else:
        _emit_event({"status": "running", "message": "Creating OpenGL context...", "progress": 0.02})
        _init_glfw_hidden(w, h, samples=0)
        ctx = _make_ctx()
    _emit_event({"status": "running", "message": "Loading background and logo assets...", "progress": 0.04})

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

    tex_readback = ctx.texture((w, h), 4)
    tex_readback.filter = (moderngl.LINEAR, moderngl.LINEAR)
    fbo_readback = ctx.framebuffer(color_attachments=[tex_readback])
    prog_readback_flip = _compile_readback_flip(ctx)
    vao_readback_flip = _quad_vao(ctx, prog_readback_flip)

    line_vbo = ctx.buffer(reserve=4 * 6 * 512)
    vao_lines = ctx.vertex_array(prog_lines, [(line_vbo, "2f 4f", "in_pos", "in_col")])
    prog_lines["clip_enabled"].value = 0
    prog_lines["clip_center_px"].value = (0.0, 0.0)
    prog_lines["clip_radius_px"].value = 0.0

    gpu_spectrum = None
    gpu_layer_keys: dict[int, int] = {}
    from .spectrum_gpu import (
        SpectrumGpuRenderer,
        gpu_bar_half_width_scale,
        gpu_bar_style_mode,
        gpu_spectrum_enabled,
        is_gpu_bar_style_slice1,
        is_waveform_spectrum_style,
        quantize_fft_for_gpu_bar_style,
    )

    if gpu_spectrum_enabled():
        gpu_spectrum = SpectrumGpuRenderer(ctx)

    pt_vbo = ctx.buffer(reserve=4 * 3 * 1024)
    vao_pts = ctx.vertex_array(prog_points, [(pt_vbo, "2f 1f", "in_pos", "in_size")])
    # Same styled-quad particle path as live preview (not GL_POINTS).
    prog_particle_quads = _compile_particle_quads(ctx)
    particle_quad_vbo = ctx.buffer(reserve=4 * 10 * 6 * 2048)
    vao_particle_quads = ctx.vertex_array(
        prog_particle_quads,
        [(particle_quad_vbo, "2f 2f 4f 2f", "in_pos", "in_uv", "in_col", "in_meta")],
    )
    music_icon_tex_holder: dict = {}

    _emit_event({"status": "running", "message": "Loading audio analysis...", "progress": 0.08})

    # In the new format, the root template IS the spectrum container
    spectrum_container = template
    point_count = 1024 # Fixed to 1024 for high-res FFT
    
    # We no longer have spec_style or spec_tex for background scale/offset in the spectrum layer.
    # Background scale/offset is now handled via backgroundSettings (if added) or just defaults to 1.0/0.0
    bg_scale = 1.0
    bg_offset = (0.0, 0.0)

    from shared.services.audio_analysis_cache import get_audio_analysis_cache, set_audio_analysis_cache

    if existing_analyzer is not None:
        analyzer = existing_analyzer
        _emit_event(
            {
                "status": "running",
                "message": "Reusing preview audio analysis",
                "progress": 0.09,
                "cacheHit": True,
            }
        )
    else:
        cached_analyzer = get_audio_analysis_cache(
            opts.mp3_path, fps=ANALYSIS_FPS, point_count=point_count
        )
        if cached_analyzer is not None:
            analyzer = cached_analyzer
            _emit_event(
                {
                    "status": "running",
                    "message": "Audio analysis loaded from cache",
                    "progress": 0.09,
                    "cacheHit": True,
                }
            )
        else:
            _emit_event(
                {
                    "status": "running",
                    "message": "Analyzing audio (first track can take a minute)…",
                    "progress": 0.08,
                }
            )

            def _analysis_progress(message: str) -> None:
                _emit_event(
                    {
                        "status": "running",
                        "message": str(message or "Analyzing audio…"),
                        "progress": 0.08,
                    }
                )

            analyzer = AudioAnalyzer(
                opts.mp3_path,
                fps=ANALYSIS_FPS,
                point_count=point_count,
                on_progress=_analysis_progress,
            )
            set_audio_analysis_cache(analyzer, opts.mp3_path)
            _emit_event(
                {
                    "status": "running",
                    "message": "Audio analysis complete, preparing encoder...",
                    "progress": 0.09,
                    "cacheHit": False,
                }
            )
    duration_sec = float(analyzer.info.duration_sec)
    # Encode at export fps, but sample audio analysis at preview fps (60).
    total_frames = int(max(1, int(np.ceil(duration_sec * float(fps)))))

    particles_cfg_raw = template.get("particlesSettings", {}) if isinstance(template.get("particlesSettings"), dict) else {}
    if not particles_cfg_raw and isinstance(template.get("particles"), dict):
        particles_cfg_raw = template.get("particles")  # legacy fallback
    _pt_max = int(particles_cfg_raw.get("maxCount", particles_cfg_raw.get("count", 400)))
    _pt_spawn = float(particles_cfg_raw.get("spawnRate", particles_cfg_raw.get("spawn_rate", 40.0)))
    _pt_max, _pt_spawn = export_particle_caps(
        export_speed_mode, max_count=_pt_max, spawn_rate=_pt_spawn
    )
    particles_cfg = ParticleConfig(
        enabled=bool(particles_cfg_raw.get("enabled", True)),
        max_count=_pt_max,
        spawn_rate=_pt_spawn,
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

    golden_png = str(single_frame_png or "").strip() or None
    golden_idx = int(single_frame_index) if single_frame_index is not None else None
    golden_mode = golden_png is not None and golden_idx is not None
    pipe_writer = None
    native_writer = None
    if golden_mode:
        total_frames = int(max(1, golden_idx + 1))
        enc = None
        video_codec = ""
        async_reader = None

        def _write_pipe_frame(_raw_rgba: bytes) -> None:
            return
    else:
        _emit_event({"status": "running", "message": "Starting encoder...", "progress": 0.1})
        from visualizer.readback import (
            AsyncFramebufferReader,
            PipeFramePacker,
            pipe_needs_cpu_pack,
            prepare_pipe_payload,
            resolve_pipe_pix_fmt,
        )
        from visualizer.encode_pipeline import (
            PipelinedEncodeWriter,
            pipelined_encode_enabled,
            resolve_encode_queue_size,
        )
        from visualizer.native_encode_writer import (
            remux_native_h264_with_audio,
            try_open_native_encode_writer,
        )

        native_h264_path = str(Path(out_path).with_suffix(".native.h264"))
        native_writer = try_open_native_encode_writer(
            width=w,
            height=h,
            fps=fps,
            h264_path=native_h264_path,
        )
        encode_q = resolve_encode_queue_size()
        async_reader = AsyncFramebufferReader(
            ctx,
            width=w,
            height=h,
            components=4,
            cpu_pool_size=encode_q + 2,
        )
        pipe_writer: PipelinedEncodeWriter | None = None
        pack_on_writer = False
        pipe_pix_fmt = "rgba"
        enc = None
        video_codec = "native_nvenc"

        if native_writer is not None:
            if cancel_hooks is not None:
                cancel_hooks["pipe_writer"] = native_writer

            def _write_pipe_frame(raw_rgba: bytes | bytearray) -> None:
                native_writer.submit(raw_rgba)

            codec_label = "NVENC (native)"
            pipe_label = "RGBA→NVENC"
            _emit_event(
                {
                    "status": "running",
                    "message": f"Encoder started ({codec_label})",
                    "progress": 0.11,
                    "videoCodec": video_codec,
                    "pipePixFmt": "rgba",
                    "encodeBackend": "native_nvenc",
                }
            )
        else:
            pipe_pix_fmt = resolve_pipe_pix_fmt(export_speed_mode)
            enc, video_codec = _start_ffmpeg(
                opts.ffmpeg_path,
                opts.mp3_path,
                out_path,
                w,
                h,
                fps,
                export_speed_mode,
                pipe_pix_fmt=pipe_pix_fmt,
            )
            pack_on_writer = pipe_needs_cpu_pack(pipe_pix_fmt)
            if pipelined_encode_enabled():
                pack_fn = PipeFramePacker(w, h, pipe_pix_fmt) if pack_on_writer else None
                pipe_writer = PipelinedEncodeWriter(
                    enc,
                    queue_size=encode_q,
                    err_file=getattr(enc, "_err_file", None),
                    pack_fn=pack_fn,
                )
                if cancel_hooks is not None:
                    cancel_hooks["pipe_writer"] = pipe_writer

            def _write_pipe_frame(raw_rgba: bytes | bytearray) -> None:
                # When pack_fn is set, enqueue raw RGBA and convert on the writer thread.
                if pipe_writer is not None and pack_on_writer:
                    pipe_writer.submit(raw_rgba)
                    return
                payload = prepare_pipe_payload(raw_rgba, w, h, pipe_pix_fmt)
                if pipe_writer is not None:
                    pipe_writer.submit(payload)
                    return
                if enc is None or enc.stdin is None:
                    raise RuntimeError("FFmpeg stdin is not available")
                try:
                    enc.stdin.write(payload)
                except (BrokenPipeError, OSError) as e:
                    if hasattr(enc, "_err_file"):
                        enc._err_file.seek(0)
                        err_txt = enc._err_file.read()
                    else:
                        err_txt = ""
                    raise RuntimeError(f"FFmpeg pipe closed unexpectedly: {err_txt} (OS Error: {e})")

            codec_label = export_video_codec_label(video_codec)
            pipe_label = pipe_pix_fmt.upper()
            _emit_event(
                {
                    "status": "running",
                    "message": f"Encoder started ({codec_label}, {pipe_label} pipe)" if codec_label else f"Encoder started ({pipe_label} pipe)",
                    "progress": 0.11,
                    "videoCodec": video_codec,
                    "pipePixFmt": pipe_pix_fmt,
                    "encodeBackend": "ffmpeg_pipe",
                }
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

        prog_post["tex_in"].value = 0
        prog_post["out_size"].value = (float(w), float(h))
    except Exception as e:
        import traceback
        _emit_event({"status": "failed", "message": f"Shader setup failed: {e}\n{traceback.format_exc()}", "progress": 0.0})
        raise e

    shake_state = CameraShakeState()
    bg_shake_state = BgVibrateState()
    # Use encode-frame dt so particle spawn/motion and envelope time constants
    # advance in wall-clock time (same as integrating preview's 1/60 steps).
    encode_dt = 1.0 / max(1.0, float(fps))
    dt = encode_dt
    kick_bass_state = KickBassEnvelopeState()
    kick_bass_config = KickBassEnvelopeConfig(
        bg_smoothing=bg_smoothing,
        logo_smoothing=logo_smoothing,
    )
    particle_audio_state = ParticleAudioState()
    audio_settings = template.get("audioSettings") if isinstance(template.get("audioSettings"), dict) else {}
    aud_smooth = float(max(0.0, min(0.99, float(audio_settings.get("smoothing", 0.8) or 0.8))))
    if audio_settings.get("motionSmoothing") is not None:
        try:
            aud_smooth = float(max(0.0, min(0.99, float(audio_settings.get("motionSmoothing")))))
        except (TypeError, ValueError):
            pass
    fft_smoothed = np.zeros(64, dtype=np.float32)
    spectrum_peak_cache: dict[str, np.ndarray] = {}
    particles_warmed = False

    _emit_event(
        {
            "status": "running",
            "message": "Preparing first frame...",
            "progress": _EXPORT_INIT_PROGRESS_MAX,
            "videoCodec": video_codec,
        }
    )

    # --- Pre-compute spectrum mapping (once, outside frame loop) ---
    from ._spectrum_fast import (
        precompute_fft_mapping, fft_to_log_bins, smooth_and_mirror, smooth_fft_envelope,
        generate_spectrum_layer_geometry,
        build_waveform_vertices, build_bar_vertices, resolve_bar_pixel_width,
        clamp_spectrum_bar_count, resample_fft_bins, build_solid_band_strip_vertices,
        normalize_spectrum_gravity, build_contour_wave_strips, mirror_spectrum_points_vertical,
        scroll_spectrum_heights,
    )
    from features.video.lib.logo_spectrum_bindings import normalize_logo_shape
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
    _tpl_logo_shape = normalize_logo_shape(circle_mask=logo_circle_mask)
    _tpl_attached_base_radius = float(max(0.0, (logo_base_radius * logo_scale_base * logo_visible_radius_ratio) + spectrum_logo_gap))
    _tpl_attached_layer_base_offset = _resolve_attached_layer_base_offset(_tpl_spectrum_layers, sf)
    last_analysis_idx = -1

    if gpu_spectrum is not None and _tpl_spectrum_enabled:
        _gpu_preregister_layers = _tpl_spectrum_layers
        if not _gpu_preregister_layers:
            try:
                from visualizer.template_runtime import default_renderer_template, normalize_renderer_template

                fallback = normalize_renderer_template(default_renderer_template()).get("layers") or []
                _gpu_preregister_layers = [dict(x) for x in fallback if isinstance(x, dict)]
            except Exception:
                _gpu_preregister_layers = []
    else:
        _gpu_preregister_layers = []

    if gpu_spectrum is not None and _tpl_spectrum_enabled and _gpu_preregister_layers:
        bar_height_mult_pre = _audio_bar_height_mult(template)
        logo_base_radius_pre = float(logo_raw.get("size", 192.0)) * 0.5 * sf if isinstance(logo_raw, dict) else 96.0 * sf
        logo_visual_radius_pre = logo_base_radius_pre * logo_scale_base
        for layer_idx, sl_pre in enumerate(_gpu_preregister_layers):
            style_pre = _resolve_export_spectrum_style(_tpl_style_preset, sl_pre)
            color_cfg_pre = sl_pre.get("color", {}) if isinstance(sl_pre.get("color"), dict) else {}
            dir_pre = str(color_cfg_pre.get("gradientDirection", "left-to-right") or "left-to-right").lower().strip()
            if (
                is_waveform_spectrum_style(style_pre)
                or not is_gpu_bar_style_slice1(style_pre)
                or bool(sl_pre.get("solidBand", False))
                or bool(sl_pre.get("peakCapsEnabled", False))
                or dir_pre == "top-to-bottom"
            ):
                continue
            curved_pre = bool(sl_pre.get("curved", False))
            mirrored_pre = bool(sl_pre.get("mirrored", False))
            bar_width_pre = float(sl_pre.get("barWidth", 4.0)) * sf
            thickness_pre = float(sl_pre.get("thickness", 30.0)) * sf * bar_height_mult_pre
            gravity_pre = normalize_spectrum_gravity(sl_pre.get("gravity", "top"))
            radius_offset_pre = float(sl_pre.get("radiusOffset", 0.0)) * sf
            radius_pre = _resolve_spectrum_layer_radius(
                attached_to_logo=_tpl_attached_to_logo,
                attached_base_radius=_tpl_attached_base_radius,
                attached_layer_base_offset=_tpl_attached_layer_base_offset,
                logo_visual_radius=logo_visual_radius_pre,
                bar_width=bar_width_pre,
                radius_offset=radius_offset_pre,
            )
            c_pre = color_cfg_pre.get("solidColor", "#ffffff")
            if isinstance(c_pre, str) and c_pre.startswith("#"):
                c_pre = c_pre.lstrip("#")
                c_pre = tuple(int(c_pre[i : i + 2], 16) for i in (0, 2, 4))
            op_pre = float(sl_pre.get("opacity", 1.0))
            try:
                spec_col_pre = (
                    float(c_pre[0]) / 255.0,
                    float(c_pre[1]) / 255.0,
                    float(c_pre[2]) / 255.0,
                    float(max(0.0, min(1.0, op_pre))),
                )
            except Exception:
                spec_col_pre = (1.0, 1.0, 1.0, float(max(0.0, min(1.0, op_pre))))
            glow_strength_pre = float(max(0.0, min(100.0, float(sl_pre.get("glow", 0.0))))) / 100.0
            glow_softness_pre = float(max(0.0, min(30.0, float(sl_pre.get("blur", 0.0)))))
            n_pre = clamp_spectrum_bar_count(sl_pre.get("barCount", 64))
            px_pre, py_pre, dx_pre, dy_pre, base_total_length_pre = generate_spectrum_layer_geometry(
                n_pre,
                curved=curved_pre,
                mirrored=mirrored_pre,
                gravity=gravity_pre,
                path_mode=sl_pre.get("pathMode", "auto"),
                radius=radius_pre,
                half_w=radius_pre,
                half_h=radius_pre,
                attached_to_logo=_tpl_attached_to_logo,
                logo_shape=_tpl_logo_shape,
                frame_w=w,
                frame_h=h,
                linear_span=float(sl_pre.get("linearSpan", 1.0) or 1.0),
            )
            pass_specs_pre: list[dict] = []
            if glow_strength_pre > 0.0 and glow_pass_limit >= 1:
                pass_specs_pre.append(
                    {
                        "alpha": op_pre * (0.14 + glow_strength_pre * 0.22),
                        "bar_width": bar_width_pre + ((glow_softness_pre * 1.8) + (glow_strength_pre * 18.0)) * sf,
                        "thickness": thickness_pre + ((glow_softness_pre * 2.2) + (glow_strength_pre * 22.0)) * sf,
                    }
                )
                if glow_pass_limit >= 2:
                    pass_specs_pre.append(
                        {
                            "alpha": op_pre * (0.08 + glow_strength_pre * 0.15),
                            "bar_width": bar_width_pre + ((glow_softness_pre * 3.0) + (glow_strength_pre * 32.0)) * sf,
                            "thickness": thickness_pre + ((glow_softness_pre * 3.4) + (glow_strength_pre * 34.0)) * sf,
                        }
                    )
            pass_specs_pre.append(
                {
                    "alpha": op_pre,
                    "bar_width": bar_width_pre,
                    "thickness": thickness_pre,
                }
            )
            pass_colors_pre: list[np.ndarray] = []
            for pass_i_pre, pass_cfg_pre in enumerate(pass_specs_pre):
                pass_alpha_pre = float(max(0.0, min(1.0, float(pass_cfg_pre["alpha"]))))
                is_glow_pre = pass_i_pre < (len(pass_specs_pre) - 1)
                pass_colors_pre.append(
                    _build_spectrum_vertex_colors(
                        color_cfg_pre,
                        spec_col_pre,
                        n_pre,
                        pass_alpha_pre,
                        glow=is_glow_pre,
                    )
                )
                bw_pre = resolve_bar_pixel_width(
                    float(pass_cfg_pre["bar_width"]),
                    base_total_length_pre / max(1, n_pre),
                )
                bw_pre = float(bw_pre) * float(gpu_bar_half_width_scale(style_pre))
                pass_cfg_pre["bar_half_width"] = float(bw_pre) * 0.5
            if gpu_spectrum.register_layer(
                layer_idx,
                px=px_pre,
                py=py_pre,
                dx=dx_pre,
                dy=dy_pre,
                pass_specs=pass_specs_pre,
                pass_colors=pass_colors_pre,
            ):
                gpu_layer_keys[layer_idx] = layer_idx

    frame_profiler: _ExportFrameProfiler | None = None
    if _export_profile_enabled() and not golden_mode:
        frame_profiler = _ExportFrameProfiler(emit=_emit_event)

    for i in range(total_frames):
        if cancel_check is not None and cancel_check():
            _emit_event({"status": "failed", "message": "Export cancelled.", "progress": 0.0})
            if pipe_writer is not None:
                pipe_writer.cancel()
            elif native_writer is not None:
                native_writer.cancel()
            elif enc is not None and enc.poll() is None:
                try:
                    enc.terminate()
                except OSError:
                    pass
            if ctx_factory is None and not os.environ.get("CAMXORA_DAEMON_JOB"):
                try:
                    glfw.terminate()
                except Exception:
                    pass
            return 1
        _t_frame = time.perf_counter() if frame_profiler is not None else 0.0
        # Sample analysis at preview rate (60 Hz) for identical FFT/features at wall time T.
        time_sec = float(i) / float(max(1.0, float(fps)))
        analysis_idx = int(max(0, min(int(analyzer.info.frames) - 1, int(time_sec * float(ANALYSIS_FPS)))))
        # Advance temporal FFT smooth through every skipped 60 Hz analysis frame so
        # aud_smooth matches preview (which updates once per 60 Hz paint).
        fft = None
        for aidx in range(max(0, last_analysis_idx + 1), analysis_idx + 1):
            fft = analyzer.fft_for_frame(aidx)
            fft_log_step = fft_to_log_bins(fft, _fft_idx1, _fft_idx2, _fft_frac)
            fft_smoothed = smooth_fft_envelope(fft_smoothed, fft_log_step, aud_smooth)
        last_analysis_idx = analysis_idx
        if fft is None:
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
        env_out = integrate_kick_bass_envelopes(
            kick_bass_state,
            KickBassEnvelopeStepInput(bass=bass),
            kick_bass_config,
            dt=encode_dt,
        )
        kick_pow = env_out.kick_pow
        bg_audio_env = env_out.bg_audio_env
        logo_audio_env = env_out.logo_audio_env
        ps_smoothing = float(max(0.0, min(0.99, particles_cfg_raw.get("smoothing", 0.65))))
        onset = float(feats.get("onset", 0.0) or 0.0)
        beat = float(feats.get("beat", 0.0) or 0.0)
        spawn_trigger = str(particles_cfg_raw.get("spawnTrigger", "both") or "both")
        particle_out = integrate_particle_audio(
            particle_audio_state,
            ParticleAudioStepInput(bass=bass, kick_pow=kick_pow, onset=onset, beat=beat),
            ParticleAudioConfig(smoothing=ps_smoothing, spawn_trigger=spawn_trigger),
            dt=encode_dt,
        )
        particle_audio_env = particle_out.particle_audio_env
        p_trigger_env = particle_out.p_trigger_env

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
            
            logo_anchor_pos = template.get("position") if isinstance(template.get("position"), dict) else {}
            _spec_c, l_pos = _resolve_spectrum_logo_centers(
                w=w,
                h=h,
                sf=sf,
                position=logo_anchor_pos,
                spectrum_attach_to_logo=spectrum_attach_to_logo,
                template=template,
            )
            # The shader expects `logo_px` to be an offset from the CENTER (w/2, h/2).
            prog_logo["logo_px"].value = (l_pos[0] - float(w)*0.5 + float(shake_state.x), l_pos[1] - float(h)*0.5 + float(shake_state.y))

        shake_out = integrate_camera_shake(
            shake_state,
            CameraShakeStepInput(
                frame_index=i,
                bass=float(feats.get("bass", 0.0)),
                beat=float(feats.get("beat", 0.0) or 0.0),
                intensity=float(state.get("camera_shake.intensity", shake_intensity)),
            ),
            CameraShakeConfig(enabled=shake_enabled, smoothing=shake_smoothing),
            dt=encode_dt,
        )

        _t_audio = time.perf_counter() if frame_profiler is not None else 0.0
        fbo_scene.use()
        ctx.viewport = (0, 0, w, h)
        ctx.clear(0.0, 0.0, 0.0, 1.0)
        
        # RE-BIND background and logo textures because fbo_out overwrites location 0 with tex_scene!
        tex_bg.use(location=0)
        if tex_logo is not None and logo_enabled:
            tex_logo.use(location=1)
        bg_vibrate_out = integrate_bg_vibrate(
            bg_shake_state,
            BgVibrateStepInput(frame_index=i, bg_audio_env=bg_audio_env),
            BgVibrateConfig(
                motion_mode=bg_motion_mode,
                react_bass=bg_react_bass,
                smoothing=bg_smoothing,
                vibrate_strength=bg_motion_vibrate_strength,
                scale_factor=sf,
            ),
            dt=encode_dt,
        )
        prog_scene["bg_offset"].value = (
            float((-bg_user_off_x / max(1.0, float(w))) + (bg_vibrate_out.x / max(1.0, float(w)))),
            float((bg_user_off_y / max(1.0, float(h))) + (bg_vibrate_out.y / max(1.0, float(h)))),
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
        try:
            from features.video.lib.lightning_render import apply_vignette_reactivity, peak_lightning_flash

            lightning_flash = peak_lightning_flash(
                template if isinstance(template, dict) else {},
                time_sec=float(time_sec),
                bass=float(bass),
                kick=float(kick_pow),
                beat=float(feats.get("beat", 0.0) or 0.0),
                onset=float(feats.get("onset", 0.0) or 0.0),
                audio_env=float(max(bass, kick_pow, bg_audio_env)),
            )
        except Exception:
            apply_vignette_reactivity = None  # type: ignore[assignment]
            lightning_flash = 0.0
        flash_env = float(max(bg_audio_env, lightning_flash))
        prog_scene["vignette_enabled"].value = 1 if bool(vig.get("enabled", False)) else 0
        vig_strength = float(max(0.0, min(1.0, float(vig.get("strength", 0.35) or 0.35))))
        vig_opacity = float(max(0.0, min(1.0, float(vig.get("opacity", 0.65) or 0.65))))
        vig_react = float(max(0.0, min(5.0, float(vig.get("reactivity", 0.0) or 0.0))))
        if apply_vignette_reactivity is not None and vig_react > 0.0:
            vig_strength, vig_opacity = apply_vignette_reactivity(
                strength=vig_strength,
                opacity=vig_opacity,
                reactivity=vig_react,
                flash_env=flash_env,
            )
        prog_scene["vignette_strength"].value = float(vig_strength)
        prog_scene["vignette_feather"].value = float(max(0.0, min(1.0, float(vig.get("feather", 0.65) or 0.65))))
        prog_scene["vignette_opacity"].value = float(vig_opacity)
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
        prog_scene["bg_brightness"].value = float(
            max(0.0, min(3.0, bg_brightness * (1.0 + flash_env * bg_react_bass + lightning_flash * 0.55)))
        )
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
        
        c_pos, _logo_unused = _resolve_spectrum_logo_centers(
            w=w,
            h=h,
            sf=sf,
            position=_tpl_position,
            spectrum_attach_to_logo=spectrum_attach_to_logo,
            template=template,
        )
        cx = c_pos[0] + float(shake_out.x)
        cy = c_pos[1] + float(shake_out.y)

        try:
            from features.video.lib.lightning_render import render_lightning_layers_gl

            render_lightning_layers_gl(
                ctx,
                line_vbo=line_vbo,
                vao_lines=vao_lines,
                template=template if isinstance(template, dict) else {},
                w=w,
                h=h,
                sf=sf,
                cx=cx,
                cy=cy,
                time_sec=float(time_sec),
                bass=float(bass),
                kick=float(kick_pow),
                beat=float(feats.get("beat", 0.0) or 0.0),
                onset=float(feats.get("onset", 0.0) or 0.0),
                audio_env=float(max(bass, kick_pow, bg_audio_env)),
            )
        except Exception:
            pass
        
        for layer_idx, sl in enumerate(spectrum_layers):
            style_preset = _resolve_export_spectrum_style(template_style_preset, sl)
            curved = bool(sl.get("curved", False))
            mirrored = bool(sl.get("mirrored", False))
            bar_width = float(sl.get("barWidth", 4.0)) * sf
            bar_count = clamp_spectrum_bar_count(sl.get("barCount", 64))
            bar_height_mult = _audio_bar_height_mult(template)
            # Match preview default thickness (30), not the old export fallback (150).
            thickness = float(sl.get("thickness", 30.0)) * sf * bar_height_mult
            gravity = normalize_spectrum_gravity(sl.get("gravity", "top"))
            
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
            peak_hold_blend = float(
                max(0.0, min(1.0, float(audio_settings.get("peakHoldBlend", 0.0) or 0.0)))
            )
            peak_caps_wanted = bool(sl.get("peakCapsEnabled", False))
            effective_peak_hold = float(peak_hold_blend)
            if peak_caps_wanted and effective_peak_hold <= 0.001:
                effective_peak_hold = 0.45
            peak_caps_enabled = peak_caps_wanted
            peak_hold_blend = effective_peak_hold
            peak_cap_gap = float(max(0.0, min(24.0, float(sl.get("peakCapGap", 4.0) or 0.0)))) * sf
            peak_cap_thickness = float(max(1.0, min(16.0, float(sl.get("peakCapThickness", 3.0) or 1.0)))) * sf
            peak_cap_decay = float(max(0.7, min(0.995, float(sl.get("peakCapDecay", 0.92) or 0.92))))
            peak_cap_color = str(sl.get("peakCapColor", "#ffffff") or "#ffffff")
            solid_band = bool(sl.get("solidBand", False))

            # 2) 5-Tap Moving Average Smoothing & Mirroring (vectorized)
            render_fft = smooth_and_mirror(fft_s, mirrored)
            render_fft = scroll_spectrum_heights(render_fft, sl.get("frequencyScroll", 0.0))

            sampled_fft = resample_fft_bins(render_fft, bar_count)

            # 3) Generate Points (vectorized)
            n = int(sampled_fft.shape[0])
            px_arr, py_arr, dx_arr, dy_arr, total_length = generate_spectrum_layer_geometry(
                n,
                curved=curved,
                mirrored=mirrored,
                gravity=gravity,
                path_mode=sl.get("pathMode", "auto"),
                radius=radius,
                half_w=radius,
                half_h=radius,
                attached_to_logo=_tpl_attached_to_logo,
                logo_shape=_tpl_logo_shape,
                frame_w=w,
                frame_h=h,
                linear_span=float(sl.get("linearSpan", 1.0) or 1.0),
            )
            reflection_enabled = bool(sl.get("reflectionEnabled", False))
            try:
                reflection_opacity = float(sl.get("reflectionOpacity", 0.32) or 0.32)
            except (TypeError, ValueError):
                reflection_opacity = 0.32
            reflection_opacity = float(max(0.05, min(0.85, reflection_opacity)))
            draw_variants = [(px_arr, py_arr, dx_arr, dy_arr, 1.0)]
            if reflection_enabled:
                r_px, r_py, r_dx, r_dy = mirror_spectrum_points_vertical(px_arr, py_arr, dx_arr, dy_arr)
                draw_variants.append((r_px, r_py, r_dx, r_dy, reflection_opacity))
            main_px, main_py, main_dx, main_dy = px_arr, py_arr, dx_arr, dy_arr
            base_total_length = total_length
            prog_lines["clip_enabled"].value = 0
            pass_specs: list[dict] = []
            if glow_strength > 0.0 and glow_pass_limit >= 1:
                pass_specs.append(
                    {
                        "is_glow": True,
                        "alpha": op * (0.14 + glow_strength * 0.22),
                        "bar_width": bar_width + ((glow_softness * 1.8) + (glow_strength * 18.0)) * sf,
                        "thickness": thickness + ((glow_softness * 2.2) + (glow_strength * 22.0)) * sf,
                        "fill_circle": False,
                    }
                )
                if glow_pass_limit >= 2:
                    pass_specs.append(
                        {
                            "is_glow": True,
                            "alpha": op * (0.08 + glow_strength * 0.15),
                            "bar_width": bar_width + ((glow_softness * 3.0) + (glow_strength * 32.0)) * sf,
                            "thickness": thickness + ((glow_softness * 3.4) + (glow_strength * 34.0)) * sf,
                            "fill_circle": False,
                        }
                    )
            allow_fill_circle = bool(sl.get("fillCircle", False))
            pass_specs.append(
                {
                    "is_glow": False,
                    "alpha": op,
                    "bar_width": bar_width,
                    "thickness": thickness,
                    "fill_circle": allow_fill_circle,
                }
            )

            for v_px, v_py, v_dx, v_dy, v_alpha_mul in draw_variants:
              px_arr, py_arr, dx_arr, dy_arr = v_px, v_py, v_dx, v_dy
              for pass_i, pass_cfg in enumerate(pass_specs):
                if pass_cfg["is_glow"] and v_alpha_mul < 0.999:
                    continue
                if pass_cfg["is_glow"]:
                    ctx.blend_func = moderngl.ADDITIVE_BLENDING
                elif blend_mode in ("screen", "add", "lighten"):
                    ctx.blend_func = moderngl.ADDITIVE_BLENDING
                else:
                    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

                pass_alpha = float(max(0.0, min(1.0, float(pass_cfg["alpha"]) * float(v_alpha_mul))))
                pass_bar_width = float(pass_cfg["bar_width"])
                pass_thickness = float(pass_cfg["thickness"])
                fill_circle_pass = bool(pass_cfg["fill_circle"])

                val_arr = (sampled_fft * pass_thickness).astype(np.float32)

                cols = _build_spectrum_vertex_colors(
                    color_cfg,
                    spec_col,
                    n,
                    pass_alpha,
                    glow=bool(pass_cfg["is_glow"]),
                )

                bw = resolve_bar_pixel_width(pass_bar_width, base_total_length / max(1, n))

                if style_preset == "contour-waves":
                    nn = n
                    px2, py2, dx2, dy2 = px_arr, py_arr, dx_arr, dy_arr
                    val2 = val_arr
                    if curved and mirrored:
                        px2 = np.concatenate([px_arr, px_arr[:1]])
                        py2 = np.concatenate([py_arr, py_arr[:1]])
                        dx2 = np.concatenate([dx_arr, dx_arr[:1]])
                        dy2 = np.concatenate([dy_arr, dy_arr[:1]])
                        val2 = np.concatenate([val_arr, val_arr[:1]])
                        nn += 1
                    strips = build_contour_wave_strips(
                        px2, py2, dx2, dy2, val2, cx, cy, w, h,
                        line_count=5,
                        line_half_px=float(max(0.7, pass_bar_width * 0.45)),
                    )
                    for strip_i, strip_pos in enumerate(strips):
                        strip_nn = int(strip_pos.shape[0] // 2)
                        strip_alpha = float(
                            max(0.0, min(1.0, pass_alpha * (0.45 + 0.55 * ((strip_i + 1) / max(1, len(strips))))))
                        )
                        strip_cols = np.repeat(
                            _build_spectrum_vertex_colors(
                                color_cfg,
                                spec_col,
                                strip_nn,
                                strip_alpha,
                                glow=bool(pass_cfg["is_glow"]),
                            ),
                            2,
                            axis=0,
                        )
                        strip_verts = np.column_stack([strip_pos, strip_cols]).astype(np.float32)
                        if strip_verts.nbytes > line_vbo.size:
                            line_vbo.orphan(size=strip_verts.nbytes)
                        line_vbo.write(strip_verts.tobytes())
                        vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(strip_pos.shape[0]))
                elif style_preset in ("aurora-ribbon", "magma-ridge", "plasma-bloom", "soft-waveform", "mountain", "liquid", "continuous-waveform"):
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
                elif gpu_spectrum is not None and layer_idx in gpu_layer_keys:
                    gpu_fft = quantize_fft_for_gpu_bar_style(
                        style_preset,
                        render_fft,
                        thickness=pass_thickness,
                        sf=sf,
                    )
                    half_w = float(bw) * 0.5 * float(gpu_bar_half_width_scale(style_preset))
                    gpu_spectrum.draw_pass(
                        gpu_layer_keys[layer_idx],
                        pass_i,
                        gpu_fft,
                        cx=cx,
                        cy=cy,
                        w=w,
                        h=h,
                        pass_thickness=pass_thickness,
                        bar_half_width=half_w,
                        style_mode=int(gpu_bar_style_mode(style_preset)),
                        style_sf=float(sf),
                    )
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
                    if colsi.shape[0] == n * 6:
                        colsi = _build_spectrum_bar_quad_colors(color_cfg, spec_col, n, pass_alpha)

                    verts = np.column_stack([pos, colsi]).astype(np.float32)
                    if verts.nbytes > line_vbo.size:
                        line_vbo.orphan(size=verts.nbytes)
                    line_vbo.write(verts.tobytes())
                    vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(pos.shape[0]))
                    if curved and fill_circle_pass and n > 0:
                        tip_h = np.maximum(2.0, val_arr[:n]).astype(np.float32)
                        xs_o = ((cx + px_arr[:n] + dx_arr[:n] * tip_h) / float(w) * 2.0 - 1.0).astype(np.float32)
                        ys_o = ((cy + py_arr[:n] + dy_arr[:n] * tip_h) / float(h) * 2.0 - 1.0).astype(np.float32)
                        if curved and mirrored:
                            xs_o = np.concatenate([xs_o, xs_o[:1]])
                            ys_o = np.concatenate([ys_o, ys_o[:1]])
                        tip_n = int(xs_o.shape[0])
                        cx_ndc = float(cx) / float(w) * 2.0 - 1.0
                        cy_ndc = float(cy) / float(h) * 2.0 - 1.0
                        pos_fill = np.empty((tip_n + 1, 2), dtype=np.float32)
                        pos_fill[0, 0] = cx_ndc
                        pos_fill[0, 1] = cy_ndc
                        pos_fill[1:, 0] = xs_o
                        pos_fill[1:, 1] = ys_o
                        cols_edge = _build_spectrum_vertex_colors(color_cfg, spec_col, tip_n, pass_alpha)
                        cols_center = cols_edge[:1].copy()
                        cols_fill = np.concatenate([cols_center, cols_edge], axis=0)
                        verts_fill = np.column_stack([pos_fill, cols_fill]).astype(np.float32)
                        if verts_fill.nbytes > line_vbo.size:
                            line_vbo.orphan(size=verts_fill.nbytes)
                        line_vbo.write(verts_fill.tobytes())
                        vao_lines.render(mode=moderngl.TRIANGLE_FAN, vertices=int(tip_n + 1))
            px_arr, py_arr, dx_arr, dy_arr = main_px, main_py, main_dx, main_dy
            if solid_band:
                band_pos = build_solid_band_strip_vertices(
                    px_arr,
                    py_arr,
                    dx_arr,
                    dy_arr,
                    cx=float(cx),
                    cy=float(cy),
                    w=int(w),
                    h=int(h),
                    band_width_px=float(max(1.0, bar_width * 0.45)),
                )
                if band_pos.shape[0]:
                    # Keep color rows aligned with strip rows when geometry adds
                    # a closing point for mirrored curved waveform layers.
                    band_bar_count = int(max(1, band_pos.shape[0] // 2))
                    band_cols = np.repeat(
                        _build_spectrum_vertex_colors(
                            color_cfg,
                            spec_col,
                            band_bar_count,
                            float(max(0.0, min(1.0, op * 0.6))),
                        ),
                        2,
                        axis=0,
                    )
                    band_verts = np.column_stack([band_pos, band_cols]).astype(np.float32)
                    if band_verts.nbytes > line_vbo.size:
                        line_vbo.orphan(size=band_verts.nbytes)
                    line_vbo.write(band_verts.tobytes())
                    vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(band_pos.shape[0]))
            if peak_caps_enabled and n > 0:
                # Mirrored curved waveform styles may append a closing point;
                # peak caps must use the original bar-count geometry only.
                cap_px = px_arr[:n]
                cap_py = py_arr[:n]
                cap_dx = dx_arr[:n]
                cap_dy = dy_arr[:n]
                peak_key = f"{layer_idx}:{'c' if curved else 'l'}:{'m' if mirrored else 's'}:{gravity}:{n}"
                prev = spectrum_peak_cache.get(peak_key)
                if prev is None or prev.shape[0] != n:
                    prev = np.zeros((n,), dtype=np.float32)
                peak_vals = np.maximum(sampled_fft, prev * peak_cap_decay).astype(np.float32)
                spectrum_peak_cache[peak_key] = peak_vals
                cap_vals = (peak_vals * thickness).astype(np.float32)
                cap_base = cap_vals + peak_cap_gap
                wx = -cap_dy * (bw * 0.5)
                wy = cap_dx * (bw * 0.5)
                p0x = cap_px + cap_dx * cap_base - wx
                p0y = cap_py + cap_dy * cap_base - wy
                p1x = cap_px + cap_dx * cap_base + wx
                p1y = cap_py + cap_dy * cap_base + wy
                p2x = cap_px + cap_dx * (cap_base + peak_cap_thickness) + wx
                p2y = cap_py + cap_dy * (cap_base + peak_cap_thickness) + wy
                p3x = cap_px + cap_dx * (cap_base + peak_cap_thickness) - wx
                p3y = cap_py + cap_dy * (cap_base + peak_cap_thickness) - wy
                inv_w = 2.0 / float(w)
                inv_h = 2.0 / float(h)
                cap_pos = np.empty((n * 6, 2), dtype=np.float32)
                ndc_p0x = (cx + p0x) * inv_w - 1.0
                ndc_p0y = (cy + p0y) * inv_h - 1.0
                ndc_p1x = (cx + p1x) * inv_w - 1.0
                ndc_p1y = (cy + p1y) * inv_h - 1.0
                ndc_p2x = (cx + p2x) * inv_w - 1.0
                ndc_p2y = (cy + p2y) * inv_h - 1.0
                ndc_p3x = (cx + p3x) * inv_w - 1.0
                ndc_p3y = (cy + p3y) * inv_h - 1.0
                cap_pos[0::6, 0] = ndc_p0x
                cap_pos[0::6, 1] = ndc_p0y
                cap_pos[1::6, 0] = ndc_p1x
                cap_pos[1::6, 1] = ndc_p1y
                cap_pos[2::6, 0] = ndc_p2x
                cap_pos[2::6, 1] = ndc_p2y
                cap_pos[3::6, 0] = ndc_p0x
                cap_pos[3::6, 1] = ndc_p0y
                cap_pos[4::6, 0] = ndc_p2x
                cap_pos[4::6, 1] = ndc_p2y
                cap_pos[5::6, 0] = ndc_p3x
                cap_pos[5::6, 1] = ndc_p3y
                cap_cols = _build_spectrum_bar_quad_colors(
                    {"mode": "solid", "solidColor": peak_cap_color},
                    spec_col,
                    n,
                    float(max(0.0, min(1.0, op * peak_hold_blend))),
                )
                cap_verts = np.column_stack([cap_pos, cap_cols]).astype(np.float32)
                if cap_verts.nbytes > line_vbo.size:
                    line_vbo.orphan(size=cap_verts.nbytes)
                line_vbo.write(cap_verts.tobytes())
                vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(cap_pos.shape[0]))

        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        spawn_rate = float(particles_cfg_raw.get("spawnRate", particles_cfg_raw.get("spawn_rate", particles_cfg.spawn_rate)))
        lifetime_sec = float(particles_cfg_raw.get("lifetimeSec", particles_cfg_raw.get("lifetime_sec", 1.6)))
        # Preview default / template_runtime clamp uses ~15, not 120.
        speed_base = float(particles_cfg_raw.get("speed", 15.0))
        prb = float(particles_cfg_raw.get("reactivity", 0.5))
        pt_size = float(particles_cfg_raw.get("size", 2.0))
        pt_color = tuple(_as_rgb(particles_cfg_raw.get("color", "#ffffff")))
        pt_count = int(particles_cfg_raw.get("maxCount", particles_cfg_raw.get("count", 400)))
        pt_count, spawn_rate = export_particle_caps(
            export_speed_mode, max_count=pt_count, spawn_rate=spawn_rate
        )
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

        _pt_trail_enabled, _pt_trail_length, _pt_trail_fade, _pt_trail_width = _particle_trail_cfg_from_settings(
            particles_cfg_raw if isinstance(particles_cfg_raw, dict) else {}
        )
        
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
                trail_enabled=_pt_trail_enabled,
                trail_length=_pt_trail_length,
                trail_fade=_pt_trail_fade,
                trail_width=_pt_trail_width,
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
                style_scale = _particle_style_size_scale(int(pt_style))
                glow_amount = _clamp_particle_glow(particles_cfg_raw.get("glow", 0.0))
                pt_size_px = float(max(1.0, pt_size * (2.2 if style in ("bokeh", "music") else 1.5) * sf))
                base_px = float(max(2.5, pt_size_px)) * style_scale
                icons = None
                angles = None
                if pt_style == 5 and hasattr(particles, "_icon") and hasattr(particles, "_angle"):
                    icons = particles._icon
                    angles = particles._angle
                    if icons.shape[0] != pts.shape[0]:
                        icons = None
                        angles = None
                if _pt_trail_enabled and hasattr(particles, "build_trail_draw_arrays"):
                    trail_batch = particles.build_trail_draw_arrays(
                        w=w,
                        h=h,
                        head_colors_rgba=colors_rgba,
                    )
                    if trail_batch is not None:
                        trail_pts, trail_cols = trail_batch
                        _render_particle_styled_quads(
                            ctx,
                            prog_particle_quads=prog_particle_quads,
                            particle_quad_vbo=particle_quad_vbo,
                            vao_particle_quads=vao_particle_quads,
                            pts=trail_pts,
                            colors_rgba=trail_cols,
                            pt_style=1 if pt_style == 5 else int(pt_style),
                            w=w,
                            h=h,
                            pt_size=base_px * 0.55,
                            glow_amount=glow_amount * 0.55,
                            music_tex_holder=music_icon_tex_holder,
                        )
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
                    glow_amount=glow_amount,
                    icons=icons,
                    angles=angles,
                    music_tex_holder=music_icon_tex_holder,
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

        _t_gl = time.perf_counter() if frame_profiler is not None else 0.0
        _blit_readback_oriented(
            src_tex=tex_out,
            fbo_readback=fbo_readback,
            prog=prog_readback_flip,
            vao=vao_readback_flip,
        )
        if golden_mode and i == golden_idx:
            raw = fbo_readback.read(components=4, alignment=1)
            arr = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 4))
            img = Image.fromarray(arr, mode="RGBA")
            Path(golden_png).parent.mkdir(parents=True, exist_ok=True)
            img.save(golden_png)
            break
        if not golden_mode:
            raw_prev = async_reader.queue_frame(fbo_readback)
            _t_readback = time.perf_counter() if frame_profiler is not None else 0.0
            if raw_prev is not None:
                _write_pipe_frame(raw_prev)
            if frame_profiler is not None:
                frame_profiler.record(
                    audio_ms=(_t_audio - _t_frame) * 1000.0,
                    gl_ms=(_t_gl - _t_audio) * 1000.0,
                    readback_ms=(_t_readback - _t_gl) * 1000.0,
                    encode_ms=(time.perf_counter() - _t_readback) * 1000.0,
                )

        if i == 0 or (i + 1) % 10 == 0 or i + 1 == total_frames:
            _emit_event(
                {
                    "status": "running",
                    "message": f"Rendering {i + 1}/{total_frames}",
                    "progress": _encode_frame_progress(i, total_frames),
                    "frame": i + 1,
                    "totalFrames": total_frames,
                    "videoCodec": video_codec,
                }
            )

    if frame_profiler is not None:
        frame_profiler.flush()

    if golden_mode:
        _emit_event(
            {
                "status": "done",
                "message": "Golden export frame saved",
                "progress": 1.0,
                "outputPath": golden_png,
            }
        )
        if ctx_factory is None and not os.environ.get("CAMXORA_DAEMON_JOB"):
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

    raw_last = async_reader.flush()
    if raw_last is not None:
        _write_pipe_frame(raw_last)

    _emit_event({"status": "running", "message": "Finalizing MP4...", "progress": 0.99, "videoCodec": video_codec})
    if native_writer is not None:
        native_writer.finish()
        remux_native_h264_with_audio(
            ffmpeg_path=opts.ffmpeg_path,
            h264_path=native_writer.h264_path,
            mp3_path=opts.mp3_path,
            out_path=out_path,
        )
    elif pipe_writer is not None:
        pipe_writer.finish()
        if os.environ.get("CAMXORA_ENCODE_METRICS", "").strip().lower() in {"1", "true", "yes", "on"}:
            stats = pipe_writer.stats()
            pack_avg = stats.get("packAvgMs")
            pack_part = f", pack avg={pack_avg:.2f} ms" if isinstance(pack_avg, (int, float)) else ""
            _emit_event(
                {
                    "status": "running",
                    "message": (
                        "Encode pipe metrics: "
                        f"submit p95={stats.get('submitBlockP95Ms')} ms, "
                        f"stdin p95={stats.get('stdinBlockP95Ms')} ms"
                        f"{pack_part}"
                    ),
                    "progress": 0.995,
                    "encodePipeMetrics": stats,
                }
            )
        if enc is not None:
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
    elif enc is not None:
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

    _emit_event({"status": "done", "message": "Exported MP4", "progress": 1.0, "outputPath": out_path})
    if ctx_factory is None and not os.environ.get("CAMXORA_DAEMON_JOB"):
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


def render_export_png(opts: GpuOptions, out_png_path: str, export_frame: int = 24) -> str:
    """Render one export-path frame to PNG (no ffmpeg). REQ-2.7 golden parity."""
    run_gpu_render(
        opts,
        single_frame_png=out_png_path,
        single_frame_index=int(export_frame),
    )
    return out_png_path


def render_preview_png(
    opts: GpuOptions,
    out_png_path: str,
    preview_frame: int = 150,
    *,
    msaa_samples: int = 4,
    analysis_fps: int | None = None,
) -> str:
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
    _init_glfw_hidden(w, h, samples=int(msaa_samples))
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

    tex_readback = ctx.texture((w, h), 4)
    tex_readback.filter = (moderngl.LINEAR, moderngl.LINEAR)
    fbo_readback = ctx.framebuffer(color_attachments=[tex_readback])
    prog_readback_flip = _compile_readback_flip(ctx)
    vao_readback_flip = _quad_vao(ctx, prog_readback_flip)

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
    afps = int(max(1, min(120, int(analysis_fps if analysis_fps is not None else fps))))
    analyzer = AudioAnalyzer(opts.mp3_path, fps=afps, point_count=point_count) if has_audio else None
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
    shake_state = CameraShakeState()
    bg_shake_state = BgVibrateState()
    kick_bass_state = KickBassEnvelopeState()
    kick_bass_config = KickBassEnvelopeConfig(
        bg_smoothing=bg_smoothing,
        logo_smoothing=logo_smoothing,
    )
    particle_audio_state = ParticleAudioState()

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
            
            _spec_c, l_pos = _resolve_spectrum_logo_centers(
                w=w,
                h=h,
                sf=sf,
                position=template.get("position") if isinstance(template.get("position"), dict) else {},
                spectrum_attach_to_logo=spectrum_attach_to_logo,
            template=template,
            )
            prog_logo["logo_px"].value = (l_pos[0] - float(w)*0.5 + float(shake_state.x), l_pos[1] - float(h)*0.5 + float(shake_state.y))

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

        env_out = integrate_kick_bass_envelopes(
            kick_bass_state,
            KickBassEnvelopeStepInput(bass=bass),
            kick_bass_config,
            dt=dt,
        )
        kick_pow = env_out.kick_pow
        bg_audio_env = env_out.bg_audio_env
        logo_audio_env = env_out.logo_audio_env
        bg_vibrate_out = integrate_bg_vibrate(
            bg_shake_state,
            BgVibrateStepInput(frame_index=i, bg_audio_env=bg_audio_env),
            BgVibrateConfig(
                motion_mode=bg_motion_mode,
                react_bass=bg_react_bass,
                smoothing=bg_smoothing,
                vibrate_strength=bg_motion_vibrate_strength,
                scale_factor=sf,
            ),
            dt=dt,
        )
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
        spawn_trigger = str(particles_cfg_raw.get("spawnTrigger", "both") or "both")
        particle_out = integrate_particle_audio(
            particle_audio_state,
            ParticleAudioStepInput(bass=bass, kick_pow=kick_pow, onset=onset, beat=beat),
            ParticleAudioConfig(smoothing=ps_smoothing, spawn_trigger=spawn_trigger),
            dt=dt,
        )
        particle_audio_env = particle_out.particle_audio_env
        p_trigger_env = particle_out.p_trigger_env

        spawn_mode = str(particles_cfg_raw.get("spawnMode", "always") or "always")
        spawn_threshold = float(particles_cfg_raw.get("spawnThreshold", 0.15) or 0.15)
        spawn_threshold = float(max(0.0, min(1.0, spawn_threshold)))

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

        shake_out = integrate_camera_shake(
            shake_state,
            CameraShakeStepInput(
                frame_index=i,
                bass=float(feats.get("bass", 0.0)),
                beat=float(feats.get("beat", 0.0) or 0.0),
                intensity=float(state.get("camera_shake.intensity", shake_intensity)),
            ),
            CameraShakeConfig(enabled=shake_enabled, smoothing=shake_smoothing),
            dt=dt,
        )

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
                float(bg_vibrate_out.x / max(1.0, float(w))),
                float(bg_vibrate_out.y / max(1.0, float(h))),
            )
        else:
            prog_scene["bg_offset"].value = (0.0, 0.0)
        tex_bg.use(location=0)
        fx = template.get("effects") if isinstance(template.get("effects"), dict) else {}
        vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
        sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
        _time_sec_bg = float(i) / float(max(1.0, float(fps)))
        try:
            from features.video.lib.lightning_render import apply_vignette_reactivity, peak_lightning_flash

            lightning_flash = peak_lightning_flash(
                template if isinstance(template, dict) else {},
                time_sec=_time_sec_bg,
                bass=float(bass),
                kick=float(kick_pow),
                beat=float(feats.get("beat", 0.0) or 0.0),
                onset=float(feats.get("onset", 0.0) or 0.0),
                audio_env=float(max(bass, kick_pow, bg_audio_env)),
            )
        except Exception:
            apply_vignette_reactivity = None  # type: ignore[assignment]
            lightning_flash = 0.0
        flash_env = float(max(bg_audio_env, lightning_flash))
        prog_scene["bg_brightness"].value = float(
            max(0.0, min(3.0, bg_brightness * (1.0 + flash_env * bg_react_bass + lightning_flash * 0.55)))
        )
        prog_scene["vignette_enabled"].value = 1 if bool(vig.get("enabled", False)) else 0
        vig_strength = float(max(0.0, min(1.0, float(vig.get("strength", 0.35) or 0.35))))
        vig_opacity = float(max(0.0, min(1.0, float(vig.get("opacity", 0.65) or 0.65))))
        vig_react = float(max(0.0, min(5.0, float(vig.get("reactivity", 0.0) or 0.0))))
        if apply_vignette_reactivity is not None and vig_react > 0.0:
            vig_strength, vig_opacity = apply_vignette_reactivity(
                strength=vig_strength,
                opacity=vig_opacity,
                reactivity=vig_react,
                flash_env=flash_env,
            )
        prog_scene["vignette_strength"].value = float(vig_strength)
        prog_scene["vignette_feather"].value = float(max(0.0, min(1.0, float(vig.get("feather", 0.65) or 0.65))))
        prog_scene["vignette_opacity"].value = float(vig_opacity)
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
        prog_scene["time_sec"].value = _time_sec_bg
        vao_quad_scene.render(mode=moderngl.TRIANGLE_STRIP)

        scale = float(state.get("spectrum.scale", 1.0))
        cx = float(w) * 0.5 + float(shake_out.x)
        cy = float(h) * 0.5 + float(shake_out.y)

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
        
        c_pos, _logo_unused = _resolve_spectrum_logo_centers(
            w=w,
            h=h,
            sf=sf,
            position=template.get("position") if isinstance(template.get("position"), dict) else {},
            spectrum_attach_to_logo=spectrum_attach_to_logo,
            template=template,
        )
        cx = c_pos[0] + float(shake_out.x)
        cy = c_pos[1] + float(shake_out.y)

        try:
            from features.video.lib.lightning_render import render_lightning_layers_gl

            _time_sec = float(i) / float(max(1.0, float(fps)))
            _bass = float(feats.get("bass", 0.0) or 0.0)
            render_lightning_layers_gl(
                ctx,
                line_vbo=line_vbo,
                vao_lines=vao_lines,
                template=template if isinstance(template, dict) else {},
                w=w,
                h=h,
                sf=sf,
                cx=cx,
                cy=cy,
                time_sec=_time_sec,
                bass=_bass,
                kick=float(kick_pow),
                beat=float(feats.get("beat", 0.0) or 0.0),
                onset=float(feats.get("onset", 0.0) or 0.0),
                audio_env=float(max(_bass, float(kick_pow), float(bg_audio_env))),
            )
        except Exception:
            pass
        
        for sl in spectrum_layers:
            style_preset = _resolve_export_spectrum_style(template_style_preset, sl)
            curved = bool(sl.get("curved", False))
            mirrored = bool(sl.get("mirrored", False))
            bar_width = float(sl.get("barWidth", 4.0)) * sf
            bar_height_mult = _audio_bar_height_mult(template)
            thickness = float(sl.get("thickness", 30.0)) * sf * bar_height_mult
            gravity = normalize_spectrum_gravity(sl.get("gravity", "top"))
            
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

            render_fft = scroll_spectrum_heights(render_fft, sl.get("frequencyScroll", 0.0))

            react_mult = rg * thickness
            
            # 3) Generate Points
            n = BINS
            _legacy_logo_shape = "square" if not bool(logo_circle_mask) else "circle"
            from ._spectrum_fast import generate_spectrum_layer_geometry as _gen_spec_geom
            px_arr, py_arr, dx_arr, dy_arr, total_length = _gen_spec_geom(
                n,
                curved=curved,
                mirrored=mirrored,
                gravity=gravity,
                path_mode=sl.get("pathMode", "auto"),
                radius=radius,
                half_w=radius,
                half_h=radius,
                attached_to_logo=attached_to_logo,
                logo_shape=_legacy_logo_shape,
                frame_w=w,
                frame_h=h,
                linear_span=float(sl.get("linearSpan", 1.0) or 1.0),
            )
            val_arr = (render_fft[:n] * thickness).astype(np.float32)

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
                        needle = float(max(1.0, bw * 0.55))
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
                            wx_base = wx * 1.35
                            wy_base = wy * 1.35
                            wx_tip = wx * 0.55
                            wy_tip = wy * 0.55
                            p0x = px_arr[i] - wx_base
                            p0y = py_arr[i] - wy_base
                            p1x = px_arr[i] + wx_base
                            p1y = py_arr[i] + wy_base
                            p2x = px_arr[i] + dx_arr[i] * h_val + wx_tip
                            p2y = py_arr[i] + dy_arr[i] * h_val + wy_tip
                            p3x = px_arr[i] + dx_arr[i] * h_val - wx_tip
                            p3y = py_arr[i] + dy_arr[i] * h_val - wy_tip
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

        _blit_readback_oriented(
            src_tex=tex_out,
            fbo_readback=fbo_readback,
            prog=prog_readback_flip,
            vao=vao_readback_flip,
        )
        raw = fbo_readback.read(components=4, alignment=1)
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 4))
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
    try:
        from shared.lib.win32_window import exclude_glfw_window_from_taskbar, glfw_window_hwnd

        exclude_glfw_window_from_taskbar(win)
        native_hwnd = glfw_window_hwnd(win)
    except Exception:
        native_hwnd = 0
        if sys.platform == "win32":
            try:
                get_win32_window = getattr(glfw, "get_win32_window", None)
                if callable(get_win32_window):
                    native_hwnd = int(get_win32_window(win))
            except Exception:
                native_hwnd = 0

    ctx = _make_ctx()

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
    shake_state = CameraShakeState()
    bg_shake_state = BgVibrateState()
    kick_bass_state = KickBassEnvelopeState()
    particle_audio_state = ParticleAudioState()
    
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
        env_out = integrate_kick_bass_envelopes(
            kick_bass_state,
            KickBassEnvelopeStepInput(bass=bass),
            KickBassEnvelopeConfig(bg_smoothing=bg_smoothing, logo_smoothing=logo_smoothing),
            dt=dt,
        )
        kick_pow = env_out.kick_pow
        bg_audio_env = env_out.bg_audio_env
        logo_audio_env = env_out.logo_audio_env
        bg_vibrate_out = integrate_bg_vibrate(
            bg_shake_state,
            BgVibrateStepInput(frame_index=frame_idx, bg_audio_env=bg_audio_env),
            BgVibrateConfig(
                motion_mode=bg_motion_mode,
                react_bass=bg_react_bass,
                smoothing=bg_smoothing,
                vibrate_strength=bg_motion_vibrate_strength,
                scale_factor=sf,
            ),
            dt=dt,
        )

        if bg_motion_mode in ("zoom", "both"):
            bg_scale_live = float(1.0 + min(2.5, max(0.0, bg_audio_env * bg_react_bass * 0.04 * bg_motion_zoom_strength)))
        else:
            bg_scale_live = 1.0
        bg_offset_uv = (
            float(bg_vibrate_out.x / max(1.0, float(w))),
            float(bg_vibrate_out.y / max(1.0, float(h))),
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
        try:
            from features.video.lib.lightning_render import apply_vignette_reactivity, peak_lightning_flash

            lightning_flash = peak_lightning_flash(
                template if isinstance(template, dict) else {},
                time_sec=float(c_time),
                bass=float(bass),
                kick=float(kick_pow),
                beat=float(feats.get("beat", 0.0) or 0.0),
                onset=float(feats.get("onset", 0.0) or 0.0),
                audio_env=float(max(bass, kick_pow, bg_audio_env)),
            )
        except Exception:
            apply_vignette_reactivity = None  # type: ignore[assignment]
            lightning_flash = 0.0
        flash_env = float(max(bg_audio_env, lightning_flash))
        prog_scene["bg_brightness"].value = float(
            max(0.0, min(3.0, bg_brightness * (1.0 + flash_env * bg_react_bass + lightning_flash * 0.55)))
        )
        prog_scene["vignette_enabled"].value = 1 if bool(vig.get("enabled", False)) else 0
        vig_strength = float(max(0.0, min(1.0, float(vig.get("strength", 0.35) or 0.35))))
        vig_opacity = float(max(0.0, min(1.0, float(vig.get("opacity", 0.65) or 0.65))))
        vig_react = float(max(0.0, min(5.0, float(vig.get("reactivity", 0.0) or 0.0))))
        if apply_vignette_reactivity is not None and vig_react > 0.0:
            vig_strength, vig_opacity = apply_vignette_reactivity(
                strength=vig_strength,
                opacity=vig_opacity,
                reactivity=vig_react,
                flash_env=flash_env,
            )
        prog_scene["vignette_strength"].value = float(vig_strength)
        prog_scene["vignette_feather"].value = float(max(0.0, min(1.0, float(vig.get("feather", 0.65) or 0.65))))
        prog_scene["vignette_opacity"].value = float(vig_opacity)
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

        shake_out = integrate_camera_shake(
            shake_state,
            CameraShakeStepInput(
                frame_index=frame_idx,
                bass=float(feats.get("bass", 0.0)),
                beat=float(feats.get("beat", 0.0) or 0.0),
                intensity=float(state.get("camera_shake.intensity", shake_intensity)),
            ),
            CameraShakeConfig(enabled=shake_enabled, smoothing=shake_smoothing),
            dt=dt,
        )

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
        
        c_pos, _logo_unused = _resolve_spectrum_logo_centers(
            w=w,
            h=h,
            sf=sf,
            position=template.get("position") if isinstance(template.get("position"), dict) else {},
            spectrum_attach_to_logo=spectrum_attach_to_logo,
            template=template,
        )
        cx = c_pos[0] + float(shake_out.x)
        cy = c_pos[1] + float(shake_out.y)
        attached_to_logo = bool(spectrum_attach_to_logo and logo_rgba is not None)
        attached_base_radius = float(
            max(0.0, ((float(logo_raw.get("size", 192.0)) * 0.5) * sf * float(logo_scale_base) * logo_visible_radius_ratio) + spectrum_logo_gap)
        )
        attached_layer_base_offset = _resolve_attached_layer_base_offset(spectrum_layers, sf)

        try:
            from features.video.lib.lightning_render import render_lightning_layers_gl

            render_lightning_layers_gl(
                ctx,
                line_vbo=line_vbo,
                vao_lines=vao_lines,
                template=template if isinstance(template, dict) else {},
                w=w,
                h=h,
                sf=sf,
                cx=cx,
                cy=cy,
                time_sec=float(c_time),
                bass=float(bass),
                kick=float(kick_pow),
                beat=float(feats.get("beat", 0.0) or 0.0),
                onset=float(feats.get("onset", 0.0) or 0.0),
                audio_env=float(max(bass, kick_pow, bg_audio_env)),
            )
        except Exception:
            pass
        
        for sl in spectrum_layers:
            style_preset = _resolve_export_spectrum_style(template_style_preset, sl)
            curved = bool(sl.get("curved", False))
            mirrored = bool(sl.get("mirrored", False))
            bar_width = float(sl.get("barWidth", 4.0)) * sf
            bar_height_mult = _audio_bar_height_mult(template)
            thickness = float(sl.get("thickness", 30.0)) * sf * bar_height_mult
            gravity = normalize_spectrum_gravity(sl.get("gravity", "top"))
            
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

            render_fft = scroll_spectrum_heights(render_fft, sl.get("frequencyScroll", 0.0))

            n = BINS
            _legacy_logo_shape = "square" if not bool(logo_circle_mask) else "circle"
            from ._spectrum_fast import generate_spectrum_layer_geometry as _gen_spec_geom
            px_arr, py_arr, dx_arr, dy_arr, total_length = _gen_spec_geom(
                n,
                curved=curved,
                mirrored=mirrored,
                gravity=gravity,
                path_mode=sl.get("pathMode", "auto"),
                radius=radius,
                half_w=radius,
                half_h=radius,
                attached_to_logo=attached_to_logo,
                logo_shape=_legacy_logo_shape,
                frame_w=w,
                frame_h=h,
                linear_span=float(sl.get("linearSpan", 1.0) or 1.0),
            )
            val_arr = (render_fft[:n] * thickness).astype(np.float32)

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
                        needle = float(max(1.0, bw * 0.55))
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
                            wx_base = wx * 1.35
                            wy_base = wy * 1.35
                            wx_tip = wx * 0.55
                            wy_tip = wy * 0.55
                            p0x = px_arr[i] - wx_base
                            p0y = py_arr[i] - wy_base
                            p1x = px_arr[i] + wx_base
                            p1y = py_arr[i] + wy_base
                            p2x = px_arr[i] + dx_arr[i] * h_val + wx_tip
                            p2y = py_arr[i] + dy_arr[i] * h_val + wy_tip
                            p3x = px_arr[i] + dx_arr[i] * h_val - wx_tip
                            p3y = py_arr[i] + dy_arr[i] * h_val - wy_tip
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
        onset = float(feats.get("onset", 0.0) or 0.0)
        beat = float(feats.get("beat", 0.0) or 0.0)
        spawn_trigger = str(particles_cfg_raw.get("spawnTrigger", "both") or "both")
        particle_out = integrate_particle_audio(
            particle_audio_state,
            ParticleAudioStepInput(bass=bass, kick_pow=kick_pow, onset=onset, beat=beat),
            ParticleAudioConfig(smoothing=ps_smoothing, spawn_trigger=spawn_trigger),
            dt=dt,
        )
        particle_audio_env = particle_out.particle_audio_env
        p_trigger_env = particle_out.p_trigger_env

        spawn_mode = str(particles_cfg_raw.get("spawnMode", "always") or "always")
        spawn_threshold = float(particles_cfg_raw.get("spawnThreshold", 0.15) or 0.15)
        spawn_threshold = float(max(0.0, min(1.0, spawn_threshold)))

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
                
                _spec_c, l_pos = _resolve_spectrum_logo_centers(
                    w=w,
                    h=h,
                    sf=sf,
                    position=template.get("position") if isinstance(template.get("position"), dict) else {},
                    spectrum_attach_to_logo=spectrum_attach_to_logo,
                template=template,
                )
                prog_logo["logo_px"].value = (l_pos[0] - float(w)*0.5 + float(shake_out.x), l_pos[1] - float(h)*0.5 + float(shake_out.y))
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
