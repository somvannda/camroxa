
import time
import threading
from pathlib import Path
import numpy as np

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import pyqtSignal, QTimer, QByteArray, Qt, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

import moderngl
from ...visualizer.gpu_render import _compile, _quad_vao, ParticleSystem, ParticleConfig
from ...visualizer.audio import AudioAnalyzer
from ...visualizer.contracts import PreviewConfig
from ...models.spectrum_model import default_template, normalize_template

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

def _smooth_env(prev: float, target: float, smoothing: float) -> float:
    s = float(max(0.0, min(0.99, smoothing)))
    t = float(max(0.0, min(1.0, target)))
    return float(float(prev) * s + t * (1.0 - s))

STYLE_PRESET_PATCHES: dict[str, dict] = {'classic-vertical': {'curved': True, 'mirrored': True, 'fillCircle': False, 'barWidth': 4.0, 'thickness': 30.0, 'gravity': 'bottom'}, 'thin-lines': {'curved': True, 'mirrored': True, 'fillCircle': False, 'barWidth': 2.0, 'thickness': 34.0, 'gravity': 'bottom'}, 'dot-matrix': {'curved': True, 'mirrored': True, 'fillCircle': False, 'barWidth': 4.0, 'thickness': 28.0, 'gravity': 'bottom'}, 'symmetrical-bars': {'curved': True, 'mirrored': True, 'fillCircle': False, 'barWidth': 5.0, 'thickness': 38.0, 'gravity': 'bottom'}, 'soft-waveform': {'curved': True, 'mirrored': True, 'fillCircle': False, 'barWidth': 4.0, 'thickness': 24.0, 'gravity': 'bottom'}, 'mountain': {'curved': True, 'mirrored': True, 'fillCircle': True, 'barWidth': 5.0, 'thickness': 56.0, 'gravity': 'bottom'}, 'liquid': {'curved': True, 'mirrored': True, 'fillCircle': True, 'barWidth': 9.0, 'thickness': 38.0, 'gravity': 'bottom'}, 'pixel-bars': {'curved': True, 'mirrored': True, 'fillCircle': False, 'barWidth': 5.0, 'thickness': 36.0, 'gravity': 'bottom'}, 'neon-pulse': {'curved': True, 'mirrored': True, 'fillCircle': False, 'barWidth': 7.0, 'thickness': 42.0, 'gravity': 'bottom'}, 'floating-blocks': {'curved': True, 'mirrored': True, 'fillCircle': False, 'barWidth': 6.0, 'thickness': 34.0, 'gravity': 'bottom'}}

STACKED_LAYER_PRESETS: dict[str, dict] = {'triple-neon-halo': {'style': 'neon-pulse', 'layers': [{'name': 'Inner Core', 'radiusOffset': 0, 'barWidth': 10, 'thickness': 26, 'fillCircle': True, 'opacity': 0.95, 'blend_mode': 'normal', 'glow': 24, 'blur': 6, 'color': {'mode': 'gradient', 'gradientColors': ['#ffffff', '#ffe082'], 'gradientDirection': 'circular'}}, {'name': 'Pulse Ring', 'radiusOffset': 26, 'barWidth': 9, 'thickness': 42, 'fillCircle': False, 'opacity': 0.85, 'blend_mode': 'add', 'glow': 68, 'blur': 14, 'color': {'mode': 'gradient', 'gradientColors': ['#ff00ff', '#00ffff'], 'gradientDirection': 'circular'}}, {'name': 'Outer Aura', 'radiusOffset': 56, 'barWidth': 8, 'thickness': 30, 'fillCircle': False, 'opacity': 0.72, 'blend_mode': 'screen', 'glow': 82, 'blur': 20, 'color': {'mode': 'gradient', 'gradientColors': ['#7c3aed', '#38bdf8'], 'gradientDirection': 'circular'}}]}, 'bass-vortex-stack': {'style': 'liquid', 'layers': [{'name': 'Vortex Fill', 'radiusOffset': 0, 'barWidth': 12, 'thickness': 36, 'fillCircle': True, 'opacity': 0.92, 'blend_mode': 'normal', 'glow': 18, 'blur': 5, 'color': {'mode': 'gradient', 'gradientColors': ['#ffffff', '#f5f3ff'], 'gradientDirection': 'circular'}}, {'name': 'Energy Ring', 'radiusOffset': 22, 'barWidth': 11, 'thickness': 52, 'fillCircle': False, 'opacity': 0.82, 'blend_mode': 'add', 'glow': 72, 'blur': 16, 'color': {'mode': 'gradient', 'gradientColors': ['#8b5cf6', '#ec4899'], 'gradientDirection': 'circular'}}, {'name': 'Outer Shock', 'radiusOffset': 52, 'barWidth': 6, 'thickness': 60, 'fillCircle': False, 'opacity': 0.7, 'blend_mode': 'screen', 'glow': 88, 'blur': 22, 'color': {'mode': 'gradient', 'gradientColors': ['#60a5fa', '#ffffff'], 'gradientDirection': 'radial'}}]}, 'soft-aura-stack': {'style': 'soft-waveform', 'layers': [{'name': 'Base Halo', 'radiusOffset': 0, 'barWidth': 7, 'thickness': 22, 'fillCircle': False, 'opacity': 0.85, 'blend_mode': 'normal', 'glow': 24, 'blur': 8, 'color': {'mode': 'gradient', 'gradientColors': ['#c084fc', '#f0abfc'], 'gradientDirection': 'circular'}}, {'name': 'Bright Ribbon', 'radiusOffset': 20, 'barWidth': 5, 'thickness': 28, 'fillCircle': False, 'opacity': 0.72, 'blend_mode': 'screen', 'glow': 58, 'blur': 14, 'color': {'mode': 'gradient', 'gradientColors': ['#ffffff', '#93c5fd'], 'gradientDirection': 'circular'}}, {'name': 'Outer Mist', 'radiusOffset': 42, 'barWidth': 9, 'thickness': 18, 'fillCircle': False, 'opacity': 0.55, 'blend_mode': 'screen', 'glow': 76, 'blur': 18, 'color': {'mode': 'gradient', 'gradientColors': ['#38bdf8', '#818cf8'], 'gradientDirection': 'radial'}}]}}

