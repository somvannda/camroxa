"""Live GPU preview widget — PySide6 port of python_app SpectrumPreview."""


import math
import os
import time
import threading
from pathlib import Path
from typing import Any
import numpy as np

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Signal, QTimer, QByteArray, Qt, QRectF, QSize, QMetaObject, Slot, Q_ARG
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QSurfaceFormat


def _preview_target_hz() -> int:
    """Studio preview paint rate. Default 120; override with CAMXORA_PREVIEW_HZ."""
    raw = str(os.environ.get("CAMXORA_PREVIEW_HZ") or "120").strip()
    try:
        return int(max(30, min(240, int(raw))))
    except (TypeError, ValueError):
        return 120


def _configure_preview_gl_format() -> QSurfaceFormat:
    """Prefer unlocked swap + full RGB; optional 10-bit via CAMXORA_PREVIEW_DEEP_COLOR=1."""
    fmt = QSurfaceFormat(QSurfaceFormat.defaultFormat())
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    fmt.setSwapInterval(0)  # uncapped when the driver/compositor allows
    # Multisample edges — classic spectrum quads otherwise look jagged/aliased.
    if fmt.samples() < 4:
        fmt.setSamples(4)
    if fmt.depthBufferSize() < 16:
        fmt.setDepthBufferSize(24)
    deep = str(os.environ.get("CAMXORA_PREVIEW_DEEP_COLOR") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if deep:
        # Request 10-bit; Qt/OS fall back to 8-bit when unsupported.
        fmt.setRedBufferSize(10)
        fmt.setGreenBufferSize(10)
        fmt.setBlueBufferSize(10)
        fmt.setAlphaBufferSize(2)
    else:
        fmt.setRedBufferSize(8)
        fmt.setGreenBufferSize(8)
        fmt.setBlueBufferSize(8)
        fmt.setAlphaBufferSize(8)
    return fmt

import moderngl
from visualizer.gpu_render import (
    _clamp_logo_size_inside_shape,
    _compile,
    _compile_particle_quads,
    _composition_spectrum_base_radius_px,
    _compute_visible_logo_radius_ratio,
    _logo_contain_in_shape_enabled,
    _particle_trail_cfg_from_settings,
    _quad_vao,
    _render_particle_styled_quads,
    _resolve_attached_layer_base_offset,
    _resolve_export_spectrum_style,
    _resolve_particle_style_index,
    _resolve_spectrum_layer_radius,
    ParticleSystem,
    ParticleConfig,
)
from visualizer.hdr_bloom import (
    PreviewHdrBloomPass,
    bloom_params_from_template,
    preview_hdr_bloom_enabled,
)
from visualizer._spectrum_fast import (
    apply_bar_height_overrides,
    build_contour_wave_strips,
    build_solid_band_strip_vertices,
    build_solid_graph_strip_vertices,
    clamp_frequency_scroll,
    clamp_spectrum_bar_count,
    generate_spectrum_layer_geometry,
    mirror_spectrum_points_vertical,
    normalize_spectrum_gravity,
    resample_fft_bins,
    resolve_bar_pixel_width,
    rotate_spectrum_bases,
    scroll_spectrum_heights,
    smooth_fft_envelope,
)
from features.video.lib.logo_spectrum_bindings import normalize_logo_shape
from features.video.lib.particle_color_engine import (
    build_particle_rgba_rows,
    extract_particle_color_model,
    palette_colors_to_rgb_tuple,
)
from features.video.lib.spectrum_color_engine import (
    build_spectrum_bar_quad_rgba,
    build_spectrum_fill_fan_rgba,
    build_spectrum_solid_graph_strip_rgba,
    build_spectrum_spatial_edge_rgba,
    build_spectrum_vertex_rgba,
    dampen_spectrum_glow_rgba,
)
from visualizer.audio import AudioAnalyzer
from visualizer.automation import apply_automations
from visualizer.contracts import PreviewConfig
from visualizer.frame_integrator import (
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
)
from visualizer.preview_diag import DiagLevel, format_gl_context_info, write_preview_gl_diag
from visualizer.template_runtime import default_renderer_template, normalize_renderer_template


def _fmt_time(sec: float) -> str:
    s = max(0.0, float(sec))
    mm = int(s // 60)
    ss = int(s % 60)
    return f'{mm:02d}:{ss:02d}'

def _get_anchor_coords(anchor: str, offset_x: float, offset_y: float, w: int, h: int) -> tuple[float, float]:
    a = str(anchor).lower().strip()
    if 'left' in a:
        cx = 0.0
    elif 'right' in a:
        cx = float(w)
    else:
        cx = float(w) * 0.5
    if 'top' in a:
        cy = float(h)
    elif 'bottom' in a:
        cy = 0.0
    else:
        cy = float(h) * 0.5
    return (cx + float(offset_x), cy - float(offset_y))


def _anchor_base(anchor: str, w: int, h: int) -> tuple[float, float]:
    a = str(anchor or "center").lower().strip()
    if "left" in a:
        bx = 0.0
    elif "right" in a:
        bx = float(w)
    else:
        bx = float(w) * 0.5
    if "top" in a:
        by = float(h)
    elif "bottom" in a:
        by = 0.0
    else:
        by = float(h) * 0.5
    return bx, by


def clamp_template_offset_to_preview(
    *,
    anchor: str,
    offset_x: float,
    offset_y: float,
    w: int,
    h: int,
    sf: float,
    margin_frac: float = 0.0,
) -> tuple[float, float]:
    """Keep an anchored object center inside the preview frame.

    Offsets are template units (renderBaseHeight space); ``sf`` converts to pixels.
    Default margin is 0 so logo/spectrum can sit flush on an edge (e.g. bottom).
    """
    width = max(1, int(w))
    height = max(1, int(h))
    scale = float(sf) if float(sf) > 1e-06 else 1.0
    margin_x = float(width) * float(max(0.0, min(0.45, margin_frac)))
    margin_y = float(height) * float(max(0.0, min(0.45, margin_frac)))
    ox_px = float(offset_x) * scale
    oy_px = float(offset_y) * scale
    cx, cy = _get_anchor_coords(anchor, ox_px, oy_px, width, height)
    cx = float(max(margin_x, min(float(width) - margin_x, cx)))
    cy = float(max(margin_y, min(float(height) - margin_y, cy)))
    base_x, base_y = _anchor_base(anchor, width, height)
    # Invert: cx = base_x + ox_px, cy = base_y - oy_px
    return ((cx - base_x) / scale, (base_y - cy) / scale)


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

class _QtGLContextLoader:

    def __init__(self, qt_context):
        self._qt_context = qt_context

    def load_opengl_function(self, name):
        if self._qt_context is None:
            return 0
        try:
            qb = QByteArray(name if isinstance(name, (bytes, bytearray)) else str(name).encode('ascii'))
            addr = self._qt_context.getProcAddress(qb)
        except Exception:
            try:
                addr = self._qt_context.getProcAddress(str(name))
            except Exception:
                return 0
        return int(addr) if addr else 0
    load = load_opengl_function

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def release(self):
        return None

class AspectRatioBox(QWidget):

    def __init__(
        self,
        child: QWidget,
        ratio_w: int = 16,
        ratio_h: int = 9,
        parent=None,
        *,
        enforce_height_for_width: bool = True,
    ):
        super().__init__(parent)
        self._child = child
        self._overlay: QWidget | None = None
        self._ratio = float(ratio_w) / float(ratio_h)
        self._enforce_height_for_width = bool(enforce_height_for_width)
        self._child.setParent(self)

    def _apply_child_geometry(self) -> None:
        w = max(1, int(self.width()))
        h = max(1, int(self.height()))
        target_w = int(min(w, int(round(h * self._ratio))))
        target_h = int(min(h, int(round(w / self._ratio))))
        if target_w / float(self._ratio) <= h:
            cw, ch = (target_w, int(round(target_w / self._ratio)))
        else:
            cw, ch = (int(round(target_h * self._ratio)), target_h)
        x = (w - cw) // 2
        y = (h - ch) // 2
        self._child.setGeometry(x, y, cw, ch)
        if self._overlay is not None:
            self._overlay.setGeometry(x, y, cw, ch)
            self._overlay.raise_()

    def set_overlay(self, overlay: QWidget | None) -> None:
        """Optional CapCut-style UI layer stacked exactly on the preview surface."""
        if self._overlay is not None and self._overlay is not overlay:
            self._overlay.setParent(None)
        self._overlay = overlay
        if overlay is not None:
            overlay.setParent(self)
            overlay.raise_()
        self._apply_child_geometry()
        self.update()

    def replace_child(self, child: QWidget) -> None:
        if self._child is not None:
            self._child.setParent(None)
            self._child.deleteLater()
        self._child = child
        child.setParent(self)
        if self._overlay is not None:
            self._overlay.raise_()
        self._apply_child_geometry()
        self.update()

    def set_ratio(self, ratio_w: int, ratio_h: int) -> None:
        try:
            w = max(1, int(ratio_w))
            h = max(1, int(ratio_h))
            self._ratio = float(w) / float(h)
        except Exception:
            self._ratio = 16.0 / 9.0
        self.updateGeometry()
        self._apply_child_geometry()
        self.update()

    def hasHeightForWidth(self) -> bool:
        return bool(self._enforce_height_for_width)

    def heightForWidth(self, w: int) -> int:
        width = max(1, int(w))
        return int(round(width / self._ratio))

    def sizeHint(self):
        from PySide6.QtCore import QSize
        w = 480
        if not self._enforce_height_for_width:
            return QSize(w, 270)
        return QSize(w, self.heightForWidth(w))

    def resizeEvent(self, ev):
        self._apply_child_geometry()
        super().resizeEvent(ev)

class VideoSpectrumPreview(QOpenGLWidget):
    position_changed = Signal(int, int)
    lightning_position_changed = Signal(int, int)
    logo_position_changed = Signal(int, int)
    spectrum_layer_patch_changed = Signal(object)
    spectrum_size_delta_requested = Signal(float)
    background_transform_changed = Signal(float, float, float)
    playback_state_changed = Signal(object)
    text_domain_position_changed = Signal(str, float, float)
    gl_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFormat(_configure_preview_gl_format())
        self.ctx = None
        self._gl_ready = False
        self._target_hz = _preview_target_hz()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(max(1, 1000 // int(self._target_hz)))
        self.template = normalize_renderer_template(default_renderer_template())
        self.audio_path = None
        self.bg_path = None
        self._bg_video = None
        self._bg_video_path = ""
        self.logo_path = None
        self._logo_rgba_cache = None
        self._logo_visible_radius_ratio = 1.0
        self._logo_visible_radius_key: tuple[int, bool] | None = None
        self._last_clean_preview_at = 0.0
        self.analyzer = None
        self.current_time = 0.0
        self.particles = None
        import pygame
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception:
            pass
        self.audio_playing = False
        self._loop_playback = False
        self.audio_loading = False
        self.audio_ready = False
        self.analysis_loading = False
        self.audio_error = ''
        self._audio_clock_base = 0.0
        self._audio_clock_started_at = None
        self._audio_duration_sec = 0.0
        self._audio_duration_cache: dict[str, float] = {}
        self._audio_load_seq = 0
        self._audio_load_lock = threading.Lock()
        self.fft_log = np.zeros(64, dtype=np.float32)
        self.fft_smoothed = np.zeros(64, dtype=np.float32)
        self._spectrum_peak_cache: dict[str, np.ndarray] = {}
        self.shake_state = CameraShakeState()
        self.bg_shake_state = BgVibrateState()
        self.kick_bass_state = KickBassEnvelopeState()
        self.bg_audio_env = 0.0
        self.logo_audio_env = 0.0
        self.particle_audio_env = 0.0
        self.p_trigger_env = 0.0
        self._particle_audio_state = ParticleAudioState()
        self.dt = 1.0 / float(self._target_hz)
        self._frame_counter = 0
        self._screen_fbo = None
        self._particles_wh = (0, 0)
        self._text_cache_keys: list[str | None] = []
        self._text_textures: list[any] = []
        self._text_sizes: list[tuple[int, int]] = []
        self._dragging = False
        self._drag_last = None
        self._bar_edit_mode = None  # "raise" | "phase" | "height" | None
        self._bar_edit_index = -1
        self._bar_edit_layer_index = 0
        self._bar_hit_cache: list[dict] = []
        self._bar_edit_center = (0.0, 0.0)
        self._bar_edit_last_angle = 0.0
        self._spectrum_path_radius_px = 0.0
        self._spectrum_center_px = (0.0, 0.0)
        self._bg_edit_mode = False
        self._spectrum_position_edit_mode = False
        self._lightning_position_edit_mode = False
        self._logo_position_edit_mode = False
        self._selected_spectrum_instance_index = 0
        self._selected_lightning_layer_index = 0
        self._text_domain_edit_mode = ""  # "album" | "title" | ""
        # GPU real-time drag: paint-time screen offset only (no template rebuild).
        self._text_drag_domain = ""
        self._text_drag_dx = 0.0
        self._text_drag_dy = 0.0
        self._bg_tex_size = (1.0, 1.0)
        self._perf_last_paint_at = 0.0
        self._export_overlay_active = False
        self._export_overlay_message = ""
        self._last_clean_preview: QPixmap | None = None
        self._export_freeze_label = QLabel(self)
        self._export_freeze_label.setScaledContents(True)
        self._export_freeze_label.setStyleSheet("background-color: #0a0e27;")
        self._export_freeze_label.hide()
        self._export_freeze_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._export_overlay_label = QLabel(self)
        self._export_overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._export_overlay_label.setStyleSheet(
            "background-color: rgba(8, 16, 40, 160); color: #ffffff; font-size: 16px;"
        )
        self._export_overlay_label.hide()
        self._export_overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._gl_failure_label = QLabel(self)
        self._gl_failure_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gl_failure_label.setWordWrap(True)
        self._gl_failure_label.setStyleSheet(
            "background-color: #0a0e27; color: #e2e8f0; padding: 20px; font-size: 14px;"
        )
        self._gl_failure_label.hide()
        self._fbo_bind_failures = 0
        self._FBO_BIND_FAIL_LIMIT = 30
        self._gl_failure_emitted = False
        self._export_offscreen_surface = None
        self._export_gl_context = None
        self._blocking_export_gl_result = None
        self._blocking_export_gl_error = None
        self._perf_frame_ms = 0.0
        self._perf_fps = 0.0
        self._last_gl_error = ""
        self._gl_info: dict[str, str] = {}
        self._template_fingerprint = None
        self._template_generation = 0
        self._interactive_scrub = False
        self._hdr_bloom: PreviewHdrBloomPass | None = None
        self._hdr_bloom_frame_active = False
        self._log("SpectrumPreview init")

    def _frame_metrics(self) -> tuple[int, int, int, int]:
        lw = max(1, int(self.width()))
        lh = max(1, int(self.height()))
        dpr = float(max(1.0, float(self.devicePixelRatioF() or 1.0)))
        vw = max(1, int(round(lw * dpr)))
        vh = max(1, int(round(lh * dpr)))
        return lw, lh, vw, vh

    def _particle_settings(self) -> dict:
        ps = self.template.get("particlesSettings") if isinstance(self.template.get("particlesSettings"), dict) else {}
        if not ps and isinstance(self.template.get("particles"), dict):
            return dict(self.template.get("particles") or {})
        return dict(ps)

    def _ensure_particle_system(self, width: int, height: int) -> None:
        w = max(1, int(width))
        h = max(1, int(height))
        if getattr(self, "particles", None) is None or tuple(getattr(self, "_particles_wh", (0, 0))) != (w, h):
            self.particles = ParticleSystem(
                ParticleConfig(
                    enabled=True,
                    max_count=400,
                    spawn_rate=40,
                    lifetime_sec=1.6,
                    spawn_radius=0.0,
                    size=2.0,
                    opacity=0.35,
                    color=(255, 255, 255),
                    speed=120.0,
                ),
                width=w,
                height=h,
                rng_seed=1,
            )
            self._particles_wh = (w, h)

    def _prepare_particle_audio(
        self,
        *,
        bass: float,
        kick_pow: float,
        ps: dict,
        onset: float = 0.0,
        beat: float = 0.0,
    ) -> None:
        out = integrate_particle_audio(
            self._particle_audio_state,
            ParticleAudioStepInput(
                bass=bass,
                kick_pow=kick_pow,
                onset=onset,
                beat=beat,
            ),
            ParticleAudioConfig(
                smoothing=float(ps.get("smoothing", 0.65)),
                spawn_trigger=str(ps.get("spawnTrigger", "both") or "both"),
            ),
        )
        self.particle_audio_env = out.particle_audio_env
        self.p_trigger_env = out.p_trigger_env

    def _resolve_particle_spawn_rate(self, *, ps: dict, ps_spawn: float, prb: float) -> float:
        spawn_mode = str(ps.get("spawnMode", "always") or "always")
        spawn_threshold = float(max(0.0, min(1.0, float(ps.get("spawnThreshold", 0.15) or 0.15))))
        if spawn_mode == "reactiveOnly" and self.p_trigger_env < spawn_threshold:
            # Preview should never go fully silent while particles are enabled.
            return float(max(12.0, ps_spawn * 0.12))
        rate = ps_spawn * float(0.2 + self.particle_audio_env * (1.1 + prb * 2.8))
        return float(max(12.0, rate))

    def _draw_particle_batch(
        self,
        *,
        pts: np.ndarray,
        colors_rgba: np.ndarray,
        pt_size: float,
        pt_style: int,
        w: int,
        h: int,
        glow_amount: float = 0.0,
        icons: np.ndarray | None = None,
        angles: np.ndarray | None = None,
    ) -> None:
        if pts.shape[0] <= 0 or self.ctx is None or not hasattr(self, "particle_quad_vbo"):
            return
        self._use_qt_framebuffer()
        _, _, vw, vh = self._frame_metrics()
        self.ctx.viewport = (0, 0, vw, vh)
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)
        from visualizer.gpu_render import _particle_style_size_scale

        style_scale = _particle_style_size_scale(int(pt_style))
        base_px = float(max(2.5, pt_size)) * style_scale
        _render_particle_styled_quads(
            self.ctx,
            prog_particle_quads=self.prog_particle_quads,
            particle_quad_vbo=self.particle_quad_vbo,
            vao_particle_quads=self.vao_particle_quads,
            pts=pts,
            colors_rgba=colors_rgba,
            pt_style=int(pt_style),
            w=w,
            h=h,
            pt_size=base_px,
            glow_amount=float(glow_amount),
            icons=icons,
            angles=angles,
            music_tex_holder=getattr(self, "_music_icon_tex_holder", None),
        )

    def _finish_particles_frame(
        self,
        *,
        w: int,
        h: int,
        sf: float,
        logo_visual_radius: float,
        bass: float,
        kick_pow: float,
        feats: dict,
        logo_enabled: bool = True,
    ) -> None:
        if self.ctx is None or not hasattr(self, "vao_particle_quads"):
            return
        ps = self._particle_settings()
        ps_enabled = bool(ps.get("enabled", True))
        self._ensure_particle_system(w, h)
        if not getattr(self, "particles", None):
            return

        if not ps_enabled:
            self.particles.update_cfg(
                ParticleConfig(
                    enabled=False,
                    max_count=0,
                    spawn_rate=0.0,
                    lifetime_sec=1.0,
                    spawn_radius=0.0,
                    size=1.0,
                    opacity=0.0,
                    color=(255, 255, 255),
                    speed=1.0,
                )
            )
            self.particles.update(self.dt, feats)
            return

        ps_count = int(ps.get("maxCount", 400))
        ps_spawn = float(ps.get("spawnRate", 40.0))
        ps_life = float(ps.get("lifetimeSec", 1.6))
        ps_speed = float(ps.get("speed", 15.0))
        ps_react = float(ps.get("reactivity", 0.0))
        ps_size = float(ps.get("size", 2.0))
        ps_op = float(ps.get("opacity", 0.35))
        ps_col = (255, 255, 255)
        try:
            col_hex = str(ps.get("color", "#ffffff"))
            if col_hex.startswith("#") and len(col_hex) == 7:
                ps_col = (int(col_hex[1:3], 16), int(col_hex[3:5], 16), int(col_hex[5:7], 16))
        except Exception:
            ps_col = (255, 255, 255)
        prb = float(max(0.0, min(1.0, ps_react)))
        color_model = extract_particle_color_model(ps)
        palette_rgb = palette_colors_to_rgb_tuple(list(color_model.get("paletteColors") or []))
        # Audio envelopes are prepared once per paintGL frame; do not smooth again here
        # or react-color flashes get double-damped into invisibility.
        spawn_rate = float(max(0.0, min(20000.0, self._resolve_particle_spawn_rate(ps=ps, ps_spawn=ps_spawn, prb=prb))))
        if logo_enabled:
            spawn_radius = float(max(0.0, logo_visual_radius + max(2.0 * sf, ps_size * sf)))
        else:
            spawn_radius = float(max(min(w, h) * 0.22, ps_size * sf * 6.0))
        speed_boost = float(18.0 + self.particle_audio_env * (50.0 + prb * 130.0))
        speed2 = float(max(0.0, min(2500.0, ps_speed * speed_boost * sf)))
        trail_enabled, trail_length, trail_fade, trail_width = _particle_trail_cfg_from_settings(ps)
        self.particles.update_cfg(
            ParticleConfig(
                enabled=True,
                max_count=ps_count,
                spawn_rate=spawn_rate,
                lifetime_sec=ps_life,
                spawn_radius=spawn_radius,
                size=ps_size * sf,
                opacity=ps_op,
                color=ps_col,
                speed=speed2,
                size_jitter=float(ps.get("sizeJitter", 0.0) or 0.0),
                drift=float(ps.get("drift", 0.0) or 0.0),
                swirl=float(ps.get("swirl", 0.0) or 0.0),
                spawn_area=str(ps.get("spawnArea", "centerRing") or "centerRing"),
                travel_mode=str(ps.get("travelMode", "spawnFlow") or "spawnFlow"),
                color_mode=str(color_model.get("mode") or "solid"),
                palette_colors=palette_rgb,
                trail_enabled=trail_enabled,
                trail_length=trail_length,
                trail_fade=trail_fade,
                trail_width=trail_width,
            )
        )
        self.particles.update(self.dt, feats)

        pos = self.particles._pos if hasattr(self.particles, "_pos") else np.zeros((0, 2), dtype=np.float32)
        if pos.shape[0] <= 0 and spawn_rate > 0.0:
            self.particles.update(0.35, feats)
            pos = self.particles._pos if hasattr(self.particles, "_pos") else np.zeros((0, 2), dtype=np.float32)
        if pos.shape[0] <= 0:
            return

        p = pos.astype(np.float32)
        xs2 = p[:, 0] / float(w) * 2.0 - 1.0
        # Particle sim is top-left (y down). OpenGL NDC is y-up — flip Y so
        # Bottom Arc + Rise Up appear at the bottom and travel upward.
        ys2 = 1.0 - (p[:, 1] / float(h) * 2.0)
        sz = self.particles._size.astype(np.float32) if hasattr(self.particles, "_size") else np.ones((p.shape[0],), dtype=np.float32)
        pts = np.column_stack([xs2, ys2, sz]).astype(np.float32)
        particle_rgbs = self.particles._rgb if hasattr(self.particles, "_rgb") else None
        colors_rgba = build_particle_rgba_rows(
            settings=ps,
            particle_rgbs=particle_rgbs,
            reactive_env=float(getattr(self, "particle_audio_env", 0.0) or 0.0),
            trigger_env=float(getattr(self, "p_trigger_env", 0.0) or 0.0),
        )
        variant = str(ps.get("variant", "classic") or "classic")
        style = str(ps.get("style", "dot") or "dot")
        pt_style = _resolve_particle_style_index(variant, style)
        glow_amount = float(ps.get("glow", 0.0) or 0.0)
        try:
            glow_amount = float(max(0.0, min(1.0, glow_amount)))
        except (TypeError, ValueError):
            glow_amount = 0.0
        pt_size = float(max(1.0, ps_size * (2.2 if style in ("bokeh", "music") else 1.5) * sf))
        icons = None
        angles = None
        if pt_style == 5 and hasattr(self.particles, "_icon") and hasattr(self.particles, "_angle"):
            icons = self.particles._icon
            angles = self.particles._angle
            if icons.shape[0] != pts.shape[0]:
                icons = None
                angles = None
        trail_batch = None
        if trail_enabled and hasattr(self.particles, "build_trail_draw_arrays"):
            trail_batch = self.particles.build_trail_draw_arrays(
                w=w,
                h=h,
                head_colors_rgba=colors_rgba,
            )
        if trail_batch is not None:
            trail_pts, trail_cols = trail_batch
            # Trails stay soft dots for readability even when heads are music icons.
            self._draw_particle_batch(
                pts=trail_pts,
                colors_rgba=trail_cols,
                pt_size=pt_size * 0.55,
                pt_style=1 if pt_style == 5 else pt_style,
                w=w,
                h=h,
                glow_amount=glow_amount * 0.55,
            )
        self._draw_particle_batch(
            pts=pts,
            colors_rgba=colors_rgba,
            pt_size=pt_size,
            pt_style=pt_style,
            w=w,
            h=h,
            glow_amount=glow_amount,
            icons=icons,
            angles=angles,
        )

    def _draw_atmosphere_pass(self, *, w: int, h: int, time_sec: float) -> None:
        """Session B atmosphere — per-style weather/volume/sky (not particle emitters)."""
        if self.ctx is None or not hasattr(self, "vao_lines"):
            return
        tpl = self.template if isinstance(self.template, dict) else {}
        atm = tpl.get("atmosphereDraw") if isinstance(tpl.get("atmosphereDraw"), dict) else None
        if atm is None or not bool(atm.get("enabled")):
            self._draw_post_effect_proxies(w=w, h=h, time_sec=time_sec)
            return
        try:
            from visualizer.composition_effects.atmosphere_gpu import (
                _hex_rgba,
                atmosphere_aurora_ribbons,
                atmosphere_caustic_points,
                atmosphere_cloud_bands,
                atmosphere_dust_points,
                atmosphere_fog_quad,
                atmosphere_heat_shimmer,
                atmosphere_star_points,
                atmosphere_weather_segments,
            )
        except Exception:
            self._draw_post_effect_proxies(w=w, h=h, time_sec=time_sec)
            return
        aid = str(atm.get("atmosphereId") or "fog")
        kind = str(atm.get("kind") or "volume")
        density = float(atm.get("density") or 0.35)
        tint = str(atm.get("tint") or "#a8b4c8")
        speed = float(atm.get("speed") or 1.0)
        opacity = float(atm.get("opacity") or 1.0)
        wind = float(atm.get("wind") or 1.0)
        try:
            self._blend_normal()
            # Volume/sky wash scales with density×opacity — no fixed floor (was stuck shade).
            # Weather (rain/snow/storm) is streaks only — never a full-screen tint.
            dens = max(0.0, float(density))
            op = max(0.0, min(1.0, float(opacity)))
            if dens > 0.001 and op > 0.001 and kind in {"volume", "distort", "sky"}:
                wash_a = dens * op * (0.55 if aid == "void" else (0.22 if kind == "volume" else 0.12))
                if wash_a > 0.01:
                    rgba = _hex_rgba(tint, wash_a)
                    verts = atmosphere_fog_quad(rgba)
                    self._write_vbo(self.line_vbo, verts)
                    self.vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(verts.shape[0]))

            if kind == "weather" or aid in {"rain", "snow", "storm"}:
                weather_kind = "snow" if aid == "snow" else ("storm" if aid == "storm" else "rain")
                segs = atmosphere_weather_segments(
                    kind=weather_kind,
                    density=density,
                    speed=speed,
                    tint=tint,
                    time_sec=time_sec,
                    width=w,
                    height=h,
                    wind=wind,
                    opacity=opacity,
                )
                if segs.shape[0]:
                    self._blend_additive()
                    self._write_vbo(self.line_vbo, segs)
                    self.vao_lines.render(mode=moderngl.LINES, vertices=int(segs.shape[0]))
                    self._blend_normal()
                if aid == "storm" and float(atm.get("flash") or 0.0) > 0.05:
                    flash = abs(math.sin(float(time_sec) * 7.0 * speed)) ** 12
                    if flash > 0.35:
                        rgba = _hex_rgba("#e0f2fe", 0.12 * flash * opacity)
                        verts = atmosphere_fog_quad(rgba)
                        self._blend_additive()
                        self._write_vbo(self.line_vbo, verts)
                        self.vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(verts.shape[0]))
                        self._blend_normal()

            if aid in {"dust", "smoke", "haze", "fog", "mist"} and hasattr(self, "vao_pts"):
                pts = atmosphere_dust_points(
                    density=density * (1.25 if aid == "dust" else 0.9),
                    speed=speed,
                    time_sec=time_sec,
                    wind=wind,
                )
                if pts.shape[0]:
                    self._blend_additive()
                    self._write_vbo(self.pt_vbo, pts)
                    self.vao_pts.render(mode=moderngl.POINTS, vertices=int(pts.shape[0]))
                    self._blend_normal()

            if aid == "clouds":
                bands = atmosphere_cloud_bands(
                    density=density,
                    speed=speed,
                    tint=tint,
                    time_sec=time_sec,
                    opacity=opacity,
                )
                if bands.shape[0]:
                    self._blend_normal()
                    self._write_vbo(self.line_vbo, bands)
                    self.vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(bands.shape[0]))

            if aid == "aurora":
                ribbons = atmosphere_aurora_ribbons(
                    density=density,
                    speed=speed,
                    tint=tint,
                    time_sec=time_sec,
                    opacity=opacity,
                )
                if ribbons.shape[0]:
                    self._blend_additive()
                    self._write_vbo(self.line_vbo, ribbons)
                    self.vao_lines.render(mode=moderngl.LINES, vertices=int(ribbons.shape[0]))
                    self._blend_normal()

            if aid in {"stars", "nebula", "void"} and hasattr(self, "vao_pts"):
                pts = atmosphere_star_points(
                    density=density * (0.35 if aid == "void" else 1.0),
                    twinkle=float(atm.get("twinkle") or (0.75 if aid == "stars" else 0.35)),
                    time_sec=time_sec,
                )
                if pts.shape[0]:
                    self._blend_additive()
                    self._write_vbo(self.pt_vbo, pts)
                    self.vao_pts.render(mode=moderngl.POINTS, vertices=int(pts.shape[0]))
                    self._blend_normal()

            if aid == "heatwave" or kind == "distort":
                shimmer = atmosphere_heat_shimmer(
                    density=density,
                    speed=speed,
                    amplitude=float(atm.get("amplitude") or 0.03),
                    time_sec=time_sec,
                    opacity=opacity,
                )
                if shimmer.shape[0]:
                    self._blend_additive()
                    self._write_vbo(self.line_vbo, shimmer)
                    self.vao_lines.render(mode=moderngl.LINES, vertices=int(shimmer.shape[0]))
                    self._blend_normal()

            if aid == "underwater" and hasattr(self, "vao_pts"):
                pts = atmosphere_caustic_points(density=density, speed=speed, time_sec=time_sec)
                if pts.shape[0]:
                    self._blend_additive()
                    self._write_vbo(self.pt_vbo, pts)
                    self.vao_pts.render(mode=moderngl.POINTS, vertices=int(pts.shape[0]))
                    self._blend_normal()
        except Exception as exc:
            if not getattr(self, "_atmosphere_err_logged", False):
                self._atmosphere_err_logged = True
                self._log(f"Atmosphere pass skipped: {exc}", level="warn")
        self._draw_post_effect_proxies(w=w, h=h, time_sec=time_sec)

    def _draw_post_effect_proxies(self, *, w: int, h: int, time_sec: float) -> None:
        """Visible Studio proxies for post/overlay effects the full export stack may also run."""
        if self.ctx is None or not hasattr(self, "vao_lines"):
            return
        tpl = self.template if isinstance(self.template, dict) else {}
        fx = tpl.get("effects") if isinstance(tpl.get("effects"), dict) else {}

        def _amt(key: str, default: float = 0.2) -> float:
            block = fx.get(key) if isinstance(fx.get(key), dict) else {}
            if not bool(block.get("enabled")):
                return 0.0
            try:
                return float(block.get("amount") or default)
            except (TypeError, ValueError):
                return default

        try:
            from visualizer.composition_effects.atmosphere_gpu import (
                _hex_rgba,
                atmosphere_fog_quad,
                atmosphere_star_points,
                atmosphere_weather_segments,
            )
        except Exception:
            return
        try:
            grain_amt = max(_amt("film_grain"), _amt("sharpen") * 0.7, _amt("posterize") * 0.55)
            if grain_amt > 0.01 and hasattr(self, "vao_pts") and hasattr(self, "pt_vbo"):
                pts = atmosphere_star_points(
                    density=0.28 + grain_amt,
                    twinkle=0.55 + 0.5 * _amt("posterize"),
                    time_sec=time_sec,
                )
                if pts.shape[0]:
                    self._blend_normal()
                    self._write_vbo(self.pt_vbo, pts)
                    self.vao_pts.render(mode=moderngl.POINTS, vertices=int(pts.shape[0]))

            # Soft washes — keep alpha low so spectrum palette hues stay readable.
            wash_specs = (
                ("soft_diffusion", "#c7d2fe", 0.04),
                ("color_grading", "#f9a8d4", 0.03),
                ("tone_mapping", "#fde68a", 0.03),
                ("hdr", "#fef3c7", 0.03),
                ("exposure", "#fff7ed", 0.03),
                ("gamma", "#e2e8f0", 0.03),
                ("contrast", "#94a3b8", 0.03),
                ("glow", "#a78bfa", 0.05),
                ("bloom", "#e9d5ff", 0.04),
            )
            for key, tint, base_a in wash_specs:
                amt = _amt(key)
                if amt <= 0.01:
                    continue
                if key in {"glow", "bloom", "hdr"}:
                    self._blend_additive()
                else:
                    self._blend_normal()
                rgba = _hex_rgba(tint, base_a + 0.08 * amt)
                verts = atmosphere_fog_quad(rgba)
                self._write_vbo(self.line_vbo, verts)
                self.vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(verts.shape[0]))
                self._blend_normal()

            split_amt = max(_amt("rgb_split"), _amt("chromatic_aberration"), _amt("lens_distortion") * 0.8)
            if split_amt > 0.01:
                self._blend_additive()
                for hex_tint, alpha in (
                    ("#ff3355", 0.05 + 0.12 * split_amt),
                    ("#33e0ff", 0.04 + 0.1 * split_amt),
                ):
                    rgba = _hex_rgba(hex_tint, alpha)
                    verts = atmosphere_fog_quad(rgba)
                    self._write_vbo(self.line_vbo, verts)
                    self.vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(verts.shape[0]))
                self._blend_normal()

            motion_amt = max(_amt("motion_blur"), _amt("depth_of_field"))
            if motion_amt > 0.01:
                segs = atmosphere_weather_segments(
                    kind="rain" if _amt("motion_blur") >= _amt("depth_of_field") else "snow",
                    density=0.2 + motion_amt,
                    speed=0.6 + motion_amt,
                    tint="#e2e8f0",
                    time_sec=time_sec,
                    width=w,
                    height=h,
                )
                if segs.shape[0]:
                    self._blend_normal()
                    self._write_vbo(self.line_vbo, segs)
                    self.vao_lines.render(mode=moderngl.LINES, vertices=int(segs.shape[0]))

            letter_amt = _amt("letterbox")
            if letter_amt > 0.01:
                band = max(0.04, min(0.28, 0.08 + 0.22 * letter_amt))
                rgba = _hex_rgba("#020617", 0.55 + 0.35 * letter_amt)
                # Top + bottom bars in NDC.
                bars = np.array(
                    [
                        [-1.0, 1.0 - band, *rgba],
                        [1.0, 1.0 - band, *rgba],
                        [1.0, 1.0, *rgba],
                        [-1.0, 1.0 - band, *rgba],
                        [1.0, 1.0, *rgba],
                        [-1.0, 1.0, *rgba],
                        [-1.0, -1.0, *rgba],
                        [1.0, -1.0, *rgba],
                        [1.0, -1.0 + band, *rgba],
                        [-1.0, -1.0, *rgba],
                        [1.0, -1.0 + band, *rgba],
                        [-1.0, -1.0 + band, *rgba],
                    ],
                    dtype=np.float32,
                )
                self._blend_normal()
                self._write_vbo(self.line_vbo, bars)
                self.vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(bars.shape[0]))
        except Exception as exc:
            if not getattr(self, "_post_proxy_err_logged", False):
                self._post_proxy_err_logged = True
                self._log(f"Post proxy pass skipped: {exc}", level="warn")

    def _finish_lightning_frame(
        self,
        *,
        w: int,
        h: int,
        sf: float,
        cx: float,
        cy: float,
        time_sec: float,
        audio_env: float,
        bass: float = 0.0,
        kick: float = 0.0,
        beat: float = 0.0,
        onset: float = 0.0,
    ) -> None:
        if self.ctx is None or not hasattr(self, "vao_lines"):
            return
        try:
            from features.video.lib.lightning_render import render_lightning_layers_gl
        except Exception:
            return
        render_lightning_layers_gl(
            self.ctx,
            line_vbo=self.line_vbo,
            vao_lines=self.vao_lines,
            template=self.template if isinstance(self.template, dict) else {},
            w=w,
            h=h,
            sf=sf,
            cx=cx,
            cy=cy,
            time_sec=float(time_sec),
            bass=float(bass),
            kick=float(kick),
            beat=float(beat),
            onset=float(onset),
            audio_env=float(audio_env),
        )

    def _write_vbo(self, vbo, arr: np.ndarray) -> None:
        """Upload float32 verts without ``.tobytes()`` copies (cuts GC hitch)."""
        data = np.ascontiguousarray(arr, dtype=np.float32)
        nbytes = int(data.nbytes)
        if nbytes > int(vbo.size):
            vbo.orphan(size=nbytes)
        vbo.write(data)

    def _log(self, msg: str, *, level: DiagLevel = "info", mirror_app_log: bool | None = None) -> None:
        """Preview GL breadcrumb → AppData preview-gl-diag.log (+ AppLogger when useful)."""
        text = str(msg or "").strip()
        if not text:
            return
        # Strip legacy ``[HH:MM:SS]`` prefixes; diag writer stamps wall clock.
        if text.startswith("[") and "]" in text[:12]:
            text = text.split("]", 1)[1].strip() or text
        write_preview_gl_diag(text, level=level, mirror_app_log=mirror_app_log)

    def _set_gl_error(self, message: str) -> None:
        text = str(message or "").strip()
        self._last_gl_error = text
        if text:
            self._log(text, level="error")

    def _gl_failure_user_message(self, detail: str = "") -> str:
        detail_text = str(detail or getattr(self, "_last_gl_error", "") or "").strip()
        lines = [
            "GPU preview failed to start on this PC.",
            "The Video page stays usable; try Remount Preview or restart Camxora.",
            "Send support: %LOCALAPPDATA%\\Camxora\\logs\\preview-gl-diag.log",
            "and the daily camxora-*.log from the same folder.",
        ]
        if detail_text:
            lines.append(f"Detail: {detail_text}")
        return "\n\n".join(lines)

    def _show_gl_failure_overlay(self, detail: str = "") -> None:
        """REQ-P1.2: opaque panel — never leave a transparent GL hole."""
        message = self._gl_failure_user_message(detail)
        label = getattr(self, "_gl_failure_label", None)
        if label is None:
            return
        label.setText(message)
        label.setGeometry(self.rect())
        label.show()
        label.raise_()
        if not getattr(self, "_gl_failure_emitted", False):
            self._gl_failure_emitted = True
            try:
                self.gl_failed.emit(message)
            except Exception:
                pass

    def _hide_gl_failure_overlay(self) -> None:
        label = getattr(self, "_gl_failure_label", None)
        if label is not None:
            label.hide()
        self._gl_failure_emitted = False
        self._fbo_bind_failures = 0

    def _ensure_gl_current(self, action: str) -> bool:
        """makeCurrent + validate context before texture upload / draw work."""
        action_key = str(action or "gl").strip() or "gl"
        try:
            self.makeCurrent()
        except Exception as exc:
            self._set_gl_error(f"{action_key}: makeCurrent raised: {exc}")
            return False
        qt_ctx = self.context()
        if qt_ctx is None or not bool(qt_ctx.isValid()):
            self._set_gl_error(f"{action_key}: OpenGL context missing or invalid")
            return False
        try:
            from PySide6.QtGui import QOpenGLContext

            current = QOpenGLContext.currentContext()
            if current is not None and current is not qt_ctx:
                self._log(
                    f"{action_key}: current context mismatch (multi-GPU / wrong surface?)",
                    level="warn",
                )
        except Exception:
            pass
        return True

    def _use_qt_framebuffer(self) -> bool:
        """Bind Qt's FBO. Returns False when bind fails (REQ-P1.3)."""
        if not self.ctx:
            return False
        try:
            self.makeCurrent()
            qt_fbo = int(self.defaultFramebufferObject())
            if not self._screen_fbo or int(getattr(self._screen_fbo, "glo", 0) or 0) != qt_fbo:
                self._screen_fbo = self.ctx.detect_framebuffer(qt_fbo)
            self._screen_fbo.use()
            self._fbo_bind_failures = 0
            return True
        except Exception as exc:
            self._log(f"detect_framebuffer bind failed: {exc}", level="warn", mirror_app_log=False)
        try:
            self.makeCurrent()
            from OpenGL import GL
            GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, int(self.defaultFramebufferObject()))
            self._fbo_bind_failures = 0
            return True
        except Exception as exc:
            self._fbo_bind_failures = int(getattr(self, "_fbo_bind_failures", 0) or 0) + 1
            self._log(
                f"Qt FBO bind failed (count={self._fbo_bind_failures}): {exc}",
                level="warn",
            )
            if self._fbo_bind_failures >= int(getattr(self, "_FBO_BIND_FAIL_LIMIT", 30) or 30):
                self._set_gl_error(f"Qt FBO bind failed repeatedly: {exc}")
                self._show_gl_failure_overlay(self._last_gl_error)
            return False

    def on_position_changed(self, position):
        self.current_time = position / 1000.0

    def _mark_playback_started(self, start_sec: float | None=None):
        base = float(self.current_time if start_sec is None else start_sec)
        self._audio_clock_base = max(0.0, base)
        self._audio_clock_started_at = time.perf_counter()
        self.current_time = self._audio_clock_base

    def _mark_playback_paused(self):
        if self._audio_clock_started_at is not None:
            elapsed = max(0.0, time.perf_counter() - self._audio_clock_started_at)
            self._audio_clock_base = max(0.0, self._audio_clock_base + elapsed)
        self._audio_clock_started_at = None
        self.current_time = self._audio_clock_base

    def _mark_playback_stopped(self):
        self._audio_clock_base = 0.0
        self._audio_clock_started_at = None
        self.current_time = 0.0

    def _sync_current_time_from_clock(self):
        if self._audio_clock_started_at is None:
            self.current_time = max(0.0, self._audio_clock_base)
            return
        elapsed = max(0.0, time.perf_counter() - self._audio_clock_started_at)
        self.current_time = max(0.0, self._audio_clock_base + elapsed)

    def _audio_duration_cache_key(self, path: str) -> str:
        try:
            stat = os.stat(path)
            return f'{path}|{int(stat.st_mtime_ns)}|{int(stat.st_size)}'
        except Exception:
            return str(path or '').strip()

    def set_template(self, tpl: dict, *, generation: int | None = None, clear_peak_cache: bool | None = None):
        # Don't clobber live GPU drag offset with a full rebuild mid-drag.
        if self._text_drag_domain in {"album", "title"} and (
            abs(self._text_drag_dx) > 1e-06 or abs(self._text_drag_dy) > 1e-06
        ):
            return
        # Skip identical payloads — normalize_renderer_template is expensive and
        # clearing the peak cache caused periodic hitch after every draft push.
        if tpl is self.template:
            return
        if generation is not None and generation == getattr(self, "_template_generation", None):
            return
        if generation is None:
            try:
                import json as _json

                key = _json.dumps(tpl, sort_keys=True, default=str)
            except Exception:
                key = None
            if key is not None and key == getattr(self, "_template_fingerprint", None):
                return
            self._template_fingerprint = key
            self._template_generation = int(getattr(self, "_template_generation", 0) or 0) + 1
        else:
            self._template_generation = int(generation)
            self._template_fingerprint = None
        self.template = normalize_renderer_template(tpl)
        should_clear = True if clear_peak_cache is None else bool(clear_peak_cache)
        if should_clear:
            self._spectrum_peak_cache.clear()
        self.update()

    def apply_preview_patch(self, patch: dict) -> bool:
        """REQ-P2.2: mutate live normalized template without re-normalize.

        Supported shapes:
          ``{"particlesSettings": {"opacity": …, "size": …}}``
          ``{"layerIndex": int, "layer": {"glow"|"opacity"|"barWidth": …}}``
          ``{"instanceIndex": int, "layerIndex": int, "layer": {...}}``

        Returns True when the patch was applied (allowlisted). False → caller
        must full-push.
        """
        if not isinstance(patch, dict) or not patch:
            return False
        applied = False
        clear_peaks = False

        ps_patch = patch.get("particlesSettings")
        if isinstance(ps_patch, dict) and ps_patch:
            allowed = {"opacity", "size"}
            if set(ps_patch.keys()) - allowed:
                return False
            ps = self.template.get("particlesSettings")
            if not isinstance(ps, dict):
                ps = {}
                self.template["particlesSettings"] = ps
            if "opacity" in ps_patch:
                from features.video.lib.preview_scrub_patch import clamp_particle_scrub_value

                ps["opacity"] = clamp_particle_scrub_value("particlesOpacity", ps_patch["opacity"])
                applied = True
            if "size" in ps_patch:
                from features.video.lib.preview_scrub_patch import clamp_particle_scrub_value

                ps["size"] = clamp_particle_scrub_value("particlesSize", ps_patch["size"])
                applied = True

        layer_patch = patch.get("layer")
        if isinstance(layer_patch, dict) and layer_patch:
            from features.video.lib.preview_scrub_patch import (
                PREVIEW_SCRUB_LAYER_KEYS,
                clamp_layer_scrub_value,
            )

            if set(layer_patch.keys()) - PREVIEW_SCRUB_LAYER_KEYS:
                return False
            layer_index = int(patch.get("layerIndex", 0) or 0)
            instance_index = patch.get("instanceIndex", None)

            def _apply_into(layers_obj: object) -> bool:
                if not isinstance(layers_obj, list) or not layers_obj:
                    return False
                idx = max(0, min(layer_index, len(layers_obj) - 1))
                current = layers_obj[idx] if isinstance(layers_obj[idx], dict) else {}
                updated = dict(current)
                for key, raw in layer_patch.items():
                    updated[key] = clamp_layer_scrub_value(key, raw)
                layers_obj[idx] = updated
                return True

            layers = self.template.get("layers")
            if isinstance(layers, list):
                applied = _apply_into(layers) or applied
            instances = self.template.get("spectrumInstances")
            if isinstance(instances, list) and instances:
                inst_i = (
                    int(instance_index)
                    if instance_index is not None
                    else int(getattr(self, "_selected_spectrum_instance_index", 0) or 0)
                )
                inst_i = max(0, min(inst_i, len(instances) - 1))
                inst = instances[inst_i] if isinstance(instances[inst_i], dict) else None
                if isinstance(inst, dict):
                    inst_layers = inst.get("layers")
                    if isinstance(inst_layers, list):
                        applied = _apply_into(inst_layers) or applied

        if not applied:
            return False
        # Opacity/glow/size patches do not invalidate peak geometry (REQ-P2.4).
        if clear_peaks:
            self._spectrum_peak_cache.clear()
        self._template_generation = int(getattr(self, "_template_generation", 0) or 0) + 1
        self._template_fingerprint = None
        self.update()
        return True

    def set_interactive_scrub(self, active: bool) -> None:
        """REQ-P2.5: lower paint rate while dragging inspector sliders."""
        want = bool(active)
        if want == bool(getattr(self, "_interactive_scrub", False)):
            return
        self._interactive_scrub = want
        try:
            hz = 20 if want else int(getattr(self, "_target_hz", _preview_target_hz()) or 120)
            self.timer.setInterval(max(1, 1000 // hz))
        except Exception:
            pass

    def configure(self, config: PreviewConfig) -> None:
        """Apply a PreviewConfig DTO to set up the preview widget.

        This is the DTO-based entry point for configuring the preview.
        It sets the template, background, and logo from the DTO fields.
        """
        self.template = normalize_renderer_template(config.template)
        self._spectrum_peak_cache.clear()
        if config.background_path:
            self.load_background(config.background_path)
        if config.logo_path:
            self.load_logo(config.logo_path)

    def set_bg_edit_mode(self, enabled: bool) -> None:
        self._bg_edit_mode = bool(enabled)

    def set_spectrum_position_edit_mode(self, enabled: bool) -> None:
        self._spectrum_position_edit_mode = bool(enabled)

    def set_lightning_position_edit_mode(self, enabled: bool) -> None:
        self._lightning_position_edit_mode = bool(enabled)

    def set_selected_lightning_layer_index(self, index: int) -> None:
        self._selected_lightning_layer_index = int(max(0, index))

    def set_logo_position_edit_mode(self, enabled: bool) -> None:
        self._logo_position_edit_mode = bool(enabled)

    def set_selected_spectrum_instance_index(self, index: int) -> None:
        self._selected_spectrum_instance_index = int(max(0, index))

    def set_edit_modes(
        self,
        *,
        background: bool = False,
        spectrum_position: bool = False,
        text_domain: str = "",
        lightning_position: bool = False,
        logo_position: bool = False,
    ) -> None:
        self._bg_edit_mode = bool(background)
        self._spectrum_position_edit_mode = bool(spectrum_position)
        self._lightning_position_edit_mode = bool(lightning_position)
        self._logo_position_edit_mode = bool(logo_position)
        domain = str(text_domain or "").strip().lower()
        self._text_domain_edit_mode = domain if domain in {"album", "title"} else ""
        if not self._text_domain_edit_mode:
            self._text_drag_domain = ""
            self._text_drag_dx = 0.0
            self._text_drag_dy = 0.0
        self.update()

    def set_interaction_modes(
        self,
        *,
        spectrum_position: bool = False,
        logo_position: bool = False,
        background: bool = False,
        text_domain: str = "",
        lightning_position: bool = False,
    ) -> None:
        """Studio alias for ``set_edit_modes`` (position drag on/off)."""
        self.set_edit_modes(
            background=background,
            spectrum_position=spectrum_position,
            text_domain=text_domain,
            lightning_position=lightning_position,
            logo_position=logo_position,
        )

    def set_text_drag_offset(self, domain: str, dx: float, dy: float) -> None:
        """Apply live widget-pixel offset in paintGL (GPU real-time drag)."""
        key = str(domain or "").strip().lower()
        if key not in {"album", "title"}:
            self._text_drag_domain = ""
            self._text_drag_dx = 0.0
            self._text_drag_dy = 0.0
            self.update()
            return
        self._text_drag_domain = key
        self._text_drag_dx = float(dx)
        self._text_drag_dy = float(dy)
        self.update()

    def _text_drag_source(self) -> str:
        if self._text_drag_domain == "album":
            return "albumText"
        if self._text_drag_domain == "title":
            return "titleText"
        return ""

    def _is_text_domain_dragging(self) -> bool:
        return bool(
            self._text_drag_domain in {"album", "title"}
            and (abs(self._text_drag_dx) > 1e-06 or abs(self._text_drag_dy) > 1e-06)
        )

    def apply_text_domain_position(self, domain: str, nx: float, ny: float) -> None:
        """Bake committed coords into template after overlay release."""
        key = str(domain or "").strip().lower()
        if key not in {"album", "title"}:
            return
        block_key = "albumText" if key == "album" else "titleText"
        source = block_key
        block = self.template.get(block_key)
        block = dict(block) if isinstance(block, dict) else {}
        style = block.get("style")
        style = dict(style) if isinstance(style, dict) else {}
        old_x = float(style.get("x", block.get("x", 0.0)) or 0.0)
        old_y = float(style.get("y", block.get("y", 0.0)) or 0.0)
        style["x"] = float(nx)
        style["y"] = float(ny)
        block["style"] = style
        self.template[block_key] = block
        overlays = self.template.get("textOverlays")
        if isinstance(overlays, list):
            delta_x = float(nx) - old_x
            delta_y = float(ny) - old_y
            if abs(delta_x) > 1e-09 or abs(delta_y) > 1e-09:
                from features.video.lib.text_domain_runtime import TITLE_DOMAIN_DRAG_SOURCES

                for o in overlays:
                    if not isinstance(o, dict):
                        continue
                    src = str(o.get("source") or "")
                    if key == "title" and src in TITLE_DOMAIN_DRAG_SOURCES:
                        o["x"] = float(o.get("x", 0) or 0) + delta_x
                        o["y"] = float(o.get("y", 0) or 0) + delta_y
                    elif src == source:
                        o["x"] = float(o.get("x", 0) or 0) + delta_x
                        o["y"] = float(o.get("y", 0) or 0) + delta_y
        self._text_drag_dx = 0.0
        self._text_drag_dy = 0.0
        self._text_drag_domain = ""
        self.update()

    def performance_snapshot(self) -> dict:
        return {
            "frameMs": float(self._perf_frame_ms),
            "fps": float(self._perf_fps),
            "frameCounter": int(self._frame_counter),
            "glReady": bool(getattr(self, "_gl_ready", False)),
            "lastGlError": str(getattr(self, "_last_gl_error", "") or ""),
            "bgPathSet": bool(str(getattr(self, "bg_path", "") or "").strip()),
            "logoPathSet": bool(str(getattr(self, "logo_path", "") or "").strip()),
            "bgTexSize": [
                float(getattr(self, "_bg_tex_size", (0.0, 0.0))[0]),
                float(getattr(self, "_bg_tex_size", (0.0, 0.0))[1]),
            ],
            "glInfo": dict(getattr(self, "_gl_info", {}) or {}),
            "diagLog": "preview-gl-diag.log",
        }

    def preview_lifecycle_snapshot(self) -> dict:
        last_error = str(getattr(self, "_last_gl_error", "") or "").strip()
        if not getattr(self, "_gl_ready", False):
            if last_error:
                return {
                    "status": "error",
                    "message": last_error,
                    "lastGlError": last_error,
                    "glInfo": dict(getattr(self, "_gl_info", {}) or {}),
                }
            if self.audio_loading or self.analysis_loading:
                return {"status": "initializing", "message": "Preview is loading audio analysis and GPU resources."}
            return {"status": "initializing", "message": "Preview GPU surface is initializing."}
        if last_error and any(
            token in last_error
            for token in (
                "initializeGL",
                "texture upload",
                "OpenGL context",
                "makeCurrent",
                "Background",
                "Logo",
            )
        ):
            return {
                "status": "error",
                "message": last_error,
                "lastGlError": last_error,
                "glInfo": dict(getattr(self, "_gl_info", {}) or {}),
            }
        if str(self.audio_error or "").strip():
            return {"status": "error", "message": str(self.audio_error)}
        if not str(self.bg_path or "").strip() or not str(self.audio_path or "").strip():
            return {
                "status": "fallback-active",
                "message": "Attach a background image and preview MP3 for full stage validation.",
                "lastGlError": last_error,
            }
        return {
            "status": "running",
            "message": "GPU preview compositor is running.",
            "lastGlError": last_error,
            "glInfo": dict(getattr(self, "_gl_info", {}) or {}),
        }

    def _sync_export_overlay_geometry(self) -> None:
        rect = (0, 0, max(1, int(self.width())), max(1, int(self.height())))
        for label in (
            getattr(self, "_export_freeze_label", None),
            getattr(self, "_export_overlay_label", None),
        ):
            if label is not None:
                label.setGeometry(*rect)

    def _cache_clean_preview_frame(self) -> None:
        """Store a known-good preview snapshot for export freeze UX.

        ``grabFramebuffer`` stalls the GPU pipeline. Never call this from the
        60fps ``paintGL`` loop — that caused periodic freezes every ~2.5–5s.
        Snapshot only on pause / explicit request.
        """
        if self._export_overlay_active or not getattr(self, "_gl_ready", False):
            return
        if bool(getattr(self, "audio_playing", False)):
            return
        try:
            img = self.grabFramebuffer()
            if img.isNull():
                return
            self._last_clean_preview = QPixmap.fromImage(img)
            self._last_clean_preview_at = time.perf_counter()
        except Exception:
            pass

    def _schedule_clean_preview_snapshot(self) -> None:
        """One-shot grab after pause — not on a repeating paint cadence."""
        if bool(getattr(self, "audio_playing", False)):
            return
        QTimer.singleShot(0, self._cache_clean_preview_frame)

    def _invalidate_logo_visible_radius_cache(self) -> None:
        self._logo_visible_radius_key = None
        self._logo_visible_radius_ratio = 1.0

    def _logo_visible_radius_ratio_cached(self, *, circle_mask: bool) -> float:
        """Alpha-scan once per logo / mask change — not every paint frame."""
        logo_rgba = getattr(self, "_logo_rgba_cache", None)
        if logo_rgba is None:
            self._invalidate_logo_visible_radius_cache()
            return 1.0
        key = (int(id(logo_rgba)), bool(circle_mask))
        if self._logo_visible_radius_key == key:
            return float(self._logo_visible_radius_ratio)
        ratio = float(_compute_visible_logo_radius_ratio(logo_rgba, bool(circle_mask)))
        self._logo_visible_radius_ratio = ratio
        self._logo_visible_radius_key = key
        return ratio

    def _apply_freeze_pixmap(self, pix: QPixmap | None) -> None:
        freeze = getattr(self, "_export_freeze_label", None)
        if freeze is None:
            return
        if pix is None or pix.isNull():
            freeze.clear()
            return
        freeze.setPixmap(
            pix.scaled(
                max(1, int(self.width())),
                max(1, int(self.height())),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def prepare_export_surface(self) -> Any:
        """Create QOffscreenSurface on the GUI thread (Qt requirement)."""
        from PySide6.QtGui import QOffscreenSurface

        share_ctx = self.context()
        if share_ctx is None:
            raise RuntimeError("Preview OpenGL context is not available")
        surface = QOffscreenSurface()
        surface.setFormat(share_ctx.format())
        surface.create()
        if not surface.isValid():
            raise RuntimeError("Failed to create export offscreen surface")
        self._export_offscreen_surface = surface
        self._export_gl_context = None
        return surface

    def blocking_prepare_export_surface(self) -> Any:
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None and QThread.currentThread() == app.thread():
            return self.prepare_export_surface()
        self._blocking_export_gl_result = None
        self._blocking_export_gl_error = None
        ok = QMetaObject.invokeMethod(
            self,
            "_prepare_export_surface_on_gui",
            Qt.ConnectionType.BlockingQueuedConnection,
        )
        if not ok:
            raise RuntimeError("Failed to dispatch export surface setup to GUI thread")
        if self._blocking_export_gl_error is not None:
            raise self._blocking_export_gl_error
        if self._blocking_export_gl_result is None:
            raise RuntimeError("Export surface setup returned nothing")
        return self._blocking_export_gl_result

    @Slot()
    def _prepare_export_surface_on_gui(self) -> None:
        try:
            self._blocking_export_gl_result = self.prepare_export_surface()
            self._blocking_export_gl_error = None
        except Exception as exc:
            self._blocking_export_gl_error = exc
            self._blocking_export_gl_result = None

    # Back-compat aliases used by older call sites / tests.
    def prepare_export_shared_gl(self) -> Any:
        return self.prepare_export_surface()

    def blocking_prepare_export_shared_gl(self) -> Any:
        return self.blocking_prepare_export_surface()

    @Slot()
    def _prepare_export_shared_gl_on_gui(self) -> None:
        self._prepare_export_surface_on_gui()

    def set_export_overlay(self, active: bool, message: str = "") -> None:
        """Show or hide in-process export status on the preview surface."""
        self._export_overlay_active = bool(active)
        self._export_overlay_message = str(message or ("Exporting…" if active else ""))
        overlay = getattr(self, "_export_overlay_label", None)
        freeze = getattr(self, "_export_freeze_label", None)
        if overlay is not None:
            overlay.setText(self._export_overlay_message)
        self._sync_export_overlay_geometry()
        if active:
            # Prefer last clean snapshot from live playback — never grab GL right as
            # export starts (that frame is often already half-corrupt under load).
            cached = self._last_clean_preview
            if cached is not None and not cached.isNull():
                self._apply_freeze_pixmap(cached)
            else:
                try:
                    img = self.grabFramebuffer()
                    if not img.isNull():
                        self._apply_freeze_pixmap(QPixmap.fromImage(img))
                    else:
                        self._apply_freeze_pixmap(None)
                except Exception:
                    self._apply_freeze_pixmap(None)
            if freeze is not None:
                freeze.show()
                freeze.raise_()
            if overlay is not None:
                overlay.show()
                overlay.raise_()
            self.timer.stop()
        else:
            if freeze is not None:
                freeze.hide()
                freeze.clear()
            if overlay is not None:
                overlay.hide()
            if not self.timer.isActive():
                self.timer.start(1000 // 60)
            self.update()

    @Slot(bool, str)
    def _set_export_overlay_on_gui(self, active: bool, message: str = "") -> None:
        self.set_export_overlay(active, message)

    def invoke_set_export_overlay(self, active: bool, message: str = "") -> None:
        connection = (
            Qt.ConnectionType.BlockingQueuedConnection
            if active
            else Qt.ConnectionType.QueuedConnection
        )
        try:
            ok = QMetaObject.invokeMethod(
                self,
                "_set_export_overlay_on_gui",
                connection,
                Q_ARG(bool, bool(active)),
                Q_ARG(str, str(message or "")),
            )
            if ok:
                return
        except Exception:
            pass
        self.set_export_overlay(active, message)

    def playback_snapshot(self) -> dict:
        return {
            "isPlaying": bool(self.audio_playing),
            "isReady": bool(self.audio_ready),
            "isLoading": bool(self.audio_loading or self.analysis_loading),
            "currentTimeSec": float(max(0.0, self.current_time)),
            "durationSec": float(max(0.0, self._audio_duration_sec)),
        }

    def _emit_playback_state(self) -> None:
        # load_audio runs on a worker thread — marshal UI signal to the GUI thread.
        try:
            ok = QMetaObject.invokeMethod(
                self,
                "_emit_playback_state_on_gui",
                Qt.ConnectionType.QueuedConnection,
            )
            if ok:
                return
        except Exception:
            pass
        self.playback_state_changed.emit(self.playback_snapshot())

    @Slot()
    def _emit_playback_state_on_gui(self) -> None:
        self.playback_state_changed.emit(self.playback_snapshot())

    def set_loop_playback(self, enabled: bool) -> None:
        self._loop_playback = bool(enabled)

    def loop_playback(self) -> bool:
        return bool(getattr(self, "_loop_playback", False))

    def play_preview(self) -> None:
        if not str(self.audio_path or "").strip():
            return
        import pygame

        if not self.audio_ready:
            return
        try:
            duration = float(max(0.0, self._audio_duration_sec))
            # After a track ends (or near the end), Play should restart from 0.
            at_end = duration > 0.05 and float(self.current_time) >= (duration - 0.08)
            if at_end or float(self.current_time) < 0.0:
                self.current_time = 0.0
                self._audio_clock_base = 0.0
                self._audio_clock_started_at = None
            if not pygame.mixer.music.get_busy():
                start = float(max(0.0, self.current_time))
                if duration > 0:
                    start = min(start, max(0.0, duration - 0.05))
                pygame.mixer.music.play(start=start)
            else:
                pygame.mixer.music.unpause()
        except Exception as exc:
            self.audio_error = str(exc)
            self._emit_playback_state()
            return
        self.audio_playing = True
        self._mark_playback_started(self.current_time)
        self._emit_playback_state()

    def pause_preview(self) -> None:
        import pygame

        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
        except Exception:
            pass
        self.audio_playing = False
        self._mark_playback_paused()
        self._emit_playback_state()
        self._schedule_clean_preview_snapshot()

    def stop_preview(self) -> None:
        import pygame

        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.audio_playing = False
        self._mark_playback_stopped()
        self._emit_playback_state()
        self._schedule_clean_preview_snapshot()

    def seek_preview(self, time_sec: float) -> None:
        import pygame

        target = float(max(0.0, time_sec))
        if self._audio_duration_sec > 0:
            target = min(target, float(self._audio_duration_sec))
        was_playing = bool(self.audio_playing)
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.current_time = target
        self._audio_clock_base = target
        self._audio_clock_started_at = None
        if was_playing and self.audio_ready and str(self.audio_path or "").strip():
            try:
                pygame.mixer.music.play(start=target)
                self.audio_playing = True
                self._mark_playback_started(target)
            except Exception:
                self.audio_playing = False
        self._emit_playback_state()

    def issue_playback_command(self, command: dict) -> None:
        command_type = str((command or {}).get("type") or "").strip().lower()
        if command_type == "play":
            self.play_preview()
        elif command_type == "pause":
            self.pause_preview()
        elif command_type == "stop":
            self.stop_preview()
        elif command_type == "seek":
            self.seek_preview(float((command or {}).get("timeSec") or 0.0))

    def mousePressEvent(self, ev):
        # Album/Title drag is handled by TextDragOverlay (CapCut-style UI layer).
        if ev.button() == Qt.MouseButton.LeftButton and bool(
            getattr(self, "_spectrum_position_edit_mode", False)
        ):
            mods = ev.modifiers()
            shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
            alt = bool(mods & Qt.KeyboardModifier.AltModifier)
            if shift or alt:
                hit = self._nearest_bar_hit(float(ev.position().x()), float(ev.position().y()))
                if hit is not None:
                    self._dragging = True
                    self._drag_last = (float(ev.position().x()), float(ev.position().y()))
                    self._bar_edit_layer_index = int(hit["layer"])
                    self._bar_edit_index = int(hit["bar"])
                    self._bar_edit_center = (float(hit["cx"]), float(hit["cy"]))
                    self._bar_edit_last_angle = math.atan2(
                        float(ev.position().y()) - float(hit["cy"]),
                        float(ev.position().x()) - float(hit["cx"]),
                    )
                    if shift and alt:
                        self._bar_edit_mode = "height"
                    elif shift:
                        self._bar_edit_mode = "raise"
                    else:
                        self._bar_edit_mode = "phase"
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    self.grabMouse()
                    ev.accept()
                    return
        if ev.button() == Qt.MouseButton.LeftButton and (
            self._bg_edit_mode
            or self._spectrum_position_edit_mode
            or getattr(self, "_lightning_position_edit_mode", False)
            or getattr(self, "_logo_position_edit_mode", False)
        ):
            self._dragging = True
            self._drag_last = (float(ev.position().x()), float(ev.position().y()))
            self._bar_edit_mode = None
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.grabMouse()
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._drag_last = None
            self._bar_edit_mode = None
            self._bar_edit_index = -1
            self.releaseMouse()
            self.unsetCursor()
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def _nearest_bar_hit(self, x: float, y: float, max_dist: float = 28.0) -> dict | None:
        best = None
        best_d = float(max_dist)
        for hit in list(getattr(self, "_bar_hit_cache", []) or []):
            try:
                d = math.hypot(float(hit["tx"]) - x, float(hit["ty"]) - y)
            except Exception:
                continue
            if d < best_d:
                best_d = d
                best = hit
        return best

    def _patch_selected_spectrum_layer(self, **fields) -> None:
        """Live-mutate authored + compiled layer knobs, then persist via signal."""
        comp = self.template.get("composition")
        layer_idx = int(getattr(self, "_bar_edit_layer_index", 0) or 0)
        if isinstance(comp, dict):
            spec = dict(comp.get("spectrum") if isinstance(comp.get("spectrum"), dict) else {})
            layers = list(spec.get("layers") or [])
            if layers:
                idx = max(0, min(len(layers) - 1, layer_idx))
                layer = dict(layers[idx]) if isinstance(layers[idx], dict) else {}
                layer.update(fields)
                layers[idx] = layer
                spec["layers"] = layers
                self.template["composition"] = {**comp, "spectrum": spec}
        # Compiled rings used by paintGL.
        for key in ("layers",):
            rings = self.template.get(key)
            if isinstance(rings, list) and rings:
                idx = max(0, min(len(rings) - 1, layer_idx))
                if isinstance(rings[idx], dict):
                    rings[idx] = {**rings[idx], **fields}
                    self.template[key] = rings
        instances = self.template.get("spectrumInstances")
        if isinstance(instances, list) and instances:
            inst0 = instances[0] if isinstance(instances[0], dict) else {}
            rings = list(inst0.get("layers") or [])
            if rings:
                idx = max(0, min(len(rings) - 1, layer_idx))
                if isinstance(rings[idx], dict):
                    rings[idx] = {**rings[idx], **fields}
                    instances[0] = {**inst0, "layers": rings}
                    self.template["spectrumInstances"] = instances
        try:
            self.spectrum_layer_patch_changed.emit(dict(fields))
        except Exception:
            pass
        self.update()

    def mouseMoveEvent(self, ev):
        if not self._dragging or not self._drag_last:
            super().mouseMoveEvent(ev)
            return
        x0, y0 = self._drag_last
        x1 = float(ev.position().x())
        y1 = float(ev.position().y())
        dx = x1 - x0
        dy = y1 - y0
        self._drag_last = (x1, y1)

        mode = getattr(self, "_bar_edit_mode", None)
        if mode in ("raise", "phase", "height"):
            hits = list(getattr(self, "_bar_hit_cache", []) or [])
            hit = None
            for item in hits:
                if int(item.get("bar", -1)) == int(self._bar_edit_index) and int(
                    item.get("layer", -1)
                ) == int(self._bar_edit_layer_index):
                    hit = item
                    break
            if hit is None and hits:
                hit = hits[min(len(hits) - 1, max(0, int(self._bar_edit_index)))]
            if mode == "raise" and hit is not None:
                vx = x1 - float(hit["bx"])
                vy = -(y1 - float(hit["by"]))  # screen Y down → math Y up
                if abs(vx) + abs(vy) > 1e-3:
                    deg = (math.degrees(math.atan2(vy, vx)) + 360.0) % 360.0
                    self._patch_selected_spectrum_layer(raiseAngleDeg=float(deg))
            elif mode == "phase":
                cx, cy = self._bar_edit_center
                ang = math.atan2(y1 - cy, x1 - cx)
                delta = ang - float(self._bar_edit_last_angle)
                # Wrap to [-pi, pi]
                while delta > math.pi:
                    delta -= 2.0 * math.pi
                while delta < -math.pi:
                    delta += 2.0 * math.pi
                self._bar_edit_last_angle = ang
                # Read current scroll from authored layer when possible.
                scroll = 0.0
                comp = self.template.get("composition")
                if isinstance(comp, dict):
                    spec = comp.get("spectrum") if isinstance(comp.get("spectrum"), dict) else {}
                    layers = spec.get("layers") if isinstance(spec.get("layers"), list) else []
                    idx = max(0, min(len(layers) - 1, int(self._bar_edit_layer_index)))
                    if layers and isinstance(layers[idx], dict):
                        scroll = clamp_frequency_scroll(layers[idx].get("frequencyScroll"), 0.0)
                scroll = clamp_frequency_scroll(scroll - delta / (2.0 * math.pi), 0.0)
                self._patch_selected_spectrum_layer(frequencyScroll=float(scroll))
            elif mode == "height" and hit is not None:
                bdx = float(hit.get("dx") or 0.0)
                bdy = float(hit.get("dy") or 0.0)
                along = float(dx) * bdx + float(dy) * bdy
                # Pull tip outward → taller
                delta_scale = along / 80.0
                overrides = {}
                comp = self.template.get("composition")
                if isinstance(comp, dict):
                    spec = comp.get("spectrum") if isinstance(comp.get("spectrum"), dict) else {}
                    layers = spec.get("layers") if isinstance(spec.get("layers"), list) else []
                    idx = max(0, min(len(layers) - 1, int(self._bar_edit_layer_index)))
                    if layers and isinstance(layers[idx], dict):
                        raw = layers[idx].get("barHeightOverrides")
                        if isinstance(raw, dict):
                            overrides = dict(raw)
                key = str(int(self._bar_edit_index))
                try:
                    cur = float(overrides.get(key, 1.0))
                except (TypeError, ValueError):
                    cur = 1.0
                nxt = max(0.05, min(4.0, cur + delta_scale))
                if abs(nxt - 1.0) < 1e-3:
                    overrides.pop(key, None)
                else:
                    overrides[key] = float(nxt)
                self._patch_selected_spectrum_layer(barHeightOverrides=overrides)
            ev.accept()
            return

        if bool(getattr(self, "_bg_edit_mode", False)):
            bg = self.template.get("backgroundSettings", {}) if isinstance(self.template.get("backgroundSettings"), dict) else {}
            ox = float(bg.get("userOffsetX", 0.0) or 0.0) + float(dx)
            oy = float(bg.get("userOffsetY", 0.0) or 0.0) + float(dy)
            self.template["backgroundSettings"] = {**bg, "userOffsetX": float(ox), "userOffsetY": float(oy)}
            self.background_transform_changed.emit(float(ox), float(oy), float(bg.get("userScale", 1.0) or 1.0))
            ev.accept()
            return
        base_h = float(self.template.get('renderBaseHeight', 450.0))
        base_h = float(max(1.0, min(4000.0, base_h)))
        sf = float(max(1.0, self.height())) / base_h
        if sf <= 1e-06:
            return
        preview_w = int(max(1, self.width()))
        preview_h = int(max(1, self.height()))

        def _clamp_xy(anchor: str, nx: float, ny: float) -> tuple[int, int]:
            cx, cy = clamp_template_offset_to_preview(
                anchor=str(anchor or "center"),
                offset_x=float(nx),
                offset_y=float(ny),
                w=preview_w,
                h=preview_h,
                sf=sf,
            )
            return int(round(cx)), int(round(cy))

        if bool(getattr(self, "_lightning_position_edit_mode", False)):
            layers = self.template.get("lightningLayers")
            if not isinstance(layers, list) or not layers:
                ev.accept()
                return
            idx = int(max(0, min(getattr(self, "_selected_lightning_layer_index", 0), len(layers) - 1)))
            layer = layers[idx] if isinstance(layers[idx], dict) else {}
            nx = float(layer.get("x", 0.0) or 0.0) + float(dx) / sf
            ny = float(layer.get("y", 0.0) or 0.0) + float(dy) / sf
            nx, ny = _clamp_xy(str(layer.get("anchor") or "center"), nx, ny)
            layers[idx] = {**layer, "x": float(nx), "y": float(ny)}
            self.template["lightningLayers"] = layers
            self.lightning_position_changed.emit(nx, ny)
            ev.accept()
            return

        # Spectrum free-drag first — Stay inside / attach also updates logo.
        # (Logo edit mode used to run first and only patched `position`, while paint
        # reads `spectrumInstances`, so the pair looked stuck.)
        def _free_spectrum_xy(nx: float, ny: float) -> tuple[float, float]:
            return (
                float(max(-960.0, min(960.0, nx))),
                float(max(-540.0, min(540.0, ny))),
            )

        def _mirror_spectrum_offsets(nx: float, ny: float) -> None:
            comp = self.template.get("composition")
            if not isinstance(comp, dict):
                return
            spec = dict(comp.get("spectrum") if isinstance(comp.get("spectrum"), dict) else {})
            spec["offsetX"] = float(nx) / 480.0
            spec["offsetY"] = float(ny) / 270.0
            self.template["composition"] = {**comp, "spectrum": spec}

        def _logo_locked_to_spectrum() -> bool:
            preview_bindings = (
                self.template.get("previewBindings")
                if isinstance(self.template.get("previewBindings"), dict)
                else {}
            )
            ls = self.template.get("logoSettings") if isinstance(self.template.get("logoSettings"), dict) else {}
            return bool(preview_bindings.get("spectrumAttachToLogo", False)) or bool(
                ls.get("containInShape")
            )

        def _mirror_logo_to_spectrum(nx: float, ny: float) -> None:
            if not _logo_locked_to_spectrum():
                return
            ls = self.template.get("logoSettings") if isinstance(self.template.get("logoSettings"), dict) else {}
            logo_pos = ls.get("position") if isinstance(ls.get("position"), dict) else {}
            self.template["logoSettings"] = {
                **ls,
                "position": {**logo_pos, "anchor": "center", "x": float(nx), "y": float(ny)},
            }

        def _apply_spectrum_drag(nx: float, ny: float) -> None:
            instances = self.template.get("spectrumInstances")
            if isinstance(instances, list) and instances:
                idx = int(
                    max(0, min(getattr(self, "_selected_spectrum_instance_index", 0), len(instances) - 1))
                )
                inst = instances[idx] if isinstance(instances[idx], dict) else {}
                instances[idx] = {**inst, "x": float(nx), "y": float(ny)}
                self.template["spectrumInstances"] = instances
            pos_cfg = self.template.get("position", {}) if isinstance(self.template.get("position"), dict) else {}
            self.template["position"] = {**pos_cfg, "x": float(nx), "y": float(ny)}
            _mirror_spectrum_offsets(nx, ny)
            _mirror_logo_to_spectrum(nx, ny)
            self.position_changed.emit(int(round(nx)), int(round(ny)))
            if _logo_locked_to_spectrum():
                self.logo_position_changed.emit(int(round(nx)), int(round(ny)))

        if bool(getattr(self, "_spectrum_position_edit_mode", False)):
            pos_cfg = self.template.get("position", {}) if isinstance(self.template.get("position"), dict) else {}
            instances = self.template.get("spectrumInstances")
            if isinstance(instances, list) and instances:
                idx = int(
                    max(0, min(getattr(self, "_selected_spectrum_instance_index", 0), len(instances) - 1))
                )
                inst = instances[idx] if isinstance(instances[idx], dict) else {}
                cur_x = float(inst.get("x", pos_cfg.get("x", 0.0)) or 0.0)
                cur_y = float(inst.get("y", pos_cfg.get("y", 0.0)) or 0.0)
            else:
                cur_x = float(pos_cfg.get("x", 0.0) or 0.0)
                cur_y = float(pos_cfg.get("y", 0.0) or 0.0)
            nx, ny = _free_spectrum_xy(cur_x + float(dx) / sf, cur_y + float(dy) / sf)
            _apply_spectrum_drag(nx, ny)
            ev.accept()
            return

        if bool(getattr(self, "_logo_position_edit_mode", False)):
            preview_bindings = (
                self.template.get("previewBindings")
                if isinstance(self.template.get("previewBindings"), dict)
                else {}
            )
            ls = self.template.get("logoSettings") if isinstance(self.template.get("logoSettings"), dict) else {}
            attached = bool(preview_bindings.get("spectrumAttachToLogo", False)) or bool(
                ls.get("containInShape")
            )
            if attached:
                pos_cfg = self.template.get("position", {}) if isinstance(self.template.get("position"), dict) else {}
                nx = float(pos_cfg.get("x", 0.0) or 0.0) + float(dx) / sf
                ny = float(pos_cfg.get("y", 0.0) or 0.0) + float(dy) / sf
                nx, ny = _free_spectrum_xy(nx, ny)
                _apply_spectrum_drag(nx, ny)
            else:
                logo_pos = ls.get("position") if isinstance(ls.get("position"), dict) else {}
                anchor = str(logo_pos.get("anchor") or "center")
                nx = float(logo_pos.get("x", 0.0) or 0.0) + float(dx) / sf
                ny = float(logo_pos.get("y", 0.0) or 0.0) + float(dy) / sf
                nx, ny = _clamp_xy(anchor, nx, ny)
                self.template["logoSettings"] = {
                    **ls,
                    "position": {**logo_pos, "anchor": "center", "x": nx, "y": ny},
                }
                self.logo_position_changed.emit(nx, ny)
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def wheelEvent(self, ev):
        if bool(getattr(self, "_bg_edit_mode", False)):
            try:
                delta = float(ev.angleDelta().y())
            except Exception:
                delta = 0.0
            if abs(delta) > 1e-06:
                bg = self.template.get("backgroundSettings", {}) if isinstance(self.template.get("backgroundSettings"), dict) else {}
                cur = float(bg.get("userScale", 1.0) or 1.0)
                factor = 1.0 + (delta / 1200.0)
                nxt = float(max(0.05, min(20.0, cur * factor)))
                self.template["backgroundSettings"] = {**bg, "userScale": nxt}
                self.background_transform_changed.emit(float(bg.get("userOffsetX", 0.0) or 0.0), float(bg.get("userOffsetY", 0.0) or 0.0), float(nxt))
                ev.accept()
                return
        if bool(getattr(self, "_spectrum_position_edit_mode", False)):
            try:
                delta = float(ev.angleDelta().y())
            except Exception:
                delta = 0.0
            if abs(delta) > 1e-06:
                # Positive wheel = larger spectrum (~0.05 steps).
                step = 0.05 if delta > 0 else -0.05
                self.spectrum_size_delta_requested.emit(float(step))
                ev.accept()
                return
        super().wheelEvent(ev)

    def load_audio(self, path):
        requested_path = str(path or '').strip()
        previous_path = str(self.audio_path or '').strip()
        self._audio_load_seq += 1
        load_seq = int(self._audio_load_seq)
        self.audio_path = requested_path
        self._mark_playback_stopped()
        self.audio_playing = False
        self.audio_loading = True
        self.audio_ready = False
        self.analysis_loading = False
        self.audio_error = ''
        self._audio_duration_sec = 0.0
        self.analyzer = None
        self._log(f"[{time.strftime('%H:%M:%S')}] Audio load request #{load_seq}: new={requested_path} previous={previous_path or '<none>'}")

        def analyze():
            import pygame
            active_path = requested_path
            with self._audio_load_lock:
                if load_seq != self._audio_load_seq:
                    self._log(f"[{time.strftime('%H:%M:%S')}] Audio load stale before decode #{load_seq}: {active_path}")
                    return
                try:
                    pygame.mixer.music.load(active_path)
                    cache_key = self._audio_duration_cache_key(active_path)
                    decoded_duration = float(self._audio_duration_cache.get(cache_key, 0.0) or 0.0)
                    if decoded_duration <= 0:
                        # Cheap metadata probe so seek/total time work before STFT finishes.
                        from visualizer.audio import probe_audio_duration_sec

                        decoded_duration = float(probe_audio_duration_sec(active_path) or 0.0)
                        if decoded_duration > 0:
                            self._audio_duration_cache[cache_key] = decoded_duration
                except Exception as e:
                    if load_seq != self._audio_load_seq:
                        self._log(f"[{time.strftime('%H:%M:%S')}] Audio load failed on stale request #{load_seq}: {e}")
                        return
                    self.audio_ready = False
                    self.audio_error = str(e)
                    self.audio_loading = False
                    self.analysis_loading = False
                    self._log(f"[{time.strftime('%H:%M:%S')}] Audio load failed #{load_seq}: {active_path} error={e}")
                    return
                if load_seq != self._audio_load_seq:
                    self._log(f"[{time.strftime('%H:%M:%S')}] Audio decode ignored for stale request #{load_seq}: {active_path}")
                    return
                self._audio_duration_sec = decoded_duration
                self.audio_ready = True
                self.audio_error = ''
                self.audio_loading = False
                self.analysis_loading = True
                self._log(f"[{time.strftime('%H:%M:%S')}] Audio decode ready #{load_seq}: {active_path} duration={self._audio_duration_sec:.2f}s")
                self._emit_playback_state()
            try:
                cache_key = self._audio_duration_cache_key(active_path)
                cached_analyzer = getattr(self, '_audio_analyzer_cache', {}).get(cache_key)
                if cached_analyzer:
                    analyzer = cached_analyzer
                else:
                    from shared.services.audio_analysis_cache import load_audio_analyzer

                    analyzer, _cache_hit = load_audio_analyzer(
                        active_path, fps=60, point_count=1024, use_cache=True
                    )
                    if not hasattr(self, '_audio_analyzer_cache'):
                        self._audio_analyzer_cache = {}
                        self._audio_analyzer_cache_order = []
                    self._audio_analyzer_cache[cache_key] = analyzer
                    if cache_key in self._audio_analyzer_cache_order:
                        self._audio_analyzer_cache_order.remove(cache_key)
                    self._audio_analyzer_cache_order.append(cache_key)
                    if len(self._audio_analyzer_cache_order) > 5:
                        oldest = self._audio_analyzer_cache_order.pop(0)
                        self._audio_analyzer_cache.pop(oldest, None)
            except Exception as e:
                if load_seq != self._audio_load_seq:
                    self._log(f"[{time.strftime('%H:%M:%S')}] Audio analysis failed on stale request #{load_seq}: {e}")
                    return
                self.analyzer = None
                # Keep any probed/cached duration — wiping it re-breaks seek mid-play.
                self._log(f"[{time.strftime('%H:%M:%S')}] Audio analysis failed #{load_seq}: {active_path} error={e}")
                self._emit_playback_state()
            else:
                if load_seq != self._audio_load_seq:
                    self._log(f"[{time.strftime('%H:%M:%S')}] Audio analysis ignored for stale request #{load_seq}: {active_path}")
                    return
                self.analyzer = analyzer
                self._audio_duration_sec = float(getattr(analyzer.info, 'duration_sec', 0.0) or 0.0)
                if self._audio_duration_sec > 0:
                    self._audio_duration_cache[self._audio_duration_cache_key(active_path)] = self._audio_duration_sec
                self._log(f"[{time.strftime('%H:%M:%S')}] Audio analysis ready #{load_seq}: {active_path} duration={self._audio_duration_sec:.2f}s")
                self._emit_playback_state()
            finally:
                if load_seq == self._audio_load_seq:
                    self.analysis_loading = False
        t = threading.Thread(target=analyze, daemon=True)
        t.start()

    def clear_background_video(self) -> None:
        if self._bg_video is not None:
            try:
                self._bg_video.close()
            except Exception:
                pass
        self._bg_video = None
        self._bg_video_path = ""

    def load_background_video(self, path) -> None:
        """Open a video plate; frames upload each paint from current_time."""
        p = str(path or "").strip()
        self.clear_background_video()
        if not p or not Path(p).exists():
            self.bg_path = ""
            self.load_background("")
            return
        try:
            from visualizer.composition_effects.video_background import VideoBackgroundSource
        except Exception as exc:
            self._set_gl_error(f"Video background unavailable: {exc}")
            return
        source = VideoBackgroundSource()
        if not source.open(p):
            self._set_gl_error(f"Video background open failed: {p}")
            return
        self._bg_video = source
        self._bg_video_path = p
        self.bg_path = p
        self._log(f"Background video selected: {p}")
        self._upload_background_video_frame(force=True)

    def _upload_background_video_frame(self, *, force: bool = False) -> None:
        if self._bg_video is None or not self.ctx:
            return
        try:
            if not self._ensure_gl_current("load_background_video"):
                return
            rgba = self._bg_video.frame_rgba_at(float(self.current_time or 0.0))
            if rgba is None:
                return
            arr = np.flipud(np.asarray(rgba, dtype=np.uint8))
            h, w = int(arr.shape[0]), int(arr.shape[1])
            if h < 1 or w < 1:
                return
            if force or not hasattr(self, "tex_bg") or tuple(getattr(self, "_bg_tex_size", (0, 0))) != (float(w), float(h)):
                if hasattr(self, "tex_bg"):
                    try:
                        self.tex_bg.release()
                    except Exception:
                        pass
                self.tex_bg = self.ctx.texture((w, h), 4, arr.tobytes())
                self.tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
                self._bg_tex_size = (float(w), float(h))
            else:
                self.tex_bg.write(arr.tobytes())
            if self._last_gl_error.startswith("Background"):
                self._last_gl_error = ""
        except Exception as exc:
            self._set_gl_error(f"Background video frame failed: {exc}")

    def load_background(self, path):
        p = str(path or "").strip()
        # Still-image plate replaces any active video source.
        if self._bg_video is not None and p != self._bg_video_path:
            self.clear_background_video()
        if not p or not Path(p).exists():
            self.bg_path = ""
            self._log("Background cleared")
            if self.ctx:
                if not self._ensure_gl_current("load_background.clear"):
                    return
                if hasattr(self, "tex_bg"):
                    try:
                        self.tex_bg.release()
                    except Exception:
                        pass
                try:
                    self.tex_bg = self.ctx.texture((1, 1), 4, b"\x00\x00\x00\x00")
                    self.tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
                    self._bg_tex_size = (1.0, 1.0)
                except Exception as exc:
                    self._set_gl_error(f"Background clear texture failed: {exc}")
            return
        self.bg_path = p
        self._log(f"Background selected: {p}")
        if not self.ctx:
            self._log("Background path stored; waiting for initializeGL to upload texture", level="warn")
            return
        try:
            if not self._ensure_gl_current("load_background"):
                return
            from PIL import Image

            img = Image.open(p).convert("RGBA")
            arr = np.array(img, dtype=np.uint8)
            arr = np.flipud(arr)
            if hasattr(self, "tex_bg"):
                try:
                    self.tex_bg.release()
                except Exception:
                    pass
            self.tex_bg = self.ctx.texture((img.width, img.height), 4, arr.tobytes())
            self.tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._bg_tex_size = (float(max(1, int(img.width))), float(max(1, int(img.height))))
            if self._last_gl_error.startswith("Background"):
                self._last_gl_error = ""
            self._log(f"Background texture uploaded: {img.width}x{img.height} path={p}")
        except Exception as exc:
            self._set_gl_error(f"Background texture upload failed: {exc} path={p}")

    def load_logo(self, path):
        p = str(path or "").strip()
        if not p or not Path(p).exists():
            self.logo_path = ""
            self._logo_rgba_cache = None
            self._invalidate_logo_visible_radius_cache()
            self._log("Logo cleared")
            if self.ctx:
                if not self._ensure_gl_current("load_logo.clear"):
                    return
                if hasattr(self, "tex_logo"):
                    try:
                        self.tex_logo.release()
                    except Exception:
                        pass
                try:
                    self.tex_logo = self.ctx.texture((1, 1), 4, b"\x00\x00\x00\x00")
                    self.tex_logo.filter = (moderngl.LINEAR, moderngl.LINEAR)
                except Exception as exc:
                    self._set_gl_error(f"Logo clear texture failed: {exc}")
            return
        self.logo_path = p
        self._log(f"Logo selected: {p}")
        if not self.ctx:
            self._log("Logo path stored; waiting for initializeGL to upload texture", level="warn")
            return
        try:
            if not self._ensure_gl_current("load_logo"):
                return
            from PIL import Image

            img = Image.open(p).convert("RGBA")
            arr = np.array(img, dtype=np.uint8)
            arr = np.flipud(arr)
            self._logo_rgba_cache = arr
            self._invalidate_logo_visible_radius_cache()
            if hasattr(self, "tex_logo"):
                try:
                    self.tex_logo.release()
                except Exception:
                    pass
            self.tex_logo = self.ctx.texture((img.width, img.height), 4, arr.tobytes())
            self.tex_logo.filter = (moderngl.LINEAR, moderngl.LINEAR)
            if self._last_gl_error.startswith("Logo"):
                self._last_gl_error = ""
            self._log(f"Logo texture uploaded: {img.width}x{img.height} path={p}")
        except Exception as exc:
            self._set_gl_error(f"Logo texture upload failed: {exc} path={p}")

    def _ensure_text_texture(self, idx: int, overlay: dict, sf: float) -> tuple[any, tuple[int, int]]:
        if not self.ctx:
            return (None, (0, 0))
        kind = str((overlay or {}).get("overlayKind") or "text").strip().lower()
        text = str((overlay or {}).get("text", "") or "").strip()
        if kind not in {"panel", "pill", "stage_art"} and not text:
            return (None, (0, 0))
        while len(self._text_cache_keys) <= idx:
            self._text_cache_keys.append(None)
            self._text_textures.append(None)
            self._text_sizes.append((0, 0))
        # Template units are authored against renderBaseHeight; scale 1:1 with preview height.
        scale = float(max(0.05, min(16.0, float(sf or 1.0))))
        if kind in {"panel", "pill", "stage_art"}:
            opacity_mul = float((overlay or {}).get("opacity", 1.0) if "opacity" in (overlay or {}) else 1.0)
            key = (
                f"shape:{kind}|{float((overlay or {}).get('panelWidth') or 0):.1f}"
                f"|{float((overlay or {}).get('panelHeight') or 0):.1f}"
                f"|{(overlay or {}).get('color')}|{opacity_mul:.3f}|{(overlay or {}).get('strokeColor')}"
                f"|{float((overlay or {}).get('strokeWidth') or 0):.2f}"
                f"|{float((overlay or {}).get('panelRadius') or 0):.2f}"
                f"|{float((overlay or {}).get('panelFrost') or 0):.2f}"
                f"|{float((overlay or {}).get('panelSpecular') or 0):.2f}|{text}"
                f"|{float((overlay or {}).get('sizePx') or 0):.2f}|{(overlay or {}).get('fontFamily')}"
                f"|{(overlay or {}).get('logoPath')}|sf:{scale:.4f}"
            )
        else:
            size_px = float((overlay or {}).get("sizePx", 46.0) if "sizePx" in (overlay or {}) else 46.0)
            size_px = float(max(5.0, min(200.0, size_px)))
            col = str((overlay or {}).get("color", "#ffffff") or "#ffffff").strip()
            scol = str((overlay or {}).get("strokeColor", "#000000") or "#000000").strip()
            sw = float((overlay or {}).get("strokeWidth", 2.0) if "strokeWidth" in (overlay or {}) else 2.0)
            sh = float((overlay or {}).get("shadow", 0.4) if "shadow" in (overlay or {}) else 0.4)
            font_family = str((overlay or {}).get("fontFamily", "arial") or "arial").strip().lower()
            bold = bool((overlay or {}).get("bold", False))
            italic = bool((overlay or {}).get("italic", False))
            letter_spacing = float((overlay or {}).get("letterSpacing", 0.0) if "letterSpacing" in (overlay or {}) else 0.0)
            line_spacing = float((overlay or {}).get("lineSpacing", 1.15) if "lineSpacing" in (overlay or {}) else 1.15)
            align = str((overlay or {}).get("align", "left") or "left")
            box_width = float((overlay or {}).get("boxWidth", 0.0) if "boxWidth" in (overlay or {}) else 0.0)
            fill_mode = str((overlay or {}).get("fillMode", "solid") or "solid")
            gradient_colors = (overlay or {}).get("gradientColors") if isinstance((overlay or {}).get("gradientColors"), list) else []
            gradient_direction = str((overlay or {}).get("gradientDirection", "vertical") or "vertical")
            glow_amt = float((overlay or {}).get("glow", 0.0) if "glow" in (overlay or {}) else 0.0)
            glow_color = str((overlay or {}).get("glowColor", "#ff4fd8") or "#ff4fd8")
            glow_blur = float((overlay or {}).get("glowBlur", 8.0) if "glowBlur" in (overlay or {}) else 8.0)
            glow_mode = str((overlay or {}).get("glowMode", "solid") or "solid")
            glow_gradient_colors = (
                (overlay or {}).get("glowGradientColors")
                if isinstance((overlay or {}).get("glowGradientColors"), list)
                else []
            )
            glow_gradient_direction = str(
                (overlay or {}).get("glowGradientDirection", "horizontal") or "horizontal"
            )
            shadow_blur = float((overlay or {}).get("shadowBlur", 0.0) if "shadowBlur" in (overlay or {}) else 0.0)
            extrude_depth = float((overlay or {}).get("extrudeDepth", 0.0) if "extrudeDepth" in (overlay or {}) else 0.0)
            extrude_color = str((overlay or {}).get("extrudeColor", "#1a1a1a") or "#1a1a1a")
            grad_key = ",".join(str(c) for c in gradient_colors)
            glow_grad_key = ",".join(str(c) for c in glow_gradient_colors)
            # Include scale so maximize / resize rebuilds the raster (same look at any size).
            key = (
                f"{text}|{size_px:.2f}|{col}|{scol}|{sw:.2f}|{sh:.2f}|{font_family}|{int(bold)}|{int(italic)}"
                f"|{letter_spacing:.2f}|{line_spacing:.2f}|{align}|{box_width:.1f}|{fill_mode}|{grad_key}|{gradient_direction}"
                f"|{glow_amt:.2f}|{glow_color}|{glow_blur:.2f}|{glow_mode}|{glow_grad_key}|{glow_gradient_direction}"
                f"|{shadow_blur:.2f}|{extrude_depth:.2f}|{extrude_color}|sf:{scale:.4f}"
            )
        if self._text_cache_keys[idx] == key and self._text_textures[idx] is not None:
            return (self._text_textures[idx], self._text_sizes[idx])
        from visualizer.gpu_render import _render_overlay_rgba

        arr, tw, th = _render_overlay_rgba(overlay, scale)
        self.makeCurrent()
        if self._text_textures[idx] is not None:
            try:
                self._text_textures[idx].release()
            except Exception:
                pass
        tx = self.ctx.texture((tw, th), 4, arr.tobytes())
        tx.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._text_textures[idx] = tx
        self._text_sizes[idx] = (int(tw), int(th))
        self._text_cache_keys[idx] = key
        return (tx, (int(tw), int(th)))

    def initializeGL(self):
        try:
            self._gl_ready = False
            self._last_gl_error = ""
            self._log("initializeGL start")
            if not self._ensure_gl_current("initializeGL"):
                self._gl_ready = False
                self.ctx = None
                self._show_gl_failure_overlay(self._last_gl_error or "OpenGL context missing or invalid")
                return
            moderngl.init_context(loader=_QtGLContextLoader(self.context()))
            self.ctx = moderngl.get_context()
            self._gl_info = format_gl_context_info(self.ctx)
            info_bits = " ".join(f"{k}={v}" for k, v in self._gl_info.items())
            self._log(f"moderngl ctx ready {info_bits}")
            self.prog_scene, self.prog_logo, self.prog_post, self.prog_lines, self.prog_points, self.prog_text = _compile(self.ctx)
            self.vao_quad_scene = _quad_vao(self.ctx, self.prog_scene)
            self.vao_quad_logo = _quad_vao(self.ctx, self.prog_logo)
            self.vao_quad_text = _quad_vao(self.ctx, self.prog_text)
            self.line_vbo = self.ctx.buffer(reserve=4 * 6 * 1024)
            self.vao_lines = self.ctx.vertex_array(self.prog_lines, [(self.line_vbo, '2f 4f', 'in_pos', 'in_col')])
            self.prog_lines['clip_enabled'].value = 0
            self.prog_lines['clip_center_px'].value = (0.0, 0.0)
            self.prog_lines['clip_radius_px'].value = 0.0
            self.pt_vbo = self.ctx.buffer(reserve=4 * 3 * 2048)
            self.vao_pts = self.ctx.vertex_array(self.prog_points, [(self.pt_vbo, '2f 1f', 'in_pos', 'in_size')])
            self.prog_particle_quads = _compile_particle_quads(self.ctx)
            self.particle_quad_vbo = self.ctx.buffer(reserve=4 * 10 * 6 * 2048)
            self.vao_particle_quads = self.ctx.vertex_array(
                self.prog_particle_quads,
                [(self.particle_quad_vbo, "2f 2f 4f 2f", "in_pos", "in_uv", "in_col", "in_meta")],
            )
            self._music_icon_tex_holder: dict = {}
            w, h = (1280, 720)
            self.tex_bg = self.ctx.texture((w, h), 4, b'"""\xff' * (w * h))
            self.tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._bg_tex_size = (float(w), float(h))
            self.tex_logo = self.ctx.texture((192, 192), 4, b'\xff\xaa\x00\xff' * (192 * 192))
            self.tex_logo.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._text_textures = []
            for _i in range(5):
                tx = self.ctx.texture((1, 1), 4, b"\x00\x00\x00\x00")
                tx.filter = (moderngl.LINEAR, moderngl.LINEAR)
                self._text_textures.append(tx)
            if self._bg_video_path:
                self.load_background_video(self._bg_video_path)
            elif self.bg_path:
                self.load_background(self.bg_path)
            if self.logo_path:
                self.load_logo(self.logo_path)
            self.particles = ParticleSystem(ParticleConfig(enabled=True, max_count=400, spawn_rate=40, lifetime_sec=1.6, spawn_radius=0, size=2, opacity=0.35, color=(255, 255, 255), speed=120), width=w, height=h, rng_seed=1)
            self._particles_wh = (w, h)
            self.ctx.enable(moderngl.BLEND)
            self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
            self._blend_normal()
            self._gl_ready = True
            self._hide_gl_failure_overlay()
            if preview_hdr_bloom_enabled():
                self._log("HDR bloom path enabled (CAMXORA_PREVIEW_HDR_BLOOM=1)")
            self._log(f"initializeGL ok (qt_fbo={int(self.defaultFramebufferObject())})")
        except Exception as e:
            self._gl_info = format_gl_context_info(getattr(self, "ctx", None))
            self._set_gl_error(f"initializeGL failed: {e}")
            import traceback
            traceback.print_exc()
            self._gl_ready = False
            self.ctx = None
            self._hdr_bloom = None
            self._show_gl_failure_overlay(str(e))

    def _ensure_hdr_bloom(self) -> PreviewHdrBloomPass | None:
        if not self.ctx or not getattr(self, "_gl_ready", False):
            return None
        if self._hdr_bloom is None:
            try:
                self._hdr_bloom = PreviewHdrBloomPass(self.ctx)
                self._log("HDR bloom pass compiled")
            except Exception as exc:
                self._log(f"HDR bloom init failed: {exc}", level="warn")
                self._hdr_bloom = None
        return self._hdr_bloom

    def _hdr_bloom_params(self) -> tuple[float, float, float]:
        """Return (strength, threshold, exposure) for the preview bloom path."""
        return bloom_params_from_template(self.template if isinstance(self.template, dict) else {})

    def _blend_normal(self) -> None:
        """Standard alpha for RGB; keep framebuffer alpha opaque.

        Soft glow / glass textures write a < 1. With the default
        ``SRC_ALPHA, ONE_MINUS_SRC_ALPHA`` on *all* channels, that punches
        holes in the QOpenGLWidget alpha and Qt composites the app chrome
        through the preview. Lock alpha with ``ZERO, ONE`` so clear(…, 1)
        stays fully opaque.
        """
        if not self.ctx:
            return
        self.ctx.blend_func = (
            moderngl.SRC_ALPHA,
            moderngl.ONE_MINUS_SRC_ALPHA,
            moderngl.ZERO,
            moderngl.ONE,
        )

    def _blend_additive(self) -> None:
        """Additive RGB bloom without lowering framebuffer opacity."""
        if not self.ctx:
            return
        self.ctx.blend_func = (
            moderngl.SRC_ALPHA,
            moderngl.ONE,
            moderngl.ZERO,
            moderngl.ONE,
        )

    def _force_framebuffer_opaque_alpha(self) -> None:
        """REQ-P0.4: keep Qt FBO alpha at 1 so translucent windows stay opaque.

        Soft-glow draws can still leak alpha if a future pass forgets Alpha_Lock.
        Clear alpha only (RGB untouched) without grabFramebuffer.
        Skipped when export overlay short-circuits paintGL before drawing.

        Important: do **not** use ``moderngl.Context.clear`` with a color mask.
        ModernGL's clear path ignores the mask and wipes RGB to the clear color
        (black preview with textures still uploading). Use raw GL colorMask+clear.
        """
        if not self.ctx or not getattr(self, "_gl_ready", False):
            return
        try:
            self._use_qt_framebuffer()
            from OpenGL import GL

            GL.glColorMask(GL.GL_FALSE, GL.GL_FALSE, GL.GL_FALSE, GL.GL_TRUE)
            GL.glClearColor(0.0, 0.0, 0.0, 1.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        except Exception:
            pass
        finally:
            try:
                from OpenGL import GL

                GL.glColorMask(GL.GL_TRUE, GL.GL_TRUE, GL.GL_TRUE, GL.GL_TRUE)
            except Exception:
                try:
                    self.ctx.color_mask = (True, True, True, True)
                except Exception:
                    pass

    def resizeEvent(self, ev):
        self._sync_export_overlay_geometry()
        label = getattr(self, "_gl_failure_label", None)
        if label is not None and label.isVisible():
            label.setGeometry(self.rect())
        super().resizeEvent(ev)

    def paintGL(self):
        paint_started = time.perf_counter()
        try:
            if self._export_overlay_active:
                return
            if not self.ctx or not getattr(self, "_gl_ready", False):
                if self._frame_counter == 0:
                    self._log(
                        "paintGL skipped (gl not ready) "
                        f"ctx={bool(self.ctx)} gl_ready={bool(getattr(self, '_gl_ready', False))} "
                        f"last_error={getattr(self, '_last_gl_error', '') or 'none'}",
                        level="warn",
                    )
                self._frame_counter += 1
                if str(getattr(self, "_last_gl_error", "") or "").strip():
                    self._show_gl_failure_overlay(self._last_gl_error)
                return
            if not self._use_qt_framebuffer():
                # REQ-P1.3: do not draw into an unbound / wrong target.
                self._frame_counter += 1
                return
            self._frame_counter += 1
            # REQ-P4.2: offscreen HDR bloom when flagged; skip during P2 scrub.
            self._hdr_bloom_frame_active = False
            use_hdr = (
                preview_hdr_bloom_enabled()
                and not bool(getattr(self, "_interactive_scrub", False))
            )
            if use_hdr:
                hdr = self._ensure_hdr_bloom()
                if hdr is not None:
                    try:
                        w0, h0, vw0, vh0 = self._frame_metrics()
                        scene_fbo = hdr.begin_scene(vw0, vh0)
                        scene_fbo.use()
                        self._hdr_bloom_frame_active = True
                    except Exception as exc:
                        self._log(f"HDR bloom begin failed: {exc}", level="warn")
                        self._hdr_bloom_frame_active = False
                        if not self._use_qt_framebuffer():
                            return
            if self._frame_counter in (1, 2, 3, 60, 120):
                self._log(
                    f"paintGL frame={self._frame_counter} qt_fbo={int(self.defaultFramebufferObject())} "
                    f"size={self.width()}x{self.height()} bg={bool(str(self.bg_path or '').strip())} "
                    f"logo={bool(str(self.logo_path or '').strip())} "
                    f"hdr_bloom={int(bool(self._hdr_bloom_frame_active))}",
                    mirror_app_log=False,
                )
            # Ensure viewport matches widget dimensions (device pixels on HiDPI).
            w, h, vw, vh = self._frame_metrics()
            self.ctx.viewport = (0, 0, vw, vh)
            self.ctx.clear(0.02, 0.02, 0.02, 1.0)
            self.ctx.enable(moderngl.BLEND)
            self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
            self._blend_normal()
            import pygame
            if getattr(self, 'audio_playing', False):
                if pygame.mixer.music.get_busy():
                    self._sync_current_time_from_clock()
                elif bool(getattr(self, "_loop_playback", False)):
                    # Repeat: restart from the beginning without flipping to Pause.
                    self.current_time = 0.0
                    self._audio_clock_base = 0.0
                    self._audio_clock_started_at = None
                    try:
                        pygame.mixer.music.play(start=0.0)
                        self._mark_playback_started(0.0)
                    except Exception:
                        self.audio_playing = False
                        self._emit_playback_state()
                        self._schedule_clean_preview_snapshot()
                    else:
                        self._emit_playback_state()
                else:
                    # Track finished (or mixer stopped). Snap to end so Play restarts cleanly.
                    duration = float(max(0.0, self._audio_duration_sec))
                    if duration > 0:
                        self.current_time = duration
                        self._audio_clock_base = duration
                    self.audio_playing = False
                    self._audio_clock_started_at = None
                    self._emit_playback_state()
                    self._schedule_clean_preview_snapshot()
            frame_idx = int(self.current_time * 60)
            if self.analyzer:
                fft = self.analyzer.fft_for_frame(frame_idx)
                feats = self.analyzer.features_for_frame(frame_idx)
            else:
                fft = np.zeros(1024, dtype=np.float32)
                feats = {'bass': 0.0, 'beat': 0.0, 'onset': 0.0}
            bass = float(feats.get('bass', 0.0))
            if self._bg_video is not None:
                self._upload_background_video_frame()
            # Keep composition axes time-live (camera/bg/logo/mapping) — not frozen compile snapshot.
            try:
                from visualizer.composition_effects.live_motion import apply_live_composition_motion

                apply_live_composition_motion(
                    self.template if isinstance(self.template, dict) else {},
                    time_sec=float(self.current_time or 0.0),
                    bass=bass,
                    treble=float(feats.get("treble", feats.get("high", 0.0)) or 0.0),
                    kick=float(feats.get("kick", feats.get("beat", 0.0)) or 0.0),
                    beat=float(feats.get("beat", 0.0) or 0.0),
                    onset=float(feats.get("onset", 0.0) or 0.0),
                    mid=float(feats.get("mid", 0.0) or 0.0) if feats.get("mid") is not None else None,
                )
            except Exception:
                pass
            tpl_bg = self.template.get('backgroundSettings', {}) if isinstance(self.template.get('backgroundSettings'), dict) else {}
            bg_enabled = bool(tpl_bg.get('enabled', True))
            bg_brightness = float(tpl_bg.get('brightness', 1.0))
            bg_contrast = float(max(0.0, min(2.0, float(tpl_bg.get('contrast', 1.0) or 1.0))))
            bg_saturation = float(max(0.0, min(2.0, float(tpl_bg.get('saturation', 1.0) or 1.0))))
            bg_hue = float(max(-180.0, min(180.0, float(tpl_bg.get('hue', 0.0) or 0.0))))
            bg_react = float(tpl_bg.get('reactivity', 0.0))
            bg_smooth = float(tpl_bg.get('smoothing', 0.8))
            bg_motion_mode = str(tpl_bg.get('motionMode', 'none') or 'none')
            if bg_motion_mode not in ('none', 'zoom', 'vibrate', 'both'):
                bg_motion_mode = 'none'
            bg_motion_zoom_strength = float(tpl_bg.get('motionZoomStrength', 1.0) or 1.0)
            bg_motion_zoom_strength = float(max(0.0, min(20.0, bg_motion_zoom_strength)))
            bg_motion_vibrate_strength = float(tpl_bg.get('motionVibrateStrength', 1.0) or 1.0)
            bg_motion_vibrate_strength = float(max(0.0, min(20.0, bg_motion_vibrate_strength)))
            tpl_audio = self.template.get('audioSettings', {}) if isinstance(self.template.get('audioSettings'), dict) else {}
            try:
                aud_sens = float(
                    tpl_audio.get('inputGain', tpl_audio.get('sensitivity', 1.0))
                    if tpl_audio.get('inputGain', tpl_audio.get('sensitivity', None)) is not None
                    else 1.0
                )
            except (TypeError, ValueError):
                aud_sens = 1.0
            if not aud_sens:
                aud_sens = 1.0
            aud_bar_height = float(tpl_audio.get('barHeight', 1.0) or 1.0)
            aud_bar_height = float(max(0.25, min(12.0, aud_bar_height)))
            if tpl_audio.get("motionSmoothing") is not None:
                aud_smooth = float(tpl_audio.get("motionSmoothing", 0.8))
            else:
                aud_smooth = float(tpl_audio.get("smoothing", 0.8))
            aud_smooth = float(max(0.0, min(0.99, aud_smooth)))
            peak_hold_blend = float(max(0.0, min(1.0, float(tpl_audio.get("peakHoldBlend", 0.0) or 0.0))))
            ls_early = self.template.get('logoSettings', {}) if isinstance(self.template.get('logoSettings'), dict) else {}
            logo_smooth = float(ls_early.get('smoothing', 0.75))
            env_out = integrate_kick_bass_envelopes(
                self.kick_bass_state,
                KickBassEnvelopeStepInput(bass=bass),
                KickBassEnvelopeConfig(bg_smoothing=bg_smooth, logo_smoothing=logo_smooth),
                dt=self.dt,
            )
            kick_pow = env_out.kick_pow
            self.bg_audio_env = env_out.bg_audio_env
            base_h = float(self.template.get('renderBaseHeight', 450.0))
            base_h = float(max(1.0, min(4000.0, base_h)))
            sf = float(h) / base_h
            bg_vibrate_out = integrate_bg_vibrate(
                self.bg_shake_state,
                BgVibrateStepInput(frame_index=frame_idx, bg_audio_env=self.bg_audio_env),
                BgVibrateConfig(
                    motion_mode=bg_motion_mode,
                    react_bass=bg_react,
                    smoothing=bg_smooth,
                    vibrate_strength=bg_motion_vibrate_strength,
                    scale_factor=sf,
                ),
                dt=self.dt,
            )
            self.prog_scene['tex_bg'].value = 0
            if hasattr(self, 'tex_bg'):
                self.tex_bg.use(location=0)
            if 'out_size' in self.prog_scene:
                self.prog_scene['out_size'].value = (float(w), float(h))
            bg_fit_mode = str(tpl_bg.get("fitMode", "cover") or "cover")
            if bg_fit_mode not in ("cover", "contain", "original"):
                bg_fit_mode = "cover"
            fit_mode_i = 0 if bg_fit_mode == "cover" else (1 if bg_fit_mode == "contain" else 2)
            if "bg_fit_mode" in self.prog_scene:
                self.prog_scene["bg_fit_mode"].value = int(fit_mode_i)
            if "bg_tex_size" in self.prog_scene:
                self.prog_scene["bg_tex_size"].value = (float(self._bg_tex_size[0]), float(self._bg_tex_size[1]))
            user_off_x = float(tpl_bg.get("userOffsetX", 0.0) or 0.0)
            user_off_y = float(tpl_bg.get("userOffsetY", 0.0) or 0.0)
            user_scale = float(tpl_bg.get("userScale", 1.0) or 1.0)
            user_scale = float(max(0.05, min(20.0, user_scale)))
            off_uv_x = float(-user_off_x / max(1.0, float(w)))
            off_uv_y = float(user_off_y / max(1.0, float(h)))
            if bg_motion_mode in ('vibrate', 'both'):
                self.prog_scene['bg_offset'].value = (
                    float(off_uv_x + bg_vibrate_out.x / max(1.0, float(w))),
                    float(off_uv_y + bg_vibrate_out.y / max(1.0, float(h))),
                )
            else:
                self.prog_scene['bg_offset'].value = (float(off_uv_x), float(off_uv_y))
            if bg_motion_mode in ('zoom', 'both'):
                # Soft-cap the pulse so max Zoom Strength stays punchy but not runaway.
                zoom_delta = float(self.bg_audio_env * bg_react * 0.04 * bg_motion_zoom_strength)
                bg_scale = float(1.0 + min(2.5, max(0.0, zoom_delta)))
            else:
                bg_scale = 1.0
            bg_scale = float(bg_scale) * float(user_scale)
            self.prog_scene['bg_scale'].value = (float(bg_scale), float(bg_scale))
            # Brightness still receives audio-react; contrast/sat/hue are static grade.
            # Lightning flash peaks also drive brightness + vignette open so strikes light the room.
            lightning_enabled = bool(
                isinstance(self.template, dict) and self.template.get("lightningEnabled", False)
            )
            vig_react_peek = 0.0
            try:
                fx_peek = self.template.get("effects") if isinstance(self.template.get("effects"), dict) else {}
                vig_peek = fx_peek.get("vignette") if isinstance(fx_peek.get("vignette"), dict) else {}
                vig_react_peek = float(vig_peek.get("reactivity", 0.0) or 0.0)
            except Exception:
                vig_react_peek = 0.0
            apply_vignette_reactivity = None
            lightning_flash = 0.0
            # Skip peak flash math unless lightning is on and something actually uses it.
            if lightning_enabled and (float(bg_react) > 0.0 or vig_react_peek > 0.0):
                try:
                    from features.video.lib.lightning_render import (
                        apply_vignette_reactivity as _apply_vig,
                        peak_lightning_flash,
                    )

                    apply_vignette_reactivity = _apply_vig
                    lightning_flash = peak_lightning_flash(
                        self.template if isinstance(self.template, dict) else {},
                        time_sec=float(self.current_time),
                        bass=float(bass),
                        kick=float(kick_pow),
                        beat=float(feats.get("beat", 0.0) or 0.0),
                        onset=float(feats.get("onset", 0.0) or 0.0),
                        audio_env=float(max(bass, kick_pow, self.bg_audio_env)),
                    )
                except Exception:
                    apply_vignette_reactivity = None
                    lightning_flash = 0.0
            elif vig_react_peek > 0.0:
                try:
                    from features.video.lib.lightning_render import apply_vignette_reactivity as _apply_vig

                    apply_vignette_reactivity = _apply_vig
                except Exception:
                    apply_vignette_reactivity = None
            flash_env = float(max(self.bg_audio_env, lightning_flash))
            self.prog_scene['bg_brightness'].value = float(
                max(0.0, min(3.0, bg_brightness * (1.0 + flash_env * bg_react + lightning_flash * 0.55)))
            )
            if "bg_contrast" in self.prog_scene:
                self.prog_scene["bg_contrast"].value = float(bg_contrast)
            if "bg_saturation" in self.prog_scene:
                self.prog_scene["bg_saturation"].value = float(bg_saturation)
            if "bg_hue" in self.prog_scene:
                self.prog_scene["bg_hue"].value = float(bg_hue)
            fx = self.template.get("effects") if isinstance(self.template.get("effects"), dict) else {}
            vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
            sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
            if "vignette_enabled" in self.prog_scene:
                self.prog_scene["vignette_enabled"].value = 1 if bool(vig.get("enabled", False)) else 0
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
                self.prog_scene["vignette_strength"].value = float(vig_strength)
                self.prog_scene["vignette_feather"].value = float(max(0.0, min(1.0, float(vig.get("feather", 0.65) or 0.65))))
                self.prog_scene["vignette_opacity"].value = float(vig_opacity)
                vcol = str(vig.get("color", "#000000") or "#000000")
                try:
                    self.prog_scene["vignette_color"].value = (int(vcol[1:3], 16) / 255.0, int(vcol[3:5], 16) / 255.0, int(vcol[5:7], 16) / 255.0) if vcol.startswith("#") and len(vcol) == 7 else (0.0, 0.0, 0.0)
                except Exception:
                    self.prog_scene["vignette_color"].value = (0.0, 0.0, 0.0)
            if "smoke_enabled" in self.prog_scene:
                self.prog_scene["smoke_enabled"].value = 1 if bool(sm.get("enabled", False)) else 0
                self.prog_scene["smoke_strength"].value = float(max(0.0, min(1.0, float(sm.get("strength", 0.35) or 0.35))))
                self.prog_scene["smoke_blur"].value = float(max(0.0, min(1.0, float(sm.get("blur", 0.55) or 0.55))))
                self.prog_scene["smoke_noise"].value = float(max(0.0, min(1.0, float(sm.get("noise", 0.55) or 0.55))))
                self.prog_scene["smoke_speed"].value = float(max(0.0, min(2.0, float(sm.get("speed", 0.35) or 0.35))))
                self.prog_scene["smoke_opacity"].value = float(max(0.0, min(1.0, float(sm.get("opacity", 0.55) or 0.55))))
                scol = str(sm.get("color", "#000000") or "#000000")
                try:
                    self.prog_scene["smoke_color"].value = (int(scol[1:3], 16) / 255.0, int(scol[3:5], 16) / 255.0, int(scol[5:7], 16) / 255.0) if scol.startswith("#") and len(scol) == 7 else (0.0, 0.0, 0.0)
                except Exception:
                    self.prog_scene["smoke_color"].value = (0.0, 0.0, 0.0)
            if "time_sec" in self.prog_scene:
                self.prog_scene["time_sec"].value = float(self.current_time)
            if bg_enabled and bool(str(self.bg_path or "").strip()):
                self.vao_quad_scene.render(mode=moderngl.TRIANGLE_STRIP)
            pos_cfg = self.template.get('position', {}) if isinstance(self.template.get('position'), dict) else {}
            fx_motion = self.template.get("effects") if isinstance(self.template.get("effects"), dict) else {}
            shake_raw = fx_motion.get("camera_shake") if isinstance(fx_motion.get("camera_shake"), dict) else {}
            shake_enabled = bool(shake_raw.get("enabled", False))
            shake_intensity = float(shake_raw.get("intensity", 8.0))
            shake_smoothing = float(shake_raw.get("smoothing", 0.85))
            autos = self.template.get("automations") if isinstance(self.template.get("automations"), list) else []
            auto_state = apply_automations(
                {"camera_shake.intensity": shake_intensity},
                feats,
                autos,
            )
            shake_out = integrate_camera_shake(
                self.shake_state,
                CameraShakeStepInput(
                    frame_index=frame_idx,
                    bass=bass,
                    beat=float(feats.get("beat", 0.0) or 0.0),
                    intensity=float(auto_state.get("camera_shake.intensity", shake_intensity)),
                ),
                CameraShakeConfig(enabled=shake_enabled, smoothing=shake_smoothing),
                dt=self.dt,
            )
            ls = self.template.get('logoSettings', {}) if isinstance(self.template.get('logoSettings'), dict) else {}
            logo_enabled = bool(ls.get('enabled', True))
            logo_size_base = float(ls.get('size', 192.0))
            logo_scale_base = float(ls.get('scale', 1.0))
            logo_react = float(ls.get('reactivity', 0.0))
            self.logo_audio_env = env_out.logo_audio_env
            preview_bindings = (
                self.template.get("previewBindings")
                if isinstance(self.template.get("previewBindings"), dict)
                else {}
            )
            spectrum_attach_to_logo = bool(preview_bindings.get("spectrumAttachToLogo", True))
            if _logo_contain_in_shape_enabled(self.template) or bool(ls.get("containInShape")):
                spectrum_attach_to_logo = True
            spectrum_logo_gap = float(max(0.0, float(preview_bindings.get("spectrumLogoGap", 0.0) or 0.0))) * sf
            # Shape frame radius (no gap) — used to keep image inside the spectrum path.
            shape_radius_px = _composition_spectrum_base_radius_px(
                self.template,
                frame_w=float(w),
                frame_h=float(h),
                sf=float(sf),
                logo_visual_radius=0.0,
                spectrum_logo_gap=0.0,
                attached_to_logo=False,
            )
            if _logo_contain_in_shape_enabled(self.template):
                # logo_size_base is logical px; shape_radius is screen px → convert.
                logo_size_base = _clamp_logo_size_inside_shape(
                    logo_size_base,
                    float(shape_radius_px) / max(float(sf), 1e-6),
                    contain=True,
                )
            logo_visual_radius = logo_size_base * 0.5 * sf * logo_scale_base
            from features.video.lib.logo_spectrum_bindings import resolve_spectrum_logo_centers

            (cx, cy), (logo_cx, logo_cy) = resolve_spectrum_logo_centers(
                _get_anchor_coords,
                w=w,
                h=h,
                sf=sf,
                position=pos_cfg,
                spectrum_attach_to_logo=spectrum_attach_to_logo,
                logo_position=ls.get("position") if isinstance(ls.get("position"), dict) else {},
            )
            cx += shake_out.x
            cy += shake_out.y
            logo_cx += shake_out.x
            logo_cy += shake_out.y
            # Composition cameraSettings — pan/orbit offsets (+ mild zoom via center pull).
            try:
                from visualizer.composition_effects.camera_gpu import camera_view_offset_px

                cam_settings = (
                    self.template.get("cameraSettings")
                    if isinstance(self.template.get("cameraSettings"), dict)
                    else {}
                )
                cam_ox, cam_oy, cam_zoom = camera_view_offset_px(cam_settings, width=w, height=h)
                cx += cam_ox
                cy += cam_oy
                logo_cx += cam_ox
                logo_cy += cam_oy
                if abs(cam_zoom - 1.0) > 1e-3:
                    # Pull centers slightly toward screen mid when zoomed for punch/dolly feel.
                    mid_x, mid_y = float(w) * 0.5, float(h) * 0.5
                    pull = 1.0 - (1.0 / cam_zoom)
                    cx = cx + (mid_x - cx) * pull * 0.35
                    cy = cy + (mid_y - cy) * pull * 0.35
                    logo_cx = logo_cx + (mid_x - logo_cx) * pull * 0.35
                    logo_cy = logo_cy + (mid_y - logo_cy) * pull * 0.35
            except Exception:
                pass
            spectrum_logo_gap = float(max(0.0, float(preview_bindings.get("spectrumLogoGap", 0.0) or 0.0))) * sf
            logo_circle_mask = bool(ls.get("circleMask", False))
            logo_fit_to_shape = bool(ls.get("fitToShape", True))
            from visualizer.logo_mask import resolve_logo_mask_mode, spectrum_shape_from_template

            logo_mask_mode = resolve_logo_mask_mode(
                spectrum_shape_from_template(self.template),
                mask_shape=ls.get("maskShape"),
                fit_to_shape=logo_fit_to_shape,
                circle_mask=logo_circle_mask,
            )
            logo_shape = normalize_logo_shape(circle_mask=logo_mask_mode != 0)
            logo_visible_radius_ratio = (
                self._logo_visible_radius_ratio_cached(circle_mask=logo_mask_mode != 0)
                if spectrum_attach_to_logo
                else 1.0
            )
            attached_to_logo = bool(spectrum_attach_to_logo and logo_enabled and bool(str(self.logo_path or "").strip()))
            attached_base_radius = _composition_spectrum_base_radius_px(
                self.template,
                frame_w=float(w),
                frame_h=float(h),
                sf=float(sf),
                logo_visual_radius=float(logo_visual_radius),
                logo_visible_radius_ratio=float(logo_visible_radius_ratio),
                spectrum_logo_gap=float(spectrum_logo_gap),
                attached_to_logo=bool(attached_to_logo),
            )
            ps_early = self._particle_settings()
            if bool(ps_early.get("enabled", True)):
                self._prepare_particle_audio(
                    bass=bass,
                    kick_pow=kick_pow,
                    ps=ps_early,
                    onset=float(feats.get("onset", 0.0) or 0.0),
                    beat=float(feats.get("beat", 0.0) or 0.0),
                )

            self._finish_lightning_frame(
                w=w,
                h=h,
                sf=sf,
                cx=cx,
                cy=cy,
                time_sec=float(self.current_time),
                audio_env=float(max(bass, kick_pow, getattr(self, "bg_audio_env", 0.0) or 0.0)),
                bass=float(bass),
                kick=float(kick_pow),
                beat=float(feats.get("beat", 0.0) or 0.0),
                onset=float(feats.get("onset", 0.0) or 0.0),
            )

            def hex_to_rgb(hx: str):
                s2 = str(hx or '').strip()
                if s2.startswith('#'):
                    s2 = s2[1:]
                if len(s2) != 6:
                    return (255, 255, 255)
                try:
                    return (int(s2[0:2], 16), int(s2[2:4], 16), int(s2[4:6], 16))
                except Exception:
                    return (255, 255, 255)
            BINS = 64
            fft_size_half = 1024
            n0 = int(min(1024, fft.shape[0]))
            for b_idx in range(BINS):
                log_freq = np.log10(20.0) + b_idx / float(BINS) * (np.log10(12000.0) - np.log10(20.0))
                freq = 10.0 ** log_freq
                linear_index = freq / 22050.0 * fft_size_half
                idx1 = int(np.floor(linear_index))
                idx2 = int(min(np.ceil(linear_index), fft_size_half - 1))
                frac = linear_index - float(idx1)
                val1 = float(fft[idx1]) if idx1 < n0 else 0.0
                val2 = float(fft[idx2]) if idx2 < n0 else 0.0
                raw_val = val1 * (1.0 - frac) + val2 * frac
                freq_boost = 1.0 + (b_idx / float(BINS)) ** 2 * 2.0
                self.fft_log[b_idx] = float(max(0.01, min(1.0, raw_val * freq_boost)))
            self.fft_smoothed = smooth_fft_envelope(self.fft_smoothed, self.fft_log, aud_smooth)
            rg = float(max(0.1, min(8.0, aud_sens)))
            fft_s = np.clip(self.fft_smoothed * rg, 0.0, 2.5).astype(np.float32)
            self._finish_particles_frame(
                w=w,
                h=h,
                sf=sf,
                logo_visual_radius=logo_visual_radius,
                bass=bass,
                kick_pow=kick_pow,
                feats=feats,
                logo_enabled=logo_enabled,
            )
            self._draw_atmosphere_pass(w=w, h=h, time_sec=float(self.current_time))

            spectrum_enabled = bool(self.template.get("spectrumEnabled", True))
            from features.video.lib.spectrum_instance_registry import (
                instance_position_dict,
                iter_render_spectrum_instances,
            )
            spectrum_instances = iter_render_spectrum_instances(self.template) if spectrum_enabled else []
            self._bar_hit_cache = []
            if spectrum_enabled and not spectrum_instances:
                spectrum_layers = self.template.get("layers") if isinstance(self.template.get("layers"), list) else []
                spectrum_layers = [sl for sl in spectrum_layers if isinstance(sl, dict)]
                if not spectrum_layers:
                    spectrum_layers = [dict(normalize_renderer_template(default_renderer_template()).get("layers", [{}])[0])]
                spectrum_instances = [{
                    "style": str(self.template.get("style", "orbit-spikes") or "orbit-spikes"),
                    "anchor": str((self.template.get("position") or {}).get("anchor", "center") if isinstance(self.template.get("position"), dict) else "center"),
                    "x": float((self.template.get("position") or {}).get("x", 0.0) if isinstance(self.template.get("position"), dict) else 0.0),
                    "y": float((self.template.get("position") or {}).get("y", 0.0) if isinstance(self.template.get("position"), dict) else 0.0),
                    "spectrumAttachToLogo": bool(spectrum_attach_to_logo),
                    "spectrumLogoGap": float(max(0.0, float(preview_bindings.get("spectrumLogoGap", 0.0) or 0.0))),
                    "audioSettings": dict(tpl_audio) if isinstance(tpl_audio, dict) else {},
                    "layers": spectrum_layers,
                    "enabled": True,
                }]
            for inst_idx, spectrum_inst in enumerate(spectrum_instances):
                spectrum_layers = [sl for sl in (spectrum_inst.get("layers") or []) if isinstance(sl, dict)]
                if not spectrum_layers:
                    # Heal corrupt empty instance rings from top-level layers.
                    fallback_layers = self.template.get("layers") if isinstance(self.template.get("layers"), list) else []
                    spectrum_layers = [sl for sl in fallback_layers if isinstance(sl, dict)]
                if not spectrum_layers:
                    continue
                inst_attach = bool(spectrum_inst.get("spectrumAttachToLogo", True))
                inst_pos = instance_position_dict(spectrum_inst)
                (inst_cx, inst_cy), _inst_logo = resolve_spectrum_logo_centers(
                    _get_anchor_coords,
                    w=w,
                    h=h,
                    sf=sf,
                    position=inst_pos,
                    spectrum_attach_to_logo=inst_attach,
                    logo_position=ls.get("position") if isinstance(ls.get("position"), dict) else {},
                )
                cx = float(inst_cx) + float(shake_out.x)
                cy = float(inst_cy) + float(shake_out.y)
                attached_to_logo = bool(inst_attach and logo_enabled and bool(str(self.logo_path or "").strip()))
                spectrum_logo_gap = float(max(0.0, float(spectrum_inst.get("spectrumLogoGap", 0.0) or 0.0))) * sf
                logo_visible_radius_ratio = (
                    self._logo_visible_radius_ratio_cached(circle_mask=logo_mask_mode != 0)
                    if attached_to_logo
                    else 1.0
                )
                attached_base_radius = _composition_spectrum_base_radius_px(
                    self.template,
                    frame_w=float(w),
                    frame_h=float(h),
                    sf=float(sf),
                    logo_visual_radius=float(logo_visual_radius),
                    logo_visible_radius_ratio=float(logo_visible_radius_ratio),
                    spectrum_logo_gap=float(spectrum_logo_gap),
                    attached_to_logo=bool(attached_to_logo),
                )
                inst_audio = spectrum_inst.get("audioSettings") if isinstance(spectrum_inst.get("audioSettings"), dict) else {}
                try:
                    raw_gain = inst_audio.get("inputGain", inst_audio.get("sensitivity", aud_sens))
                    inst_aud_sens = float(aud_sens if raw_gain is None else raw_gain)
                except (TypeError, ValueError):
                    inst_aud_sens = aud_sens
                if not inst_aud_sens:
                    inst_aud_sens = aud_sens if aud_sens else 1.0
                try:
                    raw_bar = inst_audio.get("barHeight", aud_bar_height)
                    inst_aud_bar_height = float(aud_bar_height if raw_bar is None else raw_bar)
                except (TypeError, ValueError):
                    inst_aud_bar_height = aud_bar_height
                inst_aud_bar_height = float(max(0.25, min(12.0, inst_aud_bar_height)))
                try:
                    raw_peak = inst_audio.get("peakHoldBlend", peak_hold_blend)
                    inst_peak_hold = float(peak_hold_blend if raw_peak is None else raw_peak)
                except (TypeError, ValueError):
                    inst_peak_hold = peak_hold_blend
                inst_peak_hold = float(max(0.0, min(1.0, inst_peak_hold)))
                rg = float(max(0.1, min(8.0, inst_aud_sens)))
                fft_s = np.clip(self.fft_smoothed * rg, 0.0, 2.5).astype(np.float32)
                inst_style = str(spectrum_inst.get("style") or self.template.get("style", "orbit-spikes") or "orbit-spikes")
                attached_layer_base_offset = _resolve_attached_layer_base_offset(spectrum_layers, sf)
                try:
                    from visualizer.composition_effects.audio_mapping import resolve_bus_levels

                    treble_v = float(feats.get("treble", feats.get("high", 0.0)) or 0.0)
                    kick_v = float(
                        feats.get("kick", feats.get("onset", feats.get("beat", 0.0))) or 0.0
                    )
                    beat_v = float(feats.get("beat", 0.0) or 0.0)
                    onset_v = float(feats.get("onset", 0.0) or 0.0)
                    mid_v = float(feats.get("mid", 0.0) or 0.0) if feats.get("mid") is not None else (bass + treble_v) * 0.5
                    # Prefer distinct kick proxy when analyzer has no dedicated kick.
                    if feats.get("kick") is None:
                        kick_v = max(kick_v, onset_v, float(bass) * beat_v)
                    layer_bus_levels = resolve_bus_levels(
                        bass=bass,
                        treble=treble_v,
                        kick=kick_v,
                        overall=max(bass, treble_v, kick_v, beat_v),
                        mid=mid_v,
                        presence=max(treble_v, mid_v * 0.85),
                        transient_mid=max(onset_v, kick_v * 0.7),
                    )
                except Exception:
                    layer_bus_levels = {}
                for layer_idx, sl in enumerate(spectrum_layers):
                    curved = bool(sl.get('curved', False))
                    mirrored = bool(sl.get('mirrored', False))
                    gravity = normalize_spectrum_gravity(sl.get('gravity', 'top'))
                    style_preset = _resolve_export_spectrum_style(
                        inst_style,
                        sl,
                    )
                    anim_scale = float(sl.get("animScale", 1.0) or 1.0)
                    anim_scale = float(max(0.55, min(1.85, anim_scale)))
                    bar_width_px = float(sl.get('barWidth', 4.0)) * sf * (0.85 + 0.15 * anim_scale)
                    spike_height_px = float(sl.get('thickness', 30.0)) * sf * inst_aud_bar_height * anim_scale
                    radius_offset_px = float(sl.get('radiusOffset', 0.0)) * sf
                    layer_op = float(max(0.0, min(1.0, float(sl.get('opacity', 1.0)))))
                    color_cfg = sl.get('color') if isinstance(sl.get('color'), dict) else {}
                    col_mode = str(color_cfg.get('mode', 'solid')).lower().strip()
                    solid_hex = str(color_cfg.get('solidColor', '#ffffff'))
                    grad_cols = color_cfg.get('gradientColors') if isinstance(color_cfg.get('gradientColors'), list) else ['#ff4fd8', '#22d3ee']
                    grad_dir = str(color_cfg.get("gradientDirection", "left-to-right") or "left-to-right")
                    if not grad_cols:
                        grad_cols = [solid_hex, '#22d3ee']
                    # Prefer vivid gradient stops; if mode is solid, still use solid_hex.
                    blend_mode = str(sl.get('blend_mode', 'normal')).lower().strip()
                    glow_strength = float(max(0.0, min(100.0, float(sl.get('glow', 0.0))))) / 100.0
                    glow_softness = float(max(0.0, min(30.0, float(sl.get('blur', 0.0)))))
                    # Additive materials read brighter; lift glow floor so Neon/Chrome ≠ Matte.
                    if blend_mode == "add":
                        glow_strength = float(min(1.0, glow_strength * 1.25 + 0.04))
                    bar_count = clamp_spectrum_bar_count(sl.get("barCount", 64))
                    solid_band = bool(sl.get("solidBand", False))
                    # Peak Caps must work from the checkbox alone — don't require
                    # Peak Hold Blend > 0 (that made the toggle look broken).
                    peak_caps_wanted = bool(sl.get("peakCapsEnabled", False))
                    effective_peak_hold = float(inst_peak_hold)
                    if peak_caps_wanted and effective_peak_hold <= 0.001:
                        effective_peak_hold = 0.45
                    peak_caps_enabled = peak_caps_wanted
                    peak_cap_gap = float(max(0.0, min(24.0, float(sl.get("peakCapGap", 4.0) or 0.0)))) * sf
                    peak_cap_thickness = float(max(1.0, min(16.0, float(sl.get("peakCapThickness", 3.0) or 1.0)))) * sf
                    peak_cap_decay = float(max(0.7, min(0.995, float(sl.get("peakCapDecay", 0.92) or 0.92))))
                    peak_cap_color = str(sl.get("peakCapColor", "#ffffff") or "#ffffff")
                    render_fft = np.zeros(BINS, dtype=np.float32)
                    if mirrored:
                        half = BINS // 2
                        for i in range(half):
                            smoothed = fft_s[i]
                            if 1 < i < half - 2:
                                smoothed = fft_s[i - 2] * 0.1 + fft_s[i - 1] * 0.2 + fft_s[i] * 0.4 + fft_s[i + 1] * 0.2 + fft_s[i + 2] * 0.1
                            render_fft[half - 1 - i] = smoothed
                            render_fft[half + i] = smoothed
                    else:
                        for i in range(BINS):
                            smoothed = fft_s[i]
                            if 1 < i < BINS - 2:
                                smoothed = fft_s[i - 2] * 0.1 + fft_s[i - 1] * 0.2 + fft_s[i] * 0.4 + fft_s[i + 1] * 0.2 + fft_s[i + 2] * 0.1
                            render_fft[i] = smoothed
                    # Match export attach-to-logo radius (previewBindings + visible logo ratio).
                    radius = _resolve_spectrum_layer_radius(
                        attached_to_logo=attached_to_logo,
                        attached_base_radius=attached_base_radius,
                        attached_layer_base_offset=attached_layer_base_offset,
                        logo_visual_radius=logo_visual_radius,
                        bar_width=bar_width_px,
                        radius_offset=radius_offset_px,
                    )
                    if int(inst_idx) == 0 and int(layer_idx) == 0:
                        self._spectrum_path_radius_px = float(radius)
                        self._spectrum_center_px = (float(cx), float(cy))
                    # Keep ring diameter stable — animation scale drives bar height/width only.
                    # (Multiplying radius by animScale made circles permanently zoom in/out.)
                    render_fft = scroll_spectrum_heights(
                        render_fft, sl.get("frequencyScroll", 0.0)
                    )
                    sampled_fft = resample_fft_bins(render_fft, bar_count)
                    sampled_fft = apply_bar_height_overrides(
                        sampled_fft, sl.get("barHeightOverrides")
                    )
                    # Per-layer audio bus: frequency weights + drive (Bass≠Treble).
                    # Layer override wins; else Audio Mapping → Spectrum reaction.
                    _apply_bus = None
                    layer_bus = None
                    layer_gain = 1.0
                    try:
                        from visualizer.composition_effects.bus_fft import apply_layer_audio_bus as _apply_bus
                        from visualizer.presets.audio_buses import normalize_audio_bus_id

                        layer_bus = normalize_audio_bus_id(sl.get("audioBus"))
                        if layer_bus is None:
                            mapped = (
                                (self.template.get("audioMapping") or {}).get("mapping")
                                if isinstance(self.template.get("audioMapping"), dict)
                                else {}
                            )
                            if isinstance(mapped, dict):
                                layer_bus = normalize_audio_bus_id(mapped.get("spectrum"))
                        layer_gain = float(
                            sl.get("audioGain") if sl.get("audioGain") is not None else 1.0
                        )
                        # Composition-wide gain / bass emphasis.
                        audio_comp = (
                            (self.template.get("composition") or {}).get("audio")
                            if isinstance(self.template.get("composition"), dict)
                            else {}
                        )
                        if isinstance(audio_comp, dict):
                            try:
                                layer_gain *= float(audio_comp.get("gain") or 1.0)
                            except (TypeError, ValueError):
                                pass
                            if layer_bus == "bass":
                                try:
                                    layer_gain *= float(audio_comp.get("bassEmphasis") or 1.0)
                                except (TypeError, ValueError):
                                    pass
                    except Exception:
                        _apply_bus = None
                        layer_bus = None
                        layer_gain = 1.0
                    if _apply_bus is not None:
                        sampled_fft = _apply_bus(
                            sampled_fft,
                            bus_id=layer_bus,
                            bus_levels=layer_bus_levels if isinstance(layer_bus_levels, dict) else {},
                            audio_gain=layer_gain,
                        )
                    # Animation kickImpact punches spectrum bins for bounce/flash/etc.
                    try:
                        kick_impact = float(
                            (inst_audio.get("kickImpact") if inst_audio else None)
                            if (inst_audio or {}).get("kickImpact") is not None
                            else (tpl_audio.get("kickImpact", 0.0) if isinstance(tpl_audio, dict) else 0.0)
                            or 0.0
                        )
                    except (TypeError, ValueError):
                        kick_impact = 0.0
                    if kick_impact > 0.01:
                        punch = 1.0 + kick_impact * (0.35 + 0.9 * float(bass))
                        sampled_fft = np.clip(sampled_fft * punch, 0.0, 3.5).astype(np.float32)
                    n = int(sampled_fft.shape[0])
                    px_arr, py_arr, dx_arr, dy_arr, base_total_length = generate_spectrum_layer_geometry(
                        n,
                        curved=curved,
                        mirrored=mirrored,
                        gravity=gravity,
                        path_mode=sl.get("pathMode", "auto"),
                        radius=radius,
                        half_w=radius,
                        half_h=radius,
                        attached_to_logo=attached_to_logo,
                        logo_shape=logo_shape,
                        frame_w=w,
                        frame_h=h,
                        raise_angle_deg=sl.get("raiseAngleDeg"),
                    )
                    # Spectrum animation / shape rotation (pulse/rotate/twist/…).
                    try:
                        rot_deg = float(sl.get("rotation") or 0.0)
                    except (TypeError, ValueError):
                        rot_deg = 0.0
                    px_arr, py_arr, dx_arr, dy_arr = rotate_spectrum_bases(
                        px_arr,
                        py_arr,
                        dx_arr,
                        dy_arr,
                        rot_deg,
                        raise_angle_deg=sl.get("raiseAngleDeg"),
                    )
                    contour_style = style_preset == 'contour-waves'
                    waveform_style = style_preset in ('aurora-ribbon', 'magma-ridge', 'plasma-bloom', 'soft-waveform', 'mountain', 'liquid', 'continuous-waveform')
                    ring_close_style = waveform_style or contour_style
                    if curved and mirrored and ring_close_style:
                        px_arr = np.concatenate([px_arr, px_arr[:1]])
                        py_arr = np.concatenate([py_arr, py_arr[:1]])
                        dx_arr = np.concatenate([dx_arr, dx_arr[:1]])
                        dy_arr = np.concatenate([dy_arr, dy_arr[:1]])
                    reflection_enabled = bool(sl.get('reflectionEnabled', False))
                    try:
                        reflection_opacity = float(sl.get('reflectionOpacity', 0.32) or 0.32)
                    except (TypeError, ValueError):
                        reflection_opacity = 0.32
                    reflection_opacity = float(max(0.05, min(0.85, reflection_opacity)))
                    draw_variants: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]] = [
                        (px_arr, py_arr, dx_arr, dy_arr, 1.0)
                    ]
                    if reflection_enabled:
                        r_px, r_py, r_dx, r_dy = mirror_spectrum_points_vertical(px_arr, py_arr, dx_arr, dy_arr)
                        draw_variants.append((r_px, r_py, r_dx, r_dy, reflection_opacity))
                    main_px, main_py, main_dx, main_dy = px_arr, py_arr, dx_arr, dy_arr
                    # Hit targets for Shift/Alt bar editing (primary instance only).
                    if int(inst_idx) == 0 and int(main_px.shape[0]) > 0:
                        tip = np.maximum(
                            8.0,
                            np.asarray(sampled_fft[: int(main_px.shape[0])], dtype=np.float32)
                            * float(spike_height_px),
                        )
                        for bi in range(int(main_px.shape[0])):
                            bx = float(cx) + float(main_px[bi])
                            by = float(cy) + float(main_py[bi])
                            tx = bx + float(main_dx[bi]) * float(tip[bi])
                            ty = by + float(main_dy[bi]) * float(tip[bi])
                            self._bar_hit_cache.append(
                                {
                                    "layer": int(layer_idx),
                                    "bar": int(bi),
                                    "bx": bx,
                                    "by": by,
                                    "tx": tx,
                                    "ty": ty,
                                    "dx": float(main_dx[bi]),
                                    "dy": float(main_dy[bi]),
                                    "cx": float(cx),
                                    "cy": float(cy),
                                }
                            )
                    pass_specs: list[dict] = []
                    if glow_strength > 0.0:
                        # Softness comes mostly from Blur; keep Glow crisp when Blur=0
                        # so bars don't look smeared/"square blur" while raising.
                        soft = float(max(0.0, glow_softness))
                        bloom = 0.35 + 0.65 * min(1.0, soft / 4.0)
                        pass_specs.append({
                            'is_glow': True,
                            'alpha': layer_op * (0.10 + glow_strength * 0.16) * bloom,
                            'bar_width': bar_width_px + (soft * 1.4 + glow_strength * 8.0 * bloom) * sf,
                            'spike_height': spike_height_px + (soft * 1.6 + glow_strength * 10.0 * bloom) * sf,
                            'fill_circle': False,
                        })
                        if soft > 0.15 or glow_strength > 0.55:
                            pass_specs.append({
                                'is_glow': True,
                                'alpha': layer_op * (0.06 + glow_strength * 0.10) * bloom,
                                'bar_width': bar_width_px + (soft * 2.4 + glow_strength * 16.0 * bloom) * sf,
                                'spike_height': spike_height_px + (soft * 2.8 + glow_strength * 18.0 * bloom) * sf,
                                'fill_circle': False,
                            })
                    pass_specs.append({'is_glow': False, 'alpha': layer_op, 'bar_width': bar_width_px, 'spike_height': spike_height_px, 'fill_circle': bool(sl.get('fillCircle', False))})
                    for v_px, v_py, v_dx, v_dy, v_alpha_mul in draw_variants:
                      px_arr, py_arr, dx_arr, dy_arr = v_px, v_py, v_dx, v_dy
                      for pass_cfg in pass_specs:
                        # Skip expensive glow passes on the reflection copy.
                        if pass_cfg['is_glow'] and v_alpha_mul < 0.999:
                            continue
                        pass_bar_width_px = float(pass_cfg['bar_width'])
                        pass_spike_height_px = float(pass_cfg['spike_height'])
                        pass_alpha = float(max(0.0, min(1.0, float(pass_cfg['alpha']) * float(v_alpha_mul))))
                        fill_circle_pass = bool(pass_cfg['fill_circle'])
                        if pass_cfg['is_glow']:
                            self._blend_additive()
                        elif blend_mode in ('screen', 'add', 'lighten'):
                            self._blend_additive()
                        else:
                            self._blend_normal()
                        val_arr = (sampled_fft * pass_spike_height_px).astype(np.float32)
                        if curved and mirrored and ring_close_style:
                            val_arr = np.concatenate([val_arr, val_arr[:1]])
                        nn = int(px_arr.shape[0])
                        half_t = float(max(1.0, pass_bar_width_px)) * 0.5

                        def mk_col_array(nn0: int):
                            # Closed rings: color by screen position so first/last
                            # stops melt instead of hard-joining at the seam.
                            closed = bool(curved and mirrored) or str(
                                sl.get("pathMode") or ""
                            ).lower().strip() in (
                                "heart",
                                "infinity",
                                "hexagon",
                                "diamond",
                                "triangle",
                                "circle",
                            )
                            if (
                                closed
                                and col_mode == "gradient"
                                and nn0 > 1
                                and int(px_arr.shape[0]) >= nn0
                            ):
                                tip = np.maximum(1.0, np.asarray(val_arr[:nn0], dtype=np.float32))
                                xs_ndc = (
                                    (float(cx) + px_arr[:nn0] + dx_arr[:nn0] * tip) / float(max(1, w)) * 2.0
                                    - 1.0
                                ).astype(np.float32)
                                ys_ndc = (
                                    (float(cy) + py_arr[:nn0] + dy_arr[:nn0] * tip) / float(max(1, h)) * 2.0
                                    - 1.0
                                ).astype(np.float32)
                                cols0 = build_spectrum_spatial_edge_rgba(
                                    xs_ndc=xs_ndc,
                                    ys_ndc=ys_ndc,
                                    mode=col_mode,
                                    solid_color=solid_hex,
                                    gradient_colors=list(grad_cols)
                                    if isinstance(grad_cols, list)
                                    else None,
                                    alpha=pass_alpha,
                                    gradient_direction=grad_dir,
                                    close_loop=True,
                                )
                            else:
                                cols0 = build_spectrum_vertex_rgba(
                                    mode=col_mode,
                                    solid_color=solid_hex,
                                    gradient_colors=list(grad_cols) if isinstance(grad_cols, list) else None,
                                    count=nn0,
                                    alpha=pass_alpha,
                                )
                            if pass_cfg["is_glow"]:
                                return dampen_spectrum_glow_rgba(cols0, strength=0.38)
                            return cols0
                        ctx_col = mk_col_array(nn)
                        slot_w = float(base_total_length / max(1, n))
                        bw = resolve_bar_pixel_width(pass_bar_width_px, slot_w)
                        # Solid graph: filled base→tip strip instead of discrete bars.
                        if solid_band and not contour_style and not waveform_style:
                            graph_pos = build_solid_graph_strip_vertices(
                                px_arr,
                                py_arr,
                                dx_arr,
                                dy_arr,
                                val_arr,
                                cx=float(cx),
                                cy=float(cy),
                                w=int(w),
                                h=int(h),
                            )
                            if graph_pos.shape[0]:
                                tip_xs = graph_pos[0::2, 0]
                                tip_ys = graph_pos[0::2, 1]
                                graph_cols = build_spectrum_solid_graph_strip_rgba(
                                    tip_xs_ndc=tip_xs,
                                    tip_ys_ndc=tip_ys,
                                    mode=col_mode,
                                    solid_color=solid_hex,
                                    gradient_colors=list(grad_cols) if isinstance(grad_cols, list) else None,
                                    alpha=pass_alpha,
                                    gradient_direction=grad_dir,
                                    close_loop=bool(curved and mirrored),
                                )
                                if pass_cfg["is_glow"]:
                                    graph_cols = dampen_spectrum_glow_rgba(graph_cols, strength=0.38)
                                graph_verts = np.column_stack([graph_pos, graph_cols]).astype(np.float32)
                                self._write_vbo(self.line_vbo, graph_verts)
                                self.vao_lines.render(
                                    mode=moderngl.TRIANGLE_STRIP, vertices=int(graph_pos.shape[0])
                                )
                            continue
                        if contour_style:
                            strips = build_contour_wave_strips(
                                px_arr, py_arr, dx_arr, dy_arr, val_arr, cx, cy, w, h,
                                line_count=5,
                                line_half_px=float(max(0.7, pass_bar_width_px * 0.45)),
                            )
                            for strip_i, strip_pos in enumerate(strips):
                                strip_nn = int(strip_pos.shape[0] // 2)
                                strip_alpha = float(max(0.0, min(1.0, pass_alpha * (0.45 + 0.55 * ((strip_i + 1) / max(1, len(strips)))))))
                                tip_xs = strip_pos[0::2, 0]
                                tip_ys = strip_pos[0::2, 1]
                                strip_cols = build_spectrum_solid_graph_strip_rgba(
                                    tip_xs_ndc=tip_xs,
                                    tip_ys_ndc=tip_ys,
                                    mode=col_mode,
                                    solid_color=solid_hex,
                                    gradient_colors=list(grad_cols) if isinstance(grad_cols, list) else None,
                                    alpha=strip_alpha,
                                    gradient_direction=grad_dir,
                                    close_loop=bool(curved and mirrored),
                                )
                                if pass_cfg["is_glow"]:
                                    strip_cols = dampen_spectrum_glow_rgba(strip_cols, strength=0.38)
                                strip_verts = np.column_stack([strip_pos, strip_cols]).astype(np.float32)
                                self._write_vbo(self.line_vbo, strip_verts)
                                self.vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(strip_pos.shape[0]))
                        elif waveform_style:
                            xs_o = np.zeros(nn, dtype=np.float32)
                            ys_o = np.zeros(nn, dtype=np.float32)
                            xs_i = np.zeros(nn, dtype=np.float32)
                            ys_i = np.zeros(nn, dtype=np.float32)
                            for i in range(nn):
                                h_val = float(max(2.0, val_arr[i]))
                                dx, dy = (float(dx_arr[i]), float(dy_arr[i]))
                                if style_preset in ('magma-ridge', 'mountain'):
                                    peak_h = h_val * 1.18
                                    xs_o[i] = (cx + float(px_arr[i]) + dx * peak_h) / float(w) * 2.0 - 1.0
                                    ys_o[i] = (cy + float(py_arr[i]) + dy * peak_h) / float(h) * 2.0 - 1.0
                                    xs_i[i] = (cx + float(px_arr[i]) + dx * (half_t * 0.2)) / float(w) * 2.0 - 1.0
                                    ys_i[i] = (cy + float(py_arr[i]) + dy * (half_t * 0.2)) / float(h) * 2.0 - 1.0
                                elif style_preset in ('plasma-bloom', 'liquid'):
                                    liquid_h = h_val * 0.92
                                    inner_pull = half_t * 1.35
                                    xs_o[i] = (cx + float(px_arr[i]) + dx * liquid_h) / float(w) * 2.0 - 1.0
                                    ys_o[i] = (cy + float(py_arr[i]) + dy * liquid_h) / float(h) * 2.0 - 1.0
                                    xs_i[i] = (cx + float(px_arr[i]) - dx * inner_pull) / float(w) * 2.0 - 1.0
                                    ys_i[i] = (cy + float(py_arr[i]) - dy * inner_pull) / float(h) * 2.0 - 1.0
                                else:
                                    xs_o[i] = (cx + float(px_arr[i]) + dx * (h_val + half_t)) / float(w) * 2.0 - 1.0
                                    ys_o[i] = (cy + float(py_arr[i]) + dy * (h_val + half_t)) / float(h) * 2.0 - 1.0
                                    xs_i[i] = (cx + float(px_arr[i]) + dx * (h_val - half_t)) / float(w) * 2.0 - 1.0
                                    ys_i[i] = (cy + float(py_arr[i]) + dy * (h_val - half_t)) / float(h) * 2.0 - 1.0
                            if curved and fill_circle_pass:
                                cx_ndc = float(cx) / float(w) * 2.0 - 1.0
                                cy_ndc = float(cy) / float(h) * 2.0 - 1.0
                                pos_fill = np.empty((nn + 1, 2), dtype=np.float32)
                                pos_fill[0, 0] = cx_ndc
                                pos_fill[0, 1] = cy_ndc
                                pos_fill[1:, 0] = xs_o
                                pos_fill[1:, 1] = ys_o
                                cols_fill = build_spectrum_fill_fan_rgba(
                                    xs_ndc=xs_o,
                                    ys_ndc=ys_o,
                                    mode=col_mode,
                                    solid_color=solid_hex,
                                    gradient_colors=list(grad_cols) if isinstance(grad_cols, list) else None,
                                    alpha=pass_alpha,
                                    gradient_direction=grad_dir,
                                    close_loop=bool(curved and mirrored),
                                )
                                if pass_cfg["is_glow"]:
                                    cols_fill = dampen_spectrum_glow_rgba(cols_fill, strength=0.38)
                                verts_fill = np.column_stack([pos_fill, cols_fill]).astype(np.float32)
                                self._write_vbo(self.line_vbo, verts_fill)
                                self.vao_lines.render(mode=moderngl.TRIANGLE_FAN, vertices=int(nn + 1))
                            pos = np.empty((2 * nn, 2), dtype=np.float32)
                            pos[0::2, 0] = xs_o
                            pos[0::2, 1] = ys_o
                            pos[1::2, 0] = xs_i
                            pos[1::2, 1] = ys_i
                            if col_mode == "gradient":
                                colsi = build_spectrum_solid_graph_strip_rgba(
                                    tip_xs_ndc=xs_o,
                                    tip_ys_ndc=ys_o,
                                    mode=col_mode,
                                    solid_color=solid_hex,
                                    gradient_colors=list(grad_cols) if isinstance(grad_cols, list) else None,
                                    alpha=pass_alpha,
                                    gradient_direction=grad_dir,
                                    close_loop=bool(curved and mirrored),
                                )
                                if pass_cfg["is_glow"]:
                                    colsi = dampen_spectrum_glow_rgba(colsi, strength=0.38)
                            else:
                                colsi = np.repeat(ctx_col, 2, axis=0)
                            verts = np.column_stack([pos, colsi]).astype(np.float32)
                            self._write_vbo(self.line_vbo, verts)
                            self.vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(2 * nn))
                        else:
                            # Match export: shared bar builder (same geometry as paintGL).
                            from visualizer._spectrum_fast import build_bar_vertices
                            try:
                                tip_taper = float(sl.get("tipTaper") if sl.get("tipTaper") is not None else 0.0)
                            except (TypeError, ValueError):
                                tip_taper = 0.0
                            tip_taper = float(max(0.0, min(1.0, tip_taper)))
                            if style_preset in ("soft-eq", "rounded-bars") or bool(sl.get("roundCaps")):
                                tip_taper = 0.0
                            bar_out = build_bar_vertices(
                                px_arr, py_arr, dx_arr, dy_arr, val_arr, cx, cy, w, h,
                                bw, style_preset, sf, self.logo_audio_env, self.particle_audio_env,
                                colors=ctx_col[:n],
                                tip_taper=tip_taper,
                            )
                            if isinstance(bar_out, tuple):
                                pos, colsi = bar_out
                            else:
                                pos = bar_out
                                colsi = np.repeat(ctx_col[:BINS], 6, axis=0)
                            if pos.shape[0]:
                                if (
                                    col_mode == "gradient"
                                    and str(grad_dir).lower().strip() == "top-to-bottom"
                                    and colsi.shape[0] == n * 6
                                ):
                                    colsi = build_spectrum_bar_quad_rgba(
                                        mode=col_mode,
                                        solid_color=solid_hex,
                                        gradient_colors=list(grad_cols) if isinstance(grad_cols, list) else None,
                                        count=n,
                                        alpha=pass_alpha,
                                        gradient_direction=grad_dir,
                                    )
                                verts = np.column_stack([pos, colsi]).astype(np.float32)
                                self._write_vbo(self.line_vbo, verts)
                                self.vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(pos.shape[0]))
                            # Fill Circle on bar styles (Orbit Spikes, etc.) — was waveform-only before.
                            if curved and fill_circle_pass and n > 0:
                                tip_h = np.maximum(2.0, val_arr[:n]).astype(np.float32)
                                xs_o = ((cx + px_arr[:n] + dx_arr[:n] * tip_h) / float(w) * 2.0 - 1.0).astype(np.float32)
                                ys_o = ((cy + py_arr[:n] + dy_arr[:n] * tip_h) / float(h) * 2.0 - 1.0).astype(np.float32)
                                close_loop = bool(mirrored)
                                if close_loop:
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
                                cols_fill = build_spectrum_fill_fan_rgba(
                                    xs_ndc=xs_o,
                                    ys_ndc=ys_o,
                                    mode=col_mode,
                                    solid_color=solid_hex,
                                    gradient_colors=list(grad_cols) if isinstance(grad_cols, list) else None,
                                    alpha=pass_alpha,
                                    gradient_direction=grad_dir,
                                    close_loop=close_loop,
                                )
                                if pass_cfg["is_glow"]:
                                    cols_fill = dampen_spectrum_glow_rgba(cols_fill, strength=0.38)
                                verts_fill = np.column_stack([pos_fill, cols_fill]).astype(np.float32)
                                self._write_vbo(self.line_vbo, verts_fill)
                                self.vao_lines.render(mode=moderngl.TRIANGLE_FAN, vertices=int(tip_n + 1))
                    px_arr, py_arr, dx_arr, dy_arr = main_px, main_py, main_dx, main_dy
                    if peak_caps_enabled and n > 0 and not solid_band:
                        # Mirrored curved waveform styles may append a closing point
                        # to px/dx arrays; peak caps must stay on the original bar count.
                        cap_px = px_arr[:n]
                        cap_py = py_arr[:n]
                        cap_dx = dx_arr[:n]
                        cap_dy = dy_arr[:n]
                        peak_key = f"{inst_idx}:{layer_idx}:{'c' if curved else 'l'}:{'m' if mirrored else 's'}:{gravity}:{n}"
                        prev = self._spectrum_peak_cache.get(peak_key)
                        if prev is None or prev.shape[0] != n:
                            prev = np.zeros((n,), dtype=np.float32)
                        peak_vals = np.maximum(sampled_fft, prev * peak_cap_decay).astype(np.float32)
                        self._spectrum_peak_cache[peak_key] = peak_vals
                        cap_vals = (peak_vals * spike_height_px).astype(np.float32)
                        cap_base = cap_vals + peak_cap_gap
                        cap_pos = np.zeros((n * 6, 2), dtype=np.float32)
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
                        cap_cols = build_spectrum_bar_quad_rgba(
                            mode="solid",
                            solid_color=peak_cap_color,
                            gradient_colors=None,
                            count=n,
                            alpha=float(max(0.0, min(1.0, layer_op * max(effective_peak_hold, 0.45)))),
                            gradient_direction="left-to-right",
                        )
                        cap_verts = np.column_stack([cap_pos, cap_cols]).astype(np.float32)
                        self._write_vbo(self.line_vbo, cap_verts)
                        self.vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(cap_pos.shape[0]))
            self._blend_normal()
            if logo_enabled and bool(str(self.logo_path or "").strip()):
                self.prog_logo['tex_logo'].value = 1
                if hasattr(self, 'tex_logo'):
                    self.tex_logo.use(location=1)
                if 'out_size' in self.prog_logo:
                    self.prog_logo['out_size'].value = (float(w), float(h))
                # Stay inside / attach: logo must share the spectrum path center.
                lock_center = bool(spectrum_attach_to_logo) or _logo_contain_in_shape_enabled(
                    self.template
                ) or bool(ls.get("containInShape"))
                if lock_center:
                    cached = getattr(self, "_spectrum_center_px", None)
                    if isinstance(cached, tuple) and len(cached) == 2 and (
                        abs(float(cached[0])) + abs(float(cached[1])) > 1.0
                    ):
                        ax, ay = float(cached[0]), float(cached[1])
                    else:
                        ax, ay = float(cx), float(cy)
                else:
                    ax, ay = float(logo_cx), float(logo_cy)
                self.prog_logo['logo_px'].value = (float(ax) - float(w) * 0.5, float(ay) - float(h) * 0.5)
                s_logo = logo_scale_base * (1.0 + self.logo_audio_env * logo_react)
                s_logo = float(max(0.05, min(4.0, s_logo)))
                size = logo_size_base * sf * s_logo
                frame_radius = float(getattr(self, "_spectrum_path_radius_px", 0.0) or 0.0)
                if frame_radius <= 1.0:
                    frame_radius = float(shape_radius_px)
                if _logo_contain_in_shape_enabled(self.template):
                    size = _clamp_logo_size_inside_shape(
                        size,
                        float(frame_radius),
                        contain=True,
                    )
                self.prog_logo['logo_size_px'].value = (float(size), float(size))
                self.prog_logo['logo_opacity'].value = float(max(0.0, min(1.0, float(ls.get('opacity', 1.0)))))
                from visualizer.logo_mask import (
                    apply_logo_frame_size_uniform,
                    apply_logo_mask_uniform,
                    apply_logo_rotation_uniforms,
                    logo_frame_size_for_mask,
                )

                apply_logo_mask_uniform(self.prog_logo, logo_mask_mode)
                apply_logo_frame_size_uniform(
                    self.prog_logo,
                    logo_frame_size_for_mask(
                        mask_mode=logo_mask_mode,
                        shape_radius_px=float(frame_radius),
                    ),
                )
                if "logo_rot_rad" in self.prog_logo:
                    spin_en = bool(ls.get("spinEnabled", False))
                    spin_dir = str(ls.get("spinDirection", "cw") or "cw").strip().lower()
                    dir_s = 1.0 if spin_dir == "cw" else -1.0
                    speed_deg = float(ls.get("spinSpeed", 0.0) or 0.0)
                    spin_rad = 0.0
                    if spin_en and abs(speed_deg) > 1e-06:
                        spin_rad = float(dir_s) * float(speed_deg) * 0.017453292519943295 * float(self.current_time)
                    try:
                        content_deg = float(ls.get("rotationDeg") or 0.0)
                    except (TypeError, ValueError):
                        content_deg = 0.0
                    try:
                        mask_deg = float(
                            ls.get("maskRotationDeg")
                            if ls.get("maskRotationDeg") is not None
                            else ls.get("shapeRotationDeg")
                            or 0.0
                        )
                    except (TypeError, ValueError):
                        mask_deg = 0.0
                    apply_logo_rotation_uniforms(
                        self.prog_logo,
                        content_deg=content_deg,
                        mask_deg=mask_deg,
                        spin_rad=spin_rad,
                    )
                self.vao_quad_logo.render(mode=moderngl.TRIANGLE_STRIP)
            overlays = self.template.get("textOverlays") if isinstance(self.template.get("textOverlays"), list) else []
            if overlays:
                import math
                self._blend_normal()
                drag_source = self._text_drag_source()
                for idx, o in enumerate(overlays[:64]):
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
                    t_rel = float(self.current_time) - start
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
                    fade_in = float(max(0.001, min(0.5, 0.18)))
                    fade_out = fade_in
                    if anim in ("fade", "slide_up", "slide_down", "slide_left", "slide_right", "pop", "typewriter", "glow", "shake"):
                        a_in = min(1.0, u / fade_in)
                        a_out = min(1.0, (1.0 - u) / fade_out)
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
                        s0 = 0.85 + ease * 0.2
                        scale_t = float(max(0.3, min(2.5, s0)))
                    elif anim == "typewriter":
                        reveal = float(max(0.0, min(1.0, u * 1.2)))
                    elif anim == "glow":
                        opacity *= float(0.78 + 0.22 * math.sin(u * math.tau * 2.0))
                    elif anim == "shake":
                        k = float(max(0.0, min(1.0, u))) * (1.0 - float(max(0.0, min(1.0, u))))
                        dx += float(math.sin((start + float(self.current_time)) * 38.0 + idx * 7.0) * 10.0 * sf * k)
                        dy += float(math.cos((start + float(self.current_time)) * 41.0 + idx * 11.0) * 10.0 * sf * k)
                    tx, (tw, th) = self._ensure_text_texture(idx, o, sf)
                    if tx is None or tw <= 0 or th <= 0:
                        continue
                    anchor_t = str(o.get("anchor", "top-left") or "top-left")
                    ox = float(o.get("x", 24.0) if "x" in o else 24.0) * sf
                    oy = float(o.get("y", 24.0) if "y" in o else 24.0) * sf
                    # GPU real-time drag: move title rows + panel/pill/badge together.
                    src = str(o.get("source") or "")
                    if drag_source == "titleText":
                        from features.video.lib.text_domain_runtime import TITLE_DOMAIN_DRAG_SOURCES

                        if src in TITLE_DOMAIN_DRAG_SOURCES:
                            ox += float(self._text_drag_dx)
                            oy += float(self._text_drag_dy)
                    elif drag_source and src == drag_source:
                        ox += float(self._text_drag_dx)
                        oy += float(self._text_drag_dy)
                    ax, ay = _get_anchor_coords(anchor_t, ox, oy, w, h)
                    draw_w = float(tw) * scale_t
                    draw_h = float(th) * scale_t
                    qx, qy = _text_quad_center_offset(anchor_t, draw_w, draw_h)
                    self.prog_text["tex_text"].value = 2
                    tx.use(location=2)
                    self.prog_text["out_size"].value = (float(w), float(h))
                    self.prog_text["text_px"].value = (
                        float(ax) - float(w) * 0.5 + dx + qx,
                        float(ay) - float(h) * 0.5 + dy + qy,
                    )
                    self.prog_text["text_size_px"].value = (draw_w, draw_h)
                    draw_opacity = float(
                        opacity
                        if kind in {"panel", "pill", "stage_art"}
                        else opacity * float(o.get("opacity", 1.0) or 1.0)
                    )
                    self.prog_text["text_opacity"].value = float(max(0.0, min(1.0, draw_opacity)))
                    self.prog_text["reveal"].value = float(max(0.0, min(1.0, reveal)))
                    self.vao_quad_text.render(mode=moderngl.TRIANGLE_STRIP)
            # REQ-P4.2: bloom + tonemap into Qt FBO (opaque alpha in shader).
            if self._hdr_bloom_frame_active and self._hdr_bloom is not None:
                if not self._use_qt_framebuffer():
                    self._hdr_bloom_frame_active = False
                else:
                    strength, threshold, exposure = self._hdr_bloom_params()
                    screen = getattr(self, "_screen_fbo", None)
                    if screen is None:
                        screen = self.ctx.detect_framebuffer(int(self.defaultFramebufferObject()))
                        self._screen_fbo = screen
                    _, _, vw_r, vh_r = self._frame_metrics()
                    self._hdr_bloom.resolve(
                        screen_fbo=screen,
                        viewport=(0, 0, vw_r, vh_r),
                        bloom_strength=strength,
                        threshold=threshold,
                        exposure=exposure,
                    )
                    self._hdr_bloom_frame_active = False
        except Exception as e:
            self._hdr_bloom_frame_active = False
            self._set_gl_error(f"paintGL failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Never grabFramebuffer here — it stalls GPU every few seconds.
            if (
                not self._export_overlay_active
                and self.ctx is not None
                and getattr(self, "_gl_ready", False)
            ):
                self._force_framebuffer_opaque_alpha()
            elapsed_ms = max(0.0, (time.perf_counter() - paint_started) * 1000.0)
            if elapsed_ms > 0:
                self._perf_frame_ms = elapsed_ms
                self._perf_fps = 1000.0 / elapsed_ms
            # Rate-limited hitch breadcrumb for diagnosing remaining stalls.
            if elapsed_ms >= 40.0:
                now_h = time.perf_counter()
                last_h = float(getattr(self, "_last_hitch_log_at", 0.0) or 0.0)
                if (now_h - last_h) >= 1.0:
                    self._last_hitch_log_at = now_h
                    self._log(
                        f"preview hitch frame={self._frame_counter} "
                        f"{elapsed_ms:.1f}ms playing={bool(getattr(self, 'audio_playing', False))}",
                        level="warn",
                        mirror_app_log=False,
                    )
                self._perf_last_paint_at = time.perf_counter()

    def resizeGL(self, w, h):
        if self.ctx:
            self.ctx.viewport = (0, 0, w, h)


class TimelineConnector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = "#31435d"
        self.setFixedSize(70, 220)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_color(self, color: str) -> None:
        self._color = str(color or "#31435d")
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(self._color))
        pen.setWidth(6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        y = int(10 + 98 // 2)
        p.drawLine(6, y, int(self.width() - 6), y)
        p.end()


class ProgressRingStep(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = ""
        self._details: list[str] = []
        self._duration_text = ""
        self._percent = 0
        self._state = "inactive"
        self._icon = None
        self._base_ring = "#31435d"
        self._active_ring = "#2d71df"
        self._text = "#eef4ff"
        self._text_muted = "#8ea4c7"
        self._icon_color = "#d9e5fb"
        self.setMinimumHeight(220)
        self.setMinimumWidth(180)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_data(self, *, title: str, percent: int, state: str, icon, details: list[str] | None = None, duration_text: str = "", icon_color: str | None = None) -> None:
        self._title = str(title or "")
        self._percent = int(max(0, min(100, int(percent))))
        self._state = str(state or "inactive").strip().lower()
        self._icon = icon
        self._details = [str(x or "").strip() for x in (details or []) if str(x or "").strip()]
        self._duration_text = str(duration_text or "").strip()
        if icon_color is not None:
            self._icon_color = str(icon_color or self._icon_color)

        if self._state == "done":
            self._active_ring = "#45c887"
        elif self._state == "failed":
            self._active_ring = "#d65a5a"
        elif self._state == "cancelled":
            self._active_ring = "#5e7598"
        elif self._state == "running":
            self._active_ring = "#2d71df"
        else:
            self._active_ring = "#2d71df" if self._percent > 0 else "#31435d"
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = int(self.width())
        h = int(self.height())

        circle_d = 98
        ring_w = 9
        top_pad = 10

        cx = w // 2
        cy = top_pad + circle_d // 2

        rect = QRectF(float(cx - circle_d // 2), float(cy - circle_d // 2), float(circle_d), float(circle_d))

        pen_bg = QPen(QColor(self._base_ring))
        pen_bg.setWidth(ring_w)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen_bg)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(rect, 0, 360 * 16)

        if self._percent > 0 and self._state in {"running", "done", "failed", "cancelled"}:
            pen_fg = QPen(QColor(self._active_ring))
            pen_fg.setWidth(ring_w)
            pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen_fg)
            span = int(-360.0 * float(self._percent) / 100.0 * 16.0)
            p.drawArc(rect, 90 * 16, span)
        elif self._percent > 0:
            pen_fg = QPen(QColor(self._active_ring))
            pen_fg.setWidth(ring_w)
            pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen_fg)
            span = int(-360.0 * float(self._percent) / 100.0 * 16.0)
            p.drawArc(rect, 90 * 16, span)

        if self._icon is not None:
            try:
                pm = self._icon.pixmap(QSize(26, 26))
                p.drawPixmap(int(cx - pm.width() // 2), int(cy - 20), pm)
            except Exception:
                pass

        p.setPen(QColor(self._text if self._state != "inactive" else self._text_muted))
        f = QFont("Segoe UI", 10, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(QRectF(float(cx - 40), float(cy + 6), 80.0, 24.0), int(Qt.AlignmentFlag.AlignCenter), f"{self._percent}%")

        y0 = top_pad + circle_d + 12
        p.setPen(QColor(self._text))
        ft = QFont("Segoe UI", 10, QFont.Weight.Bold)
        p.setFont(ft)
        p.drawText(QRectF(0.0, float(y0), float(w), 22.0), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), self._title)

        p.setPen(QColor(self._text_muted))
        fd = QFont("Segoe UI", 9)
        p.setFont(fd)
        yy = y0 + 22
        if self._duration_text:
            p.drawText(QRectF(0.0, float(yy), float(w), 18.0), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), self._duration_text)
            yy += 18
        for line in self._details[:2]:
            p.drawText(QRectF(0.0, float(yy), float(w), 18.0), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), line)
            yy += 18
        p.end()


class WorkflowTimeline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps: list[dict] = []
        self._step_widgets: list[ProgressRingStep] = []
        self._connector_widgets: list[TimelineConnector] = []
        self._keys: list[str] = []
        self._icon_cache: dict[tuple[str, str], object] = {}
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(10, 10, 10, 10)
        self._row.setSpacing(0)
        self.setMinimumHeight(240)

    def set_steps(self, steps: list[dict]) -> None:
        steps2 = [dict(s) for s in (steps or []) if isinstance(s, dict)]
        keys2 = [str(s.get("key", "") or str(s.get("title", "") or "")).strip() for s in steps2]

        if not steps2:
            self._steps = []
            self._keys = []
            self._step_widgets = []
            self._connector_widgets = []
            while self._row.count():
                item = self._row.takeAt(0)
                w = item.widget() if item is not None else None
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
            self.update()
            return

        can_update = bool(self._keys) and len(self._keys) == len(keys2) and all(a == b for a, b in zip(self._keys, keys2))
        if not can_update:
            self._steps = steps2
            self._keys = keys2
            self._step_widgets = []
            self._connector_widgets = []
            while self._row.count():
                item = self._row.takeAt(0)
                w = item.widget() if item is not None else None
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()

            self._row.addStretch(1)
            for idx, _ in enumerate(steps2):
                step = ProgressRingStep()
                self._step_widgets.append(step)
                self._row.addWidget(step, 0, Qt.AlignmentFlag.AlignVCenter)
                if idx < len(steps2) - 1:
                    conn = TimelineConnector()
                    self._connector_widgets.append(conn)
                    self._row.addWidget(conn, 0, Qt.AlignmentFlag.AlignVCenter)
            self._row.addStretch(1)
        else:
            self._steps = steps2

        for idx, s in enumerate(steps2):
            step = self._step_widgets[idx]
            state = str(s.get("state", "inactive") or "inactive").strip().lower()
            lucide = str(s.get("lucide", "")).strip()
            icon_col = "#8ea4c7" if state == "inactive" else "#eef4ff"
            icon = None
            cache_key = (lucide, icon_col)
            if cache_key in self._icon_cache:
                icon = self._icon_cache.get(cache_key)
            else:
                try:
                    host = self.window()
                    if host is not None and hasattr(host, "_render_svg_icon") and hasattr(host, "_lucide_icon_path"):
                        icon = host._render_svg_icon(host._lucide_icon_path(lucide), 22, icon_col)
                except Exception:
                    icon = None
                # Only cache successful icon lookups — None means the window
                # wasn't ready yet and we should retry on the next update.
                if icon is not None:
                    self._icon_cache[cache_key] = icon

            step.set_data(
                title=str(s.get("title", "") or ""),
                percent=int(s.get("percent", 0) or 0),
                state=state,
                icon=icon,
                details=list(s.get("details") or []),
                duration_text=str(s.get("durationText", "") or "").strip(),
                icon_color=icon_col,
            )

            if idx < len(steps2) - 1 and idx < len(self._connector_widgets):
                conn = self._connector_widgets[idx]
                ccol = "#31435d"
                if state in {"running", "done"}:
                    ccol = "#2d71df" if state == "running" else "#45c887"
                if state in {"failed"}:
                    ccol = "#d65a5a"
                if state in {"cancelled"}:
                    ccol = "#5e7598"
                conn.set_color(ccol)
        self.update()
