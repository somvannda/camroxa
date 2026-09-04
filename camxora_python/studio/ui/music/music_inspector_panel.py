"""Right-panel inspector for the Music library section (Kcut-style)."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal

from PySide6.QtWidgets import (

    QFileDialog,

    QFrame,

    QHBoxLayout,

    QLabel,

    QLineEdit,

    QPushButton,

    QScrollArea,

    QStackedWidget,

    QVBoxLayout,

    QWidget,

)



from studio.app.file_dialog_state import last_open_dir, set_last_open_dir
from studio.core.models import MediaAsset

from studio.core.project_state import ProjectState

from studio.media.media_loader import default_cache_dir

from studio.ui.clip_inspector_tabs import InspectorTabRow

from studio.ui.inspector_layout import (

    FIELD_GAP,

    SECTION_GAP,

    TAB_TIER_GAP,

    add_section_spacer,

    apply_music_page_layout,

    apply_page_layout,

)

from studio.ui.icons.lucide_icons import BTN_SZ_TOOLBAR, ICON_COLOR, ICON_COLOR_ON_ACCENT, set_button_lucide_icon

from studio.ui.library_panel import MediaImportWorker

from studio.core.playlist_style import apply_style_to_settings, default_sub_template_for

from studio.ui.music.playlist_background_picker import PlaylistBackgroundPicker
from studio.ui.music.playlist_editor_panel import PlaylistEditorPanel
from studio.ui.music.playlist_scene_panels import PlaylistSceneComponentsPanel

from studio.ui.music.playlist_presets import PLAYLIST_PRESETS, PRESETS_BY_ID

from studio.ui.music.playlist_song_list import PlaylistSongList



_AUDIO_FILTER = "Audio files (*.mp3 *.wav *.m4a *.flac *.ogg *.aac)"





def _field_label(text: str) -> QLabel:

    label = QLabel(text)

    label.setObjectName("FieldLabel")

    return label


def _icon_button(name: str, *, primary: bool = False, tooltip: str = "") -> QPushButton:
    btn = QPushButton()
    btn.setObjectName("MusicIconButtonPrimary" if primary else "MusicIconButton")
    btn.setFixedSize(BTN_SZ_TOOLBAR, BTN_SZ_TOOLBAR)
    btn.setToolTip(tooltip)
    set_button_lucide_icon(
        btn,
        name,
        size=12,
        color=ICON_COLOR_ON_ACCENT if primary else ICON_COLOR,
    )
    return btn





class _ComingSoonPane(QWidget):

    def __init__(self, message: str, parent: QWidget | None = None) -> None:

        super().__init__(parent)

        layout = QVBoxLayout(self)

        apply_page_layout(layout)

        hint = QLabel(message)

        hint.setObjectName("EmptyHint")

        hint.setWordWrap(True)

        layout.addWidget(hint)

        layout.addStretch(1)





class MusicInspectorPanel(QWidget):

    """Music | Playlist | CC Lyric | Layout — Content | Background | Animation."""



    playlist_selected = Signal(str)

    songs_imported = Signal(list)  # list[MediaAsset]

    preview_changed = Signal()

    timeline_synced = Signal()



    _IDX_MUSIC = 0

    _IDX_PLAYLIST = 1



    def __init__(self, project_state: ProjectState, parent: QWidget | None = None) -> None:

        super().__init__(parent)

        self._project_state = project_state

        self._playlist = project_state.project.playlist

        if not self._playlist.colors:

            apply_style_to_settings(self._playlist)



        self._selected_id = self._playlist.template_id or (

            PLAYLIST_PRESETS[0].id if PLAYLIST_PRESETS else ""

        )

        self._import_worker: MediaImportWorker | None = None

        self._content_stack: QStackedWidget | None = None

        self._songs_empty: QLabel | None = None

        self._album_title: QLineEdit | None = None



        root = QVBoxLayout(self)

        root.setContentsMargins(0, 0, 0, 0)

        root.setSpacing(0)



        tier1 = InspectorTabRow(("Music", "Playlist", "CC Lyric", "Layout"), self)

        self._tier1 = tier1



        tier2 = InspectorTabRow(("Content", "Background", "Animation"), self)

        tier2.setObjectName("InspectorTier2TabRow")

        self._tier2 = tier2

        playlist_tier2 = InspectorTabRow(("Templates", "Settings"), self)

        playlist_tier2.setObjectName("InspectorTier2TabRow")

        playlist_tier2.setVisible(False)

        self._playlist_tier2 = playlist_tier2



        tabs_wrap = QWidget(self)

        tabs_layout = QVBoxLayout(tabs_wrap)

        tabs_layout.setContentsMargins(0, 0, 0, 0)

        tabs_layout.setSpacing(TAB_TIER_GAP)

        tabs_layout.addWidget(tier1)

        tabs_layout.addWidget(tier2)

        tabs_layout.addWidget(playlist_tier2)

        root.addWidget(tabs_wrap)

        root.addSpacing(SECTION_GAP)



        self._stack = QStackedWidget(self)

        self._music_page = self._build_music_page()

        self._playlist_editor = PlaylistEditorPanel(self)

        self._playlist_editor.settings_changed.connect(self._persist_playlist_settings)
        self._playlist_editor.settings_changed.connect(self.preview_changed.emit)

        self._stack.addWidget(self._music_page)

        self._stack.addWidget(self._playlist_editor)

        self._cc_lyric_panel = PlaylistSceneComponentsPanel()
        self._cc_lyric_panel.component_selected.connect(self._on_scene_component_selected)
        self._cc_lyric_panel.bind_settings(self._playlist)
        self._stack.addWidget(self._cc_lyric_panel)

        self._layout_panel = PlaylistSceneComponentsPanel()
        self._layout_panel.component_selected.connect(self._on_scene_component_selected)
        self._layout_panel.bind_settings(self._playlist)
        self._stack.addWidget(self._layout_panel)

        root.addWidget(self._stack, 1)



        tier1.tab_changed.connect(self._on_tier1)

        tier2.tab_changed.connect(self._on_tier2)

        playlist_tier2.tab_changed.connect(self._on_playlist_tier2)



        self._playlist_editor.load_settings(self._playlist)

        self._sync_album_fields()

        self._refresh_song_list()



    @property

    def _playlist_song_ids(self) -> list[str]:

        return self._playlist.song_ids



    @_playlist_song_ids.setter

    def _playlist_song_ids(self, value: list[str]) -> None:

        self._playlist.song_ids = value



    def _on_tier2(self, index: int) -> None:

        if self._content_stack is not None:

            self._content_stack.setCurrentIndex(index)

    def _on_playlist_tier2(self, index: int) -> None:

        self._playlist_editor.set_tab_index(index)



    def _build_music_page(self) -> QWidget:

        page = QWidget()

        layout = QVBoxLayout(page)

        apply_page_layout(layout)



        self._content_stack = QStackedWidget(page)

        self._content_stack.addWidget(self._build_content_page())

        bg_page = QWidget()
        bg_layout = QVBoxLayout(bg_page)
        apply_page_layout(bg_layout)
        self._music_background_picker = PlaylistBackgroundPicker()
        self._music_background_picker.background_changed.connect(self._on_scene_background_changed)
        self._music_background_picker.bind_settings(self._playlist)
        bg_layout.addWidget(self._music_background_picker)
        bg_layout.addStretch(1)
        self._content_stack.addWidget(bg_page)

        self._content_stack.addWidget(_ComingSoonPane("Animation presets are coming soon."))

        layout.addWidget(self._content_stack, 1)

        return page



    def _build_content_page(self) -> QWidget:

        page = QWidget()

        layout = QVBoxLayout(page)

        apply_music_page_layout(layout)



        layout.addWidget(_field_label("Album"))

        layout.addSpacing(FIELD_GAP)



        self._album_title = QLineEdit()

        self._album_title.setPlaceholderText("Album title…")

        self._album_title.textChanged.connect(self._on_album_title_changed)

        layout.addWidget(self._album_title)



        add_section_spacer(layout)

        songs_row = QHBoxLayout()

        songs_row.setSpacing(6)

        songs_row.addWidget(_field_label("Songs"))

        songs_row.addStretch(1)

        add_btn = _icon_button("plus", primary=True, tooltip="Add song files")

        add_btn.clicked.connect(self._pick_song_files)

        clear_btn = _icon_button("trash-2", tooltip="Clear songs")

        clear_btn.clicked.connect(self._clear_songs)

        songs_row.addWidget(add_btn)

        songs_row.addWidget(clear_btn)

        layout.addLayout(songs_row)



        self._songs_empty = QLabel("No songs yet — click + to add files, or import via the Import tab.")

        self._songs_empty.setObjectName("EmptyHint")

        self._songs_empty.setWordWrap(True)

        layout.addSpacing(FIELD_GAP)

        layout.addWidget(self._songs_empty)



        self._song_list = PlaylistSongList()

        self._song_list.order_changed.connect(self._on_song_order_changed)

        layout.addWidget(self._song_list)

        layout.addStretch(1)

        return page



    def _on_tier1(self, index: int) -> None:

        self._stack.setCurrentIndex(index)

        self._tier2.setVisible(index == self._IDX_MUSIC)

        self._playlist_tier2.setVisible(index == self._IDX_PLAYLIST)



    def show_playlist_tab(self) -> None:

        self._tier1.set_active_index(self._IDX_PLAYLIST)

        self._stack.setCurrentIndex(self._IDX_PLAYLIST)

        self._tier2.setVisible(False)

        self._playlist_tier2.setVisible(True)


    def show_music_tab(self) -> None:
        """Default the Music panel to the Music tab (Album/Songs content)."""
        self._tier1.set_active_index(self._IDX_MUSIC)
        self._stack.setCurrentIndex(self._IDX_MUSIC)
        self._tier2.setVisible(True)
        self._playlist_tier2.setVisible(False)



    def focus_playlist_settings(self) -> None:

        self.show_playlist_tab()

        self._playlist_tier2.set_active_index(1)

        self._playlist_editor.set_tab_index(1)



    def set_selected_playlist(self, preset_id: str, *, switch_tab: bool = False) -> None:

        if preset_id not in PRESETS_BY_ID:

            return

        self._selected_id = preset_id

        preset = PRESETS_BY_ID[preset_id]

        self._playlist.template_id = preset_id
        self._playlist.sub_template_id = default_sub_template_for(preset_id)
        self._playlist.color_filter_id = "original"
        apply_style_to_settings(self._playlist)

        self._playlist_editor.load_settings(self._playlist)

        if switch_tab:

            self.show_playlist_tab()

        self.preview_changed.emit()
        self._sync_playlist_timeline()



    def _on_scene_background_changed(self) -> None:
        self._persist_playlist_settings()
        self._sync_playlist_timeline()



    def _on_scene_component_selected(self, component_id: str) -> None:
        self._project_state.set_playlist_selected_component(component_id)
        self._playlist.selected_component = component_id
        self._playlist_editor.load_settings(self._playlist)
        self.show_playlist_tab()
        self._playlist_editor.set_tab_index(1)
        self.preview_changed.emit()



    def selected_preset_id(self) -> str:

        return self._selected_id



    def _pick_song_files(self) -> None:

        if self._import_worker is not None and self._import_worker.isRunning():

            return

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add song files",
            last_open_dir("add_song"),
            _AUDIO_FILTER,
        )

        if not paths:

            return

        set_last_open_dir("add_song", paths)

        self._import_worker = MediaImportWorker(paths, default_cache_dir(), self)

        self._import_worker.finished_ok.connect(self._on_songs_imported)

        self._import_worker.failed.connect(self._on_songs_import_failed)

        self._import_worker.start()



    def _on_songs_import_failed(self, message: str) -> None:

        self._import_worker = None

        if self._songs_empty is not None:

            self._songs_empty.setText(f"Import failed: {message}")



    def _on_songs_imported(self, assets: list[MediaAsset]) -> None:

        self._import_worker = None

        from studio.render.playlist_cache import invalidate_playlist_render_cache

        added: list[MediaAsset] = []

        for asset in assets:

            if asset.type != "audio":

                continue

            existing = self._project_state.find_media_by_path(asset.path)
            if existing is not None:
                media = existing
            else:
                if self._project_state.get_media(asset.id) is None:
                    self._project_state.add_media(asset)
                media = asset

            if media.id in self._playlist_song_ids:
                continue

            self._playlist_song_ids.append(media.id)
            added.append(media)

        self._refresh_song_list()

        if added:
            invalidate_playlist_render_cache()
            self.songs_imported.emit(added)

        self._sync_playlist_timeline()



    def _clear_songs(self) -> None:

        self._playlist_song_ids.clear()

        self._refresh_song_list()

        self._sync_playlist_timeline()



    def _on_song_order_changed(self, ordered_ids: list[str]) -> None:

        table_ids = self._song_list.song_ids()

        row_count = self._song_list._table.rowCount()

        if len(table_ids) == row_count:

            ordered_ids = table_ids

        if not ordered_ids or len(ordered_ids) != row_count:

            self._refresh_song_list()

            return

        if ordered_ids == self._playlist_song_ids:

            self._song_list.renumber_rows()

            return

        self._playlist_song_ids = ordered_ids

        self._song_list.renumber_rows()

        self._sync_playlist_timeline()

    def _renumber_song_list(self) -> None:

        self._song_list.renumber_rows()



    def _refresh_song_list(self) -> None:

        if self._songs_empty is None:

            return

        media_by_id: dict[str, MediaAsset] = {}

        valid_ids: list[str] = []

        for media_id in self._playlist_song_ids:

            media = self._project_state.get_media(media_id)

            if media is not None:

                media_by_id[media_id] = media

                valid_ids.append(media_id)

        if valid_ids != self._playlist_song_ids:

            self._playlist_song_ids = valid_ids

        has_songs = bool(media_by_id)

        self._songs_empty.setVisible(not has_songs)

        self._song_list.set_songs(self._playlist_song_ids, media_by_id, current_index=self._current_track_index())



    def _current_track_index(self) -> int | None:
        if not self._playlist_song_ids:
            return None
        elapsed = 0.0
        playhead = self._project_state.playhead
        for index, media_id in enumerate(self._playlist_song_ids):
            media = self._project_state.get_media(media_id)
            duration = float(media.duration or 0) if media else 0.0
            if duration <= 0:
                continue
            if playhead < elapsed + duration:
                return index
            elapsed += duration
        return len(self._playlist_song_ids) - 1



    def _sync_playlist_timeline(self) -> None:
        self._project_state.sync_playlist_to_timeline(record_undo=True)
        self.timeline_synced.emit()
        self.preview_changed.emit()



    def _on_album_title_changed(self, text: str) -> None:

        self._playlist.album_title = text

        self.preview_changed.emit()



    def _sync_album_fields(self) -> None:

        if self._album_title is not None:

            self._album_title.blockSignals(True)

            self._album_title.setText(self._playlist.album_title)

            self._album_title.blockSignals(False)



    def _persist_playlist_settings(self) -> None:

        from studio.render.playlist_cache import invalidate_playlist_render_cache

        self._playlist = self._playlist_editor.settings()

        self._project_state.project.playlist = self._playlist
        invalidate_playlist_render_cache()
        self._music_background_picker.bind_settings(self._playlist)
        self._cc_lyric_panel.bind_settings(self._playlist)
        self._layout_panel.bind_settings(self._playlist)
        from studio.core.playlist_scene_sync import sync_playlist_scene_to_timeline

        sync_playlist_scene_to_timeline(self._project_state, record_undo=False)
        self.timeline_synced.emit()



    def refresh_playhead_track(self) -> None:

        index = self._current_track_index()

        if index is not None:

            self._song_list.set_current_index(index)