def _apply_style_preset_to_template(template: dict, style_key: str, layer_index: int=0) -> dict:
    style = str(style_key or 'classic-vertical').strip().lower() or 'classic-vertical'
    tpl = template if isinstance(template, dict) else default_template()
    layers = tpl.get('layers') if isinstance(tpl.get('layers'), list) else []
    while len(layers) <= int(max(0, layer_index)):
        layers.append(dict(default_template()['layers'][0]))
    idx = int(max(0, min(len(layers) - 1, layer_index)))
    base_layer = dict(layers[idx]) if isinstance(layers[idx], dict) else dict(default_template()['layers'][0])
    patch = STYLE_PRESET_PATCHES.get(style, STYLE_PRESET_PATCHES['classic-vertical'])
    tpl['style'] = style
    layers[idx] = {**base_layer, **patch}
    tpl['layers'] = layers
    return tpl

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
        self._ratio = float(ratio_w) / float(ratio_h)
        self._child.setParent(self)
        from python_app.views.helpers.style_helper import set_panel_role
        set_panel_role(self, "videoPreview")

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
        from PyQt6.QtCore import QSize
        w = 480
        return QSize(w, self.heightForWidth(w))

    def resizeEvent(self, ev):
        self._apply_child_geometry()
        super().resizeEvent(ev)

