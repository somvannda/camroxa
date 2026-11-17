"""Image preview card with optional source-mode control."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.icons import apply_button_icon, section_heading
from features.create.widgets.studio_controls import StudioComboBox
from features.create.widgets.studio_panel import StudioPanel


_SOURCE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Category + My prompt", "category:custom"),
    ("Category + Admin library", "category:admin_library"),
    ("Prompt only + My prompt", "prompt_only:custom"),
    ("Prompt only + Admin library", "prompt_only:admin_library"),
)

_EMPTY_BY_KIND = {
    "background": "No background generated\nGenerate a background using the current prompt.",
    "thumbnail": "No thumbnail generated\nGenerate a thumbnail using the current prompt.",
}


def _status_tone(status: str) -> str:
    key = str(status or "").strip().lower()
    if key in {"ready", "success", "completed"}:
        return "success"
    if key in {"failed", "error", "cancelled"}:
        return "danger"
    if key in {"pending", "wait", "waiting"}:
        return "warning"
    if key in {"running", "generating", "processing"}:
        return "active"
    return "muted"


class PreviewCard(StudioPanel):
    source_mode_changed = Signal(str)
    prompt_source_changed = Signal(str)
    open_requested = Signal(str, str)
    copy_path_requested = Signal(str)

    def __init__(
        self,
        title: str,
        placeholder: str,
        *,
        source_label: str = "Source",
        kind: str = "background",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._source_pixmap: QPixmap | None = None
        self._path = ""
        self._job_id = ""
        self._placeholder = placeholder or _EMPTY_BY_KIND.get(kind, "No image generated")
        self._prompt_library_count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(8)
        heading.addWidget(section_heading(title.upper(), "image"), 1)
        self._status_badge = QLabel("Empty")
        self._status_badge.setObjectName("ImageStatusBadge")
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.addWidget(self._status_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(heading)

        source_heading = QLabel(source_label)
        source_heading.setObjectName("FieldLabel")
        root.addWidget(source_heading)

        self._source_mode = StudioComboBox()
        for label, value in _SOURCE_OPTIONS:
            self._source_mode.addItem(label, value)
        self._source_mode.sync_item_tooltips()
        self._source_mode.currentIndexChanged.connect(self._emit_selection)
        root.addWidget(self._source_mode)
        self._prompt_source_note = QLabel("")
        self._prompt_source_note.setObjectName("PageSubtitle")
        self._prompt_source_note.setWordWrap(True)
        self._prompt_source_note.hide()
        root.addWidget(self._prompt_source_note)

        self._preview = QLabel()
        self._preview.setMinimumSize(0, 180)
        self._preview.setMaximumHeight(260)
        self._preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setObjectName("image_preview_stage")
        self._preview.setText(self._placeholder)
        self._preview.setWordWrap(True)
        self._preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview.mousePressEvent = self._on_preview_clicked  # type: ignore[method-assign]
        root.addWidget(self._preview, stretch=1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        self._open_btn = QPushButton()
        self._open_btn.setObjectName("SecondaryButton")
        self._open_btn.setFixedSize(26, 26)
        self._open_btn.setToolTip("Open file")
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_icon(self._open_btn, "folder-open", size=12)
        self._open_btn.clicked.connect(self._emit_open)
        self._copy_btn = QPushButton()
        self._copy_btn.setObjectName("SecondaryButton")
        self._copy_btn.setFixedSize(26, 26)
        self._copy_btn.setToolTip("Copy path")
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_icon(self._copy_btn, "copy", size=12)
        self._copy_btn.clicked.connect(self._copy_path)
        actions.addWidget(self._open_btn)
        actions.addWidget(self._copy_btn)
        actions.addStretch(1)
        root.addLayout(actions)
        self._set_actions_enabled(False)
        self.set_status("Empty")

    def _selection(self) -> tuple[str, str]:
        raw = str(self._source_mode.currentData() or "category:custom")
        source_mode, _, prompt_source = raw.partition(":")
        source_mode = (
            "prompt_only" if source_mode in {"prompt", "prompt_only"} else "category"
        )
        prompt_source = (
            "admin_library" if prompt_source == "admin_library" else "custom"
        )
        return source_mode, prompt_source

    def _select(self, source_mode: str, prompt_source: str) -> None:
        normalized_mode = (
            "prompt_only"
            if str(source_mode or "").strip().lower() in {"prompt", "prompt_only"}
            else "category"
        )
        normalized_prompt = (
            "admin_library"
            if str(prompt_source or "").strip().lower() == "admin_library"
            else "custom"
        )
        index = self._source_mode.findData(
            f"{normalized_mode}:{normalized_prompt}"
        )
        if index < 0:
            return
        blocked = self._source_mode.blockSignals(True)
        self._source_mode.setCurrentIndex(index)
        self._source_mode.blockSignals(blocked)
        self._update_prompt_source_note()

    def source_mode(self) -> str:
        return self._selection()[0]

    def set_source_mode(self, mode: str) -> None:
        self._select(mode, self.prompt_source())

    def prompt_source(self) -> str:
        return self._selection()[1]

    def set_prompt_source(self, mode: str) -> None:
        self._select(self.source_mode(), mode)

    def _emit_selection(self, *_args: object) -> None:
        self._update_prompt_source_note()
        source_mode, prompt_source = self._selection()
        self.source_mode_changed.emit(source_mode)
        self.prompt_source_changed.emit(prompt_source)

    def set_prompt_library_count(self, count: int) -> None:
        self._prompt_library_count = max(0, int(count or 0))
        self._update_prompt_source_note()

    def _update_prompt_source_note(self) -> None:
        if self.prompt_source() != "admin_library":
            self._prompt_source_note.hide()
            return
        count = int(getattr(self, "_prompt_library_count", 0) or 0)
        if count <= 0:
            text = "No active admin prompt styles. Ask an admin to add them in Image Prompts."
        elif count == 1:
            text = "1 admin style active. Both channels may reuse the same prompt."
        else:
            text = f"{count} admin styles active. A different style is chosen per channel."
        self._prompt_source_note.setText(text)
        self._prompt_source_note.show()

    def bind_job(self, job, *, empty_message: str | None = None) -> None:
        if empty_message:
            self._placeholder = empty_message
        path = str(getattr(job, "output_image_path", "") or "").strip() if job is not None else ""
        job_id = str(getattr(job, "id", "") or "").strip() if job is not None else ""
        status = str(getattr(job, "status", "") or "").strip() if job is not None else ""
        self._path = path
        self._job_id = job_id
        self.set_status(self._display_status(status, path))
        self._set_actions_enabled(bool(path))

    def set_status(self, status: str) -> None:
        text = str(status or "").strip() or "Empty"
        self._status_badge.setText(text)
        self._status_badge.setProperty("tone", _status_tone(text))
        self._status_badge.style().unpolish(self._status_badge)
        self._status_badge.style().polish(self._status_badge)

    @staticmethod
    def _display_status(status: str, path: str) -> str:
        key = str(status or "").strip().lower()
        if key in {"success", "completed"} and path:
            return "Ready"
        if key in {"success", "completed"}:
            return "Ready"
        if key in {"running", "processing"}:
            return "Generating"
        if key in {"failed", "cancelled"}:
            return "Failed"
        if key in {"pending"}:
            return "Pending"
        if path:
            return "Ready"
        return "Empty"

    def set_image_bytes(self, data: bytes | None) -> None:
        if not data:
            self._source_pixmap = None
            self._preview.clear()
            self._preview.setText(self._placeholder)
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self._source_pixmap = None
            self._preview.clear()
            self._preview.setText(self._placeholder)
            return
        self._source_pixmap = pixmap
        self._preview.setText("")
        self._fit_preview()

    def _fit_preview(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return
        target = self._preview.size()
        if target.width() < 8 or target.height() < 8:
            return
        scaled = self._source_pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self._fit_preview()

    def _set_actions_enabled(self, enabled: bool) -> None:
        self._open_btn.setEnabled(enabled)
        self._copy_btn.setEnabled(enabled)

    def _on_preview_clicked(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._path:
            self._emit_open()
        QLabel.mousePressEvent(self._preview, event)

    def _emit_open(self) -> None:
        if self._path:
            self.open_requested.emit(self._path, self._job_id)

    def _copy_path(self) -> None:
        if not self._path:
            return
        QGuiApplication.clipboard().setText(self._path)
        self._copy_btn.setToolTip("Path copied")
        self.copy_path_requested.emit(self._path)
