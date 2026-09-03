"""Left library panel: Media / Text / Effects / Visualizer tabs.

The Media tab is fully wired (import dialog, drag-drop files onto the
import zone, thumbnail grid, and drag-to-timeline sources). Text/Effects/
Visualizer tabs are populated in their respective later phases.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, QObject, QPoint, Qt, QThread, Signal
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from studio.app.theme import PALETTE
from studio.core.models import MediaAsset
from studio.core.project_state import TEXT_PRESETS, ProjectState
from studio.core.registries import FILTERS, TEXT_PRESETS_UI, VIZ_STYLES
from studio.core.time_utils import fmt_time
from studio.media.media_loader import default_cache_dir, import_files
from studio.ui.music.music_category_rail import MusicCategoryRail
from studio.ui.music.music_library_tab import MusicLibraryTab
from studio.ui.icons.lucide_icons import (
    ICON_COLOR,
    ICON_COLOR_DIM,
    ICON_SZ_LIBRARY,
    MEDIA_TYPE_ICON,
    lucide_pixmap,
    set_button_lucide_icon,
)

LIBRARY_TOP_MENU: tuple[tuple[str, str, str], ...] = (
    ("import", "Import", "upload"),
    ("media", "Media", "video"),
    ("music", "Music", "music-2"),
    ("audio", "Audio", "music-2"),
    ("text", "Text", "type"),
    ("sticker", "Sticker", "sparkles"),
    ("effects", "Effects", "sparkles"),
    ("transition", "Transition", "arrow-left-right"),
    ("caption", "Caption", "type"),
    ("filter", "Filter", "image"),
    ("visualizer", "Visualizer", "volume-2"),
)

# Sidebar filters for Import (user files) and Media (stock samples).
MEDIA_SIDE_RAIL: tuple[tuple[str, str, str], ...] = (
    ("all", "All", "layers"),
    ("video", "Video", "video"),
    ("photo", "Photo", "image"),
    ("audio", "Audio", "music-2"),
)

MEDIA_MIME_TYPE = "application/x-camxora-media"
FILTER_MIME_TYPE = "application/x-camxora-filter"
TEXT_PRESET_MIME_TYPE = "application/x-camxora-text-preset"

FILE_DIALOG_FILTER = (
    "Media files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v "
    "*.mp3 *.wav *.m4a *.flac *.ogg *.aac "
    "*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
)


def _section_title(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("SectionTitle")
    return label


def _empty_hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("EmptyHint")
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def _icon_button_width(label: str) -> int:
    """Wider cells for long single-line labels such as Music Stage."""
    return 68 if len(label) > 10 else 58


class _LibraryIconButton(QFrame):
    """14px icon above label — both horizontally centered."""

    clicked = Signal()

    _ICON_PX = 14

    def __init__(self, label: str, icon_name: str, width: int, height: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LibraryIconButton")
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_name = icon_name
        self._checked = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel()
        self._icon.setFixedSize(self._ICON_PX, self._ICON_PX)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignHCenter)

        text = QLabel(label)
        text.setObjectName("LibraryIconLabel")
        text.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        text.setWordWrap(False)
        layout.addWidget(text, 0, Qt.AlignmentFlag.AlignHCenter)

        self.setToolTip(label)
        self._sync_icon()

    def setChecked(self, checked: bool) -> None:
        self._checked = checked
        self.setProperty("active", checked)
        self._sync_icon()
        self.style().unpolish(self)
        self.style().polish(self)

    def isChecked(self) -> bool:
        return self._checked

    def _sync_icon(self) -> None:
        color = PALETTE.accent if self._checked else ICON_COLOR_DIM
        self._icon.setPixmap(lucide_pixmap(self._icon_name, size=self._ICON_PX, color=color))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CapCutImportZone(QFrame):
    """CapCut-style large drop zone — centered plus icon and helper copy."""

    files_dropped = Signal(list)

    _DEFAULT_TEXT = "Drag and drop videos, photos, and audio files here"
    _BUSY_TEXT = "Importing…"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CapCutImportZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(160)
        self._busy = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 28)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel()
        self._icon.setPixmap(lucide_pixmap("plus", size=28, color=ICON_COLOR_DIM))
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        self._label = QLabel(self._DEFAULT_TEXT)
        self._label.setObjectName("CapCutImportTitle")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        icon_name = "loader-2" if busy else "plus"
        self._icon.setPixmap(lucide_pixmap(icon_name, size=28, color=ICON_COLOR_DIM))
        self._label.setText(self._BUSY_TEXT if busy else self._DEFAULT_TEXT)
        self.setCursor(Qt.CursorShape.BusyCursor if busy else Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._busy and event.button() == Qt.MouseButton.LeftButton:
            self._open_file_dialog()
        super().mousePressEvent(event)

    def _open_file_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Import media", "", FILE_DIALOG_FILTER)
        if paths:
            self.files_dropped.emit(paths)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if not self._busy and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        if self._busy:
            event.ignore()
            return
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()


class CompactImportBar(QFrame):
    """Small import toolbar shown once the library has at least one file."""

    import_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CompactImportBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(8)

        import_btn = QPushButton(" Import")
        import_btn.setObjectName("CompactImportButton")
        set_button_lucide_icon(import_btn, "plus", size=14, color=PALETTE.accent, clear_text=False)
        import_btn.clicked.connect(self.import_clicked.emit)
        layout.addWidget(import_btn)

        record_btn = QPushButton(" Record")
        record_btn.setObjectName("CompactImportButton")
        set_button_lucide_icon(record_btn, "video", size=14, color=ICON_COLOR_DIM, clear_text=False)
        record_btn.setEnabled(False)
        record_btn.setToolTip("Coming soon")
        layout.addWidget(record_btn)
        layout.addStretch(1)


class ImportZone(QFrame):
    files_dropped = Signal(list)

    _DEFAULT_TEXT = "Import video, audio or image files"
    _BUSY_TEXT = "Importing…"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ImportZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._busy = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(8)
        self._icon = QLabel()
        self._icon.setPixmap(lucide_pixmap("upload", size=18, color=ICON_COLOR_DIM))
        self._icon.setFixedSize(20, 20)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)
        self._label = QLabel(self._DEFAULT_TEXT)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color: #8b8b9e; font-size: 12px;")
        layout.addWidget(self._label, 1)

    def set_busy(self, busy: bool) -> None:
        """Disable dropping/browsing for new files while an import is
        already running in the background — probing/thumbnailing several
        large files at once would otherwise queue up confusingly."""
        self._busy = busy
        icon_name = "loader-2" if busy else "upload"
        self._icon.setPixmap(lucide_pixmap(icon_name, size=18, color=ICON_COLOR_DIM))
        self._label.setText(self._BUSY_TEXT if busy else self._DEFAULT_TEXT)
        self.setCursor(Qt.CursorShape.BusyCursor if busy else Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self._busy and event.button() == Qt.MouseButton.LeftButton:
            self._open_file_dialog()
        super().mousePressEvent(event)

    def _open_file_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Import media", "", FILE_DIALOG_FILTER)
        if paths:
            self.files_dropped.emit(paths)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if not self._busy and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        if self._busy:
            event.ignore()
            return
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()


class MediaImportWorker(QThread):
    """Probes/thumbnails dropped files off the UI thread.

    Importing used to call `import_files()` directly from the UI thread on
    drop — OpenCV video probing + thumbnail generation is slow enough that
    dropping a handful of large files would visibly freeze the whole app,
    with no progress feedback and no way to cancel. Mirrors the export
    pipeline's `ExportWorker` pattern in `ui/main_window.py`.
    """

    finished_ok = Signal(list)  # list[MediaAsset]
    failed = Signal(str)

    def __init__(self, paths: list[str], cache_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.paths = paths
        self.cache_dir = cache_dir

    def run(self) -> None:  # noqa: D401
        try:
            assets = import_files(self.paths, self.cache_dir)
        except Exception as exc:  # noqa: BLE001 - surface unexpected errors instead of crashing
            self.failed.emit(str(exc))
        else:
            self.finished_ok.emit(assets)


class MediaItemWidget(QFrame):
    """One draggable card in the media grid — drag onto a timeline track."""

    def __init__(self, media: MediaAsset, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.media = media
        self.setFixedSize(118, 96)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet(
            "MediaItemWidget { background: #1b1b25; border: 1px solid #20202b;"
            " border-radius: 8px; } MediaItemWidget:hover { border-color: #7c5cff; }"
        )
        self._drag_start: QPoint | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        thumb_label = QLabel()
        thumb_label.setFixedHeight(58)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setStyleSheet("background: #101018; border-radius: 6px;")
        pix = QPixmap(media.thumb_path) if media.thumb_path and Path(media.thumb_path).exists() else None
        if pix and not pix.isNull():
            thumb_label.setPixmap(
                pix.scaled(110, 58, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            icon_name = MEDIA_TYPE_ICON.get(media.type, "file")
            thumb_label.setPixmap(lucide_pixmap(icon_name, size=ICON_SZ_LIBRARY, color=ICON_COLOR_DIM))
        layout.addWidget(thumb_label)

        dur_text = "IMG" if media.type == "image" else fmt_time(media.duration)[:5]
        name_label = QLabel(f"{dur_text}  {media.name}")
        name_label.setStyleSheet("color: #8b8b9e; font-size: 10px;")
        name_label.setWordWrap(False)
        name_label.setToolTip(media.name)
        layout.addWidget(name_label)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_start is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 6:
            return
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MEDIA_MIME_TYPE, QByteArray(self.media.id.encode("utf-8")))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class MediaTab(QWidget):
    """Import tab — user media. Large drop zone when empty; compact toolbar when populated."""

    media_imported = Signal(list)  # list[MediaAsset]
    toast_requested = Signal(str)

    def __init__(self, project_state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_state = project_state
        self._cache_dir = default_cache_dir()
        self._import_worker: MediaImportWorker | None = None
        self._type_filter: str | None = None  # None=all, or video/image/audio

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.compact_bar = CompactImportBar(self)
        self.compact_bar.import_clicked.connect(self._open_file_dialog)
        self.compact_bar.hide()
        layout.addWidget(self.compact_bar)

        self.import_zone = CapCutImportZone(self)
        self.import_zone.files_dropped.connect(self._on_files_dropped)
        layout.addWidget(self.import_zone, 1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.grid_container = QWidget(scroll)
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(8)
        self.grid.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, 1)
        self._grid_scroll = scroll
        self._grid_scroll.hide()

        self._refresh_grid()

    def _open_file_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Import media", "", FILE_DIALOG_FILTER)
        if paths:
            self._on_files_dropped(paths)

    def _on_files_dropped(self, paths: list[str]) -> None:
        if self._import_worker is not None and self._import_worker.isRunning():
            self.toast_requested.emit("Still importing previous files \u2014 please wait")
            return

        self.import_zone.set_busy(True)
        self.toast_requested.emit(f"Importing {len(paths)} file(s)\u2026")

        worker = MediaImportWorker(paths, self._cache_dir, self)
        worker.finished_ok.connect(self._on_import_finished)
        worker.failed.connect(self._on_import_failed)
        self._import_worker = worker
        worker.start()

    def _on_import_finished(self, assets: list[MediaAsset]) -> None:
        self.import_zone.set_busy(False)
        for asset in assets:
            self.project_state.add_media(asset)
        if assets:
            self.media_imported.emit(assets)
            self.toast_requested.emit(f"Imported {len(assets)} file(s)")
        else:
            self.toast_requested.emit("No supported media found in the dropped files")
        self._refresh_grid()

    def _on_import_failed(self, message: str) -> None:
        self.import_zone.set_busy(False)
        self.toast_requested.emit(f"Import failed: {message}")

    def wait_for_import_to_finish(self, timeout_ms: int = 30000) -> None:
        """Block until any in-flight background import completes — used on
        app shutdown so a partial import doesn't get killed mid-write."""
        if self._import_worker is not None and self._import_worker.isRunning():
            self._import_worker.wait(timeout_ms)

    def set_type_filter(self, media_type: str | None) -> None:
        """Filter grid by media type — ``photo`` maps to ``image`` assets."""
        if media_type == "all":
            media_type = None
        if media_type == "photo":
            media_type = "image"
        self._type_filter = media_type
        self._refresh_grid()

    def _refresh_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        media_library = self.project_state.project.media_library
        if self._type_filter:
            media_library = [m for m in media_library if m.type == self._type_filter]
        has_media = bool(media_library)
        self.grid_container.setVisible(has_media)
        self.import_zone.setMinimumHeight(120 if has_media else 160)

    def _refresh_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        all_media = self.project_state.project.media_library
        has_any_media = bool(all_media)
        media_library = all_media
        if self._type_filter:
            media_library = [m for m in media_library if m.type == self._type_filter]

        self.import_zone.setVisible(not has_any_media)
        self.compact_bar.setVisible(has_any_media)
        self._grid_scroll.setVisible(has_any_media)

        columns = 2
        for index, media in enumerate(media_library):
            row, col = divmod(index, columns)
            self.grid.addWidget(MediaItemWidget(media, self.grid_container), row, col)


