"""Live GPU preview widget — PySide6 port of python_app SpectrumPreview."""


import time
import threading
from pathlib import Path
from typing import Any
import numpy as np

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Signal, QTimer, QByteArray, Qt, QRectF, QSize, QMetaObject, Slot, Q_ARG
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPixmap

import moderngl
from visualizer.gpu_render import (
    _compile,
    _compile_particle_quads,
    _compute_visible_logo_radius_ratio,
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
from visualizer._spectrum_fast import (
    build_contour_wave_strips,
    build_solid_band_strip_vertices,
    clamp_spectrum_bar_count,
    generate_spectrum_layer_geometry,
    mirror_spectrum_points_vertical,
    normalize_spectrum_gravity,
    resample_fft_bins,
    resolve_bar_pixel_width,
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
from visualizer.template_runtime import default_renderer_template, normalize_renderer_template


LOG_PATH = Path(__file__).parent.parent / "debug.log"

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

    def __init__(self, child: QWidget, ratio_w: int=16, ratio_h: int=9, parent=None):
        super().__init__(parent)
        self._child = child
        self._overlay: QWidget | None = None
        self._ratio = float(ratio_w) / float(ratio_h)
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
        return True

    def heightForWidth(self, w: int) -> int:
        width = max(1, int(w))
        return int(round(width / self._ratio))

    def sizeHint(self):
        from PySide6.QtCore import QSize
        w = 480
        return QSize(w, self.heightForWidth(w))

    def resizeEvent(self, ev):
        self._apply_child_geometry()
        super().resizeEvent(ev)

class VideoSpectrumPreview(QOpenGLWidget):
    position_changed = Signal(int, int)
    lightning_position_changed = Signal(int, int)
    logo_position_changed = Signal(int, int)
    background_transform_changed = Signal(float, float, float)
    playback_state_changed = Signal(object)
    text_domain_position_changed = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = None
        self._gl_ready = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(1000 // 60)
        self.template = normalize_renderer_template(default_renderer_template())
        self.audio_path = None
        self.bg_path = None
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
        self.dt = 1.0 / 60.0
        self._frame_counter = 0
        self._screen_fbo = None
        self._particles_wh = (0, 0)
        self._text_cache_keys: list[str | None] = []
        self._text_textures: list[any] = []
        self._text_sizes: list[tuple[int, int]] = []
        self._dragging = False
        self._drag_last = None
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
        self._export_offscreen_surface = None
        self._export_gl_context = None
        self._blocking_export_gl_result = None
        self._blocking_export_gl_error = None
        self._perf_frame_ms = 0.0
        self._perf_fps = 0.0
        self._log(f"[{time.strftime('%H:%M:%S')}] SpectrumPreview init")

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

    def _log(self, msg):
        try:
            print(msg, flush=True)
        except Exception:
            pass
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception:
            pass

    def _use_qt_framebuffer(self):
        if not self.ctx:
            return
        try:
            self.makeCurrent()
            qt_fbo = int(self.defaultFramebufferObject())
            if not self._screen_fbo or int(getattr(self._screen_fbo, "glo", 0) or 0) != qt_fbo:
                self._screen_fbo = self.ctx.detect_framebuffer(qt_fbo)
            self._screen_fbo.use()
            return
        except Exception:
            pass
        try:
            self.makeCurrent()
            from OpenGL import GL
            GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, int(self.defaultFramebufferObject()))
        except Exception:
            return

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

    def set_template(self, tpl: dict):
        # Don't clobber live GPU drag offset with a full rebuild mid-drag.
        if self._text_drag_domain in {"album", "title"} and (
            abs(self._text_drag_dx) > 1e-06 or abs(self._text_drag_dy) > 1e-06
        ):
            return
        # Skip identical payloads — normalize_renderer_template is expensive and
        # clearing the peak cache caused periodic hitch after every draft push.
        if tpl is self.template:
            return
        try:
            import json as _json

            key = _json.dumps(tpl, sort_keys=True, default=str)
        except Exception:
            key = None
        if key is not None and key == getattr(self, "_template_fingerprint", None):
            return
        self.template = normalize_renderer_template(tpl)
        self._template_fingerprint = key
        self._spectrum_peak_cache.clear()
        self.update()

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
        }

    def preview_lifecycle_snapshot(self) -> dict:
        if not getattr(self, "_gl_ready", False):
            if self.audio_loading or self.analysis_loading:
                return {"status": "initializing", "message": "Preview is loading audio analysis and GPU resources."}
            return {"status": "initializing", "message": "Preview GPU surface is initializing."}
        if str(self.audio_error or "").strip():
            return {"status": "error", "message": str(self.audio_error)}
        if not str(self.bg_path or "").strip() or not str(self.audio_path or "").strip():
            return {
                "status": "fallback-active",
                "message": "Attach a background image and preview MP3 for full stage validation.",
            }
        return {"status": "running", "message": "GPU preview compositor is running."}

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
        if ev.button() == Qt.MouseButton.LeftButton and (
            self._bg_edit_mode
            or self._spectrum_position_edit_mode
            or getattr(self, "_lightning_position_edit_mode", False)
            or getattr(self, "_logo_position_edit_mode", False)
        ):
            self._dragging = True
            self._drag_last = (float(ev.position().x()), float(ev.position().y()))
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.grabMouse()
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._drag_last = None
            self.releaseMouse()
            self.unsetCursor()
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

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
        if bool(getattr(self, "_logo_position_edit_mode", False)):
            preview_bindings = (
                self.template.get("previewBindings")
                if isinstance(self.template.get("previewBindings"), dict)
                else {}
            )
            attached = bool(preview_bindings.get("spectrumAttachToLogo", True))
            if attached:
                pos_cfg = self.template.get("position", {}) if isinstance(self.template.get("position"), dict) else {}
                anchor = str(pos_cfg.get("anchor") or "center")
                nx = float(pos_cfg.get("x", 0.0) or 0.0) + float(dx) / sf
                ny = float(pos_cfg.get("y", 0.0) or 0.0) + float(dy) / sf
                nx, ny = _clamp_xy(anchor, nx, ny)
                self.template["position"] = {**pos_cfg, "x": nx, "y": ny}
                ls = self.template.get("logoSettings") if isinstance(self.template.get("logoSettings"), dict) else {}
                logo_pos = ls.get("position") if isinstance(ls.get("position"), dict) else {}
                self.template["logoSettings"] = {**ls, "position": {**logo_pos, "anchor": "center", "x": nx, "y": ny}}
                self.position_changed.emit(nx, ny)
                self.logo_position_changed.emit(nx, ny)
            else:
                ls = self.template.get("logoSettings") if isinstance(self.template.get("logoSettings"), dict) else {}
                logo_pos = ls.get("position") if isinstance(ls.get("position"), dict) else {}
                anchor = str(logo_pos.get("anchor") or "center")
                nx = float(logo_pos.get("x", 0.0) or 0.0) + float(dx) / sf
                ny = float(logo_pos.get("y", 0.0) or 0.0) + float(dy) / sf
                nx, ny = _clamp_xy(anchor, nx, ny)
                self.template["logoSettings"] = {**ls, "position": {**logo_pos, "anchor": "center", "x": nx, "y": ny}}
                self.logo_position_changed.emit(nx, ny)
            ev.accept()
            return
        # Spectrum drag — prefer selected spectrumInstances entry when present.
        if bool(getattr(self, "_spectrum_position_edit_mode", False)):
            instances = self.template.get("spectrumInstances")
            if isinstance(instances, list) and instances:
                idx = int(max(0, min(getattr(self, "_selected_spectrum_instance_index", 0), len(instances) - 1)))
                inst = instances[idx] if isinstance(instances[idx], dict) else {}
                anchor = str(inst.get("anchor") or "center")
                nx = float(inst.get("x", 0.0) or 0.0) + float(dx) / sf
                ny = float(inst.get("y", 0.0) or 0.0) + float(dy) / sf
                nx, ny = _clamp_xy(anchor, nx, ny)
                instances[idx] = {**inst, "x": float(nx), "y": float(ny)}
                self.template["spectrumInstances"] = instances
                # Mirror primary into legacy position for packs / single-path readers.
                if idx == 0:
                    pos_cfg = self.template.get("position", {}) if isinstance(self.template.get("position"), dict) else {}
                    self.template["position"] = {**pos_cfg, "x": nx, "y": ny}
                self.position_changed.emit(nx, ny)
                ev.accept()
                return
        if not bool(getattr(self, "_spectrum_position_edit_mode", False)):
            super().mouseMoveEvent(ev)
            return
        pos_cfg = self.template.get('position', {}) if isinstance(self.template.get('position'), dict) else {}
        anchor = str(pos_cfg.get("anchor") or "center")
        nx = float(pos_cfg.get('x', 0.0) or 0.0) + float(dx) / sf
        ny = float(pos_cfg.get('y', 0.0) or 0.0) + float(dy) / sf
        nx, ny = _clamp_xy(anchor, nx, ny)
        self.template['position'] = {**pos_cfg, 'x': nx, 'y': ny}
        self.position_changed.emit(nx, ny)
        ev.accept()

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

    def load_background(self, path):
        p = str(path or "").strip()
        if not p or not Path(p).exists():
            self.bg_path = ""
            self._log(f"[{time.strftime('%H:%M:%S')}] Background cleared")
            if self.ctx:
                self.makeCurrent()
                if hasattr(self, "tex_bg"):
                    try:
                        self.tex_bg.release()
                    except Exception:
                        pass
                self.tex_bg = self.ctx.texture((1, 1), 4, b"\x00\x00\x00\x00")
                self.tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
                self._bg_tex_size = (1.0, 1.0)
            return
        self.bg_path = p
        self._log(f"[{time.strftime('%H:%M:%S')}] Background selected: {p}")
        if self.ctx:
            self.makeCurrent()
            from PIL import Image
            img = Image.open(p).convert('RGBA')
            arr = np.array(img, dtype=np.uint8)
            arr = np.flipud(arr)
            if hasattr(self, 'tex_bg'):
                self.tex_bg.release()
            self.tex_bg = self.ctx.texture((img.width, img.height), 4, arr.tobytes())
            self.tex_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self._bg_tex_size = (float(max(1, int(img.width))), float(max(1, int(img.height))))

    def load_logo(self, path):
        p = str(path or "").strip()
        if not p or not Path(p).exists():
            self.logo_path = ""
            self._logo_rgba_cache = None
            self._invalidate_logo_visible_radius_cache()
            self._log(f"[{time.strftime('%H:%M:%S')}] Logo cleared")
            if self.ctx:
                self.makeCurrent()
                if hasattr(self, "tex_logo"):
                    try:
                        self.tex_logo.release()
                    except Exception:
                        pass
                self.tex_logo = self.ctx.texture((1, 1), 4, b"\x00\x00\x00\x00")
                self.tex_logo.filter = (moderngl.LINEAR, moderngl.LINEAR)
            return
        self.logo_path = p
        self._log(f"[{time.strftime('%H:%M:%S')}] Logo selected: {p}")
        if self.ctx:
            self.makeCurrent()
            from PIL import Image
            img = Image.open(p).convert('RGBA')
            arr = np.array(img, dtype=np.uint8)
            arr = np.flipud(arr)
            self._logo_rgba_cache = arr
            self._invalidate_logo_visible_radius_cache()
            if hasattr(self, 'tex_logo'):
                self.tex_logo.release()
            self.tex_logo = self.ctx.texture((img.width, img.height), 4, arr.tobytes())
            self.tex_logo.filter = (moderngl.LINEAR, moderngl.LINEAR)

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
            bg_key = str(getattr(self, "bg_path", "") or "")
            key = (
                f"shape:{kind}|{float((overlay or {}).get('panelWidth') or 0):.1f}"
                f"|{float((overlay or {}).get('panelHeight') or 0):.1f}"
                f"|{(overlay or {}).get('color')}|{opacity_mul:.3f}|{(overlay or {}).get('strokeColor')}"
                f"|{float((overlay or {}).get('strokeWidth') or 0):.2f}"
                f"|{float((overlay or {}).get('panelRadius') or 0):.2f}"
                f"|{float((overlay or {}).get('panelFrost') or 0):.2f}"
                f"|{float((overlay or {}).get('panelSpecular') or 0):.2f}|{text}"
                f"|{(overlay or {}).get('panelFillMode')}|{','.join(str(c) for c in ((overlay or {}).get('panelGradientColors') or []))}"
                f"|{float((overlay or {}).get('panelBorderAlpha') if 'panelBorderAlpha' in (overlay or {}) else 1):.2f}"
                f"|{float((overlay or {}).get('panelOuterGlow') or 0):.2f}|{(overlay or {}).get('panelOuterGlowColor')}"
                f"|{float((overlay or {}).get('sizePx') or 0):.2f}|{(overlay or {}).get('fontFamily')}"
                f"|{(overlay or {}).get('logoPath')}|bg:{bg_key}|sf:{scale:.4f}"
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

        backdrop = None
        if kind == "panel" and str(getattr(self, "bg_path", "") or "").strip():
            try:
                from features.video.lib.playlist_glass_backdrop import (
                    panel_rel_from_overlay,
                    sample_panel_backdrop_rgba,
                )

                pw = int(max(4, round(float((overlay or {}).get("panelWidth") or 120.0) * scale)))
                ph = int(max(4, round(float((overlay or {}).get("panelHeight") or 40.0) * scale)))
                rel_x, rel_y = panel_rel_from_overlay(overlay or {})
                blur = 10.0 + float((overlay or {}).get("panelFrost") or 0.0) * 18.0
                backdrop = sample_panel_backdrop_rgba(
                    str(self.bg_path),
                    panel_w=pw,
                    panel_h=ph,
                    rel_x=rel_x,
                    rel_y=rel_y,
                    blur_radius=blur,
                )
            except Exception:
                backdrop = None
        arr, tw, th = _render_overlay_rgba(overlay, scale, backdrop_rgba=backdrop)
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
            self._log(f"[{time.strftime('%H:%M:%S')}] initializeGL start")
            self.makeCurrent()
            moderngl.init_context(loader=_QtGLContextLoader(self.context()))
            self.ctx = moderngl.get_context()
            self._log(f"[{time.strftime('%H:%M:%S')}] moderngl ctx: {getattr(self.ctx, 'version_code', None)} {getattr(self.ctx, 'info', None)}")
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
            if self.bg_path:
                self.load_background(self.bg_path)
            if self.logo_path:
                self.load_logo(self.logo_path)
            self.particles = ParticleSystem(ParticleConfig(enabled=True, max_count=400, spawn_rate=40, lifetime_sec=1.6, spawn_radius=0, size=2, opacity=0.35, color=(255, 255, 255), speed=120), width=w, height=h, rng_seed=1)
            self._particles_wh = (w, h)
            self.ctx.enable(moderngl.BLEND)
            self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
            self._blend_normal()
            self._gl_ready = True
            self._log(f"[{time.strftime('%H:%M:%S')}] initializeGL ok (qt_fbo={int(self.defaultFramebufferObject())})")
        except Exception as e:
            self._log(f"[{time.strftime('%H:%M:%S')}] Error in initializeGL: {e}")
            import traceback
            traceback.print_exc()
            self._gl_ready = False
            self.ctx = None

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

    def resizeEvent(self, ev):
        self._sync_export_overlay_geometry()
        super().resizeEvent(ev)

    def paintGL(self):
        paint_started = time.perf_counter()
        try:
            if self._export_overlay_active:
                return
            if not self.ctx or not getattr(self, "_gl_ready", False):
                return
            self._use_qt_framebuffer()
            self._frame_counter += 1
            if self._frame_counter in (1, 2, 3, 60, 120):
                self._log(f"[{time.strftime('%H:%M:%S')}] paintGL frame={self._frame_counter} qt_fbo={int(self.defaultFramebufferObject())} size={self.width()}x{self.height()}")
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
            logo_visual_radius = logo_size_base * 0.5 * sf * logo_scale_base
            preview_bindings = (
                self.template.get("previewBindings")
                if isinstance(self.template.get("previewBindings"), dict)
                else {}
            )
            spectrum_attach_to_logo = bool(preview_bindings.get("spectrumAttachToLogo", True))
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
            spectrum_logo_gap = float(max(0.0, float(preview_bindings.get("spectrumLogoGap", 0.0) or 0.0))) * sf
            logo_circle_mask = bool(ls.get("circleMask", True))
            logo_shape = normalize_logo_shape(circle_mask=logo_circle_mask)
            logo_visible_radius_ratio = (
                self._logo_visible_radius_ratio_cached(circle_mask=logo_circle_mask)
                if spectrum_attach_to_logo
                else 1.0
            )
            attached_to_logo = bool(spectrum_attach_to_logo and logo_enabled and bool(str(self.logo_path or "").strip()))
            attached_base_radius = float(
                max(0.0, (logo_visual_radius * logo_visible_radius_ratio) + spectrum_logo_gap)
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
            spectrum_enabled = bool(self.template.get("spectrumEnabled", True))
            from features.video.lib.spectrum_instance_registry import (
                instance_position_dict,
                iter_render_spectrum_instances,
            )
            spectrum_instances = iter_render_spectrum_instances(self.template) if spectrum_enabled else []
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
                    self._logo_visible_radius_ratio_cached(circle_mask=logo_circle_mask)
                    if attached_to_logo
                    else 1.0
                )
                attached_base_radius = float(
                    max(0.0, (logo_visual_radius * logo_visible_radius_ratio) + spectrum_logo_gap)
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
                for layer_idx, sl in enumerate(spectrum_layers):
                    curved = bool(sl.get('curved', False))
                    mirrored = bool(sl.get('mirrored', False))
                    gravity = normalize_spectrum_gravity(sl.get('gravity', 'top'))
                    style_preset = _resolve_export_spectrum_style(
                        inst_style,
                        sl,
                    )
                    bar_width_px = float(sl.get('barWidth', 4.0)) * sf
                    spike_height_px = float(sl.get('thickness', 30.0)) * sf * inst_aud_bar_height
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
                    render_fft = scroll_spectrum_heights(
                        render_fft,
                        sl.get("frequencyScroll", 0.0),
                    )
                    # Match export attach-to-logo radius (previewBindings + visible logo ratio).
                    radius = _resolve_spectrum_layer_radius(
                        attached_to_logo=attached_to_logo,
                        attached_base_radius=attached_base_radius,
                        attached_layer_base_offset=attached_layer_base_offset,
                        logo_visual_radius=logo_visual_radius,
                        bar_width=bar_width_px,
                        radius_offset=radius_offset_px,
                    )
                    sampled_fft = resample_fft_bins(render_fft, bar_count)
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
                        linear_span=float(sl.get("linearSpan", 1.0) or 1.0),
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
                    pass_specs: list[dict] = []
                    if glow_strength > 0.0:
                        pass_specs.append({'is_glow': True, 'alpha': layer_op * (0.14 + glow_strength * 0.22), 'bar_width': bar_width_px + (glow_softness * 1.8 + glow_strength * 18.0) * sf, 'spike_height': spike_height_px + (glow_softness * 2.2 + glow_strength * 22.0) * sf, 'fill_circle': False})
                        pass_specs.append({'is_glow': True, 'alpha': layer_op * (0.08 + glow_strength * 0.15), 'bar_width': bar_width_px + (glow_softness * 3.0 + glow_strength * 32.0) * sf, 'spike_height': spike_height_px + (glow_softness * 3.4 + glow_strength * 34.0) * sf, 'fill_circle': False})
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
                        if contour_style:
                            strips = build_contour_wave_strips(
                                px_arr, py_arr, dx_arr, dy_arr, val_arr, cx, cy, w, h,
                                line_count=5,
                                line_half_px=float(max(0.7, pass_bar_width_px * 0.45)),
                            )
                            for strip_i, strip_pos in enumerate(strips):
                                strip_nn = int(strip_pos.shape[0] // 2)
                                strip_alpha = float(max(0.0, min(1.0, pass_alpha * (0.45 + 0.55 * ((strip_i + 1) / max(1, len(strips)))))))
                                strip_cols = np.repeat(
                                    build_spectrum_vertex_rgba(
                                        mode=col_mode,
                                        solid_color=solid_hex,
                                        gradient_colors=list(grad_cols) if isinstance(grad_cols, list) else None,
                                        count=strip_nn,
                                        alpha=strip_alpha,
                                    ),
                                    2,
                                    axis=0,
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
                                cols_edge = ctx_col[:nn].copy()
                                cols_center = cols_edge[:1].copy()
                                cols_fill = np.concatenate([cols_center, cols_edge], axis=0)
                                verts_fill = np.column_stack([pos_fill, cols_fill]).astype(np.float32)
                                self._write_vbo(self.line_vbo, verts_fill)
                                self.vao_lines.render(mode=moderngl.TRIANGLE_FAN, vertices=int(nn + 1))
                            pos = np.empty((2 * nn, 2), dtype=np.float32)
                            pos[0::2, 0] = xs_o
                            pos[0::2, 1] = ys_o
                            pos[1::2, 0] = xs_i
                            pos[1::2, 1] = ys_i
                            colsi = np.repeat(ctx_col, 2, axis=0)
                            verts = np.column_stack([pos, colsi]).astype(np.float32)
                            self._write_vbo(self.line_vbo, verts)
                            self.vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(2 * nn))
                        else:
                            # Match export: shared bar builder (same geometry as paintGL).
                            from visualizer._spectrum_fast import build_bar_vertices
                            bar_out = build_bar_vertices(
                                px_arr, py_arr, dx_arr, dy_arr, val_arr, cx, cy, w, h,
                                bw, style_preset, sf, self.logo_audio_env, self.particle_audio_env,
                                colors=ctx_col[:n],
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
                                if mirrored:
                                    xs_o = np.concatenate([xs_o, xs_o[:1]])
                                    ys_o = np.concatenate([ys_o, ys_o[:1]])
                                    tip_n = int(xs_o.shape[0])
                                else:
                                    tip_n = int(n)
                                cx_ndc = float(cx) / float(w) * 2.0 - 1.0
                                cy_ndc = float(cy) / float(h) * 2.0 - 1.0
                                pos_fill = np.empty((tip_n + 1, 2), dtype=np.float32)
                                pos_fill[0, 0] = cx_ndc
                                pos_fill[0, 1] = cy_ndc
                                pos_fill[1:, 0] = xs_o
                                pos_fill[1:, 1] = ys_o
                                cols_edge = mk_col_array(tip_n)
                                cols_center = cols_edge[:1].copy()
                                cols_fill = np.concatenate([cols_center, cols_edge], axis=0)
                                verts_fill = np.column_stack([pos_fill, cols_fill]).astype(np.float32)
                                self._write_vbo(self.line_vbo, verts_fill)
                                self.vao_lines.render(mode=moderngl.TRIANGLE_FAN, vertices=int(tip_n + 1))
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
                            band_width_px=float(max(1.0, bar_width_px * 0.45)),
                        )
                        if band_pos.shape[0]:
                            # Mirrored curved waveform styles append a closing point.
                            # Build colors from the actual strip vertex count to keep
                            # color rows aligned with geometry rows.
                            band_bar_count = int(max(1, band_pos.shape[0] // 2))
                            band_cols = np.repeat(
                                build_spectrum_vertex_rgba(
                                    mode=col_mode,
                                    solid_color=solid_hex,
                                    gradient_colors=list(grad_cols) if isinstance(grad_cols, list) else None,
                                    count=band_bar_count,
                                    alpha=float(max(0.0, min(1.0, layer_op * 0.6))),
                                ),
                                2,
                                axis=0,
                            )
                            band_verts = np.column_stack([band_pos, band_cols]).astype(np.float32)
                            self._write_vbo(self.line_vbo, band_verts)
                            self.vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(band_pos.shape[0]))
                    if peak_caps_enabled and n > 0:
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
            self._blend_normal()
            if logo_enabled:
                self.prog_logo['tex_logo'].value = 1
                if hasattr(self, 'tex_logo'):
                    self.tex_logo.use(location=1)
                if 'out_size' in self.prog_logo:
                    self.prog_logo['out_size'].value = (float(w), float(h))
                ax, ay = (logo_cx, logo_cy)
                self.prog_logo['logo_px'].value = (float(ax) - float(w) * 0.5, float(ay) - float(h) * 0.5)
                s_logo = logo_scale_base * (1.0 + self.logo_audio_env * logo_react)
                s_logo = float(max(0.05, min(4.0, s_logo)))
                size = logo_size_base * sf * s_logo
                self.prog_logo['logo_size_px'].value = (float(size), float(size))
                self.prog_logo['logo_opacity'].value = float(max(0.0, min(1.0, float(ls.get('opacity', 1.0)))))
                self.prog_logo['logo_circle_mask'].value = 1 if bool(ls.get('circleMask', True)) else 0
                if "logo_rot_rad" in self.prog_logo:
                    spin_en = bool(ls.get("spinEnabled", False))
                    spin_dir = str(ls.get("spinDirection", "cw") or "cw").strip().lower()
                    dir_s = 1.0 if spin_dir == "cw" else -1.0
                    speed_deg = float(ls.get("spinSpeed", 0.0) or 0.0)
                    angle = 0.0
                    if spin_en and abs(speed_deg) > 1e-06:
                        angle = float(dir_s) * float(speed_deg) * 0.017453292519943295 * float(self.current_time)
                    self.prog_logo["logo_rot_rad"].value = float(angle)
                self.vao_quad_logo.render(mode=moderngl.TRIANGLE_STRIP)
            overlays = self.template.get("textOverlays") if isinstance(self.template.get("textOverlays"), list) else []
            if overlays:
                import math
                self._blend_normal()
                drag_source = self._text_drag_source()
                for idx, o in enumerate(overlays[:256]):
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
        except Exception as e:
            self._log(f"[{time.strftime('%H:%M:%S')}] Error in paintGL: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Never grabFramebuffer here — it stalls GPU every few seconds.
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
                        f"[{time.strftime('%H:%M:%S')}] preview hitch frame={self._frame_counter} "
                        f"{elapsed_ms:.1f}ms playing={bool(getattr(self, 'audio_playing', False))}"
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
