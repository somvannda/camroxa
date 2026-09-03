"""Top-level application window: topbar, library, preview/timeline, inspector.

This module wires the four-pane layout that later phases populate:
- Topbar: project name, undo/redo, export
- Library panel (left): Media / Text / Effects / Visualizer tabs
- Center: preview canvas + transport, timeline underneath
- Inspector panel (right): per-selection property form
"""

from __future__ import annotations

import os
import threading

from PySide6.QtCore import Qt, QThread, QTimer, Signal, QSize
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from studio.core.project_state import ProjectState
from studio.export.ffmpeg_export import ExportCancelled, ExportError, export_project
from studio.ui.icons.lucide_icons import (
    BTN_SZ_ICON,
    ICON_COLOR,
    ICON_COLOR_ON_ACCENT,
    ICON_SZ_TOOLBAR,
    lucide_icon,
    set_button_lucide_icon,
)
from studio.ui.right_panel_host import RightPanelHost
from studio.ui.inspector_layout import INSPECTOR_PANEL_DEFAULT_WIDTH
from studio.ui.library_panel import LibraryPanel
from studio.ui.preview_widget import PlaybackController, PreviewWidget
from studio.ui.timeline.timeline_view import TimelineWrap


class Topbar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Topbar")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        logo_box = QVBoxLayout()
        logo_box.setSpacing(0)
        logo_row = QHBoxLayout()
        logo_row.setSpacing(6)
        logo_label = QLabel("Camxora")
        logo_label.setObjectName("LogoLabel")
        sub_label = QLabel("video studio")
        sub_label.setObjectName("LogoSubLabel")
        logo_row.addWidget(logo_label)
        logo_row.addWidget(sub_label)
        logo_row.addStretch(1)
        logo_box.addLayout(logo_row)
        layout.addLayout(logo_box)

        self.project_name_edit = QLineEdit("Untitled Project")
        self.project_name_edit.setObjectName("ProjectNameEdit")
        self.project_name_edit.setFixedWidth(200)
        layout.addWidget(self.project_name_edit)

        layout.addStretch(1)

        self.open_btn = QPushButton()
        self.open_btn.setObjectName("IconButton")
        self.open_btn.setFixedSize(BTN_SZ_ICON, BTN_SZ_ICON)
        self.open_btn.setToolTip("Open project (Ctrl+O)")
        set_button_lucide_icon(self.open_btn, "file", size=ICON_SZ_TOOLBAR, color=ICON_COLOR)

        self.save_btn = QPushButton()
        self.save_btn.setObjectName("IconButton")
        self.save_btn.setFixedSize(BTN_SZ_ICON, BTN_SZ_ICON)
        self.save_btn.setToolTip("Save project (Ctrl+S)")
        set_button_lucide_icon(self.save_btn, "download", size=ICON_SZ_TOOLBAR, color=ICON_COLOR)

        self.undo_btn = QPushButton()
        self.undo_btn.setObjectName("IconButton")
        self.undo_btn.setFixedSize(BTN_SZ_ICON, BTN_SZ_ICON)
        self.undo_btn.setToolTip("Undo (Ctrl+Z)")
        set_button_lucide_icon(self.undo_btn, "undo-2", size=ICON_SZ_TOOLBAR, color=ICON_COLOR)

        self.redo_btn = QPushButton()
        self.redo_btn.setObjectName("IconButton")
        self.redo_btn.setFixedSize(BTN_SZ_ICON, BTN_SZ_ICON)
        self.redo_btn.setToolTip("Redo (Ctrl+Y)")
        set_button_lucide_icon(self.redo_btn, "redo-2", size=ICON_SZ_TOOLBAR, color=ICON_COLOR)

        self.export_btn = QPushButton(" Export")
        self.export_btn.setObjectName("PrimaryButton")
        self.export_btn.setIcon(lucide_icon("download", size=ICON_SZ_TOOLBAR, color=ICON_COLOR_ON_ACCENT))
        self.export_btn.setIconSize(QSize(ICON_SZ_TOOLBAR, ICON_SZ_TOOLBAR))

        layout.addWidget(self.open_btn)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.undo_btn)
        layout.addWidget(self.redo_btn)
        layout.addWidget(self.export_btn)


class InspectorPanelHost(RightPanelHost):
    """Backward-compatible name for the right-side context + inspector host."""


