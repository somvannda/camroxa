"""Transparent hit layer that drives GPU text drag / CapCut-like box resize.

Mouse capture stays in Qt (reliable over QOpenGLWidget). The actual text
is drawn by the GPU preview — this widget draws a selection frame + handles
and forwards move / resize to the draft.

Resize modes (CapCut-style):
- Left / right edges: change box width → text reflows / wraps
- Top / bottom / corners: scale font size + letter spacing by ratio
  (corners also scale wrap width); opposite edge/corner stays fixed.
  Line-spacing multiplier stays put — row pitch already scales with font size.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

_HANDLE = 10  # screen px handle size
_MIN_BOX_W = 40.0
_MIN_FONT = 5.0
_MAX_FONT = 200.0
_LIVE_RESIZE_MIN_INTERVAL_S = 0.032  # ~30 fps live GPU reflow


def _cursor_for_handle(edge: str):
    if edge in {"l", "r"}:
        return Qt.CursorShape.SizeHorCursor
    if edge in {"t", "b"}:
        return Qt.CursorShape.SizeVerCursor
    if edge in {"tl", "br"}:
        return Qt.CursorShape.SizeFDiagCursor
    if edge in {"tr", "bl"}:
        return Qt.CursorShape.SizeBDiagCursor
    return Qt.CursorShape.OpenHandCursor


def compute_box_resize(
    *,
    edge: str,
    dx_tpl: float,
    dy_tpl: float,
    press_w: float,
    press_h: float,
    press_font: float,
    press_letter: float,
    press_x: float,
    press_y: float,
    press_wrap_w: float = 0.0,
    press_line: float = 1.2,
) -> dict[str, float]:
    """Pure resize math in template units (testable).

    ``press_w`` / ``press_h`` are the visible frame size (may be multi-column).
    ``press_wrap_w`` is the per-cell wrap width (0 = auto / no wrap).

    Returns keys: boxWidth, fontSize, letterSpacing, lineSpacing, x, y, scale,
    contentWidth, contentHeight.
    """
    edge = str(edge or "").lower().strip()
    w0 = float(max(_MIN_BOX_W, press_w))
    h0 = float(max(1.0, press_h))
    fs0 = float(max(_MIN_FONT, press_font))
    ls0 = float(press_letter)
    line0 = float(max(0.8, min(2.5, press_line or 1.2)))
    x0 = float(press_x)
    y0 = float(press_y)
    wrap0 = float(press_wrap_w or 0.0)
    tdx = float(dx_tpl)
    tdy = float(dy_tpl)

    # --- Width-only wrap (left / right edges) ---
    if edge in {"l", "r"}:
        # Drag changes wrap width (per-cell). Fall back to a sensible default
        # when wrap was auto so the first L/R drag enables wrapping.
        base_wrap = wrap0 if wrap0 > 8.0 else float(max(160.0, fs0 * 10.0))
        if edge == "l":
            new_wrap = float(max(_MIN_BOX_W, min(2000.0, base_wrap - tdx)))
            new_x = x0 + (base_wrap - new_wrap)
        else:
            new_wrap = float(max(_MIN_BOX_W, min(2000.0, base_wrap + tdx)))
            new_x = x0
        # Approximate live content width: replace wrap contribution.
        content_w = max(_MIN_BOX_W, w0 - base_wrap + new_wrap) if w0 >= base_wrap else new_wrap
        return {
            "boxWidth": new_wrap,
            "fontSize": fs0,
            "letterSpacing": ls0,
            "lineSpacing": line0,
            "x": new_x,
            "y": y0,
            "scale": 1.0,
            "contentWidth": float(content_w),
            "contentHeight": h0,
        }

    # --- Scale modes: top/bottom + corners ---
    new_w = w0
    new_h = h0
    if "l" in edge:
        new_w = w0 - tdx
    elif "r" in edge:
        new_w = w0 + tdx
    if "t" in edge:
        new_h = h0 - tdy
    elif "b" in edge:
        new_h = h0 + tdy

    new_w = float(max(_MIN_BOX_W * 0.25, new_w))
    new_h = float(max(1.0, new_h))

    if edge in {"t", "b"}:
        scale = new_h / h0
        scale = float(max(0.15, min(8.0, scale)))
        new_fs = float(max(_MIN_FONT, min(_MAX_FONT, fs0 * scale)))
        scale = new_fs / fs0 if fs0 > 1e-6 else 1.0
        new_ls = float(max(-20.0, min(40.0, ls0 * scale)))
        # Keep multiplier; row pitch = fontSize * lineSpacing already scales.
        new_line = line0
        new_y = y0 + (h0 - h0 * scale) if edge == "t" else y0
        new_wrap = float(max(_MIN_BOX_W, min(2000.0, wrap0 * scale))) if wrap0 > 8.0 else 0.0
        return {
            "boxWidth": new_wrap,
            "fontSize": new_fs,
            "letterSpacing": new_ls,
            "lineSpacing": new_line,
            "x": x0,
            "y": new_y,
            "scale": scale,
            "contentWidth": float(max(_MIN_BOX_W, w0 * scale)),
            "contentHeight": float(max(1.0, h0 * scale)),
        }

    # Corners: uniform scale (average of width/height ratios), lock aspect.
    scale_w = new_w / w0
    scale_h = new_h / h0
    scale = float(max(0.15, min(8.0, (scale_w + scale_h) * 0.5)))
    new_fs = float(max(_MIN_FONT, min(_MAX_FONT, fs0 * scale)))
    scale = new_fs / fs0 if fs0 > 1e-6 else 1.0
    new_ls = float(max(-20.0, min(40.0, ls0 * scale)))
    new_line = line0
    scaled_w = float(max(_MIN_BOX_W, w0 * scale))
    scaled_h = h0 * scale
    new_wrap = float(max(_MIN_BOX_W, min(2000.0, wrap0 * scale))) if wrap0 > 8.0 else 0.0

    # Keep the opposite corner fixed (top-left pin coordinate system).
    if edge == "tl":
        new_x = x0 + (w0 - scaled_w)
        new_y = y0 + (h0 - scaled_h)
    elif edge == "tr":
        new_x = x0
        new_y = y0 + (h0 - scaled_h)
    elif edge == "bl":
        new_x = x0 + (w0 - scaled_w)
        new_y = y0
    else:  # br
        new_x = x0
        new_y = y0

    return {
        "boxWidth": new_wrap,
        "fontSize": new_fs,
        "letterSpacing": new_ls,
        "lineSpacing": new_line,
        "x": new_x,
        "y": new_y,
        "scale": scale,
        "contentWidth": scaled_w,
        "contentHeight": float(max(1.0, scaled_h)),
    }


class TextDragOverlay(QWidget):
    """Full-bleed transparent catcher for Album/Title drag + box resize."""

    # Live pixel offset while dragging (domain, dx, dy) — GPU applies immediately.
    drag_offset_changed = Signal(str, float, float)
    # Final template coords after release (domain, x, y).
    position_committed = Signal(str, float, float)
    # Live CapCut box transform while resizing (domain, patch) — GPU reflows.
    box_resize_changed = Signal(str, object)
    # CapCut box transform after resize commit (domain, patch dict).
    # Keys: boxWidth, fontSize, letterSpacing, lineSpacing, x, y
    box_resized = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._domain = ""
        self._enabled = False
        self._base_x = 0.0
        self._base_y = 0.0
        self._box_width = 0.0
        self._content_width = 0.0
        self._content_height = 0.0
        self._font_size = 36.0
        self._letter_spacing = 0.0
        self._line_count = 1
        self._line_spacing = 1.2
        self._anchor = "top-left"
        self._render_base_height = 450.0
        self._drag_dx = 0.0
        self._drag_dy = 0.0
        self._dragging = False
        self._resizing = False
        self._resize_edge = ""
        self._press_pos: QPoint | None = None
        self._press_box_width = 0.0
        self._press_box_height = 0.0
        self._press_wrap_width = 0.0
        self._press_font_size = 36.0
        self._press_letter_spacing = 0.0
        self._press_line_spacing = 1.2
        self._press_x = 0.0
        self._press_y = 0.0
        self._last_live_emit_at = 0.0
        self._show_frame = False
        self.hide()

    def is_dragging(self) -> bool:
        """True while position-dragging or resizing (blocks overlay rebind)."""
        return bool((self._dragging or self._resizing) and self._domain in {"album", "title"})

    def is_position_dragging(self) -> bool:
        """True only for move-drag — preview template push must stay blocked."""
        return bool(self._dragging and self._domain in {"album", "title"})

    def is_resizing(self) -> bool:
        return bool(self._resizing and self._domain in {"album", "title"})

    def active_domain(self) -> str:
        return str(self._domain or "")

    def set_edit_domain(self, domain: str) -> None:
        key = str(domain or "").strip().lower()
        self._domain = key if key in {"album", "title"} else ""
        self._enabled = bool(self._domain)
        if not self._enabled:
            self._dragging = False
            self._resizing = False
            self._press_pos = None
            self._drag_dx = 0.0
            self._drag_dy = 0.0
            self._show_frame = False
            self.hide()
            return
        self.show()
        self.raise_()
        self.update()

    def bind_text(
        self,
        *,
        domain: str,
        enabled: bool,
        lines: list[str],
        anchor: str,
        x: float,
        y: float,
        font_family: str,
        font_size: float,
        bold: bool,
        italic: bool,
        color: str,
        render_base_height: float = 450.0,
        box_width: float = 0.0,
        line_spacing: float = 1.2,
        letter_spacing: float = 0.0,
        content_width: float = 0.0,
        content_height: float = 0.0,
    ) -> None:
        """Sync base template coords / box. GPU draws text; we draw the frame."""
        _ = (font_family, bold, italic, color)
        if self._dragging or self._resizing:
            # During live resize, still accept measured content bounds so the
            # frame tracks reflowed wrap/scale from the GPU path.
            if self._resizing and content_width > 8.0:
                self._content_width = float(content_width)
            if self._resizing and content_height > 1.0:
                self._content_height = float(content_height)
            return
        key = str(domain or "").strip().lower()
        self._domain = key if key in {"album", "title"} else ""
        self._enabled = bool(enabled and self._domain and lines)
        self._base_x = float(x or 0.0)
        self._base_y = float(y or 0.0)
        self._box_width = float(max(0.0, box_width or 0.0))
        self._content_width = float(max(0.0, content_width or 0.0))
        self._content_height = float(max(0.0, content_height or 0.0))
        self._font_size = float(max(_MIN_FONT, font_size or 36.0))
        self._letter_spacing = float(letter_spacing or 0.0)
        self._line_count = max(1, len(lines) if isinstance(lines, list) else 1)
        self._line_spacing = float(max(0.8, line_spacing or 1.2))
        # Title/album domains are top-left pinned in the GPU path.
        self._anchor = str(anchor or "top-left")
        self._render_base_height = float(max(1.0, render_base_height or 450.0))
        self._drag_dx = 0.0
        self._drag_dy = 0.0
        self._show_frame = bool(self._enabled)
        if self._enabled:
            self.show()
            self.raise_()
        else:
            self.hide()
        self.update()

    def _sf(self) -> float:
        return float(max(1.0, self.height())) / float(max(1.0, self._render_base_height))

    def _content_height_tpl(self) -> float:
        if self._content_height > 1.0:
            return float(self._content_height)
        return max(
            self._font_size * self._line_spacing * float(self._line_count),
            self._font_size * 1.2,
        )

    def _effective_box_width_tpl(self) -> float:
        # Prefer measured layout union (multi-column titles, wrapped album).
        if self._content_width > 8.0:
            return float(self._content_width)
        if self._box_width > 8.0:
            return float(self._box_width)
        return float(max(160.0, self._font_size * 10.0))

    def _current_resize_patch(self) -> dict[str, float]:
        return {
            "boxWidth": float(self._box_width),
            "fontSize": float(self._font_size),
            "letterSpacing": float(self._letter_spacing),
            "lineSpacing": float(self._line_spacing),
            "x": float(self._base_x),
            "y": float(self._base_y),
        }

    def _emit_live_resize(self, *, force: bool = False) -> None:
        if self._domain not in {"album", "title"}:
            return
        now = time.perf_counter()
        if not force and (now - self._last_live_emit_at) < _LIVE_RESIZE_MIN_INTERVAL_S:
            return
        self._last_live_emit_at = now
        self.box_resize_changed.emit(self._domain, self._current_resize_patch())

    def _box_rect_screen(self) -> QRect:
        """Selection rect in widget pixels — matches GPU top-left text placement.

        GPU: left-anchored text uses ``x`` from the left edge (not center).
        Overlay must use the same origin or the frame drifts by ~half the preview.
        """
        sf = self._sf()
        tw = self._effective_box_width_tpl() * sf
        th = self._content_height_tpl() * sf
        ox = (self._base_x + self._drag_dx / max(sf, 1e-6)) * sf
        oy = (self._base_y + self._drag_dy / max(sf, 1e-6)) * sf
        a = str(self._anchor or "top-left").lower()
        # Match visualizer._get_anchor_coords X origin (widget Y is top-down).
        if "left" in a:
            left = ox
        elif "right" in a:
            left = float(self.width()) + ox - tw
        else:
            left = float(self.width()) * 0.5 + ox - tw * 0.5
        if "top" in a:
            top = oy
        elif "bottom" in a:
            top = float(self.height()) + oy - th
        else:
            top = float(self.height()) * 0.5 + oy - th * 0.5
        return QRect(int(round(left)), int(round(top)), int(round(max(1.0, tw))), int(round(max(1.0, th))))

    def _handle_rects(self) -> dict[str, QRect]:
        rect = self._box_rect_screen()
        hs = _HANDLE
        cx = rect.left() + rect.width() // 2
        cy = rect.top() + rect.height() // 2
        half = hs // 2
        return {
            "tl": QRect(rect.left() - half, rect.top() - half, hs, hs),
            "t": QRect(cx - half, rect.top() - half, hs, hs),
            "tr": QRect(rect.right() - half, rect.top() - half, hs, hs),
            "l": QRect(rect.left() - half, cy - half, hs, hs),
            "r": QRect(rect.right() - half, cy - half, hs, hs),
            "bl": QRect(rect.left() - half, rect.bottom() - half, hs, hs),
            "b": QRect(cx - half, rect.bottom() - half, hs, hs),
            "br": QRect(rect.right() - half, rect.bottom() - half, hs, hs),
        }

    def _hit_resize_edge(self, pos: QPoint) -> str:
        if not self._enabled:
            return ""
        # Corners first so diagonal wins over edge strips.
        order = ("tl", "tr", "bl", "br", "t", "b", "l", "r")
        for key in order:
            if self._handle_rects()[key].adjusted(-2, -2, 2, 2).contains(pos):
                return key
        return ""

    def paintEvent(self, _ev) -> None:
        if not self._enabled or not self._show_frame:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._box_rect_screen()
        painter.setPen(QPen(QColor(64, 196, 255, 200), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.setBrush(QColor(64, 196, 255, 220))
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
        for handle in self._handle_rects().values():
            painter.drawRect(handle)
        painter.end()

    def mousePressEvent(self, ev) -> None:
        if not self._enabled or ev.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(ev)
            return
        pos = ev.position().toPoint()
        edge = self._hit_resize_edge(pos)
        self._press_pos = pos
        self._drag_dx = 0.0
        self._drag_dy = 0.0
        self._show_frame = True
        if edge:
            self._resizing = True
            self._dragging = False
            self._resize_edge = edge
            # Use measured content size as the press baseline so scale math
            # matches the visible multi-column / wrapped frame.
            self._press_box_width = self._effective_box_width_tpl()
            self._press_box_height = self._content_height_tpl()
            self._press_wrap_width = float(self._box_width)
            self._press_font_size = float(self._font_size)
            self._press_letter_spacing = float(self._letter_spacing)
            self._press_line_spacing = float(self._line_spacing)
            self._press_x = float(self._base_x)
            self._press_y = float(self._base_y)
            self._last_live_emit_at = 0.0
            self.setCursor(_cursor_for_handle(edge))
        else:
            self._dragging = True
            self._resizing = False
            self._resize_edge = ""
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.drag_offset_changed.emit(self._domain, 0.0, 0.0)
        self.grabMouse()
        self.update()
        ev.accept()

    def mouseMoveEvent(self, ev) -> None:
        pos = ev.position().toPoint()
        if not self._dragging and not self._resizing:
            edge = self._hit_resize_edge(pos)
            if edge:
                self.setCursor(_cursor_for_handle(edge))
            elif self._enabled:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            super().mouseMoveEvent(ev)
            return
        if self._press_pos is None:
            return
        cur = pos
        dx = float(cur.x() - self._press_pos.x())
        dy = float(cur.y() - self._press_pos.y())
        if self._resizing:
            sf = self._sf()
            result = compute_box_resize(
                edge=self._resize_edge,
                dx_tpl=dx / max(sf, 1e-6),
                dy_tpl=dy / max(sf, 1e-6),
                press_w=self._press_box_width,
                press_h=self._press_box_height,
                press_font=self._press_font_size,
                press_letter=self._press_letter_spacing,
                press_x=self._press_x,
                press_y=self._press_y,
                press_wrap_w=self._press_wrap_width,
                press_line=self._press_line_spacing,
            )
            self._box_width = float(result["boxWidth"])
            self._font_size = float(result["fontSize"])
            self._letter_spacing = float(result["letterSpacing"])
            self._line_spacing = float(result.get("lineSpacing", self._line_spacing) or self._line_spacing)
            self._base_x = float(result["x"])
            self._base_y = float(result["y"])
            self._content_width = float(result.get("contentWidth", self._box_width) or self._box_width)
            self._content_height = float(result.get("contentHeight", self._content_height) or self._content_height)
            self._emit_live_resize()
            self.update()
            ev.accept()
            return
        self._drag_dx = dx
        self._drag_dy = dy
        self.drag_offset_changed.emit(self._domain, self._drag_dx, self._drag_dy)
        self.update()
        ev.accept()

    def mouseReleaseEvent(self, ev) -> None:
        if ev.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(ev)
            return
        was_drag = self._dragging
        was_resize = self._resizing
        domain = self._domain
        dx = float(self._drag_dx)
        dy = float(self._drag_dy)
        patch = self._current_resize_patch()
        self._dragging = False
        self._resizing = False
        self._resize_edge = ""
        self._press_pos = None
        self.releaseMouse()
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if was_resize and domain in {"album", "title"}:
            # Final live tick then commit (persist + inspectors).
            self.box_resize_changed.emit(domain, patch)
            self.box_resized.emit(domain, patch)
            self.update()
        elif was_drag and domain in {"album", "title"}:
            sf = self._sf()
            if sf > 1e-06:
                nx = float(max(-2000.0, min(2000.0, self._base_x + dx / sf)))
                ny = float(max(-2000.0, min(2000.0, self._base_y + dy / sf)))
                self._base_x = nx
                self._base_y = ny
                self._drag_dx = 0.0
                self._drag_dy = 0.0
                self.drag_offset_changed.emit(domain, 0.0, 0.0)
                self.position_committed.emit(domain, nx, ny)
                self.update()
        ev.accept()