class SpectrumPreview(QOpenGLWidget):
    position_changed = pyqtSignal(int, int)
    background_transform_changed = pyqtSignal(float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = None
        self._gl_ready = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(1000 // 60)
        self.template = normalize_template(default_template())
        self.audio_path = None
        self.bg_path = None
        self.logo_path = None
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
        self.shake_state_x = 0.0
        self.shake_state_y = 0.0
        self.bg_shake_state_x = 0.0
        self.bg_shake_state_y = 0.0
        self.p_bass_fast = 0.0
        self.p_bass_slow = 0.0
        self.p_kick_env = 0.0
        self.bg_audio_env = 0.0
        self.logo_audio_env = 0.0
        self.particle_audio_env = 0.0
        self.p_trigger_env = 0.0
        self.dt = 1.0 / 60.0
        self._frame_counter = 0
        self._screen_fbo = None
        self._particles_wh = (0, 0)
        self._text_cache_keys: list[str | None] = [None, None, None, None, None]
        self._text_textures: list[any] = [None, None, None, None, None]
        self._text_sizes: list[tuple[int, int]] = [(0, 0), (0, 0), (0, 0), (0, 0), (0, 0)]
        self._dragging = False
        self._drag_last = None
        self._bg_edit_mode = False
        self._bg_tex_size = (1.0, 1.0)
        self._log(f"[{time.strftime('%H:%M:%S')}] SpectrumPreview init")

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
        self.template = normalize_template(tpl)

    def configure(self, config: PreviewConfig) -> None:
        """Apply a PreviewConfig DTO to set up the preview widget.

        This is the DTO-based entry point for configuring the preview.
        It sets the template, background, and logo from the DTO fields.
        """
        self.template = normalize_template(config.template)
        if config.background_path:
            self.load_background(config.background_path)
        if config.logo_path:
            self.load_logo(config.logo_path)

    def set_bg_edit_mode(self, enabled: bool) -> None:
        self._bg_edit_mode = bool(enabled)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_last = (int(ev.position().x()), int(ev.position().y()))
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._drag_last = None
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def mouseMoveEvent(self, ev):
        if not self._dragging or not self._drag_last:
            super().mouseMoveEvent(ev)
            return
        x0, y0 = self._drag_last
        x1 = int(ev.position().x())
        y1 = int(ev.position().y())
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
        pos_cfg = self.template.get('position', {}) if isinstance(self.template.get('position'), dict) else {}
        nx = int(round(float(pos_cfg.get('x', 0.0)) + float(dx) / sf))
        ny = int(round(float(pos_cfg.get('y', 0.0)) + float(dy) / sf))
        nx = int(max(-1000, min(1000, nx)))
        ny = int(max(-1000, min(1000, ny)))
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
            try:
                cache_key = self._audio_duration_cache_key(active_path)
                cached_analyzer = getattr(self, '_audio_analyzer_cache', {}).get(cache_key)
                if cached_analyzer:
                    analyzer = cached_analyzer
                else:
                    from ...visualizer.audio import AudioAnalyzer
                    analyzer = AudioAnalyzer(active_path, fps=60, point_count=1024)
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
                self._audio_duration_sec = 0.0
                self._log(f"[{time.strftime('%H:%M:%S')}] Audio analysis failed #{load_seq}: {active_path} error={e}")
            else:
                if load_seq != self._audio_load_seq:
                    self._log(f"[{time.strftime('%H:%M:%S')}] Audio analysis ignored for stale request #{load_seq}: {active_path}")
                    return
                self.analyzer = analyzer
                self._audio_duration_sec = float(getattr(analyzer.info, 'duration_sec', 0.0) or 0.0)
                if self._audio_duration_sec > 0:
                    self._audio_duration_cache[self._audio_duration_cache_key(active_path)] = self._audio_duration_sec
                self._log(f"[{time.strftime('%H:%M:%S')}] Audio analysis ready #{load_seq}: {active_path} duration={self._audio_duration_sec:.2f}s")
            finally:
                if load_seq == self._audio_load_seq:
                    self.analysis_loading = False
        t = threading.Thread(target=analyze, daemon=True)
        t.start()

    def load_background(self, path):
        self.bg_path = path
        self._log(f"[{time.strftime('%H:%M:%S')}] Background selected: {path}")
        if self.ctx:
            self.makeCurrent()
            from PIL import Image
            img = Image.open(path).convert('RGBA')
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
            if hasattr(self, 'tex_logo'):
                self.tex_logo.release()
            self.tex_logo = self.ctx.texture((img.width, img.height), 4, arr.tobytes())
            self.tex_logo.filter = (moderngl.LINEAR, moderngl.LINEAR)

    def _ensure_text_texture(self, idx: int, overlay: dict, sf: float) -> tuple[any, tuple[int, int]]:
        if not self.ctx:
            return (None, (0, 0))
        text = str((overlay or {}).get("text", "") or "").strip()
        if not text:
            return (None, (0, 0))
        size_px = float((overlay or {}).get("sizePx", 46.0) if "sizePx" in (overlay or {}) else 46.0)
        size_px = float(max(8.0, min(320.0, size_px)))
        col = str((overlay or {}).get("color", "#ffffff") or "#ffffff").strip()
        scol = str((overlay or {}).get("strokeColor", "#000000") or "#000000").strip()
        sw = float((overlay or {}).get("strokeWidth", 2.0) if "strokeWidth" in (overlay or {}) else 2.0)
        sh = float((overlay or {}).get("shadow", 0.4) if "shadow" in (overlay or {}) else 0.4)
        key = f"{text}|{size_px:.2f}|{col}|{scol}|{sw:.2f}|{sh:.2f}"
        if 0 <= idx < len(self._text_cache_keys) and self._text_cache_keys[idx] == key and self._text_textures[idx] is not None:
            return (self._text_textures[idx], self._text_sizes[idx])
        from PIL import Image, ImageDraw, ImageFont
        target_size = int(round(size_px * float(max(0.25, min(4.0, sf)))))
        target_size = int(max(10, min(320, target_size)))
        try:
            font = ImageFont.truetype("arial.ttf", target_size)
        except Exception:
            font = ImageFont.load_default()
        stroke_px = int(round(float(max(0.0, min(12.0, sw))) * float(max(0.25, min(4.0, sf)))))
        shadow_px = int(round(2.0 * float(max(0.0, min(1.0, sh))) * float(max(0.25, min(4.0, sf)))))
        tmp = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        d0 = ImageDraw.Draw(tmp)
        bbox = d0.multiline_textbbox((0, 0), text, font=font, stroke_width=max(0, stroke_px), spacing=int(round(target_size * 0.15)))
        w = int(max(1, bbox[2] - bbox[0]))
        h = int(max(1, bbox[3] - bbox[1]))
        pad = int(max(6, round(target_size * 0.35 + stroke_px * 1.2)))
        img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x0 = pad - int(bbox[0])
        y0 = pad - int(bbox[1])
        if shadow_px > 0:
            d.multiline_text((x0 + shadow_px, y0 + shadow_px), text, font=font, fill=(0, 0, 0, int(255 * float(max(0.0, min(1.0, sh))))), stroke_width=max(0, stroke_px), stroke_fill=(0, 0, 0, int(255 * float(max(0.0, min(1.0, sh))))), spacing=int(round(target_size * 0.15)))
        d.multiline_text((x0, y0), text, font=font, fill=col, stroke_width=max(0, stroke_px), stroke_fill=scol, spacing=int(round(target_size * 0.15)))
        arr = np.array(img.convert("RGBA"), dtype=np.uint8)
        arr = np.flipud(arr)
        self.makeCurrent()
        if 0 <= idx < len(self._text_textures) and self._text_textures[idx] is not None:
            try:
                self._text_textures[idx].release()
            except Exception:
                pass
        tx = self.ctx.texture((img.width, img.height), 4, arr.tobytes())
        tx.filter = (moderngl.LINEAR, moderngl.LINEAR)
        if 0 <= idx < len(self._text_textures):
            self._text_textures[idx] = tx
            self._text_sizes[idx] = (int(img.width), int(img.height))
            self._text_cache_keys[idx] = key
        return (tx, (int(img.width), int(img.height)))

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
            self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
            self._gl_ready = True
            self._log(f"[{time.strftime('%H:%M:%S')}] initializeGL ok (qt_fbo={int(self.defaultFramebufferObject())})")
        except Exception as e:
            self._log(f"[{time.strftime('%H:%M:%S')}] Error in initializeGL: {e}")
            import traceback
            traceback.print_exc()
            self._gl_ready = False
            self.ctx = None

    def paintGL(self):
        try:
            if not self.ctx or not getattr(self, "_gl_ready", False):
                return
            self._use_qt_framebuffer()
            self._frame_counter += 1
            if self._frame_counter in (1, 2, 3, 60, 120):
                self._log(f"[{time.strftime('%H:%M:%S')}] paintGL frame={self._frame_counter} qt_fbo={int(self.defaultFramebufferObject())} size={self.width()}x{self.height()}")
            # Ensure viewport matches widget dimensions exactly with zero margin/offset
            w = self.width()
            h = self.height()
            self.ctx.viewport = (0, 0, w, h)
            self.ctx.clear(0.02, 0.02, 0.02, 1.0)
            self.ctx.enable(moderngl.BLEND)
            self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
            self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
            import pygame
            if getattr(self, 'audio_playing', False):
                if pygame.mixer.music.get_busy():
                    self._sync_current_time_from_clock()
                else:
                    self.audio_playing = False
                    self._mark_playback_paused()
            frame_idx = int(self.current_time * 60)
            if self.analyzer:
                fft = self.analyzer.fft_for_frame(frame_idx)
                feats = self.analyzer.features_for_frame(frame_idx)
            else:
                fft = np.zeros(1024, dtype=np.float32)
                feats = {'bass': 0.0, 'beat': 0.0, 'onset': 0.0}
            bass = float(feats.get('bass', 0.0))
            tpl_bg = self.template.get('backgroundSettings', {}) if isinstance(self.template.get('backgroundSettings'), dict) else {}
            bg_brightness = float(tpl_bg.get('brightness', 1.0))
            bg_react = float(tpl_bg.get('reactivity', 0.0))
            bg_smooth = float(tpl_bg.get('smoothing', 0.8))
            bg_motion_mode = str(tpl_bg.get('motionMode', 'none') or 'none')
            if bg_motion_mode not in ('none', 'zoom', 'vibrate', 'both'):
                bg_motion_mode = 'none'
            bg_motion_zoom_strength = float(tpl_bg.get('motionZoomStrength', 1.0) or 1.0)
            bg_motion_zoom_strength = float(max(0.0, min(2.0, bg_motion_zoom_strength)))
            bg_motion_vibrate_strength = float(tpl_bg.get('motionVibrateStrength', 1.0) or 1.0)
            bg_motion_vibrate_strength = float(max(0.0, min(2.0, bg_motion_vibrate_strength)))
            tpl_audio = self.template.get('audioSettings', {}) if isinstance(self.template.get('audioSettings'), dict) else {}
            aud_sens = float(tpl_audio.get('sensitivity', 1.0))
            aud_smooth = float(tpl_audio.get('smoothing', 0.8))
            aud_smooth = float(max(0.0, min(0.99, aud_smooth)))
            self.p_bass_fast = self.p_bass_fast * (1.0 - (1.0 - float(np.exp(-self.dt / 0.06)))) + bass * (1.0 - float(np.exp(-self.dt / 0.06)))
            self.p_bass_slow = self.p_bass_slow * (1.0 - (1.0 - float(np.exp(-self.dt / 0.35)))) + bass * (1.0 - float(np.exp(-self.dt / 0.35)))
            raw_kick = float(max(0.0, self.p_bass_fast - self.p_bass_slow))
            kick0 = float(max(0.0, min(1.0, raw_kick * 4.0)))
            self.p_kick_env = float(max(kick0, self.p_kick_env * float(np.exp(-self.dt / 0.18))))
            kick_pow = float(max(0.0, min(1.0, self.p_kick_env))) ** 2
            base_h = float(self.template.get('renderBaseHeight', 450.0))
            base_h = float(max(1.0, min(4000.0, base_h)))
            sf = float(h) / base_h
            bg_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.6))))
            self.bg_audio_env = _smooth_env(self.bg_audio_env, bg_audio_raw, bg_smooth)
            if bg_motion_mode in ('vibrate', 'both'):
                bg_shake_target = float(max(0.0, bg_react) * self.bg_audio_env * 18.0 * sf * bg_motion_vibrate_strength)
                jitter_x = (time.time() * 0.81 + frame_idx * 0.013) % 1.0
                jitter_y = (time.time() * 0.83 + frame_idx * 0.017) % 1.0
                self.bg_shake_state_x = self.bg_shake_state_x * bg_smooth + (jitter_x * 2.0 - 1.0) * bg_shake_target * (1.0 - bg_smooth)
                self.bg_shake_state_y = self.bg_shake_state_y * bg_smooth + (jitter_y * 2.0 - 1.0) * bg_shake_target * (1.0 - bg_smooth)
            else:
                self.bg_shake_state_x = 0.0
                self.bg_shake_state_y = 0.0
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
                    float(off_uv_x + self.bg_shake_state_x / max(1.0, float(w))),
                    float(off_uv_y + self.bg_shake_state_y / max(1.0, float(h))),
                )
            else:
                self.prog_scene['bg_offset'].value = (float(off_uv_x), float(off_uv_y))
            if bg_motion_mode in ('zoom', 'both'):
                bg_scale = float(1.0 + self.bg_audio_env * bg_react * 0.015 * bg_motion_zoom_strength)
            else:
                bg_scale = 1.0
            bg_scale = float(bg_scale) * float(user_scale)
            self.prog_scene['bg_scale'].value = (float(bg_scale), float(bg_scale))
            self.prog_scene['bg_brightness'].value = float(max(0.0, min(3.0, bg_brightness * (1.0 + self.bg_audio_env * bg_react))))
            fx = self.template.get("effects") if isinstance(self.template.get("effects"), dict) else {}
            vig = fx.get("vignette") if isinstance(fx.get("vignette"), dict) else {}
            sm = fx.get("smoke") if isinstance(fx.get("smoke"), dict) else {}
            if "vignette_enabled" in self.prog_scene:
                self.prog_scene["vignette_enabled"].value = 1 if bool(vig.get("enabled", False)) else 0
                self.prog_scene["vignette_strength"].value = float(max(0.0, min(1.0, float(vig.get("strength", 0.35) or 0.35))))
                self.prog_scene["vignette_feather"].value = float(max(0.0, min(1.0, float(vig.get("feather", 0.65) or 0.65))))
                self.prog_scene["vignette_opacity"].value = float(max(0.0, min(1.0, float(vig.get("opacity", 0.65) or 0.65))))
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
            self.vao_quad_scene.render(mode=moderngl.TRIANGLE_STRIP)
            pos_cfg = self.template.get('position', {}) if isinstance(self.template.get('position'), dict) else {}
            anchor = str(pos_cfg.get('anchor', 'center'))
            off_x = float(pos_cfg.get('x', 0.0)) * sf
            off_y = float(pos_cfg.get('y', 0.0)) * sf
            cx, cy = _get_anchor_coords(anchor, off_x, off_y, w, h)
            ls = self.template.get('logoSettings', {}) if isinstance(self.template.get('logoSettings'), dict) else {}
            logo_enabled = bool(ls.get('enabled', True))
            logo_size_base = float(ls.get('size', 192.0))
            logo_scale_base = float(ls.get('scale', 1.0))
            logo_react = float(ls.get('reactivity', 0.0))
            logo_smooth = float(ls.get('smoothing', 0.75))
            logo_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.8))))
            self.logo_audio_env = _smooth_env(self.logo_audio_env, logo_audio_raw, logo_smooth)
            logo_visual_radius = logo_size_base * 0.5 * sf * logo_scale_base
            if getattr(self, 'particles', None):
                if tuple(getattr(self, '_particles_wh', (0, 0))) != (int(w), int(h)):
                    self.particles = ParticleSystem(ParticleConfig(enabled=True, max_count=400, spawn_rate=40, lifetime_sec=1.6, spawn_radius=0.0, size=2.0, opacity=0.35, color=(255, 255, 255), speed=120.0), width=int(w), height=int(h), rng_seed=1)
                    self._particles_wh = (int(w), int(h))
                ps = self.template.get('particlesSettings', {}) if isinstance(self.template.get('particlesSettings'), dict) else {}
                ps_enabled = bool(ps.get('enabled', False))
                ps_count = int(ps.get('maxCount', 400))
                ps_spawn = float(ps.get('spawnRate', 40.0))
                ps_life = float(ps.get('lifetimeSec', 1.6))
                ps_speed = float(ps.get('speed', 15.0))
                ps_react = float(ps.get('reactivity', 0.0))
                ps_smooth = float(ps.get('smoothing', 0.65))
                ps_size = float(ps.get('size', 2.0))
                ps_op = float(ps.get('opacity', 0.35))
                ps_col = (255, 255, 255)
                try:
                    col_hex = str(ps.get('color', '#ffffff'))
                    if col_hex.startswith('#') and len(col_hex) == 7:
                        ps_col = (int(col_hex[1:3], 16), int(col_hex[3:5], 16), int(col_hex[5:7], 16))
                except Exception:
                    ps_col = (255, 255, 255)
                prb = float(max(0.1, min(0.5, ps_react)))
                particle_audio_raw = float(max(0.0, min(1.0, max(kick_pow, bass))))
                self.particle_audio_env = _smooth_env(self.particle_audio_env, particle_audio_raw, ps_smooth)
                spawn_mode = str(ps.get('spawnMode', 'always') or 'always')
                spawn_trigger = str(ps.get('spawnTrigger', 'both') or 'both')
                spawn_threshold = float(ps.get('spawnThreshold', 0.15) or 0.15)
                spawn_threshold = float(max(0.0, min(1.0, spawn_threshold)))
                if spawn_trigger == 'kick':
                    trig_raw = kick_pow
                elif spawn_trigger == 'bass':
                    trig_raw = bass
                else:
                    trig_raw = float(max(kick_pow, bass))
                trig_raw = float(max(0.0, min(1.0, trig_raw)))
                self.p_trigger_env = _smooth_env(self.p_trigger_env, trig_raw, ps_smooth)

                if spawn_mode == 'reactiveOnly' and self.p_trigger_env < spawn_threshold:
                    spawn_rate = 0.0
                else:
                    spawn_rate = ps_spawn * float(0.2 + self.particle_audio_env * (1.1 + prb * 2.8))
                spawn_rate = float(max(0.0, min(20000.0, spawn_rate)))
                spawn_radius = float(max(0.0, logo_visual_radius + max(2.0 * sf, ps_size * sf)))
                speed_boost = float(18.0 + self.particle_audio_env * (50.0 + prb * 130.0))
                speed2 = ps_speed * speed_boost * sf
                speed2 = float(max(0.0, min(2500.0, speed2)))
                self.particles.update_cfg(
                    ParticleConfig(
                        enabled=ps_enabled,
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
                    )
                )
                self.particles.update(self.dt, feats)
                if ps_enabled:
                    pos = self.particles._pos if hasattr(self.particles, '_pos') else np.zeros((0, 2), dtype=np.float32)
                    if pos.shape[0]:
                        p = pos.astype(np.float32)
                        xs2 = p[:, 0] / float(w) * 2.0 - 1.0
                        ys2 = p[:, 1] / float(h) * 2.0 - 1.0
                        sz = self.particles._size.astype(np.float32) if hasattr(self.particles, '_size') else np.ones((p.shape[0],), dtype=np.float32)
                        pts = np.column_stack([xs2, ys2, sz]).astype(np.float32)
                        if pts.nbytes > self.pt_vbo.size:
                            self.pt_vbo.orphan(size=pts.nbytes)
                        self.pt_vbo.write(pts.tobytes())
                        alpha = float(max(0.0, min(1.0, ps_op)))
                        c = ps_col
                        try:
                            react_strength = float(ps.get('reactStrength', 0.65) or 0.65)
                            react_strength = float(max(0.0, min(1.0, react_strength)))
                            rc_hex = ps.get('reactColor', ps.get('color', '#ffffff'))
                            rc = (255, 255, 255)
                            rc_s = str(rc_hex or '').strip()
                            if rc_s.startswith('#') and len(rc_s) == 7:
                                rc = (int(rc_s[1:3], 16), int(rc_s[3:5], 16), int(rc_s[5:7], 16))
                            mix = float(max(0.0, min(1.0, self.p_trigger_env))) * react_strength
                            cr = float(c[0]) * (1.0 - mix) + float(rc[0]) * mix
                            cg = float(c[1]) * (1.0 - mix) + float(rc[1]) * mix
                            cb = float(c[2]) * (1.0 - mix) + float(rc[2]) * mix
                            colp = (cr / 255.0, cg / 255.0, cb / 255.0, alpha)
                        except Exception:
                            colp = (float(c[0]) / 255.0, float(c[1]) / 255.0, float(c[2]) / 255.0, alpha)
                        variant = str(ps.get('variant', 'classic') or 'classic')
                        style = str(ps.get('style', 'dot') or 'dot')
                        if variant == 'bokeh':
                            style = 'bokeh'
                        elif variant == 'soap':
                            style = 'ring'
                        elif variant == 'dust':
                            style = 'glow'
                        self.prog_points['pt_size'].value = float(max(1.0, ps_size * (2.0 if style == 'bokeh' else 1.5) * sf))
                        self.prog_points['pt_col'].value = colp
                        if style == 'glow':
                            self.prog_points['pt_style'].value = 1
                        elif style == 'ring':
                            self.prog_points['pt_style'].value = 2
                        elif style == 'spark':
                            self.prog_points['pt_style'].value = 3
                        elif style == 'bokeh':
                            self.prog_points['pt_style'].value = 4
                        else:
                            self.prog_points['pt_style'].value = 0
                        self.vao_pts.render(mode=moderngl.POINTS, vertices=int(pts.shape[0]))

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
            self.fft_smoothed = self.fft_smoothed * aud_smooth + self.fft_log * (1.0 - aud_smooth)
            rg = float(max(0.1, min(8.0, aud_sens)))
            fft_s = np.clip(self.fft_smoothed * rg, 0.0, 2.5).astype(np.float32)
            spectrum_enabled = bool(self.template.get("spectrumEnabled", True))
            style_preset = str(self.template.get('style', 'classic-vertical')).lower().strip()
            spectrum_layers = self.template.get('layers') if isinstance(self.template.get('layers'), list) else []
            spectrum_layers = [sl for sl in spectrum_layers if isinstance(sl, dict)]
            if spectrum_enabled and not spectrum_layers:
                spectrum_layers = [dict(normalize_template(default_template()).get('layers', [{}])[0])]
            if not spectrum_enabled:
                spectrum_layers = []
            for sl in spectrum_layers:
                curved = bool(sl.get('curved', True))
                mirrored = bool(sl.get('mirrored', True))
                gravity = str(sl.get('gravity', 'bottom')).lower().strip()
                bar_width_px = float(sl.get('barWidth', 4.0)) * sf
                spike_height_px = float(sl.get('thickness', 30.0)) * sf
                radius_offset_px = float(sl.get('radiusOffset', 0.0)) * sf
                layer_op = float(max(0.0, min(1.0, float(sl.get('opacity', 1.0)))))
                color_cfg = sl.get('color') if isinstance(sl.get('color'), dict) else {}
                col_mode = str(color_cfg.get('mode', 'solid')).lower().strip()
                solid_hex = str(color_cfg.get('solidColor', '#ffffff'))
                grad_cols = color_cfg.get('gradientColors') if isinstance(color_cfg.get('gradientColors'), list) else ['#ff00ff', '#00ffff']
                blend_mode = str(sl.get('blend_mode', 'normal')).lower().strip()
                glow_strength = float(max(0.0, min(100.0, float(sl.get('glow', 0.0))))) / 100.0
                glow_softness = float(max(0.0, min(30.0, float(sl.get('blur', 0.0)))))
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
                radius = logo_visual_radius + radius_offset_px + bar_width_px * 0.5
                n = BINS
                px_arr = np.zeros(n, dtype=np.float32)
                py_arr = np.zeros(n, dtype=np.float32)
                dx_arr = np.zeros(n, dtype=np.float32)
                dy_arr = np.zeros(n, dtype=np.float32)
                if curved:
                    total_angle = np.pi * 2.0 if mirrored else np.pi
                    start_angle = np.pi / 2.0
                    if gravity == 'top':
                        start_angle = -np.pi / 2.0
                    elif gravity == 'left':
                        start_angle = np.pi
                    elif gravity == 'right':
                        start_angle = 0.0
                    for i in range(n):
                        t0 = float(i) / float(n - 1) if n > 1 else 0.0
                        ang = start_angle - total_angle / 2.0 + t0 * total_angle
                        px_arr[i] = np.cos(ang) * radius
                        py_arr[i] = np.sin(ang) * radius
                        dx_arr[i] = np.cos(ang)
                        dy_arr[i] = np.sin(ang)
                else:
                    total_length = float(h * 0.8) if gravity in ('left', 'right') else float(w * 0.8)
                    start_x = -total_length / 2.0
                    for i in range(n):
                        t0 = float(i) / float(n - 1) if n > 1 else 0.0
                        off = start_x + t0 * total_length
                        if gravity == 'bottom':
                            px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = (off, 0.0, 0.0, -1.0)
                        elif gravity == 'top':
                            px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = (off, 0.0, 0.0, 1.0)
                        elif gravity == 'left':
                            px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = (0.0, off, 1.0, 0.0)
                        else:
                            px_arr[i], py_arr[i], dx_arr[i], dy_arr[i] = (0.0, off, -1.0, 0.0)
                waveform_style = style_preset in ('soft-waveform', 'mountain', 'liquid', 'continuous-waveform')
                if curved and mirrored and waveform_style:
                    px_arr = np.concatenate([px_arr, px_arr[:1]])
                    py_arr = np.concatenate([py_arr, py_arr[:1]])
                    dx_arr = np.concatenate([dx_arr, dx_arr[:1]])
                    dy_arr = np.concatenate([dy_arr, dy_arr[:1]])
                base_total_length = radius * (np.pi * 2.0 if mirrored else np.pi) if curved else float(h * 0.8) if gravity in ('left', 'right') else float(w * 0.8)
                pass_specs: list[dict] = []
                if glow_strength > 0.0:
                    pass_specs.append({'is_glow': True, 'alpha': layer_op * (0.14 + glow_strength * 0.22), 'bar_width': bar_width_px + (glow_softness * 1.8 + glow_strength * 18.0) * sf, 'spike_height': spike_height_px + (glow_softness * 2.2 + glow_strength * 22.0) * sf, 'fill_circle': False})
                    pass_specs.append({'is_glow': True, 'alpha': layer_op * (0.08 + glow_strength * 0.15), 'bar_width': bar_width_px + (glow_softness * 3.0 + glow_strength * 32.0) * sf, 'spike_height': spike_height_px + (glow_softness * 3.4 + glow_strength * 34.0) * sf, 'fill_circle': False})
                pass_specs.append({'is_glow': False, 'alpha': layer_op, 'bar_width': bar_width_px, 'spike_height': spike_height_px, 'fill_circle': bool(sl.get('fillCircle', False))})
                for pass_cfg in pass_specs:
                    pass_bar_width_px = float(pass_cfg['bar_width'])
                    pass_spike_height_px = float(pass_cfg['spike_height'])
                    pass_alpha = float(max(0.0, min(1.0, float(pass_cfg['alpha']))))
                    fill_circle_pass = bool(pass_cfg['fill_circle'])
                    if pass_cfg['is_glow']:
                        self.ctx.blend_func = moderngl.ADDITIVE_BLENDING
                    elif blend_mode in ('screen', 'add', 'lighten'):
                        self.ctx.blend_func = moderngl.ADDITIVE_BLENDING
                    else:
                        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
                    val_arr = (render_fft * pass_spike_height_px).astype(np.float32)
                    if curved and mirrored and waveform_style:
                        val_arr = np.concatenate([val_arr, val_arr[:1]])
                    nn = int(px_arr.shape[0])
                    half_t = float(max(1.0, pass_bar_width_px)) * 0.5

                    def mk_col_array(nn0: int):
                        if col_mode == 'gradient' and len(grad_cols) >= 2:
                            c1 = np.array(hex_to_rgb(grad_cols[0]), dtype=np.float32) / 255.0
                            c2 = np.array(hex_to_rgb(grad_cols[-1]), dtype=np.float32) / 255.0
                            t_arr = (np.arange(nn0, dtype=np.float32) / float(max(1, nn0 - 1))).reshape((nn0, 1))
                            rgb = c1.reshape((1, 3)) * (1.0 - t_arr) + c2.reshape((1, 3)) * t_arr
                            a = np.full((nn0, 1), pass_alpha, dtype=np.float32)
                            return np.concatenate([rgb, a], axis=1)
                        c = np.array(hex_to_rgb(solid_hex), dtype=np.float32) / 255.0
                        return np.tile(np.array([c[0], c[1], c[2], pass_alpha], dtype=np.float32)[None, :], (nn0, 1))
                    ctx_col = mk_col_array(nn)
                    bw = float(max(1.0, base_total_length / max(1, BINS) * (pass_bar_width_px / 10.0)))
                    if waveform_style:
                        xs_o = np.zeros(nn, dtype=np.float32)
                        ys_o = np.zeros(nn, dtype=np.float32)
                        xs_i = np.zeros(nn, dtype=np.float32)
                        ys_i = np.zeros(nn, dtype=np.float32)
                        for i in range(nn):
                            h_val = float(max(2.0, val_arr[i]))
                            dx, dy = (float(dx_arr[i]), float(dy_arr[i]))
                            if style_preset == 'mountain':
                                peak_h = h_val * 1.18
                                xs_o[i] = (cx + float(px_arr[i]) + dx * peak_h) / float(w) * 2.0 - 1.0
                                ys_o[i] = (cy + float(py_arr[i]) + dy * peak_h) / float(h) * 2.0 - 1.0
                                xs_i[i] = (cx + float(px_arr[i]) + dx * (half_t * 0.2)) / float(w) * 2.0 - 1.0
                                ys_i[i] = (cy + float(py_arr[i]) + dy * (half_t * 0.2)) / float(h) * 2.0 - 1.0
                            elif style_preset == 'liquid':
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
                            if verts_fill.nbytes > self.line_vbo.size:
                                self.line_vbo.orphan(size=verts_fill.nbytes)
                            self.line_vbo.write(verts_fill.tobytes())
                            self.vao_lines.render(mode=moderngl.TRIANGLE_FAN, vertices=int(nn + 1))
                        pos = np.empty((2 * nn, 2), dtype=np.float32)
                        pos[0::2, 0] = xs_o
                        pos[0::2, 1] = ys_o
                        pos[1::2, 0] = xs_i
                        pos[1::2, 1] = ys_i
                        colsi = np.repeat(ctx_col, 2, axis=0)
                        verts = np.column_stack([pos, colsi]).astype(np.float32)
                        if verts.nbytes > self.line_vbo.size:
                            self.line_vbo.orphan(size=verts.nbytes)
                        self.line_vbo.write(verts.tobytes())
                        self.vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=int(2 * nn))
                    else:
                        pos_parts: list[list[float]] = []
                        col_parts: list[list[float]] = []
                        for i in range(BINS):
                            h_val = float(max(2.0, val_arr[i]))
                            dx = float(dx_arr[i])
                            dy = float(dy_arr[i])
                            wx = -dy * (bw / 2.0)
                            wy = dx * (bw / 2.0)
                            if style_preset == 'symmetrical-bars':
                                p0x = px_arr[i] - dx * (h_val / 2.0) - wx
                                p0y = py_arr[i] - dy * (h_val / 2.0) - wy
                                p1x = px_arr[i] - dx * (h_val / 2.0) + wx
                                p1y = py_arr[i] - dy * (h_val / 2.0) + wy
                                p2x = px_arr[i] + dx * (h_val / 2.0) + wx
                                p2y = py_arr[i] + dy * (h_val / 2.0) + wy
                                p3x = px_arr[i] + dx * (h_val / 2.0) - wx
                                p3y = py_arr[i] + dy * (h_val / 2.0) - wy
                                quad_pts = [(p0x, p0y), (p1x, p1y), (p2x, p2y), (p0x, p0y), (p2x, p2y), (p3x, p3y)]
                                pos_parts.extend(quad_pts)
                                col_parts.extend([ctx_col[i].tolist()] * 6)
                                continue
                            if style_preset == 'floating-blocks':
                                p0x = px_arr[i] + dx * (h_val + 20.0 * sf) - wx
                                p0y = py_arr[i] + dy * (h_val + 20.0 * sf) - wy
                                p1x = px_arr[i] + dx * (h_val + 20.0 * sf) + wx
                                p1y = py_arr[i] + dy * (h_val + 20.0 * sf) + wy
                                p2x = px_arr[i] + dx * (h_val + 30.0 * sf) + wx
                                p2y = py_arr[i] + dy * (h_val + 30.0 * sf) + wy
                                p3x = px_arr[i] + dx * (h_val + 30.0 * sf) - wx
                                p3y = py_arr[i] + dy * (h_val + 30.0 * sf) - wy
                                quad_pts = [(p0x, p0y), (p1x, p1y), (p2x, p2y), (p0x, p0y), (p2x, p2y), (p3x, p3y)]
                                pos_parts.extend(quad_pts)
                                col_parts.extend([ctx_col[i].tolist()] * 6)
                                continue
                            if style_preset == 'pixel-bars':
                                step = 20.0 * sf
                                h_val = float(np.ceil(h_val / max(1.0, step)) * max(1.0, step))
                            elif style_preset == 'thin-lines':
                                wx = -dy * (1.0 * sf)
                                wy = dx * (1.0 * sf)
                            elif style_preset == 'neon-pulse':
                                pulse = 1.0 + self.logo_audio_env * 0.18 + self.particle_audio_env * 0.12
                                h_val *= pulse
                                wx *= 1.25
                                wy *= 1.25
                            elif style_preset == 'dot-matrix':
                                dot_step = max(10.0 * sf, bw * 1.2)
                                dot_len = max(6.0 * sf, bw * 0.9)
                                seg_count = max(1, int(np.ceil(h_val / max(1.0, dot_step))))
                                for seg in range(seg_count):
                                    seg_start = min(h_val, seg * dot_step)
                                    seg_end = min(h_val, seg_start + dot_len)
                                    if seg_end <= seg_start:
                                        continue
                                    p0x = px_arr[i] + dx * seg_start - wx
                                    p0y = py_arr[i] + dy * seg_start - wy
                                    p1x = px_arr[i] + dx * seg_start + wx
                                    p1y = py_arr[i] + dy * seg_start + wy
                                    p2x = px_arr[i] + dx * seg_end + wx
                                    p2y = py_arr[i] + dy * seg_end + wy
                                    p3x = px_arr[i] + dx * seg_end - wx
                                    p3y = py_arr[i] + dy * seg_end - wy
                                    quad_pts = [(p0x, p0y), (p1x, p1y), (p2x, p2y), (p0x, p0y), (p2x, p2y), (p3x, p3y)]
                                    pos_parts.extend(quad_pts)
                                    col_parts.extend([ctx_col[i].tolist()] * 6)
                                continue
                            p0x = px_arr[i] - wx
                            p0y = py_arr[i] - wy
                            p1x = px_arr[i] + wx
                            p1y = py_arr[i] + wy
                            p2x = px_arr[i] + dx * h_val + wx
                            p2y = py_arr[i] + dy * h_val + wy
                            p3x = px_arr[i] + dx * h_val - wx
                            p3y = py_arr[i] + dy * h_val - wy
                            quad_pts = [(p0x, p0y), (p1x, p1y), (p2x, p2y), (p0x, p0y), (p2x, p2y), (p3x, p3y)]
                            pos_parts.extend(quad_pts)
                            col_parts.extend([ctx_col[i].tolist()] * 6)
                        if pos_parts:
                            pos = np.array([[(cx + p[0]) / float(w) * 2.0 - 1.0, (cy + p[1]) / float(h) * 2.0 - 1.0] for p in pos_parts], dtype=np.float32)
                            colsi = np.array(col_parts, dtype=np.float32)
                            verts = np.column_stack([pos, colsi]).astype(np.float32)
                            if verts.nbytes > self.line_vbo.size:
                                self.line_vbo.orphan(size=verts.nbytes)
                            self.line_vbo.write(verts.tobytes())
                            self.vao_lines.render(mode=moderngl.TRIANGLES, vertices=int(pos.shape[0]))
            self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
            if logo_enabled:
                self.prog_logo['tex_logo'].value = 1
                if hasattr(self, 'tex_logo'):
                    self.tex_logo.use(location=1)
                if 'out_size' in self.prog_logo:
                    self.prog_logo['out_size'].value = (float(w), float(h))
                ax, ay = (cx, cy)
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
                self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
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
                    ax, ay = _get_anchor_coords(anchor_t, ox, oy, w, h)
                    self.prog_text["tex_text"].value = 2
                    tx.use(location=2)
                    self.prog_text["out_size"].value = (float(w), float(h))
                    self.prog_text["text_px"].value = (float(ax) - float(w) * 0.5 + dx, float(ay) - float(h) * 0.5 + dy)
                    self.prog_text["text_size_px"].value = (float(tw) * scale_t, float(th) * scale_t)
                    self.prog_text["text_opacity"].value = float(max(0.0, min(1.0, opacity)))
                    self.prog_text["reveal"].value = float(max(0.0, min(1.0, reveal)))
                    self.vao_quad_text.render(mode=moderngl.TRIANGLE_STRIP)
        except Exception as e:
            self._log(f"[{time.strftime('%H:%M:%S')}] Error in paintGL: {e}")
            import traceback
            traceback.print_exc()

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
        f = QFont("Open Sans", 10)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(float(cx - 40), float(cy + 6), 80.0, 24.0), int(Qt.AlignmentFlag.AlignCenter), f"{self._percent}%")

        y0 = top_pad + circle_d + 12
        p.setPen(QColor(self._text))
        ft = QFont("Open Sans", 10)
        ft.setBold(True)
        p.setFont(ft)
        p.drawText(QRectF(0.0, float(y0), float(w), 22.0), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), self._title)

        p.setPen(QColor(self._text_muted))
        fd = QFont("Open Sans", 9)
        fd.setBold(False)
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