class ExportWorker(QThread):
    """Runs `export_project` off the UI thread so the app stays responsive.

    `export_project` itself has zero Qt dependencies (per the architecture
    decision to keep preview/export rendering pure), so this thin QThread
    subclass is the only place export touches Qt.
    """

    progress = Signal(float)
    finished_ok = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, project_state: ProjectState, output_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_state = project_state
        self.output_path = output_path
        self._cancel_requested = threading.Event()

    def request_cancel(self) -> None:
        self._cancel_requested.set()

    def run(self) -> None:  # noqa: D401
        try:
            export_project(
                self.project_state,
                self.output_path,
                progress_callback=lambda p: self.progress.emit(p),
                cancel_check=self._cancel_requested.is_set,
            )
        except ExportCancelled:
            self.cancelled.emit()
        except (ExportError, ValueError, RuntimeError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - surface unexpected errors to the UI instead of crashing
            self.failed.emit(f"Unexpected export error: {exc}")
        else:
            self.finished_ok.emit(self.output_path)


class MainWindow(QMainWindow):
    def __init__(self, project_state: ProjectState | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Camxora Studio")
        self.resize(1440, 900)

        self.project_state = project_state or ProjectState()
        self._library_section = "import"

        root = QWidget(self)
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.topbar = Topbar(root)
        outer.addWidget(self.topbar)

        main_split = QSplitter(Qt.Orientation.Horizontal, root)
        main_split.setHandleWidth(1)
        outer.addWidget(main_split, 1)

        self.topbar.project_name_edit.setText(self.project_state.project.name)
        self.topbar.project_name_edit.editingFinished.connect(self._on_project_name_edited)

        self.library_panel = LibraryPanel(self.project_state, main_split)
        self.library_panel.setMinimumWidth(340)
        self.library_panel.setMaximumWidth(460)
        main_split.addWidget(self.library_panel)

        center = QWidget(main_split)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        center_split = QSplitter(Qt.Orientation.Vertical, center)
        center_split.setHandleWidth(1)
        center_layout.addWidget(center_split, 1)

        self.preview_widget = PreviewWidget(center_split)
        center_split.addWidget(self.preview_widget)

        self.timeline_wrap = TimelineWrap(self.project_state, center_split)
        center_split.addWidget(self.timeline_wrap)
        center_split.setSizes([560, 280])

        main_split.addWidget(center)

        self.inspector_host = InspectorPanelHost(self.project_state, main_split)
        main_split.addWidget(self.inspector_host)

        main_split.setCollapsible(0, False)
        main_split.setCollapsible(2, False)
        main_split.setSizes([380, 720, INSPECTOR_PANEL_DEFAULT_WIDTH])
        main_split.setStretchFactor(0, 0)
        main_split.setStretchFactor(1, 1)
        main_split.setStretchFactor(2, 0)

        self.toast_label = QLabel("", root)
        self.toast_label.setObjectName("Toast")
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.hide()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.toast_label.hide)

        self.playback_controller = PlaybackController(self.project_state, self.preview_widget)
        self.preview_widget.attach_transform_overlay(self.project_state)
        self.preview_widget.attach_playlist_overlay(self.project_state)
        if self.preview_widget.transform_overlay is not None:
            overlay = self.preview_widget.transform_overlay
            overlay.preview_changed.connect(self.playback_controller.render_drag_preview)
            overlay.transform_committed.connect(self.inspector_host.refresh)
            overlay.transform_committed.connect(self._refresh_undo_redo_buttons)
            overlay.transform_committed.connect(
                lambda: self.playback_controller.render_now(interactive=False)
            )
        if self.preview_widget.playlist_overlay is not None:
            pl_overlay = self.preview_widget.playlist_overlay
            pl_overlay.preview_changed.connect(self.playback_controller.render_drag_preview)
            pl_overlay.layout_committed.connect(
                lambda: self.playback_controller.render_now(interactive=False)
            )
        self.timeline_wrap.selection_changed.connect(self._refresh_preview_transform_overlay)
        self.library_panel.media_imported.connect(self.playback_controller.prewarm_audio)
        self.library_panel.toast_requested.connect(self.show_toast)

        self.timeline_wrap.selection_changed.connect(self.inspector_host.refresh)
        self.timeline_wrap.structure_changed.connect(self.inspector_host.refresh)
        self.library_panel.section_changed.connect(self.inspector_host.set_library_section)
        self.library_panel.section_changed.connect(self._on_library_section_changed)
        self.library_panel.music_tab.playlist_selected.connect(self.inspector_host.set_music_playlist)
        self.inspector_host.music_panel.playlist_selected.connect(self.library_panel.select_music_playlist)
        self.inspector_host.music_panel.songs_imported.connect(self._on_music_songs_imported)
        self.inspector_host.music_panel.preview_changed.connect(self._schedule_preview_render)
        self.inspector_host.music_panel.timeline_synced.connect(self._on_playlist_timeline_synced)
        self.inspector_host.inspector.changed.connect(self._on_inspector_changed)
        self.inspector_host.inspector.preview_changed.connect(self._schedule_preview_render)
        self.timeline_wrap.toast_requested.connect(self.show_toast)
        self.timeline_wrap.structure_changed.connect(self.playback_controller.render_now)
        self.timeline_wrap.structure_changed.connect(self._refresh_undo_redo_buttons)
        self.inspector_host.inspector.changed.connect(self._refresh_undo_redo_buttons)
        self.timeline_wrap.seek_requested.connect(self.playback_controller.seek)
        self.preview_widget.transport.step_back_requested.connect(lambda: self._step_playhead(-1))
        self.preview_widget.transport.step_forward_requested.connect(lambda: self._step_playhead(1))
        self.preview_widget.transport.fullscreen_requested.connect(self._toggle_preview_fullscreen)
        self.playback_controller.tick.connect(self._on_playback_tick)
        self.topbar.export_btn.clicked.connect(self._on_export_clicked)
        self.topbar.undo_btn.clicked.connect(self._on_undo_clicked)
        self.topbar.redo_btn.clicked.connect(self._on_redo_clicked)
        self.topbar.save_btn.clicked.connect(self._on_save_clicked)
        self.topbar.open_btn.clicked.connect(self._on_open_clicked)

        self._export_worker: ExportWorker | None = None
        self._export_progress_dialog: QProgressDialog | None = None
        self._current_project_path: str | None = None
        self._preview_render_timer = QTimer(self)
        self._preview_render_timer.setSingleShot(True)
        self._preview_render_timer.setInterval(16)
        self._preview_render_timer.timeout.connect(self._on_debounced_preview_render)
        self._full_quality_timer = QTimer(self)
        self._full_quality_timer.setSingleShot(True)
        self._full_quality_timer.setInterval(400)
        self._full_quality_timer.timeout.connect(
            lambda: self.playback_controller.render_now(interactive=False)
        )

        self._setup_shortcuts()
        self._refresh_undo_redo_buttons()
        self.preview_widget.set_player_title(f"Player — {self.project_state.project.name}")

    def _schedule_preview_render(self) -> None:
        self._preview_render_timer.start()

    def _on_debounced_preview_render(self) -> None:
        if self.project_state.playlist_preview_active:
            self._full_quality_timer.stop()
            self.playback_controller.render_now(interactive=False)
            return
        self.playback_controller.render_now(interactive=True)
        self._full_quality_timer.start()

    def _on_inspector_changed(self) -> None:
        """Undo stack only — preview is driven by debounced preview_changed."""
        self._refresh_undo_redo_buttons()

    def _on_music_songs_imported(self, assets: list) -> None:
        self.playback_controller.prewarm_audio(assets)
        self.library_panel.audio_tab.refresh()
        count = len(assets)
        self.show_toast(f"Added {count} song{'s' if count != 1 else ''} to playlist")
        self._sync_playlist_preview_mode()
        self._schedule_preview_render()

    def _on_playlist_timeline_synced(self) -> None:
        self.timeline_wrap.refresh_after_external_change()
        self.timeline_wrap.graphics_view.horizontalScrollBar().setValue(0)
        self._refresh_undo_redo_buttons()
        self._sync_playlist_preview_mode()

    def _sync_playlist_preview_mode(self) -> None:
        """Keep playlist preview visible when the project has songs, even off the Music tab."""
        has_content = self.project_state.has_playlist_content()
        in_music = self._library_section == "music"
        self.project_state.playlist_preview_active = has_content or in_music
        self.project_state.playlist_overlay_enabled = self.project_state.playlist_preview_active

    def _on_library_section_changed(self, section_key: str) -> None:
        self._library_section = section_key
        self._sync_playlist_preview_mode()
        self.preview_widget._sync_overlays()
        self._full_quality_timer.stop()
        self.playback_controller.render_now(interactive=False)

    def _refresh_preview_transform_overlay(self) -> None:
        from studio.core.playlist_scene_sync import SCENE_GRAPHICS

        clip_id = self.project_state.selected_clip_id
        if clip_id:
            ref = self.project_state.get_clip(clip_id)
            if ref is not None:
                _track, clip = ref
                if clip.kind == "playlist" or clip.scene_role == SCENE_GRAPHICS:
                    comp = "song_list"
                    self.project_state.set_playlist_selected_component(comp)
        self.preview_widget._sync_overlays()

    def _toggle_preview_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_playback_tick(self, _time: float) -> None:
        self.timeline_wrap.graphics_view.update_playhead()
        self.timeline_wrap.ruler.set_playhead_time(self.project_state.playhead)
        if self.project_state.playlist_preview_active:
            self.inspector_host.music_panel.refresh_playhead_track()
        if self.project_state.is_playing:
            self.timeline_wrap.follow_playhead_during_playback()

    def _step_playhead(self, direction: int) -> None:
        fps = self.project_state.project.snap_settings.frame_rate or 30.0
        dt = direction / fps
        new_time = max(0.0, min(self.project_state.project.duration, self.project_state.playhead + dt))
        self.playback_controller.seek(new_time)

    def _setup_shortcuts(self) -> None:
        from PySide6.QtGui import QKeySequence, QShortcut

        split_shortcut = QShortcut(QKeySequence(Qt.Key.Key_S), self.timeline_wrap)
        split_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        split_shortcut.activated.connect(self.timeline_wrap.graphics_view.split_selected)

        for key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            delete_shortcut = QShortcut(QKeySequence(key), self.timeline_wrap)
            delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            delete_shortcut.activated.connect(self.timeline_wrap.graphics_view.delete_selected)

        space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        space_shortcut.activated.connect(self._on_space_play_shortcut)

        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self._on_undo_clicked)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self._on_redo_clicked)
        redo_alt_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        redo_alt_shortcut.activated.connect(self._on_redo_clicked)
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._on_save_clicked)
        open_shortcut = QShortcut(QKeySequence.StandardKey.Open, self)
        open_shortcut.activated.connect(self._on_open_clicked)

        snap_shortcut = QShortcut(QKeySequence(Qt.Key.Key_N), self.timeline_wrap)
        snap_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        snap_shortcut.activated.connect(self.timeline_wrap.toggle_snap_enabled)

        ripple_shortcut = QShortcut(QKeySequence(Qt.Key.Key_R), self.timeline_wrap)
        ripple_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        ripple_shortcut.activated.connect(self.timeline_wrap.toggle_ripple_edit)

        gv = self.timeline_wrap.graphics_view
        for seq, handler in (
            (QKeySequence(Qt.Key.Key_Left), lambda: gv.nudge_selected(-1)),
            (QKeySequence(Qt.Key.Key_Right), lambda: gv.nudge_selected(1)),
            (QKeySequence("Shift+Left"), lambda: gv.nudge_selected(-1, large_step=True)),
            (QKeySequence("Shift+Right"), lambda: gv.nudge_selected(1, large_step=True)),
            (QKeySequence("Alt+Left"), lambda: gv.nudge_selected(-1, snap_to_edge=True)),
            (QKeySequence("Alt+Right"), lambda: gv.nudge_selected(1, snap_to_edge=True)),
        ):
            shortcut = QShortcut(seq, self.timeline_wrap)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)

    @staticmethod
    def _focus_blocks_space_playback(focus_widget: QWidget | None) -> bool:
        """Return True when Space should type into a field, not toggle transport."""
        if focus_widget is None:
            return False
        return isinstance(
            focus_widget,
            (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox),
        )

    def _on_space_play_shortcut(self) -> None:
        if self._focus_blocks_space_playback(QApplication.focusWidget()):
            return
        self.playback_controller.toggle_play()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._export_worker is not None and self._export_worker.isRunning():
            self._export_worker.request_cancel()
            self._export_worker.wait(5000)
        self.library_panel.media_tab.wait_for_import_to_finish()
        self.timeline_wrap.graphics_view.wait_for_preview_workers()
        self.playback_controller.shutdown()
        super().closeEvent(event)

    def show_toast(self, message: str, duration_ms: int = 2200) -> None:
        self.toast_label.setText(message)
        self.toast_label.adjustSize()
        self._position_toast()
        self.toast_label.show()
        self.toast_label.raise_()
        self._toast_timer.start(duration_ms)

    def _position_toast(self) -> None:
        root = self.centralWidget()
        if root is None:
            return
        x = (root.width() - self.toast_label.width()) // 2
        y = root.height() - self.toast_label.height() - 18
        self.toast_label.move(max(0, x), max(0, y))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.toast_label.isVisible():
            self._position_toast()

    def _on_project_name_edited(self) -> None:
        self.project_state.project.name = self.topbar.project_name_edit.text().strip() or "Untitled Project"
        self.preview_widget.set_player_title(f"Player — {self.project_state.project.name}")
        self.inspector_host.refresh()

    def _on_export_clicked(self) -> None:
        if self._export_worker is not None and self._export_worker.isRunning():
            return

        if self.project_state.project.duration <= 0:
            self.show_toast("Nothing to export — the timeline is empty.")
            return

        self.playback_controller.set_playing(False)

        default_name = f"{self.project_state.project.name or 'Untitled Project'}.mp4"
        default_path = os.path.join(os.path.expanduser("~"), default_name)
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Export video", default_path, "MP4 video (*.mp4)"
        )
        if not output_path:
            return
        if not output_path.lower().endswith(".mp4"):
            output_path += ".mp4"

        self._export_progress_dialog = QProgressDialog("Exporting video…", "Cancel", 0, 100, self)
        self._export_progress_dialog.setWindowTitle("Export")
        self._export_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._export_progress_dialog.setMinimumDuration(0)
        self._export_progress_dialog.setAutoClose(False)
        self._export_progress_dialog.setAutoReset(False)
        self._export_progress_dialog.setValue(0)

        self._export_worker = ExportWorker(self.project_state, output_path, self)
        self._export_progress_dialog.canceled.connect(self._export_worker.request_cancel)
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.finished_ok.connect(self._on_export_finished)
        self._export_worker.failed.connect(self._on_export_failed)
        self._export_worker.cancelled.connect(self._on_export_cancelled)

        self.topbar.export_btn.setEnabled(False)
        self._export_worker.start()

    def _on_export_progress(self, fraction: float) -> None:
        if self._export_progress_dialog is not None:
            self._export_progress_dialog.setValue(min(100, max(0, int(fraction * 100))))

    def _teardown_export_ui(self) -> None:
        if self._export_progress_dialog is not None:
            self._export_progress_dialog.close()
            self._export_progress_dialog = None
        self.topbar.export_btn.setEnabled(True)
        self._export_worker = None

    def _on_export_finished(self, output_path: str) -> None:
        self._teardown_export_ui()
        self.show_toast(f"Export complete: {output_path}", duration_ms=3200)

    def _on_export_failed(self, message: str) -> None:
        self._teardown_export_ui()
        QMessageBox.critical(self, "Export failed", message)

    def _on_export_cancelled(self) -> None:
        self._teardown_export_ui()
        self.show_toast("Export cancelled.")

    # ---------------- undo / redo ----------------

    def _refresh_undo_redo_buttons(self) -> None:
        self.topbar.undo_btn.setEnabled(self.project_state.can_undo())
        self.topbar.redo_btn.setEnabled(self.project_state.can_redo())

    def _after_project_mutated_externally(self) -> None:
        """Re-sync every panel after the `Project` was swapped/restored
        wholesale (undo, redo, or a fresh project load) rather than mutated
        incrementally through the normal per-gesture `ProjectState` calls."""
        self.timeline_wrap.refresh_after_external_change()
        self.inspector_host.refresh()
        self.playback_controller.render_now()
        self.topbar.project_name_edit.setText(self.project_state.project.name)
        self.preview_widget.set_player_title(f"Player — {self.project_state.project.name}")
        self.library_panel.audio_tab.refresh()
        self._refresh_undo_redo_buttons()

    def _on_undo_clicked(self) -> None:
        if self.project_state.undo():
            self._after_project_mutated_externally()

    def _on_redo_clicked(self) -> None:
        if self.project_state.redo():
            self._after_project_mutated_externally()

    # ---------------- project save / load ----------------

    def _on_save_clicked(self) -> None:
        from studio.core.project_io import PROJECT_FILE_FILTER, save_project

        default_name = f"{self.project_state.project.name or 'Untitled Project'}.camxora"
        default_path = self._current_project_path or os.path.join(os.path.expanduser("~"), default_name)
        path, _ = QFileDialog.getSaveFileName(self, "Save project", default_path, PROJECT_FILE_FILTER)
        if not path:
            return
        try:
            save_project(self.project_state, path)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self._current_project_path = path
        self.show_toast(f"Project saved: {path}")

    def _on_open_clicked(self) -> None:
        from studio.core.project_io import PROJECT_FILE_FILTER, ProjectLoadError, load_project

        path, _ = QFileDialog.getOpenFileName(
            self, "Open project", os.path.expanduser("~"), PROJECT_FILE_FILTER
        )
        if not path:
            return
        try:
            new_state = load_project(path)
        except ProjectLoadError as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return

        self.playback_controller.set_playing(False)
        self.project_state.replace_project(new_state.project)
        self._current_project_path = path
        self._after_project_mutated_externally()
        self.show_toast(f"Project opened: {path}")
