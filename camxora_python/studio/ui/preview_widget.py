"""Center preview canvas + transport bar, and the `PlaybackController` that
drives the render loop (QTimer-based master clock, mirroring the reference
app's `requestAnimationFrame` loop) and the audio mixer.
"""

from __future__ import annotations

import copy
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer, Signal, QRect
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from studio.audio.mixer import AudioMixer
from studio.core.models import MediaAsset
from studio.core.preview_settings import (
    ASPECT_RATIO_PRESETS,
    PREVIEW_QUALITY_PRESETS,
    aspect_ratio_label,
    preview_quality_label,
    preview_render_size,
)
from studio.core.models import Clip
from studio.core.playlist_scene_sync import SCENE_GRAPHICS
from studio.core.project_state import ProjectState
from studio.core.time_utils import fmt_time_hms
from studio.media.audio_source import AudioSourceCache
from studio.media.video_source import VideoSourceCache
from studio.render.compositor import frame_to_qimage, render_frame
from studio.ui.capcut_dropdown import CapCutDropdown
from studio.ui.preview_render_worker import PreviewRenderWorker
from studio.ui.preview_transform_overlay import PreviewTransformOverlay
from studio.ui.preview_playlist_overlay import PreviewPlaylistOverlay
from studio.ui.icons.lucide_icons import (
    BTN_SZ_ICON,
    BTN_SZ_PLAY,
    ICON_COLOR,
    ICON_COLOR_ON_ACCENT,
    ICON_SZ_PLAY,
    ICON_SZ_TRANSPORT,
    set_button_lucide_icon,
)

logger = logging.getLogger(__name__)


