"""A single draggable/trimmable clip on the timeline (QGraphicsObject)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal, QPointF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QGraphicsObject, QGraphicsSceneContextMenuEvent, QGraphicsSceneHoverEvent, QGraphicsSceneMouseEvent, QStyleOptionGraphicsItem, QWidget

from studio.core.models import Clip, Track
from studio.core.time_utils import snap
from studio.ui.timeline.geometry import (
    CLIP_HEIGHT,
    CLIP_LABEL_HEIGHT,
    CLIP_TYPE_STRIP_WIDTH,
    FILMSTRIP_THUMB_WIDTH_PX,
    HANDLE_HOVER_WIDTH_PX,
    HANDLE_WIDTH_PX,
    MIN_CLIP_WIDTH_PX,
    TRACK_HEIGHT,
    filmstrip_frame_stride,
    filmstrip_slot_width_px,
    waveform_sample_count,
)
from studio.ui.icons.lucide_icons import CLIP_KIND_ICON, ICON_COLOR_ON_ACCENT, ICON_SZ_CLIP_STRIP, lucide_pixmap
from studio.ui.timeline.snap_engine import SnapResult

_MIN_CLIP_DURATION_PREVIEW = 0.2

_GRADIENTS: dict[str, tuple[str, str]] = {
    "video": ("#8a6bff", "#6a4de0"),
    "audio": ("#2fe6b4", "#18a880"),
    "image": ("#ffc36b", "#e69a2e"),
    "text": ("#ffc36b", "#e69a2e"),
    "playlist": ("#7466F1", "#A259FF"),
}


def _gradient_for(track_type: str, clip_kind: str) -> tuple[str, str]:
    if clip_kind == "playlist":
        return _GRADIENTS["playlist"]
    if track_type == "video":
        return _GRADIENTS["video"]
    if track_type == "audio":
        return _GRADIENTS["audio"]
    return _GRADIENTS["text"] if clip_kind == "text" else _GRADIENTS["image"]


def _clip_kind_icon_name(track_type: str, clip_kind: str) -> str:
    if clip_kind in CLIP_KIND_ICON:
        return CLIP_KIND_ICON[clip_kind]
    if track_type == "video":
        return CLIP_KIND_ICON["video"]
    if track_type == "audio":
        return CLIP_KIND_ICON["audio"]
    return CLIP_KIND_ICON["image"]


def _handle_zone(width_px: float, local_x: float, *, selected_or_hover: bool) -> str:
    """Pick trim-left, trim-right, or move from a local X coordinate."""
    handle_w = HANDLE_HOVER_WIDTH_PX if selected_or_hover else HANDLE_WIDTH_PX
    if width_px <= handle_w * 2:
        return "trim_left" if local_x < width_px / 2 else "trim_right"
    if local_x <= handle_w:
        return "trim_left"
    if local_x >= width_px - handle_w:
        return "trim_right"
    return "move"


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def _synthetic_wave_amplitudes(seed_str: str, bars: int) -> list[float]:
    seed = 0
    for ch in seed_str:
        seed = (seed * 31 + ord(ch)) & 0xFFFFFFFF
    values = []
    for _ in range(bars):
        seed = (seed * 1103515245 + 12345) & 0xFFFFFFFF
        rnd = (seed % 1000) / 1000
        values.append(0.15 + rnd * 0.85)
    return values


def _resample(values: list[float], target_len: int) -> list[float]:
    n = len(values)
    if n == 0 or target_len <= 0:
        return [0.0] * max(0, target_len)
    if n == target_len:
        return list(values)
    if target_len == 1:
        return [values[0]]
    out: list[float] = []
    for i in range(target_len):
        pos = i * (n - 1) / (target_len - 1)
        lo = int(pos)
        hi = min(n - 1, lo + 1)
        frac = pos - lo
        out.append(values[lo] * (1.0 - frac) + values[hi] * frac)
    return out


SnapMoveFn = Callable[[float, float, bool], SnapResult]
SnapTrimFn = Callable[[str, float, float, bool], tuple[float, float, SnapResult]]
MediaTrimBoundsFn = Callable[[float, float], tuple[float, float | None]]
RowResolverFn = Callable[[float], tuple[int, str | None]]


class ClipGraphicsItem(QGraphicsObject):
    selected_requested = Signal(str)
    selection_requested = Signal(str, bool, bool)  # clip_id, ctrl, shift
    context_menu_requested = Signal(str, object)  # clip_id, QPointF scene pos
    move_committed = Signal(str, float, object, int)  # clip_id, start, target_track_id|None, preview_row
    trim_committed = Signal(str, str, float)
    snap_guides_changed = Signal(object)
    edge_scroll_requested = Signal(float, float)

    def __init__(self, track: Track, clip: Clip, parent=None) -> None:
        super().__init__(parent)
        self.track = track
        self.clip = clip
        self._px_per_sec = 70.0
        self._width_px = MIN_CLIP_WIDTH_PX
        self._is_selected = False
        self._hover_handle: str | None = None
        self._drag_mode: str | None = None
        self._press_scene_x = 0.0
        self._press_scene_y = 0.0
        self._orig_start = clip.start
        self._orig_duration = clip.duration
        self._orig_trim_start = clip.trim_start
        self._orig_row_index = 0
        self._preview_row_index = 0
        self._preview_track_id = clip.track_id
        self._preview_start = clip.start
        self._preview_duration = clip.duration
        self._thumb_pixmaps: list[QPixmap] = []
        self._image_pixmap: QPixmap | None = None
        self._thumb_cache_key: tuple[str, ...] | None = None
        self._thumb_dpr_key: float | None = None
        self._image_cache_key: str | None = None
        self._image_tile_key: tuple | None = None
        self._image_tile_pixmap: QPixmap | None = None
        self._snap_move: SnapMoveFn | None = None
        self._snap_trim: SnapTrimFn | None = None
        self._media_trim_bounds: MediaTrimBoundsFn | None = None
        self._row_resolver: RowResolverFn | None = None
        self._snap_edge: str = "none"
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setZValue(1.0)

    def set_snap_callbacks(self, move_fn: SnapMoveFn | None, trim_fn: SnapTrimFn | None) -> None:
        self._snap_move = move_fn
        self._snap_trim = trim_fn

    def set_media_trim_bounds(self, bounds_fn: MediaTrimBoundsFn | None) -> None:
        self._media_trim_bounds = bounds_fn

    def set_row_resolver(self, resolver: RowResolverFn | None) -> None:
        self._row_resolver = resolver

    @staticmethod
    def _row_y(row_index: int) -> float:
        return row_index * TRACK_HEIGHT + (TRACK_HEIGHT - CLIP_HEIGHT) / 2

    def sync_geometry(self, px_per_sec: float, row_index: int) -> None:
        self.prepareGeometryChange()
        self._px_per_sec = px_per_sec
        self._width_px = max(MIN_CLIP_WIDTH_PX, self.clip.duration * px_per_sec)
        self._orig_row_index = row_index
        self._preview_row_index = row_index
        self._preview_track_id = self.clip.track_id
        x = self.clip.start * px_per_sec
        self.setPos(x, self._row_y(row_index))
        self.update()

    def sync_from_model(self, px_per_sec: float, row_index: int) -> None:
        self._preview_start = self.clip.start
        self._preview_duration = self.clip.duration
        self.sync_geometry(px_per_sec, row_index)

    def set_selected_visual(self, selected: bool) -> None:
        if self._is_selected != selected:
            self._is_selected = selected
            self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(0, 0, self._width_px, CLIP_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:  # noqa: N802
        rect = self.boundingRect()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        color_from, color_to = _gradient_for(self.track.type, self.clip.kind)
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(color_from))
        gradient.setColorAt(1, QColor(color_to))
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        painter.fillPath(path, QBrush(gradient))

        strip = QRectF(0, 0, CLIP_TYPE_STRIP_WIDTH, rect.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 55))
        painter.drawRoundedRect(strip, 6, 6)
        icon_name = _clip_kind_icon_name(self.track.type, self.clip.kind)
        icon_px = lucide_pixmap(icon_name, size=ICON_SZ_CLIP_STRIP, color=ICON_COLOR_ON_ACCENT)
        ix = (CLIP_TYPE_STRIP_WIDTH - ICON_SZ_CLIP_STRIP) / 2
        iy = (rect.height() - ICON_SZ_CLIP_STRIP) / 2
        painter.drawPixmap(int(ix), int(iy), icon_px)

        body_top = CLIP_LABEL_HEIGHT
        body_left = CLIP_TYPE_STRIP_WIDTH
        body_rect = QRectF(body_left, body_top, max(0.0, rect.width() - body_left), max(0.0, rect.height() - body_top))
        self._paint_body(painter, body_rect, widget)
        self._paint_fades(painter, rect, body_left)

        label_rect = QRectF(CLIP_TYPE_STRIP_WIDTH, 0, max(0.0, rect.width() - CLIP_TYPE_STRIP_WIDTH), CLIP_LABEL_HEIGHT)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 80))
        painter.drawRect(label_rect)
        painter.setPen(QColor(240, 240, 245))
        font = painter.font()
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(
            self.clip.label,
            Qt.TextElideMode.ElideRight,
            max(0, int(label_rect.width()) - 6),
        )
        painter.drawText(label_rect.adjusted(4, 0, -2, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

        duration = self._preview_duration if self._drag_mode else self.clip.duration
        if rect.width() > 36:
            badge = _fmt_duration(duration)
            bw = metrics.horizontalAdvance(badge) + 8
            badge_rect = QRectF(rect.width() - bw - 4, rect.height() - 14, bw, 12)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 140))
            painter.drawRoundedRect(badge_rect, 3, 3)
            painter.setPen(QColor(230, 230, 240))
            font.setPixelSize(8)
            painter.setFont(font)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge)

        if self._is_selected:
            glow = QPen(QColor(255, 255, 255, 80), 4)
            painter.setPen(glow)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 7, 7)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 5, 5)

        self._paint_trim_handles(painter, rect)

        if self._snap_edge in ("start", "end"):
            edge_pen = QPen(QColor("#ffd54a"), 3)
            painter.setPen(edge_pen)
            x = 2.0 if self._snap_edge == "start" else rect.width() - 2.0
            painter.drawLine(int(x), int(CLIP_LABEL_HEIGHT), int(x), int(rect.height() - 2))
        elif self._snap_edge == "center":
            painter.setPen(QPen(QColor("#ffd54a"), 2, Qt.PenStyle.DashLine))
            cx = rect.width() / 2
            painter.drawLine(int(cx), int(CLIP_LABEL_HEIGHT), int(cx), int(rect.height() - 2))

    def _paint_trim_handles(self, painter: QPainter, rect: QRectF) -> None:
        show_left = self._is_selected or self._hover_handle == "trim_left"
        show_right = self._is_selected or self._hover_handle == "trim_right"
        if not (show_left or show_right):
            return

        body_top = CLIP_LABEL_HEIGHT + 2
        body_h = max(8.0, rect.height() - body_top - 4)
        handle_w = HANDLE_HOVER_WIDTH_PX if self._hover_handle else HANDLE_WIDTH_PX

        for side, show in (("left", show_left), ("right", show_right)):
            if not show:
                continue
            x = 0.0 if side == "left" else rect.width() - handle_w
            alpha = 220 if (
                (side == "left" and self._hover_handle == "trim_left")
                or (side == "right" and self._hover_handle == "trim_right")
            ) else 140
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, alpha))
            handle_rect = QRectF(x, body_top, handle_w, body_h)
            painter.drawRoundedRect(handle_rect, 2, 2)
            self._paint_resize_arrows(painter, handle_rect)

    def _paint_resize_arrows(self, painter: QPainter, handle_rect: QRectF) -> None:
        """Draw a small double-headed horizontal arrow (↔) in the trim handle."""
        cx = handle_rect.center().x()
        cy = handle_rect.center().y()
        half = min(4.0, handle_rect.width() * 0.28)
        pen = QPen(QColor(20, 20, 30, 230), 1.6)
        painter.setPen(pen)
        painter.drawLine(QPointF(cx - half, cy), QPointF(cx + half, cy))
        for direction in (-1, 1):
            tip_x = cx + direction * half
            painter.drawLine(QPointF(tip_x, cy), QPointF(tip_x - direction * 2.5, cy - 2.5))
            painter.drawLine(QPointF(tip_x, cy), QPointF(tip_x - direction * 2.5, cy + 2.5))

    def _paint_fades(self, painter: QPainter, rect: QRectF, body_left: float) -> None:
        fade_in = self.clip.fade_in or 0.0
        fade_out = self.clip.fade_out or 0.0
        if fade_in <= 0 and fade_out <= 0:
            return
        body_w = max(0.0, rect.width() - body_left)
        if fade_in > 0 and self._px_per_sec > 0:
            w = min(body_w * 0.4, fade_in * self._px_per_sec)
            grad = QLinearGradient(body_left, 0, body_left + w, 0)
            grad.setColorAt(0, QColor(0, 0, 0, 160))
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            painter.fillRect(QRectF(body_left, CLIP_LABEL_HEIGHT, w, rect.height() - CLIP_LABEL_HEIGHT), grad)
        if fade_out > 0 and self._px_per_sec > 0:
            w = min(body_w * 0.4, fade_out * self._px_per_sec)
            x0 = rect.width() - w
            grad = QLinearGradient(x0, 0, rect.width(), 0)
            grad.setColorAt(0, QColor(0, 0, 0, 0))
            grad.setColorAt(1, QColor(0, 0, 0, 160))
            painter.fillRect(QRectF(x0, CLIP_LABEL_HEIGHT, w, rect.height() - CLIP_LABEL_HEIGHT), grad)

    def _device_pixel_ratio(self, widget: QWidget | None) -> float:
        if widget is not None:
            return max(1.0, widget.devicePixelRatioF())
        scene = self.scene()
        if scene is not None:
            views = scene.views()
            if views:
                return max(1.0, views[0].devicePixelRatioF())
        return 1.0

    def _ensure_thumb_pixmaps(self, widget: QWidget | None = None) -> list[QPixmap]:
        dpr = self._device_pixel_ratio(widget)
        key = tuple(self.clip.thumb_cache or [])
        if key != self._thumb_cache_key or dpr != self._thumb_dpr_key:
            self._thumb_cache_key = key
            self._thumb_dpr_key = dpr
            self._thumb_pixmaps = []
            for thumb_path in key:
                if not Path(thumb_path).exists():
                    continue
                pix = QPixmap(thumb_path)
                if not pix.isNull():
                    pix.setDevicePixelRatio(dpr)
                    self._thumb_pixmaps.append(pix)
        return self._thumb_pixmaps

    def _ensure_image_pixmap(self, widget: QWidget | None = None) -> QPixmap | None:
        thumb = self.clip.thumb
        cache_key = thumb or ""
        if cache_key != self._image_cache_key:
            self._image_cache_key = cache_key
            self._image_pixmap = None
            self._image_tile_key = None
            self._image_tile_pixmap = None
            if thumb and Path(thumb).exists():
                pix = QPixmap(thumb)
                if not pix.isNull():
                    self._image_pixmap = pix
        return self._image_pixmap

    def _paint_image_placeholder(self, painter: QPainter, body_rect: QRectF) -> None:
        """Dark fill while the still thumbnail is not ready."""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(45, 38, 28))
        painter.drawRect(body_rect)

    def _scaled_opaque_tile(self, pix: QPixmap, tile_w: int, tile_h: int) -> QPixmap:
        """Scale a still to one timeline tile on an opaque backing (no grid bleed-through)."""
        from PySide6.QtGui import QImage

        bg = QColor(45, 38, 28)
        img = QImage(tile_w, tile_h, QImage.Format.Format_RGB32)
        img.fill(bg.rgb())
        tile_painter = QPainter(img)
        tile_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        tile_painter.drawPixmap(
            0,
            0,
            pix.scaled(tile_w, tile_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation),
        )
        tile_painter.end()
        return QPixmap.fromImage(img)

    def _paint_image_tiled(self, painter: QPainter, body_rect: QRectF, widget: QWidget | None) -> None:
        """Tile a still image horizontally — duration expands with repeats, not stretch."""
        pix = self._ensure_image_pixmap(widget)
        if pix is None:
            self._paint_image_placeholder(painter, body_rect)
            return
        logical_w = float(pix.width())
        logical_h = float(pix.height())
        if logical_w <= 0 or logical_h <= 0:
            return
        tile_h = max(1, int(body_rect.height()))
        tile_w = max(1, int(tile_h * (logical_w / logical_h)))
        tile_key = (self._image_cache_key, tile_w, tile_h)
        if tile_key != self._image_tile_key:
            self._image_tile_key = tile_key
            self._image_tile_pixmap = self._scaled_opaque_tile(pix, tile_w, tile_h)
        if self._image_tile_pixmap is None or self._image_tile_pixmap.isNull():
            return
        painter.save()
        painter.setClipRect(body_rect)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(45, 38, 28))
        painter.drawRect(body_rect)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawTiledPixmap(body_rect.toAlignedRect(), self._image_tile_pixmap)
        painter.restore()

    def _paint_body(self, painter: QPainter, body_rect: QRectF, widget: QWidget | None) -> None:
        if body_rect.height() <= 0 or body_rect.width() <= 0:
            return
        if self.track.type == "video" and self.clip.thumb_cache:
            self._paint_filmstrip(painter, body_rect, widget)
        elif self.track.type == "video":
            self._paint_loading_skeleton(painter, body_rect, blocks=True)
        elif self.track.type == "audio":
            self._paint_waveform(painter, body_rect)
        elif self.clip.kind == "image":
            self._paint_image_tiled(painter, body_rect, widget)

    def _paint_filmstrip(self, painter: QPainter, body_rect: QRectF, widget: QWidget | None) -> None:
        thumbs = self._ensure_thumb_pixmaps(widget)
        if not thumbs:
            self._paint_loading_skeleton(painter, body_rect, blocks=True)
            return
        slot_w = filmstrip_slot_width_px(self._px_per_sec)
        gap = 1.0
        stride = filmstrip_frame_stride(self._px_per_sec, len(thumbs))
        x = body_rect.left()
        idx = 0
        painted = 0
        while x < body_rect.right() and slot_w > 0:
            pix = thumbs[idx % len(thumbs)]
            target = QRectF(x, body_rect.top(), min(slot_w, body_rect.right() - x), body_rect.height())
            painter.drawPixmap(target.toRect(), pix)
            x += slot_w + gap
            idx += stride
            painted += 1
            if painted > 512:
                break

    def _paint_loading_skeleton(self, painter: QPainter, body_rect: QRectF, *, blocks: bool) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 35))
        if blocks:
            slot_w = float(FILMSTRIP_THUMB_WIDTH_PX)
            x = body_rect.left()
            while x < body_rect.right():
                painter.drawRect(QRectF(x, body_rect.top(), min(slot_w - 1, body_rect.right() - x), body_rect.height()))
                x += slot_w
        else:
            bars = max(6, int(body_rect.width() / 8))
            bar_w = body_rect.width() / bars
            mid_y = body_rect.center().y()
            for i in range(bars):
                h = body_rect.height() * (0.2 + (i % 3) * 0.15)
                painter.drawRect(QRectF(body_rect.left() + i * bar_w, mid_y - h / 2, max(1.0, bar_w - 1), h))

    def _paint_waveform(self, painter: QPainter, body_rect: QRectF) -> None:
        bars = waveform_sample_count(body_rect.width(), self._px_per_sec)
        loading = not self.clip.waveform_cache
        if self.clip.waveform_cache:
            amplitudes = _resample(self.clip.waveform_cache, bars)
        else:
            amplitudes = _synthetic_wave_amplitudes(self.clip.id, bars)

        mid_y = body_rect.center().y()
        max_h = body_rect.height() * 0.88
        path = QPainterPath()
        path.moveTo(body_rect.left(), mid_y)

        bar_w = body_rect.width() / bars
        for i, amp in enumerate(amplitudes):
            x = body_rect.left() + i * bar_w + bar_w / 2
            h = amp * max_h
            path.lineTo(x, mid_y - h / 2)

        for i in range(bars - 1, -1, -1):
            amp = amplitudes[i]
            x = body_rect.left() + i * bar_w + bar_w / 2
            h = amp * max_h
            path.lineTo(x, mid_y + h / 2)

        path.closeSubpath()
        fill = QColor(255, 255, 255, 90 if loading else 190)
        stroke = QColor(255, 255, 255, 40 if loading else 80)
        if self._is_selected:
            fill = QColor(255, 255, 255, 130 if loading else 230)
            stroke = QColor(255, 255, 255, 100)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(stroke, 0.8))
        painter.setBrush(fill)
        painter.drawPath(path)

    def _handle_zone(self, local_x: float) -> str:
        return _handle_zone(
            self._width_px,
            local_x,
            selected_or_hover=bool(self._is_selected or self._hover_handle),
        )

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        zone = self._handle_zone(event.pos().x())
        if zone == "trim_left" or zone == "trim_right":
            self._hover_handle = zone
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self._hover_handle = None
            self.setCursor(Qt.CursorShape.OpenHandCursor if self._drag_mode != "move" else Qt.CursorShape.ClosedHandCursor)
        self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        self._hover_handle = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            if event.button() == Qt.MouseButton.RightButton:
                event.accept()
            return
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        self.selection_requested.emit(self.clip.id, ctrl, shift)
        self.selected_requested.emit(self.clip.id)
        self._drag_mode = self._handle_zone(event.pos().x())
        self._press_scene_x = event.scenePos().x()
        self._press_scene_y = event.scenePos().y()
        self._orig_start = self.clip.start
        self._orig_duration = self.clip.duration
        self._orig_trim_start = self.clip.trim_start
        self._preview_start = self.clip.start
        self._preview_duration = self.clip.duration
        self._preview_row_index = self._orig_row_index
        self._preview_track_id = self.track.id
        if self._drag_mode == "move":
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:  # noqa: N802
        self.context_menu_requested.emit(self.clip.id, event.scenePos())
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._drag_mode is None or self._px_per_sec <= 0:
            return
        dx_px = event.scenePos().x() - self._press_scene_x
        dt = dx_px / self._px_per_sec
        alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        min_start = 0.0
        max_duration: float | None = None
        if self._media_trim_bounds is not None:
            min_start, max_duration = self._media_trim_bounds(self._orig_start, self._orig_trim_start)

        if self._drag_mode == "move":
            raw_start = max(0.0, self._orig_start + dt)
            if self._snap_move is not None:
                result = self._snap_move(raw_start, self._orig_duration, alt)
                new_start = result.time
                self._snap_edge = result.edge if result.snapped else "none"
                self.snap_guides_changed.emit(result)
            else:
                new_start = snap(raw_start)
                self._snap_edge = "none"
                self.snap_guides_changed.emit(SnapResult(time=new_start, snapped=False))
            self._preview_start = new_start
            self._apply_row_preview(event.scenePos().y())
            self.setPos(new_start * self._px_per_sec, self._row_y(self._preview_row_index))
            self.update()
        elif self._drag_mode == "trim_right":
            raw_duration = max(_MIN_CLIP_DURATION_PREVIEW, self._orig_duration + dt)
            if max_duration is not None:
                raw_duration = min(raw_duration, max_duration)
            if self._snap_trim is not None:
                _start, new_duration, result = self._snap_trim("trim_right", self._orig_start, raw_duration, alt)
                if max_duration is not None:
                    new_duration = min(new_duration, max_duration)
                self._snap_edge = result.edge if result.snapped else "none"
                self.snap_guides_changed.emit(result)
            else:
                new_duration = snap(raw_duration)
                self._snap_edge = "none"
                self.snap_guides_changed.emit(SnapResult(time=self._orig_start + new_duration, snapped=False))
            self._preview_duration = new_duration
            self.prepareGeometryChange()
            self._width_px = max(MIN_CLIP_WIDTH_PX, new_duration * self._px_per_sec)
            self.update()
        elif self._drag_mode == "trim_left":
            raw_start = max(min_start, self._orig_start + dt)
            delta = raw_start - self._orig_start
            raw_duration = self._orig_duration - delta
            if raw_duration > _MIN_CLIP_DURATION_PREVIEW:
                if self._snap_trim is not None:
                    new_start, new_duration, result = self._snap_trim("trim_left", raw_start, raw_duration, alt)
                    if new_start < min_start:
                        new_start = min_start
                        new_duration = max(_MIN_CLIP_DURATION_PREVIEW, self._orig_start + self._orig_duration - new_start)
                    self._snap_edge = result.edge if result.snapped else "none"
                    self.snap_guides_changed.emit(result)
                else:
                    new_start = snap(raw_start)
                    new_duration = snap(raw_duration)
                    self._snap_edge = "none"
                    self.snap_guides_changed.emit(SnapResult(time=new_start, snapped=False))
                self._preview_start = new_start
                self._preview_duration = new_duration
                self.prepareGeometryChange()
                self.setPos(new_start * self._px_per_sec, self.y())
                self._width_px = max(MIN_CLIP_WIDTH_PX, new_duration * self._px_per_sec)
                self.update()
        self.edge_scroll_requested.emit(event.scenePos().x(), event.scenePos().y())
        event.accept()

    def _apply_row_preview(self, scene_y: float) -> None:
        if self._row_resolver is None:
            self._preview_row_index = self._orig_row_index
            self._preview_track_id = self.track.id
            return
        row, track_id = self._row_resolver(scene_y)
        self._preview_row_index = row
        self._preview_track_id = track_id if track_id is not None else self.track.id

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._drag_mode is None:
            return
        mode, self._drag_mode = self._drag_mode, None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._snap_edge = "none"
        self.snap_guides_changed.emit(SnapResult(time=self._preview_start, snapped=False))
        dx_px = event.scenePos().x() - self._press_scene_x
        moved = abs(dx_px) >= 1 or (
            mode == "move" and self._preview_row_index != self._orig_row_index
        )
        if moved:
            if mode == "move":
                if self._row_resolver is not None:
                    _, target_id = self._row_resolver(
                        self._preview_row_index * TRACK_HEIGHT + TRACK_HEIGHT / 2
                    )
                else:
                    target_id = self.track.id
                self.move_committed.emit(
                    self.clip.id,
                    self._preview_start,
                    target_id,
                    self._preview_row_index,
                )
            elif mode in ("trim_left", "trim_right"):
                side = "left" if mode == "trim_left" else "right"
                self.trim_committed.emit(self.clip.id, side, dx_px / self._px_per_sec if self._px_per_sec else 0.0)
        event.accept()
