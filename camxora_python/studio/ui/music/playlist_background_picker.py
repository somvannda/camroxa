"""Scene background picker — thumbnail, choose image, reset to template default."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from studio.app.file_dialog_state import last_open_dir, set_last_open_dir
from studio.core.playlist_assets import bundled_background_path, resolve_playlist_background
from studio.core.playlist_settings import PlaylistSettings
from studio.render.playlist_cache import invalidate_playlist_render_cache
from studio.ui.inspector_layout import FIELD_GAP

_IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp)"


class PlaylistBackgroundPicker(QWidget):
    background_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = PlaylistSettings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(FIELD_GAP)

        hint = QLabel(
            "Backdrop behind the playlist card — choose a custom image "
            "or keep the template default."
        )
        hint.setWordWrap(True)
        hint.setObjectName("InspectorHint")
        layout.addWidget(hint)

        self._thumb = QLabel()
        self._thumb.setMinimumHeight(96)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            "QLabel { background: #0c1230; border: 1px solid #2a2a3a; border-radius: 8px; color: #5c5c6e; }"
        )
        layout.addWidget(self._thumb)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        self._choose_btn = QPushButton("Choose image…")
        self._choose_btn.setObjectName("BgChooseButton")
        self._choose_btn.clicked.connect(self._choose_image)
        btn_row.addWidget(self._choose_btn)

        self._reset_btn = QPushButton("Reset to default")
        self._reset_btn.setObjectName("BgResetButton")
        self._reset_btn.clicked.connect(self._reset_to_default)
        btn_row.addWidget(self._reset_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._status = QLabel("")
        self._status.setObjectName("InspectorHint")
        layout.addWidget(self._status)

    def bind_settings(self, settings: PlaylistSettings) -> None:
        self._settings = settings
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        resolved = resolve_playlist_background(self._settings)
        custom = self._settings.background_path
        if resolved is not None and resolved.is_file():
            pix = QPixmap(str(resolved))
            if not pix.isNull():
                # Fit the whole image (contain) at the picker's width so the
                # full backdrop is visible; grow the preview to match.
                label_w = self._thumb.width() or 280
                scaled = pix.scaled(
                    label_w,
                    1000,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._thumb.setPixmap(scaled)
                self._thumb.setFixedHeight(max(96, min(scaled.height(), 320)))
                self._thumb.setText("")
            else:
                self._thumb.setPixmap(QPixmap())
                self._thumb.setFixedHeight(96)
                self._thumb.setText("Preview unavailable")
        else:
            self._thumb.setPixmap(QPixmap())
            self._thumb.setFixedHeight(96)
            self._thumb.setText("No background image")

        if custom:
            self._status.setText(f"Custom: {Path(custom).name}")
            self._reset_btn.setEnabled(True)
        else:
            bundled = bundled_background_path(
                self._settings.sub_template_id or "",
                self._settings.template_id,
            )
            if bundled is not None:
                self._status.setText(f"Template default: {bundled.name}")
            else:
                self._status.setText("Using gradient fallback (no bundled image)")
            self._reset_btn.setEnabled(bool(custom))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._settings.template_id:
            self._refresh_preview()

    def _choose_image(self) -> None:
        start_dir = last_open_dir("playlist_background") or ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose scene background",
            start_dir,
            _IMAGE_FILTER,
        )
        if not path:
            return
        set_last_open_dir("playlist_background", [path])
        self._settings.background_path = path
        invalidate_playlist_render_cache()
        self._refresh_preview()
        self.background_changed.emit()

    def _reset_to_default(self) -> None:
        self._settings.background_path = None
        invalidate_playlist_render_cache()
        self._refresh_preview()
        self.background_changed.emit()
