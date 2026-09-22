"""Multi-track timeline: toolbar + track headers + scrollable track lanes.

QGraphicsView-based engine: track lanes + clip items live in a QGraphicsScene
(`TimelineGraphicsView`), while the ruler and track headers are separate
widgets kept in sync with the view's scrollbars (see module-level comment in
`ui/timeline/ruler.py` for why).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from studio.core.time_utils import clamp
from studio.core.models import MediaAsset
from studio.core.project_state import ProjectState
from studio.media.audio_source import load_audio_source
from studio.media.media_loader import FILMSTRIP_SIZE, build_video_filmstrip, default_cache_dir
from studio.ui.icons.lucide_icons import (
    BTN_SZ_TOOLBAR,
    ICON_COLOR,
    ICON_COLOR_ACTIVE,
    ICON_SZ_TOOLBAR,
    TRACK_TYPE_ICON,
    set_button_lucide_icon,
)
from studio.ui.library_panel import FILTER_MIME_TYPE, MEDIA_MIME_TYPE, TEXT_PRESET_MIME_TYPE
from studio.ui.timeline.clip_item import ClipGraphicsItem
from studio.ui.timeline.drop_ghost import DropGhostItem
from studio.ui.timeline.geometry import (
    CLIP_HEIGHT,
    MAX_PX_PER_SEC,
    MINIMAP_HEIGHT,
    MIN_CLIP_WIDTH_PX,
    MIN_PX_PER_SEC,
    RULER_HEIGHT,
    TRACK_HEADER_WIDTH,
    TRACK_HEIGHT,
    VIEWPORT_CULL_BUFFER_ROWS,
    VIEWPORT_CULL_BUFFER_X_RATIO,
    ZOOM_DEBOUNCE_MS,
    hi_dpi_filmstrip_size,
    timeline_width_px,
    effective_timeline_width_px,
    visible_track_rows,
    zoom_wheel_step,
)
from studio.ui.timeline.playhead_item import PlayheadItem
from studio.ui.timeline.ruler import TimelineRuler
from studio.ui.timeline.snap_engine import SnapContext, SnapResult, snap_clip_move, snap_clip_trim, snap_time
from studio.ui.timeline.snap_feedback import play_snap_click
from studio.ui.timeline.snap_popover import SnapSettingsPopover
from studio.ui.timeline.timeline_minimap import TimelineMinimap
from studio.ui.timeline.track_header import TrackHeaders
from studio.ui.timeline.track_lane_item import TrackLaneItem

logger = logging.getLogger(__name__)

_WAVEFORM_ENVELOPE_BARS = 60
_MARQUEE_DRAG_THRESHOLD_PX = 5


class _MarqueeRubberBand(QGraphicsRectItem):
    def __init__(self) -> None:
        super().__init__()
        self.setZValue(20.0)
        self.setPen(QPen(QColor("#7466F1"), 1, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(116, 102, 241, 50)))
        self.setVisible(False)


class _ClipPreviewWorker(QThread):
    """Computes a video clip's filmstrip thumbnails or an audio clip's real
    amplitude envelope off the UI thread, right after the clip is created.

    Without this, video clips show no filmstrip (nothing ever populated
    `Clip.thumb_cache`) and audio clips show a fake, deterministic
    pseudo-random waveform instead of the clip's actual sound — and doing
    either synchronously on drop would repeat the same "freeze the UI"
    mistake the media-import pipeline had (see `ui/library_panel.py`'s
    `MediaImportWorker`).
    """

    filmstrip_ready = Signal(str, list)  # clip_id, thumb paths
    waveform_ready = Signal(str, list)  # clip_id, amplitude envelope (0..1 floats)

    def __init__(
        self,
        clip_id: str,
        media: MediaAsset,
        trim_start: float,
        duration: float,
        device_pixel_ratio: float = 1.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.clip_id = clip_id
        self.media = media
        self.trim_start = trim_start
        self.duration = duration
        self.device_pixel_ratio = max(1.0, device_pixel_ratio)

    def run(self) -> None:  # noqa: D401
        try:
            if self.media.type == "video":
                strip_size = hi_dpi_filmstrip_size(FILMSTRIP_SIZE, self.device_pixel_ratio)
                thumbs = build_video_filmstrip(
                    Path(self.media.path),
                    self.media.duration,
                    default_cache_dir(),
                    size=strip_size,
                )
                if thumbs:
                    self.filmstrip_ready.emit(self.clip_id, thumbs)
            elif self.media.type == "audio":
                source = load_audio_source(self.media.path, self.media.type, default_cache_dir())
                if source is not None:
                    envelope = source.get_amplitude_envelope(
                        self.trim_start, self.duration, _WAVEFORM_ENVELOPE_BARS
                    )
                    self.waveform_ready.emit(self.clip_id, envelope.tolist())
        except Exception:
            logger.exception("Clip preview generation failed for %s", self.media.path)


class TimelineEditToolbar(QFrame):
    """Edit tools — split, delete, snap, tracks, zoom (transport is separate)."""

    _ICON_SIZE = BTN_SZ_TOOLBAR
    _TOOLBAR_ICONS: dict[str, str] = {
        "split": "scissors",
        "delete": "trash-2",
        "snap": "magnet",
        "ripple": "arrow-left-right",
        "settings": "settings",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TimelineToolbar")
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self.split_btn = self._icon_btn("split", "Split clip at playhead (S)")
        layout.addWidget(self.split_btn)

        self.delete_btn = self._icon_btn("delete", "Delete selected (Del)")
        layout.addWidget(self.delete_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(sep)

        self.ripple_btn = self._icon_btn("ripple", "Ripple edit — shifts downstream clips (R)", checkable=True)
        layout.addWidget(self.ripple_btn)

        self.snap_toggle_btn = self._icon_btn("snap", "Toggle magnetic snap (N)", checkable=True)
        self.snap_toggle_btn.setChecked(True)
        layout.addWidget(self.snap_toggle_btn)

        self.snap_settings_btn = self._icon_btn("settings", "Snap settings")
        layout.addWidget(self.snap_settings_btn)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(sep2)

        self.add_video_track_btn = self._track_add_btn("video", "Add video track")
        self.add_audio_track_btn = self._track_add_btn("audio", "Add audio track")
        self.add_overlay_track_btn = self._track_add_btn("overlay", "Add overlay track")
        for btn in (self.add_video_track_btn, self.add_audio_track_btn, self.add_overlay_track_btn):
            layout.addWidget(btn)

        layout.addStretch(1)

        zoom_label = QLabel("Zoom")
        zoom_label.setObjectName("ZoomLabel")
        layout.addWidget(zoom_label)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setObjectName("ZoomSlider")
        self.zoom_slider.setRange(int(MIN_PX_PER_SEC), int(MAX_PX_PER_SEC))
        self.zoom_slider.setValue(70)
        self.zoom_slider.setFixedWidth(90)
        layout.addWidget(self.zoom_slider)

    @classmethod
    def _icon_btn(cls, icon_key: str, tooltip: str, *, checkable: bool = False) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("TimelineIconButton")
        btn.setToolTip(tooltip)
        btn.setCheckable(checkable)
        btn.setFixedSize(cls._ICON_SIZE, cls._ICON_SIZE)
        lucide_name = cls._TOOLBAR_ICONS[icon_key]
        color = ICON_COLOR_ACTIVE if icon_key == "snap" and checkable else ICON_COLOR
        set_button_lucide_icon(btn, lucide_name, size=ICON_SZ_TOOLBAR, color=color)
        return btn

    @classmethod
    def _track_add_btn(cls, track_type: str, tooltip: str) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("TrackAddButton")
        btn.setToolTip(tooltip)
        btn.setFixedSize(BTN_SZ_TOOLBAR, BTN_SZ_TOOLBAR)
        icon_name = TRACK_TYPE_ICON.get(track_type, "layers")
        set_button_lucide_icon(btn, icon_name, size=ICON_SZ_TOOLBAR, color=ICON_COLOR)
        return btn

    @classmethod
    def refresh_snap_icon(cls, btn: QPushButton, enabled: bool) -> None:
        set_button_lucide_icon(
            btn,
            cls._TOOLBAR_ICONS["snap"],
            size=ICON_SZ_TOOLBAR,
            color=ICON_COLOR_ACTIVE if enabled else ICON_COLOR,
        )


    @classmethod
    def refresh_ripple_icon(cls, btn: QPushButton, enabled: bool) -> None:
        set_button_lucide_icon(
            btn,
            cls._TOOLBAR_ICONS["ripple"],
            size=ICON_SZ_TOOLBAR,
            color=ICON_COLOR_ACTIVE if enabled else ICON_COLOR,
        )


# Backward-compatible alias used by tests
TimelineToolbar = TimelineEditToolbar


class TimelineGraphicsView(QGraphicsView):
    selection_changed = Signal()
    structure_changed = Signal()
    toast_requested = Signal(str)
    seek_requested = Signal(float)
    zoom_changed = Signal(float)

    def __init__(self, project_state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_state = project_state
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setAcceptDrops(True)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setStyleSheet("background: #111118; border: none;")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self._clip_items: dict[str, ClipGraphicsItem] = {}
        self._lane_items: list[TrackLaneItem] = []
        self._playhead_item: PlayheadItem | None = None
        self._drop_ghost: DropGhostItem | None = None
        self._snap_guide_items: list = []
        self._preview_workers: list[_ClipPreviewWorker] = []
        self._track_ids: list[str] = []
        self._pending_drop_media: MediaAsset | None = None
        self._pending_drop_duration = 5.0
        self._pending_drop_label = ""
        self._pending_drop_type = "video"
        self._lane_scrubbing = False
        self._last_drop_snapped = False
        self._empty_press_pos: QPoint | None = None
        self._empty_press_scene: QPointF | None = None
        self._marquee_active = False
        self._marquee_item: _MarqueeRubberBand | None = None
        self._snap_click_active = False
        self._snap_click_guide: float | None = None
        self._viewport_scroll_timer = QTimer(self)
        self._viewport_scroll_timer.setSingleShot(True)
        self._viewport_scroll_timer.setInterval(16)
        self._viewport_scroll_timer.timeout.connect(self._on_viewport_scroll_debounced)

        self.horizontalScrollBar().valueChanged.connect(self._on_viewport_scroll)
        self.verticalScrollBar().valueChanged.connect(self._on_viewport_scroll)

        self.refresh_from_state(full=True)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_timeline_width_to_viewport()

    def _sync_timeline_width_to_viewport(self) -> None:
        if not self._lane_items:
            return
        total_width, total_height, _ = self._scene_metrics()
        if int(self._scene.sceneRect().width()) == total_width:
            return
        self._resize_lanes(total_width)
        self._scene.setSceneRect(
            0, 0, total_width, max(total_height, self.viewport().height())
        )
        self.structure_changed.emit()

    # ---------------- sync scene from ProjectState ----------------

    def refresh_from_state(self, *, full: bool = False) -> None:
        if full:
            self._full_rebuild()
        else:
            self._incremental_sync()

    def _scene_metrics(self) -> tuple[int, int, float]:
        tracks = self.project_state.project.tracks
        px_per_sec = self.project_state.project.px_per_sec
        duration = self.project_state.project.duration
        total_width = int(effective_timeline_width_px(duration, px_per_sec, self.viewport().width()))
        row_count = visible_track_rows(len(tracks))
        total_height = row_count * TRACK_HEIGHT
        return total_width, total_height, px_per_sec

    def _full_rebuild(self) -> None:
        tracks = self.project_state.project.tracks
        total_width, total_height, px_per_sec = self._scene_metrics()
        duration = self.project_state.project.duration
        self._playhead_item = None
        self._drop_ghost = None
        self._snap_guide_items.clear()
        self._scene.clear()
        self._clip_items.clear()
        self._lane_items.clear()
        self._track_ids = [t.id for t in tracks]
        self._scene.setSceneRect(0, 0, total_width, max(total_height, self.viewport().height()))

        for i, track in enumerate(tracks):
            self._lane_items.append(self._add_lane(i, track, total_width, px_per_sec, duration))

        empty_start = len(tracks)
        row_count = visible_track_rows(len(tracks))
        for i in range(empty_start, row_count):
            self._lane_items.append(self._add_lane(i, None, total_width, px_per_sec, duration))

        self._sync_viewport_clips()

        self._ensure_playhead(total_height)
        if self._drop_ghost is None:
            self._drop_ghost = DropGhostItem()
            self._scene.addItem(self._drop_ghost)
        self.structure_changed.emit()

    def _incremental_sync(self) -> None:
        tracks = self.project_state.project.tracks
        total_width, total_height, px_per_sec = self._scene_metrics()
        track_ids = [t.id for t in tracks]
        structure_changed = False

        if track_ids != self._track_ids:
            self._rebuild_lanes(tracks, total_width, total_height)
            structure_changed = True
        else:
            self._resize_lanes(total_width)
            self._scene.setSceneRect(
                0, 0, total_width, max(total_height, self.viewport().height())
            )

        model_clip_ids = {clip.id for track in tracks for clip in track.clips}
        for clip_id in list(self._clip_items):
            if clip_id not in model_clip_ids:
                item = self._clip_items.pop(clip_id)
                self._scene.removeItem(item)
                structure_changed = True

        track_index = {track.id: i for i, track in enumerate(tracks)}
        if self._sync_viewport_clips(track_index=track_index, px_per_sec=px_per_sec):
            structure_changed = True

        self._apply_selection_visuals()
        self._ensure_playhead(total_height)
        if structure_changed:
            self.structure_changed.emit()

    def _add_lane(
        self,
        row_index: int,
        track,
        total_width: int,
        px_per_sec: float,
        duration: float,
    ) -> TrackLaneItem:
        y = row_index * TRACK_HEIGHT
        track_type = track.type if track is not None else None
        is_empty = track is None
        lane = TrackLaneItem(row_index, track_type, is_empty, total_width, px_per_sec, duration)
        lane.configure(y, TRACK_HEIGHT, total_width, track_type, is_empty, px_per_sec, duration)
        self._scene.addItem(lane)
        return lane

    def _rebuild_lanes(self, tracks, total_width: int, total_height: int) -> None:
        for lane in self._lane_items:
            self._scene.removeItem(lane)
        self._lane_items.clear()
        self._track_ids = [t.id for t in tracks]
        px_per_sec = self.project_state.project.px_per_sec
        duration = self.project_state.project.duration
        self._scene.setSceneRect(0, 0, total_width, max(total_height, self.viewport().height()))
        row_count = visible_track_rows(len(tracks))
        for i in range(row_count):
            track = tracks[i] if i < len(tracks) else None
            self._lane_items.append(self._add_lane(i, track, total_width, px_per_sec, duration))
        track_index = {track.id: i for i, track in enumerate(tracks)}
        self._sync_viewport_clips(track_index=track_index, px_per_sec=px_per_sec)

    def _resize_lanes(self, total_width: int) -> None:
        px_per_sec = self.project_state.project.px_per_sec
        duration = self.project_state.project.duration
        tracks = self.project_state.project.tracks
        for i, lane in enumerate(self._lane_items):
            track = tracks[i] if i < len(tracks) else None
            lane.configure(
                i * TRACK_HEIGHT,
                TRACK_HEIGHT,
                total_width,
                track.type if track else None,
                track is None,
                px_per_sec,
                duration,
            )

    def _snap_ctx(
        self,
        *,
        exclude_clip_id: str | None = None,
        track_id: str | None = None,
        track_type: str | None = None,
        temporary_disabled: bool = False,
        clip_duration: float | None = None,
    ) -> SnapContext:
        return SnapContext(
            project_state=self.project_state,
            px_per_sec=self.project_state.project.px_per_sec,
            exclude_clip_id=exclude_clip_id,
            track_id=track_id,
            track_type=track_type,
            temporary_disabled=temporary_disabled,
            clip_duration=clip_duration,
        )

    def _track_at_row(self, row_index: int):
        tracks = self.project_state.project.tracks
        if 0 <= row_index < len(tracks):
            return tracks[row_index]
        return None

    def _viewport_scene_rect(self) -> QRectF:
        if self.viewport().width() <= 0 or self.viewport().height() <= 0:
            return QRectF(-1e9, -1e9, 2e9, 2e9)
        margin_x = self.viewport().width() * VIEWPORT_CULL_BUFFER_X_RATIO
        margin_y = TRACK_HEIGHT * VIEWPORT_CULL_BUFFER_ROWS
        tl = self.mapToScene(QPoint(0, 0))
        br = self.mapToScene(QPoint(self.viewport().width(), self.viewport().height()))
        return QRectF(
            min(tl.x(), br.x()) - margin_x,
            min(tl.y(), br.y()) - margin_y,
            abs(br.x() - tl.x()) + 2 * margin_x,
            abs(br.y() - tl.y()) + 2 * margin_y,
        )

    @staticmethod
    def _clip_scene_rect(clip, row: int, px_per_sec: float) -> QRectF:
        x = clip.start * px_per_sec
        w = max(MIN_CLIP_WIDTH_PX, clip.duration * px_per_sec)
        y = row * TRACK_HEIGHT + (TRACK_HEIGHT - CLIP_HEIGHT) / 2
        return QRectF(x, y, w, CLIP_HEIGHT)

    def _on_viewport_scroll(self, _value: int = 0) -> None:
        self._viewport_scroll_timer.start()

    def _on_viewport_scroll_debounced(self) -> None:
        self._sync_viewport_clips()

    def _sync_viewport_clips(
        self,
        *,
        track_index: dict[str, int] | None = None,
        px_per_sec: float | None = None,
    ) -> bool:
        """Create/remove clip scene items based on the visible viewport."""
        tracks = self.project_state.project.tracks
        px = px_per_sec if px_per_sec is not None else self.project_state.project.px_per_sec
        track_index = track_index or {track.id: i for i, track in enumerate(tracks)}
        viewport = self._viewport_scene_rect()
        model_clip_ids = {clip.id for track in tracks for clip in track.clips}
        structure_changed = False

        for clip_id in list(self._clip_items):
            if clip_id not in model_clip_ids:
                item = self._clip_items.pop(clip_id)
                self._scene.removeItem(item)
                structure_changed = True
                continue
            ref = self.project_state.get_clip(clip_id)
            if ref is None:
                continue
            track, clip = ref
            row = track_index.get(track.id, 0)
            if not viewport.intersects(self._clip_scene_rect(clip, row, px)):
                item = self._clip_items.pop(clip_id)
                self._scene.removeItem(item)
                structure_changed = True

        for track in tracks:
            row = track_index.get(track.id, 0)
            for clip in track.clips:
                if not viewport.intersects(self._clip_scene_rect(clip, row, px)):
                    continue
                item = self._clip_items.get(clip.id)
                if item is None:
                    self._add_clip_item(track, clip, row, px)
                    structure_changed = True
                else:
                    item.track = track
                    item.clip = clip
                    item.sync_from_model(px, row)

        return structure_changed

    def _apply_snap_feedback(self, result: SnapResult) -> None:
        settings = self.project_state.project.snap_settings
        if not settings.click_feedback:
            return
        if not result.snapped:
            self._snap_click_active = False
            self._snap_click_guide = None
            return
        guide = result.active_guide
        if self._snap_click_active and guide == self._snap_click_guide:
            return
        self._snap_click_active = True
        self._snap_click_guide = guide
        play_snap_click(True)

    def seek_with_snap(self, raw_time: float, *, alt: bool = False) -> float:
        """S8 — snap-aware seek for ruler/lane scrub."""
        result = snap_time(raw_time, self._snap_ctx(temporary_disabled=alt))
        self._apply_snap_feedback(result)
        _, total_height, _ = self._scene_metrics()
        self._set_snap_guides(result, total_height)
        self.project_state.seek(result.time)
        self.update_playhead()
        self.seek_requested.emit(result.time)
        return result.time

    def _add_clip_item(self, track, clip, row_index: int, px_per_sec: float) -> ClipGraphicsItem:
        item = ClipGraphicsItem(track, clip)

        def _move(raw: float, dur: float, alt: bool) -> SnapResult:
            ctx = self._snap_ctx(
                exclude_clip_id=item.clip.id,
                track_id=item.track.id,
                track_type=item.track.type,
                temporary_disabled=alt,
                clip_duration=dur,
            )
            result = snap_clip_move(raw, dur, ctx)
            self._apply_snap_feedback(result)
            return result

        def _trim(side: str, raw_start: float, raw_dur: float, alt: bool) -> tuple[float, float, SnapResult]:
            ctx = self._snap_ctx(
                exclude_clip_id=item.clip.id,
                track_id=item.track.id,
                track_type=item.track.type,
                temporary_disabled=alt,
            )
            start, duration, result = snap_clip_trim(item.clip, side, raw_start, raw_dur, ctx)
            self._apply_snap_feedback(result)
            return start, duration, result

        def _trim_media_bounds(orig_start: float, orig_trim_start: float) -> tuple[float, float | None]:
            ref = self.project_state.get_clip(item.clip.id)
            if ref is None:
                return 0.0, None
            _, live = ref
            min_start = self.project_state.clip_media_min_start(
                orig_start, orig_trim_start, clip_kind=live.kind
            )
            max_dur = self.project_state.clip_media_max_duration(live, orig_trim_start)
            return min_start, max_dur

        def _row_resolver(scene_y: float) -> tuple[int, str | None]:
            row = max(0, int(scene_y // TRACK_HEIGHT))
            track_at_row = self._track_at_row(row)
            return row, track_at_row.id if track_at_row is not None else None

        item.set_snap_callbacks(_move, _trim)
        item.set_media_trim_bounds(_trim_media_bounds)
        item.set_row_resolver(_row_resolver)
        item.sync_geometry(px_per_sec, row_index)
        item.set_selected_visual(clip.id in self.project_state.selected_clip_ids)
        item.selection_requested.connect(self._on_clip_selection_requested)
        item.context_menu_requested.connect(self._on_clip_context_menu)
        item.move_committed.connect(self._on_move_committed)
        item.trim_committed.connect(self._on_trim_committed)
        item.snap_guides_changed.connect(self._on_snap_guides_changed)
        item.edge_scroll_requested.connect(self._on_edge_scroll)
        self._scene.addItem(item)
        self._clip_items[clip.id] = item
        return item

    def _on_snap_guides_changed(self, result: SnapResult) -> None:
        _, total_height, _ = self._scene_metrics()
        self._set_snap_guides(result, total_height)

    def _set_snap_guides(self, result: SnapResult, total_height: float) -> None:
        self._clear_snap_guides()
        px_per_sec = self.project_state.project.px_per_sec
        dim_pen = QPen(QColor(255, 213, 74, 120), 1, Qt.PenStyle.DashLine)
        active_pen = QPen(QColor("#ffd54a"), 2, Qt.PenStyle.SolidLine)
        for t in result.nearby_guides:
            x = t * px_per_sec
            pen = active_pen if result.active_guide is not None and abs(t - result.active_guide) < 1e-9 else dim_pen
            line = self._scene.addLine(x, 0, x, total_height, pen)
            line.setZValue(18)
            self._snap_guide_items.append(line)
        if result.active_guide is not None and result.active_guide not in result.nearby_guides:
            x = result.active_guide * px_per_sec
            line = self._scene.addLine(x, 0, x, total_height, active_pen)
            line.setZValue(19)
            self._snap_guide_items.append(line)

    def _clear_snap_guides(self) -> None:
        for item in self._snap_guide_items:
            self._scene.removeItem(item)
        self._snap_guide_items.clear()

    def _ensure_playhead(self, total_height: float) -> None:
        px_per_sec = self.project_state.project.px_per_sec
        if self._playhead_item is None:
            self._playhead_item = PlayheadItem(px_per_sec, total_height)
            self._playhead_item.seek_requested.connect(self._on_playhead_drag_seek)
            self._scene.addItem(self._playhead_item)
        else:
            self._playhead_item.set_px_per_sec(px_per_sec)
            self._playhead_item.set_scene_height(total_height)
        self._playhead_item.set_time(self.project_state.playhead)

    def _on_playhead_drag_seek(self, time: float) -> None:
        self.seek_with_snap(time)

    def update_playhead(self) -> None:
        if self._playhead_item is not None:
            self._playhead_item.set_time(self.project_state.playhead)

    def ensure_playhead_visible(self, margin_ratio: float = 0.15) -> None:
        """Auto-scroll horizontally so the playhead stays in view during playback."""
        px_per_sec = self.project_state.project.px_per_sec
        if px_per_sec <= 0:
            return
        playhead_x = self.project_state.playhead * px_per_sec
        self.auto_scroll_at_scene_x(playhead_x, margin_ratio=margin_ratio)

    def auto_scroll_at_scene_x(self, scene_x: float, margin_ratio: float = 0.08) -> None:
        """Scroll horizontally when a drag point nears the viewport edge."""
        bar = self.horizontalScrollBar()
        viewport_w = self.viewport().width()
        if viewport_w <= 0:
            return
        scroll_x = float(bar.value())
        margin = max(48.0, viewport_w * margin_ratio)
        if scene_x < scroll_x + margin:
            bar.setValue(max(0, int(scene_x - margin)))
        elif scene_x > scroll_x + viewport_w - margin:
            bar.setValue(int(scene_x - viewport_w + margin))

    def auto_scroll_at_scene_y(self, scene_y: float, margin_ratio: float = 0.12) -> None:
        bar = self.verticalScrollBar()
        viewport_h = self.viewport().height()
        if viewport_h <= 0:
            return
        scroll_y = float(bar.value())
        margin = max(32.0, viewport_h * margin_ratio)
        if scene_y < scroll_y + margin:
            bar.setValue(max(0, int(scene_y - margin)))
        elif scene_y > scroll_y + viewport_h - margin:
            bar.setValue(int(scene_y - viewport_h + margin))

    def _on_edge_scroll(self, scene_x: float, scene_y: float) -> None:
        # Defer scroll to avoid re-entrant Qt paint/scroll during clip drag.
        QTimer.singleShot(0, lambda: self._apply_edge_scroll(scene_x, scene_y))

    def _apply_edge_scroll(self, scene_x: float, scene_y: float) -> None:
        self.auto_scroll_at_scene_x(scene_x)
        self.auto_scroll_at_scene_y(scene_y)

    def _apply_selection_visuals(self) -> None:
        selected = self.project_state.selected_clip_ids
        if not selected and self.project_state.selected_clip_id:
            selected = {self.project_state.selected_clip_id}
        for clip_id, item in self._clip_items.items():
            item.set_selected_visual(clip_id in selected)

    # ---------------- clip signal handlers ----------------

    def _on_clip_selection_requested(self, clip_id: str, ctrl: bool, shift: bool) -> None:
        if ctrl:
            self.project_state.select_clip(clip_id, toggle=True)
        elif shift:
            self.project_state.select_clip(clip_id, additive=True)
        else:
            self.project_state.select_clip(clip_id)
        self._apply_selection_visuals()
        self.selection_changed.emit()

    def _on_clip_context_menu(self, clip_id: str, scene_pos: QPointF) -> None:
        if clip_id not in self.project_state.selected_clip_ids:
            self.project_state.select_clip(clip_id)
            self._apply_selection_visuals()
            self.selection_changed.emit()

        menu = QMenu(self)
        split_action = menu.addAction("Split at playhead")
        duplicate_action = menu.addAction("Duplicate")
        delete_action = menu.addAction("Delete")
        detach_action = None
        ref = self.project_state.get_clip(clip_id)
        if ref is not None and ref[1].kind == "video" and ref[1].linked_group_id:
            menu.addSeparator()
            detach_action = menu.addAction("Detach audio")

        global_pos = self.mapToGlobal(self.mapFromScene(scene_pos))
        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        if chosen is split_action:
            self.project_state.select_clip(clip_id)
            self.split_selected()
        elif chosen is duplicate_action:
            self.duplicate_selected()
        elif chosen is delete_action:
            self.delete_selected()
        elif detach_action is not None and chosen is detach_action:
            if self.project_state.detach_linked_audio(clip_id):
                self.toast_requested.emit("Audio detached")
                self._incremental_sync()
            else:
                self.toast_requested.emit("No linked audio to detach")

    def _ensure_marquee_item(self) -> _MarqueeRubberBand:
        if self._marquee_item is None:
            self._marquee_item = _MarqueeRubberBand()
            self._scene.addItem(self._marquee_item)
        return self._marquee_item

    def _update_marquee_rect(self, start: QPointF, current: QPointF) -> None:
        marquee = self._ensure_marquee_item()
        rect = QRectF(start, current).normalized()
        marquee.setRect(rect)
        marquee.setVisible(True)

    def _clear_marquee(self) -> None:
        if self._marquee_item is not None:
            self._marquee_item.setVisible(False)

    def _select_clips_in_marquee(self, rect: QRectF) -> None:
        if rect.width() < 2 and rect.height() < 2:
            return
        hits: set[str] = set()
        px = self.project_state.project.px_per_sec
        track_index = {track.id: i for i, track in enumerate(self.project_state.project.tracks)}
        for track in self.project_state.project.tracks:
            row = track_index[track.id]
            for clip in track.clips:
                if rect.intersects(self._clip_scene_rect(clip, row, px)):
                    hits.add(clip.id)
        if hits:
            self.project_state.select_clips(hits)
            self._apply_selection_visuals()
            self.selection_changed.emit()

    def _row_index_for_track(self, track_id: str) -> int:
        for i, track in enumerate(self.project_state.project.tracks):
            if track.id == track_id:
                return i
        return 0

    @staticmethod
    def _should_merge_onto_track(
        *,
        clip,
        source_track,
        target,
        target_track_id: str | None,
        target_empty: bool,
        splitting: bool,
    ) -> bool:
        if target is None or target_track_id is None or target_track_id == source_track.id:
            return False
        if not ProjectState._clip_compatible_with_track(clip, target):
            return False
        if target_empty or splitting:
            return True
        # Audio tracks hold sequential songs (playlist rows); video/overlay stay one layer per row.
        return target.type == "audio" and clip.kind == "audio"

    def _on_move_committed(
        self,
        clip_id: str,
        new_start: float,
        target_track_id: str | None,
        preview_row: int,
    ) -> None:
        ref = self.project_state.get_clip(clip_id)
        if ref is None:
            return
        source_track, clip = ref
        if source_track.locked:
            self._incremental_sync()
            return

        source_row = self._row_index_for_track(source_track.id)
        tracks = self.project_state.project.tracks

        if preview_row != source_row:
            splitting = len(source_track.clips) > 1
            target = self.project_state.get_track(target_track_id) if target_track_id else None
            target_empty = target is not None and len(target.clips) == 0
            merge = self._should_merge_onto_track(
                clip=clip,
                source_track=source_track,
                target=target,
                target_track_id=target_track_id,
                target_empty=target_empty,
                splitting=splitting,
            )

            if target_track_id is None:
                if splitting:
                    clamped = max(0, min(preview_row, len(tracks)))
                    self.project_state.move_clip_to_new_track_at_row(clip_id, clamped, new_start)
                else:
                    clamped = max(0, min(preview_row, len(tracks) - 1))
                    self.project_state.reorder_track(source_track.id, clamped)
                    self.project_state.move_clip(clip_id, new_start)
            elif merge:
                self.project_state.move_clip_to_track(clip_id, target_track_id, new_start)
            elif target_track_id != source_track.id:
                clamped = max(0, min(preview_row, len(tracks) - 1))
                self.project_state.reorder_track(source_track.id, clamped)
                self.project_state.move_clip(clip_id, new_start)
            else:
                self.project_state.move_clip(clip_id, new_start)
        else:
            self.project_state.move_clip(clip_id, new_start)

        self.project_state.prune_empty_tracks()
        self._incremental_sync()
        self.structure_changed.emit()

    def _on_trim_committed(self, clip_id: str, side: str, dt: float) -> None:
        self.project_state.trim_clip(clip_id, side, dt)
        self._incremental_sync()
        self.structure_changed.emit()

    # ---------------- empty-lane click / marquee select ----------------

    def mousePressEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.pos())
        if isinstance(item, ClipGraphicsItem):
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._empty_press_pos = event.position().toPoint()
            self._empty_press_scene = self.mapToScene(self._empty_press_pos)
            self._marquee_active = False
            self._lane_scrubbing = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if (
            self._empty_press_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._empty_press_scene is not None
        ):
            delta = (event.position().toPoint() - self._empty_press_pos).manhattanLength()
            if delta >= _MARQUEE_DRAG_THRESHOLD_PX:
                self._marquee_active = True
                current = self.mapToScene(event.position().toPoint())
                self._update_marquee_rect(self._empty_press_scene, current)
                event.accept()
                return
        if self._lane_scrubbing and event.buttons() & Qt.MouseButton.LeftButton:
            scene_x = self.mapToScene(event.position().toPoint()).x()
            px = self.project_state.project.px_per_sec
            if px > 0:
                alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
                self.seek_with_snap(max(0.0, scene_x / px), alt=alt)
                self.auto_scroll_at_scene_x(scene_x)
                self.auto_scroll_at_scene_y(self.mapToScene(event.position().toPoint()).y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._marquee_active and event.button() == Qt.MouseButton.LeftButton:
            if self._marquee_item is not None and self._marquee_item.isVisible():
                self._select_clips_in_marquee(self._marquee_item.rect())
            self._clear_marquee()
            self._empty_press_pos = None
            self._empty_press_scene = None
            self._marquee_active = False
            event.accept()
            return
        if self._empty_press_pos is not None and event.button() == Qt.MouseButton.LeftButton:
            if not self._marquee_active and self._empty_press_scene is not None:
                self.project_state.clear_selection()
                self._apply_selection_visuals()
                self.selection_changed.emit()
                px = self.project_state.project.px_per_sec
                if px > 0:
                    alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
                    self.seek_with_snap(max(0.0, self._empty_press_scene.x() / px), alt=alt)
            self._empty_press_pos = None
            self._empty_press_scene = None
            event.accept()
            return
        if self._lane_scrubbing and event.button() == Qt.MouseButton.LeftButton:
            self._lane_scrubbing = False
            self._clear_snap_guides()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                event.accept()
                return
            px = self.project_state.project.px_per_sec
            step = zoom_wheel_step(px)
            new_px = clamp(px + (step if delta > 0 else -step), MIN_PX_PER_SEC, MAX_PX_PER_SEC)
            if abs(new_px - px) > 1e-9:
                self.zoom_changed.emit(new_px)
            event.accept()
            return
        super().wheelEvent(event)

    # ---------------- drag & drop from the library ----------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasFormat(MEDIA_MIME_TYPE):
            media_id = bytes(mime.data(MEDIA_MIME_TYPE)).decode("utf-8")
            media = self.project_state.get_media(media_id)
            if media is not None:
                self._pending_drop_media = media
                self._pending_drop_label = media.name
                self._pending_drop_type = media.type
                self._pending_drop_duration = 5.0 if media.type == "image" else (media.duration or 5.0)
            event.acceptProposedAction()
            return
        if mime.hasFormat(TEXT_PRESET_MIME_TYPE):
            preset = bytes(mime.data(TEXT_PRESET_MIME_TYPE)).decode("utf-8")
            self._pending_drop_media = None
            self._pending_drop_label = preset.replace("_", " ").title()
            self._pending_drop_type = "text"
            self._pending_drop_duration = 4.0
            event.acceptProposedAction()
            return
        if mime.hasFormat(FILTER_MIME_TYPE):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasFormat(FILTER_MIME_TYPE):
            event.acceptProposedAction()
            return
        if not (mime.hasFormat(MEDIA_MIME_TYPE) or mime.hasFormat(TEXT_PRESET_MIME_TYPE)):
            event.ignore()
            return

        scene_pos = self.mapToScene(event.position().toPoint())
        row_index = max(0, int(scene_pos.y() // TRACK_HEIGHT))
        px_per_sec = self.project_state.project.px_per_sec
        raw_time = max(0.0, scene_pos.x() / px_per_sec) if px_per_sec else 0.0
        track = self._track_at_row(row_index)
        ctx = self._snap_ctx(
            track_id=track.id if track else None,
            track_type=track.type if track else None,
            clip_duration=self._pending_drop_duration,
        )
        drop_result = snap_time(raw_time, ctx)
        drop_time = 0.0 if (track is None or not track.clips) else drop_result.time
        _, total_height, _ = self._scene_metrics()
        if drop_time == 0.0 and raw_time > 0.05:
            drop_result = SnapResult(time=0.0, snapped=True, edge="start")
        self._set_snap_guides(drop_result, total_height)
        if drop_result.snapped and not self._last_drop_snapped:
            self._apply_snap_feedback(drop_result)
        self._last_drop_snapped = drop_result.snapped

        if self._drop_ghost is not None:
            width_px = self._pending_drop_duration * px_per_sec if px_per_sec else 80
            self._drop_ghost.show_at(
                row_index,
                drop_time * px_per_sec,
                width_px,
                self._pending_drop_label,
                self._pending_drop_type,
                magnetized=drop_result.snapped,
            )
        event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        if self._drop_ghost is not None:
            self._drop_ghost.hide_ghost()
        self._clear_snap_guides()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        if self._drop_ghost is not None:
            self._drop_ghost.hide_ghost()
        self._clear_snap_guides()
        mime = event.mimeData()

        if mime.hasFormat(FILTER_MIME_TYPE):
            filter_id = bytes(mime.data(FILTER_MIME_TYPE)).decode("utf-8")
            item = self.itemAt(event.position().toPoint())
            if isinstance(item, ClipGraphicsItem) and (item.track.type == "video" or item.clip.kind == "image"):
                self.project_state.update_clip(item.clip.id, filter=filter_id)
                item.update()
                self.structure_changed.emit()
            else:
                self.toast_requested.emit("Drop filters onto a video or image clip")
            event.acceptProposedAction()
            return

        # CapCut-style "drop anywhere": dropping media/text onto the timeline
        # never requires a pre-existing track of the right type — a matching
        # track is auto-created (below any existing tracks, or in place of a
        # mismatched one) exactly like a real NLE. `row_index` is just a
        # *hint* for which existing track to prefer, not a hard requirement.
        scene_pos = self.mapToScene(event.position().toPoint())
        row_index = int(scene_pos.y() // TRACK_HEIGHT)
        px_per_sec = self.project_state.project.px_per_sec
        raw_time = max(0.0, scene_pos.x() / px_per_sec) if px_per_sec else 0.0
        track = self._track_at_row(row_index)
        drop_result = snap_time(
            raw_time,
            self._snap_ctx(
                track_id=track.id if track else None,
                track_type=track.type if track else None,
                clip_duration=self._pending_drop_duration,
            ),
        )
        drop_time = 0.0 if (track is None or not track.clips) else drop_result.time
        self._last_drop_snapped = False

        if mime.hasFormat(MEDIA_MIME_TYPE):
            media_id = bytes(mime.data(MEDIA_MIME_TYPE)).decode("utf-8")
            media = self.project_state.get_media(media_id)
            if media is None:
                event.ignore()
                return
            clip = self.project_state.add_clip_from_media_at_row(media, row_index, drop_time)
            self._incremental_sync()
            self._start_preview_worker(clip.id, media, clip.trim_start, clip.duration)
            event.acceptProposedAction()
            return

        if mime.hasFormat(TEXT_PRESET_MIME_TYPE):
            preset = bytes(mime.data(TEXT_PRESET_MIME_TYPE)).decode("utf-8")
            clip = self.project_state.add_text_clip_at_row(preset, row_index, drop_time)
            if clip is None:
                self.toast_requested.emit("Unknown text preset")
            else:
                self._incremental_sync()
            event.acceptProposedAction()
            return

        event.ignore()

    # ---------------- background clip preview generation ----------------

    def _start_preview_worker(self, clip_id: str, media: MediaAsset, trim_start: float, duration: float) -> None:
        if media.type not in ("video", "audio"):
            return
        worker = _ClipPreviewWorker(
            clip_id,
            media,
            trim_start,
            duration,
            self.devicePixelRatioF(),
            self,
        )
        worker.filmstrip_ready.connect(self._on_filmstrip_ready)
        worker.waveform_ready.connect(self._on_waveform_ready)
        worker.finished.connect(lambda w=worker: self._preview_workers.remove(w) if w in self._preview_workers else None)
        self._preview_workers.append(worker)
        worker.start()

    def _on_filmstrip_ready(self, clip_id: str, thumb_paths: list[str]) -> None:
        ref = self.project_state.get_clip(clip_id)
        if ref is None:
            return
        _track, clip = ref
        clip.thumb_cache = thumb_paths
        item = self._clip_items.get(clip_id)
        if item is not None:
            item.update()

    def _on_waveform_ready(self, clip_id: str, envelope: list[float]) -> None:
        ref = self.project_state.get_clip(clip_id)
        if ref is None:
            return
        _track, clip = ref
        clip.waveform_cache = envelope
        item = self._clip_items.get(clip_id)
        if item is not None:
            item.update()

    def wait_for_preview_workers(self, timeout_ms: int = 10000) -> None:
        """Block until any in-flight filmstrip/waveform workers finish —
        used on app shutdown to avoid killing them mid-write."""
        for worker in list(self._preview_workers):
            worker.wait(timeout_ms)

    # ---------------- public actions (toolbar/keyboard) ----------------

    def split_selected(self) -> None:
        if not self.project_state.selected_clip_id:
            self.toast_requested.emit("Select a clip to split")
            return
        result = self.project_state.split_clip_at_playhead()
        if result is None:
            self.toast_requested.emit("Move playhead inside the selected clip")
        else:
            self.toast_requested.emit("Clip split")
            self._incremental_sync()

    def delete_selected(self) -> None:
        removed = self.project_state.delete_selected_clips()
        if removed == 0:
            self.toast_requested.emit("No clip selected")
            return
        self.project_state.prune_empty_tracks()
        self._incremental_sync()

    def duplicate_selected(self) -> None:
        copies = self.project_state.duplicate_selected_clips()
        if not copies:
            return
        self._incremental_sync()

    def nudge_selected(self, direction: int, *, large_step: bool = False, snap_to_edge: bool = False) -> None:
        if not self.project_state._effective_selection():
            return
        if snap_to_edge:
            self.project_state.nudge_selected_clips(0.0, snap_to_edge=True, edge_direction=direction)
        else:
            fps = self.project_state.project.snap_settings.frame_rate or 30.0
            delta = (1.0 if large_step else 1.0 / fps) * direction
            self.project_state.nudge_selected_clips(delta)
        self._incremental_sync()

    def set_zoom(self, px_per_sec: float) -> None:
        self.project_state.project.px_per_sec = px_per_sec
        tracks = self.project_state.project.tracks
        total_width, total_height, px = self._scene_metrics()
        self._resize_lanes(total_width)
        self._scene.setSceneRect(
            0, 0, total_width, max(total_height, self.viewport().height())
        )
        track_index = {track.id: i for i, track in enumerate(tracks)}
        if self._sync_viewport_clips(track_index=track_index, px_per_sec=px):
            self.structure_changed.emit()
        self._ensure_playhead(total_height)
        self.update_playhead()

    def seek(self, time: float) -> None:
        self.project_state.seek(time)
        self.update_playhead()
        self.seek_requested.emit(self.project_state.playhead)

    def playhead_time(self) -> float:
        return self.project_state.playhead


class TimelineWrap(QFrame):
    seek_requested = Signal(float)
    toast_requested = Signal(str)
    selection_changed = Signal()
    structure_changed = Signal()

    def __init__(self, project_state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TimelineWrap")
        self.setMinimumHeight(200)
        self.project_state = project_state

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.toolbar = TimelineToolbar(self)
        outer.addWidget(self.toolbar)

        self._snap_popover = SnapSettingsPopover(self)

        self._zoom_debounce = QTimer(self)
        self._zoom_debounce.setSingleShot(True)
        self._zoom_debounce.setInterval(ZOOM_DEBOUNCE_MS)
        self._zoom_debounce.timeout.connect(self._commit_pending_zoom)
        self._pending_zoom: float | None = None

        body = QWidget(self)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        left_column = QWidget(body)
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        minimap_spacer = QFrame()
        minimap_spacer.setFixedHeight(MINIMAP_HEIGHT)
        minimap_spacer.setStyleSheet("background: #14141b;")
        left_layout.addWidget(minimap_spacer)

        ruler_spacer = QFrame()
        ruler_spacer.setFixedHeight(RULER_HEIGHT)
        ruler_spacer.setStyleSheet("background: #14141b; border-bottom: 1px solid #20202b;")
        left_layout.addWidget(ruler_spacer)

        self.track_headers = TrackHeaders()
        self._headers_scroll = QScrollArea()
        self._headers_scroll.setObjectName("TrackHeaders")
        self._headers_scroll.setWidget(self.track_headers)
        self._headers_scroll.setWidgetResizable(True)
        self._headers_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._headers_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._headers_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._headers_scroll.setFixedWidth(TRACK_HEADER_WIDTH)
        left_layout.addWidget(self._headers_scroll, 1)
        body_layout.addWidget(left_column)

        right_column = QWidget(body)
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.minimap = TimelineMinimap()
        right_layout.addWidget(self.minimap)

        self.ruler = TimelineRuler()
        right_layout.addWidget(self.ruler)

        self.graphics_view = TimelineGraphicsView(project_state)
        right_layout.addWidget(self.graphics_view, 1)
        body_layout.addWidget(right_column, 1)

        outer.addWidget(body, 1)

        self._rebuild_headers()
        self.ruler.set_project(project_state.project)

        self._wire_signals()
        self._sync_snap_ui_from_project()
        self._sync_ripple_ui_from_project()
        self._update_minimap_viewport()

    def _rebuild_headers(self) -> None:
        row_count = visible_track_rows(len(self.project_state.project.tracks))
        self.track_headers.rebuild(self.project_state.project.tracks, visible_rows=row_count)

    def _sync_snap_ui_from_project(self) -> None:
        settings = self.project_state.project.snap_settings
        tb = self.toolbar
        tb.snap_toggle_btn.blockSignals(True)
        tb.snap_toggle_btn.setChecked(settings.enabled)
        if settings.enabled:
            tb.snap_toggle_btn.setStyleSheet(
                "background: #3a3050; border: 1px solid #ffd54a;"
                " border-radius: 8px; padding: 0px;"
            )
        else:
            tb.snap_toggle_btn.setStyleSheet("")
        TimelineEditToolbar.refresh_snap_icon(tb.snap_toggle_btn, settings.enabled)
        tb.snap_toggle_btn.blockSignals(False)
        self._snap_popover.sync_from_settings(settings)

    def _sync_ripple_ui_from_project(self) -> None:
        tb = self.toolbar
        enabled = self.project_state.project.ripple_edit
        tb.ripple_btn.blockSignals(True)
        tb.ripple_btn.setChecked(enabled)
        if enabled:
            tb.ripple_btn.setStyleSheet(
                "background: #3a3050; border: 1px solid #ffd54a;"
                " border-radius: 8px; padding: 0px;"
            )
        else:
            tb.ripple_btn.setStyleSheet("")
        TimelineEditToolbar.refresh_ripple_icon(tb.ripple_btn, enabled)
        tb.ripple_btn.blockSignals(False)

    def toggle_ripple_edit(self) -> None:
        self.project_state.toggle_ripple_edit()
        self._sync_ripple_ui_from_project()

    def _on_ripple_toggle(self, checked: bool) -> None:
        self.project_state.project.ripple_edit = checked
        self._sync_ripple_ui_from_project()

    def _wire_signals(self) -> None:
        gv = self.graphics_view
        tb = self.toolbar

        gv.horizontalScrollBar().valueChanged.connect(self._on_h_scroll)
        gv.verticalScrollBar().valueChanged.connect(self._headers_scroll.verticalScrollBar().setValue)
        gv.toast_requested.connect(self.toast_requested.emit)
        gv.seek_requested.connect(self._on_timeline_seek)
        gv.selection_changed.connect(self._on_selection_changed)
        gv.structure_changed.connect(self._on_structure_changed)

        self.ruler.seek_requested.connect(self._on_ruler_seek_snapped)
        self.ruler.playhead_dragged.connect(self._on_ruler_scrub_snapped)

        self.minimap.seek_requested.connect(self._on_minimap_seek)

        self.track_headers.mute_requested.connect(self._on_track_mute)
        self.track_headers.solo_requested.connect(self._on_track_solo)
        self.track_headers.lock_requested.connect(self._on_track_lock)
        self.track_headers.hide_requested.connect(self._on_track_hide)
        self.track_headers.delete_requested.connect(self._on_track_delete)
        self.track_headers.rename_requested.connect(self._on_track_rename)
        self.track_headers.reorder_requested.connect(self._on_track_reorder)

        gv.zoom_changed.connect(self._on_zoom_from_view)
        tb.split_btn.clicked.connect(gv.split_selected)
        tb.delete_btn.clicked.connect(gv.delete_selected)
        tb.ripple_btn.toggled.connect(self._on_ripple_toggle)
        tb.add_video_track_btn.clicked.connect(lambda: self._add_track("video"))
        tb.add_audio_track_btn.clicked.connect(lambda: self._add_track("audio"))
        tb.add_overlay_track_btn.clicked.connect(lambda: self._add_track("overlay"))
        tb.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        tb.snap_toggle_btn.toggled.connect(self._on_snap_toggle)
        tb.snap_settings_btn.clicked.connect(self._open_snap_popover)
        self._snap_popover.changed.connect(self._on_snap_popover_changed)

    def _on_h_scroll(self, x: int) -> None:
        self.ruler.set_scroll_x(x)
        self._update_minimap_viewport()

    def _update_minimap_viewport(self) -> None:
        gv = self.graphics_view
        self.minimap.set_project(self.project_state.project)
        self.minimap.set_viewport(gv.horizontalScrollBar().value(), gv.viewport().width())

    def _on_structure_changed(self) -> None:
        self._rebuild_headers()
        self.minimap.set_project(self.project_state.project)
        self._update_minimap_viewport()
        self.structure_changed.emit()

    def _open_snap_popover(self) -> None:
        btn = self.toolbar.snap_settings_btn
        pos = btn.mapToGlobal(btn.rect().bottomLeft())
        self._snap_popover.sync_from_settings(self.project_state.project.snap_settings)
        self._snap_popover.move(pos)
        self._snap_popover.show()

    def _on_snap_popover_changed(self) -> None:
        self._snap_popover.apply_to_settings(self.project_state.project.snap_settings)

    def _on_minimap_seek(self, time: float) -> None:
        snapped = self.graphics_view.seek_with_snap(time)
        self.ruler.set_playhead_time(snapped)

    def _on_ruler_seek_snapped(self, raw_time: float) -> None:
        time = self.graphics_view.seek_with_snap(raw_time)
        self.ruler.set_playhead_time(time)

    def _on_ruler_scrub_snapped(self, raw_time: float) -> None:
        time = self.graphics_view.seek_with_snap(raw_time)
        self.ruler.set_playhead_time(time)

    def toggle_snap_enabled(self) -> None:
        settings = self.project_state.project.snap_settings
        settings.enabled = not settings.enabled
        self._sync_snap_ui_from_project()

    def _on_snap_toggle(self, enabled: bool) -> None:
        self.project_state.project.snap_settings.enabled = enabled
        self._sync_snap_ui_from_project()

    def _on_timeline_seek(self, time: float) -> None:
        self.ruler.set_playhead_time(time)
        self.seek_requested.emit(time)

    def _on_selection_changed(self) -> None:
        self.selection_changed.emit()

    def _on_track_mute(self, track_id: str) -> None:
        self.project_state.toggle_track_mute(track_id)
        self.track_headers.refresh_states(self.project_state.project.tracks)

    def _on_track_solo(self, track_id: str) -> None:
        self.project_state.toggle_track_solo(track_id)
        self.track_headers.refresh_states(self.project_state.project.tracks)

    def _on_track_hide(self, track_id: str) -> None:
        track = self.project_state.get_track(track_id)
        if track is None or track.type == "audio":
            return
        self.project_state.toggle_track_hidden(track_id)
        self.track_headers.refresh_states(self.project_state.project.tracks)
        self.graphics_view._incremental_sync()

    def _on_track_rename(self, track_id: str, name: str) -> None:
        self.project_state.rename_track(track_id, name)
        self.track_headers.refresh_states(self.project_state.project.tracks)

    def _on_track_reorder(self, track_id: str, new_index: int) -> None:
        track = self.project_state.get_track(track_id)
        if track is not None and track.scene_role:
            self.toast_requested.emit("Playlist scene tracks are auto-managed")
            self.refresh_all()
            return
        self.project_state.reorder_track(track_id, new_index)
        self.refresh_all()

    def _on_track_delete(self, track_id: str) -> None:
        track = self.project_state.get_track(track_id)
        if track is None:
            return
        if track.locked:
            self.toast_requested.emit("Track is locked")
            return
        had_clips = bool(track.clips)
        self.project_state.remove_track(track_id)
        self.project_state.prune_empty_tracks()
        if had_clips:
            self.toast_requested.emit("Track deleted")
        self.refresh_all()

    def _on_track_lock(self, track_id: str) -> None:
        self.project_state.toggle_track_lock(track_id)
        self.track_headers.refresh_states(self.project_state.project.tracks)

    def _add_track(self, track_type: str) -> None:
        self.project_state.add_track(track_type)  # type: ignore[arg-type]
        self.refresh_all()

    def _on_zoom_changed(self, value: int) -> None:
        self._pending_zoom = float(value)
        self._zoom_debounce.start()

    def _on_zoom_from_view(self, px_per_sec: float) -> None:
        self._apply_zoom(px_per_sec)

    def _commit_pending_zoom(self) -> None:
        if self._pending_zoom is not None:
            self._apply_zoom(self._pending_zoom)
            self._pending_zoom = None

    def _apply_zoom(self, px_per_sec: float) -> None:
        px_per_sec = clamp(px_per_sec, MIN_PX_PER_SEC, MAX_PX_PER_SEC)
        self.toolbar.zoom_slider.blockSignals(True)
        self.toolbar.zoom_slider.setValue(int(round(px_per_sec)))
        self.toolbar.zoom_slider.blockSignals(False)
        self.graphics_view.set_zoom(px_per_sec)
        self.ruler.set_params(self.project_state.project.duration, px_per_sec)
        self.ruler.set_project(self.project_state.project)
        self._update_minimap_viewport()

    def refresh_all(self) -> None:
        self._rebuild_headers()
        self.graphics_view.refresh_from_state(full=True)
        self.ruler.set_params(self.project_state.project.duration, self.project_state.project.px_per_sec)
        self.ruler.set_project(self.project_state.project)
        self.ruler.set_playhead_time(self.project_state.playhead)
        self._update_minimap_viewport()

    def follow_playhead_during_playback(self) -> None:
        self.graphics_view.ensure_playhead_visible()
        self.ruler.set_playhead_time(self.project_state.playhead)
        self._update_minimap_viewport()

    def refresh_after_external_change(self) -> None:
        self.refresh_all()
