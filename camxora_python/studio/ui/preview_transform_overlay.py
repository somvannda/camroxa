"""Drag-to-move / corner-drag-to-scale for the selected image or video clip."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from studio.core.models import Clip
from studio.core.project_state import ProjectState
from studio.core.time_utils import clamp
from studio.ui.preview_overlay_utils import (
    OVERLAY_ACCENT,
    OVERLAY_GHOST_FILL,
    begin_overlay_frame,
    drag_dirty_rect,
    prepare_transparent_overlay,
    repaint_parent_region,
)
from studio.render.clip_geometry import clip_dest_rect, clip_source_size
from studio.render.compositor import _load_image_rgb


class PreviewTransformOverlay(QWidget):
    """Transparent overlay on the preview canvas — drag body to move, corners to scale."""

    preview_changed = Signal()
    transform_committed = Signal()

    _HANDLE = 8

    def __init__(self, project_state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_state = project_state
        prepare_transparent_overlay(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(True)
        self._canvas_rect = QRect()
        self._clip_rect = QRect()
        self._active_clip_id: str | None = None
        self._drag_mode: str | None = None
        self._drag_start: QPointF | None = None
        self._start_scale = 1.0
        self._start_pos = (0.5, 0.5)
        self._cached_src_size: tuple[int, int] | None = None
        self._pending_tx: float | None = None
        self._pending_ty: float | None = None
        self._pending_scale: float | None = None
        self._prev_drag_rect: QRect | None = None

    @property
    def is_dragging(self) -> bool:
        return self._drag_mode is not None

    def set_canvas_rect(self, rect: QRect) -> None:
        self._canvas_rect = rect
        self.setGeometry(rect)
        if self._drag_mode is None:
            self._sync_from_state()
        elif self._active_clip_id:
            ref = self.project_state.get_clip(self._active_clip_id)
            if ref is not None:
                _track, clip = ref
                if self._cached_src_size:
                    sw, sh = self._cached_src_size
                    self._rect_for_clip(clip, src_w=sw, src_h=sh)
        self.update()

    def _selected_visual_clip(self) -> Clip | None:
        clip_id = self.project_state.selected_clip_id
        if not clip_id:
            return None
        ref = self.project_state.get_clip(clip_id)
        if ref is None:
            return None
        _track, clip = ref
        if clip.kind not in ("image", "video"):
            return None
        return clip

    def _rect_for_clip(self, clip: Clip, *, src_w: int | None = None, src_h: int | None = None) -> None:
        if src_w is None or src_h is None:
            src_w, src_h = self._project_frame_size(clip)
        canvas_w, canvas_h = self.project_state.canvas_size()
        preview_clip = clip
        if self._pending_tx is not None or self._pending_ty is not None or self._pending_scale is not None:
            preview_clip = replace(
                clip,
                transform_x=self._pending_tx if self._pending_tx is not None else clip.transform_x,
                transform_y=self._pending_ty if self._pending_ty is not None else clip.transform_y,
                transform_scale=self._pending_scale if self._pending_scale is not None else clip.transform_scale,
            )
        x0, y0, dw, dh = clip_dest_rect(preview_clip, src_w, src_h, canvas_w, canvas_h)
        if self._canvas_rect.width() <= 0 or self._canvas_rect.height() <= 0:
            self._clip_rect = QRect()
            return
        sx = self._canvas_rect.width() / canvas_w
        sy = self._canvas_rect.height() / canvas_h
        self._clip_rect = QRect(
            int(round(x0 * sx)),
            int(round(y0 * sy)),
            max(1, int(round(dw * sx))),
            max(1, int(round(dh * sy))),
        )

    def _sync_from_state(self) -> None:
        clip = self._selected_visual_clip()
        if clip is None or self._canvas_rect.isEmpty():
            self._active_clip_id = None
            self._clip_rect = QRect()
            self._cached_src_size = None
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            return

        self._active_clip_id = clip.id
        if self._drag_mode and self._cached_src_size:
            sw, sh = self._cached_src_size
            self._rect_for_clip(clip, src_w=sw, src_h=sh)
        else:
            self._rect_for_clip(clip)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def _project_frame_size(self, clip: Clip) -> tuple[int, int]:
        media = self.project_state.get_media(clip.media_id)
        if media is None:
            return 0, 0
        if clip.kind == "image":
            frame = _load_image_rgb(media.path)
            return clip_source_size(clip, frame)
        width = media.width or self.project_state.canvas_size()[0]
        height = media.height or self.project_state.canvas_size()[1]
        return clip_source_size(clip, None, fallback_w=width, fallback_h=height)

    def refresh(self) -> None:
        if self._drag_mode is None:
            self._sync_from_state()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._clip_rect.isEmpty():
            return
        painter = QPainter(self)
        if self._drag_mode is not None:
            begin_overlay_frame(painter, event.rect())
        else:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._drag_mode is not None:
            painter.fillRect(self._clip_rect, OVERLAY_GHOST_FILL)
        pen = QPen(OVERLAY_ACCENT, 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._clip_rect)
        handle = self._HANDLE
        for corner in (
            self._clip_rect.topLeft(),
            self._clip_rect.topRight(),
            self._clip_rect.bottomLeft(),
            self._clip_rect.bottomRight(),
        ):
            painter.fillRect(
                corner.x() - handle // 2,
                corner.y() - handle // 2,
                handle,
                handle,
                OVERLAY_ACCENT,
            )
        painter.end()

    def _hit_test(self, pos: QPointF) -> str | None:
        if self._clip_rect.isEmpty():
            return None
        h = self._HANDLE + 4
        half = h // 2
        corners: list[tuple[str, QPoint]] = [
            ("scale_tl", self._clip_rect.topLeft()),
            ("scale_tr", self._clip_rect.topRight()),
            ("scale_bl", self._clip_rect.bottomLeft()),
            ("scale_br", self._clip_rect.bottomRight()),
        ]
        for mode, corner in corners:
            rect = QRect(corner.x() - half, corner.y() - half, h, h)
            if rect.contains(pos.toPoint()):
                return mode
        if self._clip_rect.contains(pos.toPoint()):
            return "move"
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        clip = self._selected_visual_clip()
        if clip is None:
            return
        mode = self._hit_test(event.position())
        if mode is None:
            return
        self._drag_mode = mode
        self._drag_start = event.position()
        self._start_scale = float(clip.transform_scale or 1.0)
        self._start_pos = (
            float(clip.transform_x if clip.transform_x is not None else 0.5),
            float(clip.transform_y if clip.transform_y is not None else 0.5),
        )
        self._cached_src_size = self._project_frame_size(clip)
        self._pending_tx = None
        self._pending_ty = None
        self._pending_scale = None
        self._prev_drag_rect = QRect(self._clip_rect)
        self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        clip_id = self._active_clip_id
        if self._drag_mode is None or self._drag_start is None or clip_id is None:
            return
        ref = self.project_state.get_clip(clip_id)
        if ref is None:
            return
        _track, clip = ref
        delta = event.position() - self._drag_start

        if self._drag_mode == "move":
            dx = delta.x() / max(1, self._canvas_rect.width())
            dy = delta.y() / max(1, self._canvas_rect.height())
            self._pending_tx = clamp(self._start_pos[0] + dx, 0.0, 1.0)
            self._pending_ty = clamp(self._start_pos[1] + dy, 0.0, 1.0)
        elif self._drag_mode.startswith("scale_"):
            base = max(self._clip_rect.width(), self._clip_rect.height(), 1)
            factor = 1.0 + (delta.x() + delta.y()) / (base * 2.0)
            self._pending_scale = clamp(self._start_scale * factor, 0.1, 5.0)

        if self._cached_src_size:
            sw, sh = self._cached_src_size
            self._rect_for_clip(clip, src_w=sw, src_h=sh)
        else:
            self._rect_for_clip(clip)
        dirty = drag_dirty_rect(self._prev_drag_rect, self._clip_rect)
        repaint_parent_region(self, dirty)
        self._prev_drag_rect = QRect(self._clip_rect)
        self.update(dirty)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_mode is not None:
            self.releaseMouse()
        if event.button() == Qt.MouseButton.LeftButton and self._drag_mode is not None:
            clip_id = self._active_clip_id
            if clip_id:
                fields: dict[str, float] = {}
                if self._pending_tx is not None:
                    fields["transform_x"] = self._pending_tx
                if self._pending_ty is not None:
                    fields["transform_y"] = self._pending_ty
                if self._pending_scale is not None:
                    fields["transform_scale"] = self._pending_scale
                if fields:
                    self.project_state.update_clip(clip_id, record_undo=False, **fields)
                ref = self.project_state.get_clip(clip_id)
                if ref:
                    _track, clip = ref
                    self.project_state.update_clip(
                        clip_id,
                        transform_scale=clip.transform_scale,
                        transform_x=clip.transform_x,
                        transform_y=clip.transform_y,
                    )
            self.transform_committed.emit()
        if self._prev_drag_rect is not None and not self._clip_rect.isEmpty():
            repaint_parent_region(self, drag_dirty_rect(self._prev_drag_rect, self._clip_rect))
        self._prev_drag_rect = None
        self._drag_mode = None
        self._drag_start = None
        self._cached_src_size = None
        self._pending_tx = None
        self._pending_ty = None
        self._pending_scale = None
        self._sync_from_state()
        event.accept()
