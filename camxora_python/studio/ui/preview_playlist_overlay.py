"""Drag-to-move / corner-resize overlay for playlist template components."""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from studio.core.playlist_layout import (
    is_standalone_track_list_layout,
    resolve_component_layout,
    rect_to_pixels,
    standalone_song_list_rect_norm,
)
from studio.core.playlist_settings import COMPONENT_LABELS, PLAYLIST_COMPONENTS
from studio.core.preview_drag_log import DragShapeWatch, log_drag_event
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

_drag_log = logging.getLogger("camxora.preview.drag")


class PreviewPlaylistOverlay(QWidget):
    """Transparent overlay — select, drag, and resize playlist components on the preview."""

    preview_changed = Signal()
    layout_committed = Signal()

    _HANDLE = 8
    _logged_drag_hint = False

    def __init__(self, project_state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_state = project_state
        prepare_transparent_overlay(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(True)
        self._canvas_rect = QRect()
        self._component_rects: dict[str, QRect] = {}
        self._drag_mode: str | None = None
        self._drag_component: str | None = None
        self._drag_start: QPointF | None = None
        self._start_rect: dict[str, float] | None = None
        self._live_norm: dict[str, float] | None = None
        self._shape_watch = DragShapeWatch()
        self._prev_drag_rect: QRect | None = None

    @property
    def is_dragging(self) -> bool:
        return self._drag_mode is not None

    def set_canvas_rect(self, rect: QRect) -> None:
        prev = QRect(self._canvas_rect)
        self._canvas_rect = rect
        self.setGeometry(rect)
        if self._drag_mode is not None and prev.size() != rect.size():
            canvas_w, canvas_h = self._canvas_size()
            log_drag_event(
                "canvas_resize_during_drag",
                comp_id=self._drag_component,
                norm=self._live_norm,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                detail=f"widget {prev.width()}x{prev.height()} -> {rect.width()}x{rect.height()}",
            )
        if self._drag_mode is None:
            self._sync_from_state()
        elif self._live_norm is not None and self._drag_component:
            self._component_rects[self._drag_component] = self._widget_rect_from_norm(self._live_norm)
        self.update()

    def _canvas_size(self) -> tuple[int, int]:
        return self.project_state.canvas_size()

    def _widget_rect_from_norm(self, norm: dict[str, float]) -> QRect:
        canvas_w, canvas_h = self._canvas_size()
        if canvas_w <= 0 or canvas_h <= 0 or self._canvas_rect.isEmpty():
            return QRect()
        sx = self._canvas_rect.width() / canvas_w
        sy = self._canvas_rect.height() / canvas_h
        x, y, w, h = rect_to_pixels(norm, canvas_w, canvas_h)
        return QRect(
            int(round(x * sx)),
            int(round(y * sy)),
            max(1, int(round(w * sx))),
            max(1, int(round(h * sy))),
        )

    def _sync_from_state(self) -> None:
        if self._drag_mode is not None:
            canvas_w, canvas_h = self._canvas_size()
            log_drag_event(
                "sync_from_state_skipped",
                comp_id=self._drag_component,
                norm=self._live_norm,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                detail="called while dragging — overlay uses live_norm only",
            )
            return
        if (
            not self.project_state.playlist_preview_active
            or not self.project_state.playlist_overlay_enabled
            or self._canvas_rect.isEmpty()
        ):
            self._component_rects = {}
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            return

        settings = self.project_state.project.playlist
        canvas_w, canvas_h = self._canvas_size()
        if canvas_w <= 0 or canvas_h <= 0:
            self._component_rects = {}
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            return

        layout = resolve_component_layout(settings, canvas_w=canvas_w, canvas_h=canvas_h)
        if is_standalone_track_list_layout(settings):
            rect = layout.get("song_list")
            if not rect:
                self._component_rects = {}
                self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                return
            self._component_rects = {"song_list": self._widget_rect_from_norm(rect)}
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            return

        rects: dict[str, QRect] = {}
        for comp_id in settings.component_order:
            if comp_id not in PLAYLIST_COMPONENTS:
                continue
            rect = layout.get(comp_id)
            if not rect:
                continue
            rects[comp_id] = self._widget_rect_from_norm(rect)
        self._component_rects = rects
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not bool(rects))

    def refresh(self) -> None:
        if self._drag_mode is None:
            self._sync_from_state()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._component_rects:
            return
        settings = self.project_state.project.playlist
        minimal = is_standalone_track_list_layout(settings)
        selected = self.project_state.project.playlist.selected_component
        dragging = self._drag_mode is not None
        painter = QPainter(self)
        if dragging:
            begin_overlay_frame(painter, event.rect())
        else:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for comp_id, rect in self._component_rects.items():
            is_selected = comp_id == selected or (minimal and comp_id == "song_list")
            color = OVERLAY_ACCENT if is_selected else Qt.GlobalColor.white
            if dragging and is_selected:
                painter.fillRect(rect, OVERLAY_GHOST_FILL)
            pen = QPen(color, 2 if is_selected else 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            if not minimal:
                label = COMPONENT_LABELS.get(comp_id, comp_id)
                painter.setPen(color)
                painter.drawText(
                    rect.adjusted(4, 2, -4, -2),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    label,
                )
            if is_selected and not minimal:
                handle = self._HANDLE
                for corner in (
                    rect.topLeft(),
                    rect.topRight(),
                    rect.bottomLeft(),
                    rect.bottomRight(),
                ):
                    painter.fillRect(
                        corner.x() - handle // 2,
                        corner.y() - handle // 2,
                        handle,
                        handle,
                        color,
                    )
        painter.end()

    def _hit_test(self, pos: QPointF) -> tuple[str | None, str | None]:
        selected = self.project_state.project.playlist.selected_component
        if selected and selected in self._component_rects:
            rect = self._component_rects[selected]
            mode = self._hit_rect(rect, pos)
            if mode:
                return selected, mode

        for comp_id in reversed(list(self._component_rects)):
            rect = self._component_rects[comp_id]
            if rect.contains(pos.toPoint()):
                return comp_id, "move"
        return None, None

    def _hit_rect(self, rect: QRect, pos: QPointF) -> str | None:
        h = self._HANDLE + 4
        half = h // 2
        corners: list[tuple[str, QPoint]] = [
            ("scale_tl", rect.topLeft()),
            ("scale_tr", rect.topRight()),
            ("scale_bl", rect.bottomLeft()),
            ("scale_br", rect.bottomRight()),
        ]
        for mode, corner in corners:
            handle_rect = QRect(corner.x() - half, corner.y() - half, h, h)
            if handle_rect.contains(pos.toPoint()):
                return mode
        if rect.contains(pos.toPoint()):
            return "move"
        return None

    def _norm_rect_for(self, comp_id: str) -> dict[str, float]:
        settings = self.project_state.project.playlist
        canvas_w, canvas_h = self._canvas_size()
        if is_standalone_track_list_layout(settings) and comp_id == "song_list":
            stored = settings.component_layout.get("song_list") or {}
            return standalone_song_list_rect_norm(
                settings,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                x=float(stored["x"]) if "x" in stored else None,
                y=float(stored["y"]) if "y" in stored else None,
            )

        layout = resolve_component_layout(settings, canvas_w=canvas_w, canvas_h=canvas_h)
        rect = dict(layout.get(comp_id, {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}))
        stored = settings.component_layout.get(comp_id)
        if stored:
            rect.update({k: float(v) for k, v in stored.items() if k in ("x", "y", "w", "h")})
        return rect

    def _commit_norm_to_state(self, comp_id: str, norm: dict[str, float], *, move_only: bool) -> None:
        canvas_w, canvas_h = self._canvas_size()
        stored_before = dict(self.project_state.project.playlist.component_layout.get(comp_id) or {})
        if move_only:
            self.project_state.update_playlist_component(
                comp_id,
                record_undo=False,
                x=norm["x"],
                y=norm["y"],
            )
        else:
            self.project_state.update_playlist_component(
                comp_id,
                record_undo=False,
                x=norm["x"],
                y=norm["y"],
                w=norm["w"],
                h=norm["h"],
            )
        stored_after = dict(self.project_state.project.playlist.component_layout.get(comp_id) or {})
        log_drag_event(
            "commit",
            comp_id=comp_id,
            norm=norm,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            stored_layout=stored_after,
            detail=f"move_only={move_only} stored_before={stored_before}",
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        comp_id, mode = self._hit_test(event.position())
        if comp_id is None or mode is None:
            self.project_state.set_playlist_selected_component(None)
            self.update()
            return
        settings = self.project_state.project.playlist
        move_only = is_standalone_track_list_layout(settings)
        if move_only:
            comp_id = "song_list"
            mode = "move"
        self.project_state.set_playlist_selected_component(comp_id)
        self._drag_component = comp_id
        self._drag_mode = mode
        self._drag_start = event.position()
        start = self._norm_rect_for(comp_id)
        self._start_rect = start
        self._live_norm = dict(start)
        canvas_w, canvas_h = self._canvas_size()
        widget_rect = self._widget_rect_from_norm(start)
        self._component_rects[comp_id] = widget_rect
        self._prev_drag_rect = QRect(widget_rect)
        self._shape_watch.reset(start, widget_rect)
        if not PreviewPlaylistOverlay._logged_drag_hint:
            PreviewPlaylistOverlay._logged_drag_hint = True
            from studio.app.logging_config import log_file_path

            _drag_log.info(
                "Playlist drag diagnostics ON — filter logs with 'camxora.preview.drag' "
                "(console + %s). Set CAMXORA_DRAG_LOG=1 for verbose move samples.",
                log_file_path(),
            )
        log_drag_event(
            "press",
            comp_id=comp_id,
            norm=start,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            widget_rect=widget_rect,
            stored_layout=settings.component_layout.get(comp_id),
            detail=f"mode={mode} standalone={move_only} sub={settings.sub_template_id}",
        )
        # Lock intrinsic card size before drag — compositor is paused until release.
        self._commit_norm_to_state(comp_id, start, move_only=False)
        self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_mode is None or self._drag_start is None or self._drag_component is None:
            return
        if self._start_rect is None:
            return
        comp_id = self._drag_component
        delta = event.position() - self._drag_start
        cw = max(1, self._canvas_rect.width())
        ch = max(1, self._canvas_rect.height())
        dx = delta.x() / cw
        dy = delta.y() / ch
        rect = dict(self._start_rect)

        if self._drag_mode == "move":
            rect["x"] = clamp(rect["x"] + dx, 0.0, 1.0 - rect["w"])
            rect["y"] = clamp(rect["y"] + dy, 0.0, 1.0 - rect["h"])
        elif self._drag_mode.startswith("scale_"):
            corner = self._drag_mode.split("_", 1)[1]
            if corner.endswith("l"):
                new_w = clamp(rect["w"] - dx, 0.06, 1.0)
                rect["x"] = clamp(rect["x"] + dx, 0.0, 1.0 - new_w)
                rect["w"] = new_w
            else:
                rect["w"] = clamp(rect["w"] + dx, 0.06, 1.0 - rect["x"])
            if corner.startswith("t"):
                new_h = clamp(rect["h"] - dy, 0.04, 1.0)
                rect["y"] = clamp(rect["y"] + dy, 0.0, 1.0 - new_h)
                rect["h"] = new_h
            else:
                rect["h"] = clamp(rect["h"] + dy, 0.04, 1.0 - rect["y"])

        self._live_norm = rect
        new_rect = self._widget_rect_from_norm(rect)
        self._component_rects[comp_id] = new_rect
        canvas_w, canvas_h = self._canvas_size()
        self._shape_watch.check_move(
            rect,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            widget_rect=new_rect,
            comp_id=comp_id,
        )
        dirty = drag_dirty_rect(self._prev_drag_rect, new_rect)
        repaint_parent_region(self, dirty)
        self._prev_drag_rect = QRect(new_rect)
        self.update(dirty)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_mode is not None:
            self.releaseMouse()
        if event.button() == Qt.MouseButton.LeftButton and self._drag_mode is not None:
            comp_id = self._drag_component or "song_list"
            canvas_w, canvas_h = self._canvas_size()
            if self._live_norm is not None and self._drag_component:
                move_only = (
                    is_standalone_track_list_layout(self.project_state.project.playlist)
                    or self._drag_mode == "move"
                )
                log_drag_event(
                    "release_before_commit",
                    comp_id=comp_id,
                    norm=self._live_norm,
                    canvas_w=canvas_w,
                    canvas_h=canvas_h,
                    widget_rect=self._component_rects.get(comp_id),
                    detail=f"mode={self._drag_mode} move_only={move_only}",
                )
                self._commit_norm_to_state(self._drag_component, self._live_norm, move_only=move_only)
            self._shape_watch.summary(comp_id)
            self.layout_committed.emit()
        if self._prev_drag_rect is not None:
            comp_id = self._drag_component or "song_list"
            final = self._component_rects.get(comp_id)
            if final is not None:
                repaint_parent_region(self, drag_dirty_rect(self._prev_drag_rect, final))
        self._prev_drag_rect = None
        self._drag_mode = None
        self._drag_start = None
        self._drag_component = None
        self._start_rect = None
        self._live_norm = None
        self._shape_watch.clear()
        self._sync_from_state()
        self.update()
        event.accept()
