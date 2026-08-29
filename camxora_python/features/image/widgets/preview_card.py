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
    ("Category", "category"),
    ("Prompt only", "prompt_only"),
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
        self._source_mode.currentIndexChanged.connect(self._emit_source_mode)
        root.addWidget(self._source_mode)

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

    def source_mode(self) -> str:
        return str(self._source_mode.currentData() or "category")

    def set_source_mode(self, mode: str) -> None:
        normalized = str(mode or "category").strip().lower()
        if normalized in {"prompt", "prompt_only"}:
            normalized = "prompt_only"
        else:
            # personal_reference / unknown → category (User reference hidden until P2)
            normalized = "category"
        index = self._source_mode.findData(normalized)
        if index < 0:
            return
        self._source_mode.blockSignals(True)
        self._source_mode.setCurrentIndex(index)
        self._source_mode.blockSignals(False)

    def _emit_source_mode(self, *_args: object) -> None:
        self.source_mode_changed.emit(self.source_mode())

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