class SampleItemWidget(QFrame):
    """Placeholder card for stock media samples (Media tab)."""

    def __init__(self, title: str, media_type: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(118, 96)
        self.setToolTip("Stock samples — coming soon")
        self.setStyleSheet(
            "SampleItemWidget { background: #1b1b25; border: 1px solid #20202b;"
            " border-radius: 8px; } SampleItemWidget:hover { border-color: #7c5cff; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        thumb_label = QLabel()
        thumb_label.setFixedHeight(58)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setStyleSheet("background: #101018; border-radius: 6px;")
        icon_name = MEDIA_TYPE_ICON.get(media_type, "file")
        thumb_label.setPixmap(lucide_pixmap(icon_name, size=ICON_SZ_LIBRARY, color=ICON_COLOR_DIM))
        layout.addWidget(thumb_label)

        name_label = QLabel(title)
        name_label.setStyleSheet("color: #8b8b9e; font-size: 10px;")
        name_label.setWordWrap(False)
        layout.addWidget(name_label)


_MEDIA_SAMPLES: dict[str, tuple[tuple[str, str], ...]] = {
    "video": (
        ("City night drive", "video"),
        ("Ocean waves", "video"),
        ("Mountain timelapse", "video"),
        ("Neon street", "video"),
    ),
    "photo": (
        ("Abstract gradient", "image"),
        ("Portrait studio", "image"),
        ("Landscape sunset", "image"),
        ("Minimal texture", "image"),
    ),
    "audio": (
        ("Upbeat pop loop", "audio"),
        ("Ambient pad", "audio"),
        ("Cinematic hit", "audio"),
        ("Lo-fi beat", "audio"),
    ),
}


class MediaSamplesTab(QWidget):
    """Stock media samples — Video / Photo / Audio categories."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._type_filter: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.empty_hint = _empty_hint("Pick Video, Photo, or Audio in the sidebar to browse samples.")
        layout.addWidget(self.empty_hint)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.grid_container = QWidget(scroll)
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(8)
        self.grid.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, 1)
        self._grid_scroll = scroll
        self._grid_scroll.hide()
        self._refresh_grid()

    def set_type_filter(self, media_type: str | None) -> None:
        if media_type == "all":
            media_type = None
        if media_type == "photo":
            media_type = "image"
        self._type_filter = media_type
        self._refresh_grid()

    def _refresh_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        if self._type_filter is None:
            self.empty_hint.show()
            self._grid_scroll.hide()
            return

        samples = _MEDIA_SAMPLES.get(self._type_filter, ())
        self.empty_hint.hide()
        self._grid_scroll.show()
        columns = 2
        for index, (title, media_type) in enumerate(samples):
            row, col = divmod(index, columns)
            self.grid.addWidget(SampleItemWidget(title, media_type, self.grid_container), row, col)


class TextPresetItemWidget(QFrame):
    """Draggable text preset — drop anywhere on the timeline to create a
    clip (an overlay track is auto-created if one doesn't already exist)."""

    def __init__(self, preset_id: str, description: str, style_class: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preset_id = preset_id
        self.setFixedHeight(58)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet(
            "TextPresetItemWidget { background: #1b1b25; border: 1px solid #20202b;"
            " border-radius: 8px; } TextPresetItemWidget:hover { border-color: #7c5cff; }"
        )
        self._drag_start: QPoint | None = None

        preset = TEXT_PRESETS.get(preset_id, {})
        font_size = {"h1": 18, "h2": 14, "h3": 11}.get(style_class, 13)
        font_weight = 700 if style_class == "h1" else 500

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        label = QLabel(str(preset.get("text", description)))
        label.setStyleSheet(f"color: white; font-size: {font_size}px; font-weight: {font_weight};")
        layout.addWidget(label)
        sub = QLabel(description)
        sub.setStyleSheet("color: #5c5c6e; font-size: 10px;")
        layout.addWidget(sub)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_start is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 6:
            return
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(TEXT_PRESET_MIME_TYPE, QByteArray(self.preset_id.encode("utf-8")))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class TextTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(_section_title("Drag onto the timeline"))
        for preset_id, description, style_class in TEXT_PRESETS_UI:
            layout.addWidget(TextPresetItemWidget(preset_id, description, style_class, self))
        layout.addStretch(1)


class FilterItemWidget(QFrame):
    """Draggable filter swatch — drop onto a video/image clip to apply it."""

    def __init__(self, filter_id: str, name: str, swatch_from: str, swatch_to: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.filter_id = filter_id
        self.setFixedSize(118, 64)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet(
            f"FilterItemWidget {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f" stop:0 {swatch_from}, stop:1 {swatch_to}); border-radius: 8px; }}"
        )
        self._drag_start: QPoint | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        label = QLabel(name)
        label.setStyleSheet("color: white; font-size: 11px; font-weight: 600;")
        label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        layout.addWidget(label)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_start is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 6:
            return
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(FILTER_MIME_TYPE, QByteArray(self.filter_id.encode("utf-8")))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class EffectsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(_section_title("Filters \u2014 drag onto a video clip"))

        grid_container = QWidget(self)
        grid = QGridLayout(grid_container)
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, info in enumerate(FILTERS):
            item = FilterItemWidget(info.id, info.name, info.swatch_from, info.swatch_to, grid_container)
            grid.addWidget(item, i // 2, i % 2)
        layout.addWidget(grid_container)
        layout.addStretch(1)


class VizStylePreviewWidget(QFrame):
    def __init__(self, name: str, swatch_from: str, swatch_to: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(118, 64)
        self.setStyleSheet(
            f"VizStylePreviewWidget {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f" stop:0 {swatch_from}, stop:1 {swatch_to}); border-radius: 8px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addStretch(1)
        label = QLabel(name)
        label.setStyleSheet("color: white; font-size: 11px; font-weight: 600;")
        layout.addWidget(label)


class VisualizerTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(_section_title("Music Visualizer Styles"))

        grid_container = QWidget(self)
        grid = QGridLayout(grid_container)
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, info in enumerate(VIZ_STYLES):
            item = VizStylePreviewWidget(info.name, info.swatch_from, info.swatch_to, grid_container)
            grid.addWidget(item, i // 2, i % 2)
        layout.addWidget(grid_container)

        layout.addWidget(
            _empty_hint(
                "Select an audio clip on the timeline, then enable a visualizer "
                "style in the Inspector on the right."
            )
        )
        layout.addStretch(1)


class AudioTab(QWidget):
    """Audio-only slice of the media library — CapCut Audio rail section."""

    def __init__(self, project_state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_state = project_state
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(_section_title("Audio"))

        self.empty_hint = _empty_hint("Import audio in the Import tab, then drag files onto an audio track.")
        layout.addWidget(self.empty_hint)

        self.grid_container = QWidget(self)
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(8)
        self.grid.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.grid_container)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        audio_items = [m for m in self.project_state.project.media_library if m.type == "audio"]
        self.empty_hint.setVisible(not audio_items)
        self.grid_container.setVisible(bool(audio_items))
        for index, media in enumerate(audio_items):
            row, col = divmod(index, 2)
            self.grid.addWidget(MediaItemWidget(media, self.grid_container), row, col)


class PlaceholderTab(QWidget):
    def __init__(self, title: str, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(_section_title(title))
        layout.addWidget(_empty_hint(hint))
        layout.addStretch(1)



class LibraryTopMenuBar(QFrame):
    """Horizontally scrollable icon rail — centered icon with label underneath."""

    section_changed = Signal(str)

    _BTN_WIDTH = 58
    _BTN_HEIGHT = 54

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LibraryTopMenu")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("LibraryTopMenuScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(False)
        scroll.setFixedHeight(58)

        strip = QWidget(scroll)
        strip.setObjectName("LibraryTopMenuStrip")
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(6, 4, 6, 4)
        strip_layout.setSpacing(2)
        strip_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._buttons: list[_LibraryIconButton] = []
        self._keys: list[str] = []
        for key, label, icon_name in LIBRARY_TOP_MENU:
            btn_width = _icon_button_width(label)
            btn = _LibraryIconButton(label, icon_name, btn_width, self._BTN_HEIGHT, strip)
            btn.clicked.connect(lambda k=key: self._select(k))
            strip_layout.addWidget(btn)
            self._buttons.append(btn)
            self._keys.append(key)

        strip.adjustSize()
        scroll.setWidget(strip)
        outer.addWidget(scroll)
        self._select("import")

    def _select(self, key: str) -> None:
        for btn, k in zip(self._buttons, self._keys, strict=True):
            btn.setChecked(k == key)
        self.section_changed.emit(key)

    def set_active(self, key: str) -> None:
        self._select(key)


class LibrarySideRail(QFrame):
    """Contextual narrow sidebar — e.g. Video / Photo / Audio when Media is active."""

    filter_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LibraryIconRail")
        self.setFixedWidth(58)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 8, 4, 8)
        self._layout.setSpacing(2)
        self._buttons: list[_LibraryIconButton] = []
        self._keys: list[str] = []
        self._icon_names: list[str] = []
        self._layout.addStretch(1)

    def set_items(self, items: tuple[tuple[str, str, str], ...]) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._buttons.clear()
        self._keys.clear()
        self._icon_names.clear()
        for index, (key, label, icon_name) in enumerate(items):
            btn = _LibraryIconButton(label, icon_name, 52, 54, self)
            btn.clicked.connect(lambda k=key: self._select(k))
            self._layout.insertWidget(index, btn)
            self._buttons.append(btn)
            self._keys.append(key)
            self._icon_names.append(icon_name)
        if self._buttons:
            self._select(self._keys[0])
        self.setVisible(bool(items))

    def _select(self, key: str) -> None:
        for btn, k in zip(self._buttons, self._keys, strict=True):
            btn.setChecked(k == key)
        self.filter_changed.emit(key)


def _scrollable(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(widget)
    return area


class _LibraryTabCompat:
    """Shim so legacy tests can read section titles from the icon rail."""

    def __init__(self, titles: list[str]) -> None:
        self._titles = titles

    def count(self) -> int:
        return len(self._titles)

    def tabText(self, index: int) -> str:
        return self._titles[index]


class LibraryPanel(QFrame):
    media_imported = Signal(list)  # list[MediaAsset] — forwarded from MediaTab
    toast_requested = Signal(str)  # forwarded from MediaTab
    section_changed = Signal(str)  # top menu key — drives right panel context

    def __init__(self, project_state: ProjectState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("LibraryPanel")
        self.project_state = project_state
        self._active_section = "import"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.top_menu = LibraryTopMenuBar(self)
        outer.addWidget(self.top_menu)

        body = QWidget(self)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.side_rail = LibrarySideRail(body)
        body_layout.addWidget(self.side_rail)

        self.music_side_rail = MusicCategoryRail(body)
        self.music_side_rail.hide()
        body_layout.addWidget(self.music_side_rail)

        self.stack = QStackedWidget(body)
        self.import_tab = MediaTab(project_state)
        self.import_tab.media_imported.connect(self.media_imported.emit)
        self.import_tab.toast_requested.connect(self.toast_requested.emit)
        self.import_tab.media_imported.connect(lambda _assets: self.audio_tab.refresh())
        self.media_tab = self.import_tab  # legacy alias for tests

        self.media_samples_tab = MediaSamplesTab()
        self.audio_tab = AudioTab(project_state)
        self.text_tab = TextTab()
        self.effects_tab = EffectsTab()
        self.filter_tab = EffectsTab()
        self.visualizer_tab = VisualizerTab()

        self.music_tab = MusicLibraryTab()

        self._section_widgets: dict[str, QWidget] = {
            "import": self.import_tab,
            "media": self.media_samples_tab,
            "music": self.music_tab,
            "audio": self.audio_tab,
            "text": _scrollable(self.text_tab),
            "sticker": PlaceholderTab("Stickers", "Sticker packs are coming soon."),
            "effects": _scrollable(self.effects_tab),
            "transition": PlaceholderTab("Transitions", "Transition presets are coming soon."),
            "caption": PlaceholderTab("Captions", "Auto-caption tools are coming soon."),
            "filter": _scrollable(self.filter_tab),
            "visualizer": _scrollable(self.visualizer_tab),
        }
        for key, _label, _icon in LIBRARY_TOP_MENU:
            self.stack.addWidget(self._section_widgets[key])

        body_layout.addWidget(self.stack, 1)
        outer.addWidget(body, 1)

        self.top_menu.section_changed.connect(self._on_top_menu_changed)
        self.side_rail.filter_changed.connect(self._on_side_filter_changed)
        self.music_side_rail.category_changed.connect(self._on_music_category_changed)

        section_titles = [label for _key, label, _icon in LIBRARY_TOP_MENU]
        self.tabs = _LibraryTabCompat(section_titles)

        self._on_top_menu_changed("import")

    def _on_top_menu_changed(self, section_key: str) -> None:
        self._active_section = section_key
        index = next(i for i, (k, _l, _i) in enumerate(LIBRARY_TOP_MENU) if k == section_key)
        self.stack.setCurrentIndex(index)
        if section_key == "music":
            self.side_rail.hide()
            self.music_side_rail.show()
            self.music_side_rail.set_active("playlist")
            self.music_tab.set_category("playlist")
        else:
            self.music_side_rail.hide()
            if section_key in ("import", "media"):
                self.side_rail.show()
                self.side_rail.set_items(MEDIA_SIDE_RAIL)
            else:
                self.side_rail.hide()
        self.section_changed.emit(section_key)

    def _on_music_category_changed(self, category: str) -> None:
        self.music_tab.set_category(category)

    def select_music_playlist(self, preset_id: str) -> None:
        self.music_tab.select_playlist(preset_id)

    def _on_side_filter_changed(self, filter_key: str) -> None:
        if self._active_section == "import":
            self.import_tab.set_type_filter(filter_key)
        elif self._active_section == "media":
            self.media_samples_tab.set_type_filter(filter_key)