class PreviewCanvas(QLabel):
    """QLabel used as the render target — compositor writes QPixmaps here."""

    resized = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 180)
        self.setStyleSheet("background: #000000;")
        # Blank black canvas on first open — no placeholder copy.
        self._placeholder_text = ""
        self.setText(self._placeholder_text)
        self.setWordWrap(True)
        self._source_pixmap: QPixmap | None = None
        self._fast_scale = False

    def show_placeholder(self) -> None:
        self._source_pixmap = None
        self.setPixmap(QPixmap())
        self.setText(self._placeholder_text)

    def show_frame(self, pixmap: QPixmap, *, fast_scale: bool = False) -> None:
        self.setText("")
        self._source_pixmap = pixmap
        self._fast_scale = fast_scale
        self._apply_scaled_pixmap()

    def _apply_scaled_pixmap(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return
        mode = (
            Qt.TransformationMode.FastTransformation
            if self._fast_scale
            else Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(
            self._source_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                mode,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._source_pixmap is not None and not self._source_pixmap.isNull():
            self._apply_scaled_pixmap()
        self.resized.emit()

    def canvas_content_rect(self) -> QRect:
        pix = self.pixmap()
        if pix is None or pix.isNull():
            return QRect(0, 0, self.width(), self.height())
        scaled = pix.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())


class Transport(QFrame):
    play_toggled = Signal(bool)
    scrub_requested = Signal(float)  # fraction 0..1 — scrubber hidden; kept for API compat
    step_back_requested = Signal()
    step_forward_requested = Signal()
    fit_requested = Signal()
    fullscreen_requested = Signal()
    preview_quality_changed = Signal(str)
    aspect_ratio_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Transport")
        self.setFixedHeight(52)

        from PySide6.QtWidgets import QPushButton

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        self._playing = False
        self._preview_quality_id = "half"
        self._aspect_ratio_id = "16:9"

        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setObjectName("TimeLabel")
        layout.addWidget(self.time_label)

        layout.addStretch(1)

        transport_cluster = QHBoxLayout()
        transport_cluster.setSpacing(6)

        self.step_back_btn = QPushButton()
        self.step_back_btn.setObjectName("PreviewControlButton")
        self.step_back_btn.setFixedSize(BTN_SZ_ICON, BTN_SZ_ICON)
        self.step_back_btn.setToolTip("Previous frame")
        set_button_lucide_icon(self.step_back_btn, "skip-back", size=ICON_SZ_TRANSPORT, color=ICON_COLOR)
        self.step_back_btn.clicked.connect(self.step_back_requested.emit)
        transport_cluster.addWidget(self.step_back_btn)

        self.play_btn = QPushButton()
        self.play_btn.setObjectName("PlayButton")
        self.play_btn.setFixedSize(BTN_SZ_PLAY, BTN_SZ_PLAY)
        set_button_lucide_icon(self.play_btn, "play", size=ICON_SZ_PLAY, color=ICON_COLOR_ON_ACCENT)
        self.play_btn.clicked.connect(self._on_clicked)
        transport_cluster.addWidget(self.play_btn)

        self.step_fwd_btn = QPushButton()
        self.step_fwd_btn.setObjectName("PreviewControlButton")
        self.step_fwd_btn.setFixedSize(BTN_SZ_ICON, BTN_SZ_ICON)
        self.step_fwd_btn.setToolTip("Next frame")
        set_button_lucide_icon(self.step_fwd_btn, "skip-forward", size=ICON_SZ_TRANSPORT, color=ICON_COLOR)
        self.step_fwd_btn.clicked.connect(self.step_forward_requested.emit)
        transport_cluster.addWidget(self.step_fwd_btn)

        layout.addLayout(transport_cluster)
        layout.addStretch(1)

        self._quality_menu = CapCutDropdown(self)
        self._quality_menu.item_selected.connect(self._on_quality_selected)

        self.quality_btn = QPushButton("1/2")
        self.quality_btn.setObjectName("PreviewTextControlButton")
        self.quality_btn.setFixedHeight(28)
        self.quality_btn.setMinimumWidth(52)
        self.quality_btn.setToolTip("Preview resolution")
        self.quality_btn.clicked.connect(self._show_quality_menu)
        layout.addWidget(self.quality_btn)

        self.fit_btn = QPushButton()
        self.fit_btn.setObjectName("PreviewControlButton")
        self.fit_btn.setFixedSize(BTN_SZ_ICON, BTN_SZ_ICON)
        self.fit_btn.setToolTip("Fit preview")
        set_button_lucide_icon(self.fit_btn, "ratio", size=ICON_SZ_TRANSPORT, color=ICON_COLOR)
        self.fit_btn.clicked.connect(self.fit_requested.emit)
        layout.addWidget(self.fit_btn)

        self._ratio_menu = CapCutDropdown(self)
        self._ratio_menu.item_selected.connect(self._on_ratio_selected)

        self.ratio_btn = QPushButton("16:9")
        self.ratio_btn.setObjectName("PreviewTextControlButton")
        self.ratio_btn.setFixedHeight(28)
        self.ratio_btn.setMinimumWidth(52)
        self.ratio_btn.setToolTip("Canvas aspect ratio")
        self.ratio_btn.clicked.connect(self._show_ratio_menu)
        layout.addWidget(self.ratio_btn)

        self.fullscreen_btn = QPushButton()
        self.fullscreen_btn.setObjectName("PreviewControlButton")
        self.fullscreen_btn.setFixedSize(BTN_SZ_ICON, BTN_SZ_ICON)
        self.fullscreen_btn.setToolTip("Fullscreen preview")
        set_button_lucide_icon(self.fullscreen_btn, "maximize", size=ICON_SZ_TRANSPORT, color=ICON_COLOR)
        self.fullscreen_btn.clicked.connect(self.fullscreen_requested.emit)
        layout.addWidget(self.fullscreen_btn)

        # Hidden scrubber — timeline is the primary scrub surface (CapCut-style).
        self.scrubber = QSlider(Qt.Orientation.Horizontal)
        self.scrubber.setObjectName("Scrubber")
        self.scrubber.setRange(0, 1000)
        self.scrubber.hide()
        self.scrubber.sliderMoved.connect(lambda v: self.scrub_requested.emit(v / 1000.0))

    def _quality_sections(self) -> list[list[tuple[str, str, str | None, bool]]]:
        return [
            [
                (p.id, p.label, None, True)
                for p in PREVIEW_QUALITY_PRESETS
            ]
        ]

    def _ratio_sections(self) -> list[list[tuple[str, str, str | None, bool]]]:
        landscape = ("16:9", "4:3", "2.35:1", "2:1", "1.85:1")
        portrait = ("9:16", "3:4", "5.8-inch", "1:1")
        by_id = {p.id: p for p in ASPECT_RATIO_PRESETS}
        return [
            [
                ("original", "Original", None, True),
                ("custom", "Custom", None, False),
            ],
            [(pid, by_id[pid].label, by_id[pid].icon, True) for pid in landscape],
            [(pid, by_id[pid].label, by_id[pid].icon, True) for pid in portrait],
        ]

    def _show_quality_menu(self) -> None:
        self._quality_menu.set_items(self._quality_sections(), selected_id=self._preview_quality_id)
        self._quality_menu.popup(self.quality_btn.mapToGlobal(self.quality_btn.rect().bottomLeft()))

    def _show_ratio_menu(self) -> None:
        self._ratio_menu.set_items(self._ratio_sections(), selected_id=self._aspect_ratio_id)
        self._ratio_menu.popup(self.ratio_btn.mapToGlobal(self.ratio_btn.rect().bottomLeft()))

    def _on_quality_selected(self, quality_id: str) -> None:
        self._preview_quality_id = quality_id
        self.quality_btn.setText(preview_quality_label(quality_id))
        self.preview_quality_changed.emit(quality_id)

    def _on_ratio_selected(self, ratio_id: str) -> None:
        self._aspect_ratio_id = ratio_id
        self.ratio_btn.setText(aspect_ratio_label(ratio_id))
        self.aspect_ratio_changed.emit(ratio_id)

    def set_preview_quality(self, quality_id: str) -> None:
        self._preview_quality_id = quality_id
        self.quality_btn.setText(preview_quality_label(quality_id))

    def set_aspect_ratio(self, ratio_id: str) -> None:
        self._aspect_ratio_id = ratio_id
        self.ratio_btn.setText(aspect_ratio_label(ratio_id))

    def preview_quality_id(self) -> str:
        return self._preview_quality_id

    def _on_clicked(self) -> None:
        self.set_playing(not self._playing)
        self.play_toggled.emit(self._playing)

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        set_button_lucide_icon(
            self.play_btn,
            "pause" if playing else "play",
            size=ICON_SZ_PLAY,
            color=ICON_COLOR_ON_ACCENT,
        )

    def set_time_text(self, text: str) -> None:
        self.time_label.setText(text)

    def set_resolution_label(self, text: str) -> None:
        self.ratio_btn.setText(text)

    def set_quality_label(self, text: str) -> None:
        self.quality_btn.setText(text)

    def set_progress(self, fraction: float) -> None:
        self.scrubber.blockSignals(True)
        self.scrubber.setValue(int(max(0.0, min(1.0, fraction)) * 1000))
        self.scrubber.blockSignals(False)


class PreviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QFrame(self)
        self.header.setObjectName("PreviewHeader")
        self.header.setFixedHeight(36)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(14, 0, 14, 0)
        self.header_title = QLabel("Player")
        self.header_title.setObjectName("PreviewHeaderTitle")
        header_layout.addWidget(self.header_title)
        header_layout.addStretch(1)
        layout.addWidget(self.header)

        self.preview_area = QFrame(self)
        self.preview_area.setObjectName("PreviewArea")
        area_layout = QVBoxLayout(self.preview_area)
        area_layout.setContentsMargins(12, 12, 12, 12)
        self.canvas_host = QWidget(self.preview_area)
        host_layout = QVBoxLayout(self.canvas_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = PreviewCanvas(self.canvas_host)
        host_layout.addWidget(self.canvas)
        area_layout.addWidget(self.canvas_host, 1)
        self.transform_overlay: PreviewTransformOverlay | None = None
        self.playlist_overlay: PreviewPlaylistOverlay | None = None

        layout.addWidget(self.preview_area, 1)

        self.transport = Transport(self)
        layout.addWidget(self.transport)

    def attach_transform_overlay(self, project_state: ProjectState) -> None:
        self.transform_overlay = PreviewTransformOverlay(project_state, self.canvas)
        self.canvas.resized.connect(self._sync_overlays)
        self._sync_overlays()

    def attach_playlist_overlay(self, project_state: ProjectState) -> None:
        self.playlist_overlay = PreviewPlaylistOverlay(project_state, self.canvas)
        self.canvas.resized.connect(self._sync_overlays)
        self._sync_overlays()

    def _project_state(self) -> ProjectState | None:
        if self.transform_overlay is not None:
            return self.transform_overlay.project_state
        if self.playlist_overlay is not None:
            return self.playlist_overlay.project_state
        return None

    def _selected_preview_clip(self) -> Clip | None:
        state = self._project_state()
        if state is None:
            return None
        clip_id = state.selected_clip_id
        if not clip_id:
            return None
        ref = state.get_clip(clip_id)
        if ref is None:
            return None
        _track, clip = ref
        return clip

    def _sync_overlays(self) -> None:
        rect = self.canvas.canvas_content_rect()
        overlay_enabled = self.playlist_overlay is not None and getattr(
            self.playlist_overlay.project_state, "playlist_overlay_enabled", False
        )
        selected = self._selected_preview_clip()
        show_transform = (
            selected is not None
            and selected.kind in ("image", "video")
            and selected.scene_role != SCENE_GRAPHICS
        )
        show_playlist = overlay_enabled and (
            selected is None
            or selected.kind == "playlist"
            or selected.scene_role == SCENE_GRAPHICS
            or not show_transform
        )
        if show_transform:
            show_playlist = False

        if self.playlist_overlay is not None:
            if self.playlist_overlay.is_dragging:
                logger.debug(
                    "preview sync_overlays during playlist drag widget=%sx%s",
                    rect.width(),
                    rect.height(),
                )
            self.playlist_overlay.set_canvas_rect(rect)
            if not self.playlist_overlay.is_dragging:
                self.playlist_overlay.refresh()
            self.playlist_overlay.setVisible(show_playlist)
            if show_playlist:
                self.playlist_overlay.raise_()
        if self.transform_overlay is not None:
            self.transform_overlay.set_canvas_rect(rect)
            if not self.transform_overlay.is_dragging:
                self.transform_overlay.refresh()
            self.transform_overlay.setVisible(show_transform)
            if show_transform:
                self.transform_overlay.raise_()

    def _sync_transform_overlay(self) -> None:
        self._sync_overlays()

    def set_player_title(self, title: str) -> None:
        self.header_title.setText(title)


class PlaybackController(QObject):
    """Owns the render loop, video/audio decode caches, and the audio mixer.

    The QTimer tick is the master clock for the *visual* playhead (like the
    reference's `requestAnimationFrame` loop); see `audio/mixer.py` for the
    audio-sync trade-off this implies.
    """

    tick = Signal(float)
    playing_changed = Signal(bool)

    TICK_INTERVAL_MS = 16  # ~60Hz UI tick for playhead + video preview
    TRANSPORT_THROTTLE_MS = 100  # scrubber/time label only needs ~10Hz during audio-only playback
    PLAYLIST_RENDER_INTERVAL_MS = 50  # ~20fps is enough for playlist bar animation

    def __init__(
        self,
        project_state: ProjectState,
        preview_widget: PreviewWidget,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        super().__init__(preview_widget)
        self.project_state = project_state
        self.preview_widget = preview_widget
        canvas_w, canvas_h = project_state.canvas_size()
        self.width = width if width is not None else canvas_w
        self.height = height if height is not None else canvas_h
        self.preview_quality_id = "half"

        self.video_cache = VideoSourceCache()
        self.audio_cache = AudioSourceCache()
        self.mixer = AudioMixer(project_state, self.audio_cache)

        self._timer = QTimer(self)
        self._timer.setInterval(self.TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._on_timer)
        self._elapsed = QElapsedTimer()
        self._last_frame_was_blank = False
        self._last_transport_update_ms = 0
        self._last_playlist_render_ms = 0
        self._render_generation = 0
        self._active_worker: PreviewRenderWorker | None = None
        self._pending_mode: str | None = None
        self._last_async_interactive = False
        self._workers: list[PreviewRenderWorker] = []

        preview_widget.transport.play_toggled.connect(self.set_playing)
        preview_widget.transport.scrub_requested.connect(self._on_scrub)
        preview_widget.transport.preview_quality_changed.connect(self.set_preview_quality)
        preview_widget.transport.aspect_ratio_changed.connect(self.set_aspect_ratio)

        self._sync_transport_labels()
        self.render_now()

    # ---------------- playback control ----------------

    def _sync_transport_labels(self) -> None:
        transport = self.preview_widget.transport
        transport.set_aspect_ratio(self.project_state.project.aspect_ratio_id)
        transport.set_preview_quality(self.preview_quality_id)

    def set_preview_quality(self, quality_id: str) -> None:
        self.preview_quality_id = quality_id
        self.preview_widget.transport.set_preview_quality(quality_id)
        self.render_now(interactive=True)

    def set_aspect_ratio(self, ratio_id: str) -> None:
        w, h = self.project_state.set_aspect_ratio(ratio_id)
        self.width = w
        self.height = h
        self.preview_widget.transport.set_aspect_ratio(ratio_id)
        self.render_now()
        self.preview_widget._sync_overlays()

    def _render_dimensions(self, *, interactive: bool, drag: bool = False) -> tuple[int, int]:
        canvas_w, canvas_h = self.project_state.canvas_size()
        viewport = self.preview_widget.canvas.size()
        if drag:
            return preview_render_size(
                canvas_w,
                canvas_h,
                "quarter",
                viewport_w=viewport.width(),
                viewport_h=viewport.height(),
                interactive=True,
            )
        if interactive:
            return preview_render_size(
                canvas_w,
                canvas_h,
                self.preview_quality_id,
                viewport_w=viewport.width(),
                viewport_h=viewport.height(),
                interactive=True,
            )
        if self.project_state.playlist_preview_active:
            return canvas_w, canvas_h
        return preview_render_size(
            canvas_w,
            canvas_h,
            self.preview_quality_id,
            viewport_w=viewport.width(),
            viewport_h=viewport.height(),
            interactive=False,
        )

    def set_playing(self, playing: bool) -> None:
        if playing == self.project_state.is_playing:
            return
        if playing:
            if not self.project_state.has_timeline_clips():
                self.preview_widget.transport.set_playing(False)
                return
            if self.project_state.playhead >= self.project_state.project.duration:
                self.project_state.playhead = 0.0
            self._ensure_playback_audio_ready()
            self.mixer.sync_playhead(self.project_state.playhead)
            self.project_state.is_playing = True
            self.preview_widget.transport.set_playing(True)
            self._elapsed.restart()
            self._last_transport_update_ms = 0
            self._timer.start()
            if not self.mixer.is_running:
                self.mixer.start()
        else:
            self.project_state.is_playing = False
            self.preview_widget.transport.set_playing(False)
            self._timer.stop()
            self.render_now()
        self.playing_changed.emit(self.project_state.is_playing)

    def toggle_play(self) -> None:
        self.set_playing(not self.project_state.is_playing)

    def seek(self, time: float) -> None:
        self.project_state.seek(time)
        self.mixer.sync_playhead(self.project_state.playhead)
        self.render_now()

    def _on_scrub(self, fraction: float) -> None:
        duration = self.project_state.project.duration
        self.seek(fraction * duration)

    # ---------------- render loop ----------------

    def _on_timer(self) -> None:
        duration = self.project_state.project.duration
        # When the output stream is unavailable (headless tests, no audio
        # device), fall back to a UI-driven clock so preview still scrubs.
        if self.project_state.is_playing and not self.mixer.is_running:
            dt = self._elapsed.restart() / 1000.0
            self.project_state.playhead = min(duration, self.project_state.playhead + dt)
        if self.project_state.playhead >= duration and duration > 0:
            self.project_state.playhead = duration
            self._render_and_update()
            self.set_playing(False)
            return
        self._render_and_update()

    def render_now(self, *, interactive: bool = False, drag: bool = False) -> None:
        if drag:
            self._cancel_async_render()
            self._render_and_update(force_visual=True, interactive=True, drag=True)
            return
        if self.project_state.playlist_preview_active:
            interactive = False
        if self.project_state.is_playing or not interactive:
            self._cancel_async_render()
            self._render_and_update(force_visual=True, interactive=False)
            return
        self._start_async_render(interactive=True)

    def render_async_full(self) -> None:
        """Render one high-quality frame off the UI thread (settings edits).

        Debounced callers (slider drags in the inspector/settings) must not
        block the UI with a 50-110ms synchronous composite per value change.
        """
        if self._active_worker is not None and self._active_worker.isRunning():
            return
        self._start_async_render(interactive=False)

    def render_drag_preview(self) -> None:
        """Low-latency synchronous preview refresh while dragging on-canvas handles."""
        if self.project_state.is_playing:
            return
        self.render_now(drag=True)

    def _cancel_async_render(self) -> None:
        """Invalidate in-flight async frames without destroying running threads."""
        self._render_generation += 1
        self._pending_mode = None

    def _release_worker(self, worker: PreviewRenderWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        if self._active_worker is worker:
            self._active_worker = None
        worker.deleteLater()

    def _start_async_render(self, *, interactive: bool) -> None:
        mode = "interactive" if interactive else "full"
        if self._active_worker is not None and self._active_worker.isRunning():
            self._pending_mode = mode
            self._render_generation += 1
            logger.debug(
                "preview async superseded gen=%s pending=%s",
                self._render_generation,
                mode,
            )
            return
        self._render_generation += 1
        generation = self._render_generation
        self._last_async_interactive = interactive
        width, height = self._render_dimensions(interactive=interactive)
        snapshot = ProjectState(copy.deepcopy(self.project_state.project))
        snapshot.playhead = self.project_state.playhead
        snapshot.playlist_preview_active = self.project_state.playlist_preview_active
        worker = PreviewRenderWorker(
            generation,
            snapshot,
            snapshot.playhead,
            self.video_cache,
            width,
            height,
            audio_cache=self.audio_cache if snapshot.playlist_preview_active else None,
        )
        worker.setParent(self)
        self._active_worker = worker
        self._workers.append(worker)
        logger.debug(
            "preview async start gen=%s size=%sx%s interactive=%s",
            generation,
            width,
            height,
            interactive,
        )
        worker.finished.connect(self._on_async_frame)
        worker.start()

    def _on_async_frame(self, generation: int, frame) -> None:
        worker = self.sender()
        if isinstance(worker, PreviewRenderWorker):
            self._release_worker(worker)
        if generation == self._render_generation:
            logger.debug("preview async apply gen=%s", generation)
            self._apply_frame(frame, interactive=self._last_async_interactive)
        else:
            logger.debug(
                "preview async discard gen=%s current=%s",
                generation,
                self._render_generation,
            )
        pending = self._pending_mode
        self._pending_mode = None
        if pending is not None:
            self._start_async_render(interactive=(pending == "interactive"))

    def _apply_frame(self, frame, *, interactive: bool) -> None:
        qimage = frame_to_qimage(frame)
        fast_scale = interactive
        self.preview_widget.canvas.show_frame(QPixmap.fromImage(qimage), fast_scale=fast_scale)
        self._last_frame_was_blank = False
        self.preview_widget._sync_overlays()

    def _render_and_update(self, force_visual: bool = False, *, interactive: bool = False, drag: bool = False) -> None:
        has_any_clips = any(track.clips for track in self.project_state.project.tracks)
        playlist_active = self.project_state.playlist_preview_active
        needs_visual = False
        if has_any_clips:
            active = self.project_state.active_clips_at(self.project_state.playhead)
            needs_visual = bool(active.video) or bool(active.overlay) or any(
                clip.viz_enabled for _track, clip in active.audio
            )

        if not has_any_clips and not playlist_active:
            self.preview_widget.canvas.show_placeholder()
            self._last_frame_was_blank = True
        elif force_visual or needs_visual or playlist_active or not self._last_frame_was_blank:
            now_ms = self._elapsed.elapsed()
            playlist_playing = (
                playlist_active
                and not needs_visual
                and not has_any_clips
                and self.project_state.is_playing
                and not force_visual
            )
            if (
                playlist_playing
                and now_ms - self._last_playlist_render_ms < self.PLAYLIST_RENDER_INTERVAL_MS
            ):
                pass  # skip heavy playlist re-render this tick
            elif playlist_playing:
                # Render playlist frames off the UI thread while playing so the
                # rest of the app never blocks on the compositor (~50-110ms/frame).
                # Use the viewport-sized preview path: the full 1920x1080 canvas is
                # downscaled for display anyway, so rendering it for animation is
                # wasted work and makes the equalizer crawl.
                busy = self._active_worker is not None and self._active_worker.isRunning()
                if not busy:
                    self._last_playlist_render_ms = now_ms
                    self._start_async_render(interactive=True)
            else:
                if playlist_active:
                    self._last_playlist_render_ms = now_ms
                if interactive:
                    render_w, render_h = self._render_dimensions(interactive=True, drag=drag)
                elif playlist_active:
                    render_w, render_h = self._render_dimensions(interactive=False)
                else:
                    render_w, render_h = self.project_state.canvas_size()
                use_audio = (not interactive) or playlist_active
                frame = render_frame(
                    self.project_state,
                    self.project_state.playhead,
                    self.video_cache,
                    audio_cache=self.audio_cache if use_audio else None,
                    width=render_w,
                    height=render_h,
                )
                self._apply_frame(frame, interactive=interactive)
            if not needs_visual and not playlist_active:
                self._last_frame_was_blank = True

        duration = self.project_state.project.duration
        now_ms = self._elapsed.elapsed()
        if (
            force_visual
            or needs_visual
            or playlist_active
            or now_ms - self._last_transport_update_ms >= self.TRANSPORT_THROTTLE_MS
        ):
            cur_text = fmt_time_hms(self.project_state.playhead)
            total_text = fmt_time_hms(duration)
            self.preview_widget.transport.set_time_text(f"{cur_text} / {total_text}")
            fraction = (self.project_state.playhead / duration) if duration > 0 else 0.0
            self.preview_widget.transport.set_progress(fraction)
            self._last_transport_update_ms = now_ms

        self.tick.emit(self.project_state.playhead)

    def shutdown(self) -> None:
        self._timer.stop()
        self._render_generation += 1
        self._pending_mode = None
        for worker in list(self._workers):
            if worker.isRunning():
                logger.debug("preview shutdown waiting for worker gen=%s", worker.generation)
                worker.wait(3000)
            self._release_worker(worker)
        self._active_worker = None
        self.mixer.stop()
        self.video_cache.release_all()
        self.audio_cache.release_all()

    def _ensure_playback_audio_ready(self) -> None:
        """Decode and resample every audio-bearing timeline clip before the
        real-time mixer callback runs — avoids dropouts on the first blocks."""
        sr = self.mixer.sample_rate
        block_s = self.mixer.block_size / sr
        playhead = self.project_state.playhead
        seen: set[str] = set()
        for track in self.project_state.project.tracks:
            if track.type not in ("audio", "video"):
                continue
            for clip in track.clips:
                media = self.project_state.get_media(clip.media_id)
                if media is None or media.type not in ("audio", "video"):
                    continue
                if media.id in seen:
                    continue
                seen.add(media.id)
                try:
                    source = self.audio_cache.get(media.id, media.path, media.type)
                    if source is None:
                        continue
                    if clip.start <= playhead < clip.end:
                        local = max(0.0, (playhead - clip.start) + clip.trim_start)
                        source.slice_seconds_at_rate(local, block_s + 0.05, sr)
                    else:
                        source.slice_seconds_at_rate(clip.trim_start, block_s + 0.05, sr)
                    source.slice_seconds_at_rate(0.0, 0.01, sr)
                except Exception:
                    logger.exception("Playback audio prewarm failed for %s", media.path)

    # ---------------- background prewarm ----------------

    def prewarm_audio(self, media_assets: list[MediaAsset]) -> None:
        """Decode audio off the UI thread so first playback/scrub stays smooth.

        Large playlist imports decode files in parallel. STFT band precompute
        runs for the first track only — remaining tracks defer spectrum work
        until playback needs them.
        """
        assets = [m for m in media_assets if m.type in ("audio", "video")]
        if not assets:
            return

        mixer_sr = self.mixer.sample_rate
        cache = self.audio_cache

        def _warm_one(media: MediaAsset, *, spectrum: bool) -> None:
            try:
                source = cache.get(media.id, media.path, media.type)
                if source is None:
                    return
                source.slice_seconds_at_rate(0.0, 0.1, mixer_sr)
                if spectrum:
                    source.get_spectrum_bands(0.0)
            except Exception:
                logger.exception("Audio prewarm failed for %s", media.path)

        def _warm() -> None:
            _warm_one(assets[0], spectrum=True)
            if len(assets) == 1:
                return
            workers = min(4, len(assets) - 1)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_warm_one, media, spectrum=False) for media in assets[1:]]
                for future in as_completed(futures):
                    future.result()

        threading.Thread(target=_warm, name="camxora-audio-prewarm", daemon=True).start()
