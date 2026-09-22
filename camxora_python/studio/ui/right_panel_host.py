"""Right panel host — clip inspector, music panel, or library-section context."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from studio.core.playlist_scene_sync import SCENE_GRAPHICS
from studio.core.project_state import ProjectState
from studio.render.compositor import DEFAULT_HEIGHT, DEFAULT_WIDTH
from studio.ui.inspector_layout import INSPECTOR_PANEL_MIN_WIDTH
from studio.ui.inspector_panel import InspectorPanel
from studio.ui.music.music_inspector_panel import MusicInspectorPanel

_SECTION_COPY: dict[str, tuple[str, str]] = {
    "import": (
        "Import",
        "Your imported files live here. Drag them onto the timeline, or use the "
        "Media tab for stock samples.",
    ),
    "media": (
        "Media",
        "Stock video, photo, and audio samples. Pick a category in the sidebar.",
    ),
    "music": (
        "Music",
        "Pick a playlist template from the library. Song editing and styles ship next.",
    ),
    "audio": (
        "Audio",
        "Browse imported audio in the library. Drag onto an audio track, or enable "
        "a music visualizer on an audio clip from the Visualizer section.",
    ),
    "text": (
        "Text",
        "Drag a text preset onto the timeline to add a title or caption clip. "
        "Select the clip to edit wording, color, and position in this panel.",
    ),
    "sticker": (
        "Sticker",
        "Sticker packs and animated overlays will appear here in a future update.",
    ),
    "effects": (
        "Effects",
        "Drag effect presets from the library onto compatible clips. "
        "Select a clip on the timeline to fine-tune effect strength here.",
    ),
    "transition": (
        "Transition",
        "Transition presets between clips will appear here in a future update.",
    ),
    "caption": (
        "Caption",
        "Auto-caption and subtitle tools will appear here in a future update.",
    ),
    "filter": (
        "Filter",
        "Drag a filter swatch onto a video or image clip. Select the clip to "
        "change or remove the filter in this panel.",
    ),
    "visualizer": (
        "Visualizer",
        "Select an audio clip on the timeline, then pick a music visualizer style. "
        "The visualizer renders on the video preview during playback.",
    ),
}


class _SectionContextPanel(QWidget):
    def __init__(self, section_key: str, project_state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_state = project_state
        title_text, body_text = _SECTION_COPY.get(section_key, ("Panel", ""))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title = QLabel(title_text)
        title.setObjectName("DetailsSectionTitle")
        layout.addWidget(title)

        if section_key == "import":
            self._add_project_rows(layout)

        body = QLabel(body_text)
        body.setObjectName("EmptyHint")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(body)
        layout.addStretch(1)

    def _add_project_rows(self, layout: QVBoxLayout) -> None:
        project = self.project_state.project
        fps = project.snap_settings.frame_rate or 30.0
        for label, value in (
            ("Resolution", f"{DEFAULT_WIDTH}\u00d7{DEFAULT_HEIGHT}"),
            ("Frame rate", f"{fps:.2f} fps"),
            ("Media items", str(len(project.media_library))),
        ):
            name = QLabel(label)
            name.setObjectName("FieldLabel")
            val = QLabel(value)
            val.setObjectName("DetailsFieldValue")
            layout.addWidget(name)
            layout.addWidget(val)


class RightPanelHost(QFrame):
    """Clip inspector when a clip is selected; music panel in Music tab; else section help."""

    _IDX_INSPECTOR = 0
    _IDX_MUSIC = 1

    def __init__(self, project_state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorPanel")
        self.setMinimumWidth(INSPECTOR_PANEL_MIN_WIDTH)
        self.project_state = project_state
        self._active_section = "import"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        self.stack = QStackedWidget(self)

        self.inspector = InspectorPanel(project_state, self)
        inspector_scroll = QScrollArea(self)
        inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setFrameShape(QFrame.Shape.NoFrame)
        inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inspector_scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StaticContents, True)
        inspector_scroll.setWidget(self.inspector)
        self.stack.addWidget(inspector_scroll)

        self.music_panel = MusicInspectorPanel(project_state, self)
        self.stack.addWidget(self.music_panel)

        self._section_panels: dict[str, QWidget] = {}
        for key in _SECTION_COPY:
            if key == "music":
                continue
            panel = _SectionContextPanel(key, project_state, self)
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(panel)
            self._section_panels[key] = scroll
            self.stack.addWidget(scroll)

        layout.addWidget(self.stack)
        self.refresh()

    def set_library_section(self, section_key: str) -> None:
        self._active_section = section_key
        if section_key == "music":
            self.music_panel.show_music_tab()
        self.refresh()

    def set_music_playlist(self, preset_id: str) -> None:
        self._active_section = "music"
        # Apply the whole-look template but keep the right panel on the Music
        # tab so users can add tracks right away.
        self.music_panel.set_selected_playlist(preset_id, switch_tab=False)
        self.music_panel.show_music_tab()
        self.refresh()

    def refresh(self) -> None:
        self.inspector.refresh()
        clip_ref = (
            self.project_state.get_clip(self.project_state.selected_clip_id)
            if self.project_state.selected_clip_id
            else None
        )
        if clip_ref is not None:
            _track, clip = clip_ref
            if clip.kind == "playlist" or clip.scene_role == SCENE_GRAPHICS:
                self.music_panel.focus_playlist_settings()
                self.stack.setCurrentIndex(self._IDX_MUSIC)
            else:
                self.stack.setCurrentIndex(self._IDX_INSPECTOR)
        elif self._active_section == "music":
            self.stack.setCurrentIndex(self._IDX_MUSIC)
        elif self._active_section in self._section_panels:
            self.stack.setCurrentWidget(self._section_panels[self._active_section])


InspectorPanelHost = RightPanelHost
