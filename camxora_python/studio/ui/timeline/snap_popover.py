"""Compact snap settings popover (scope, threshold, beats, frames)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from studio.core.snap_models import SnapSettings


class SnapSettingsPopover(QFrame):
    changed = Signal()

    _SCOPE_LABELS = ["All tracks", "Same track", "Video", "Audio", "Overlay"]
    _SCOPE_VALUES = ["all", "same_track", "video", "audio", "overlay"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("SnapSettingsPopover")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame#SnapSettingsPopover { background: #1b1b25; border: 1px solid #33333f; border-radius: 8px; }"
            "QLabel { color: #a8a8bc; font-size: 11px; }"
            "QCheckBox { color: #c8c8d8; font-size: 11px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Scope"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(self._SCOPE_LABELS)
        self.scope_combo.setFixedWidth(110)
        scope_row.addWidget(self.scope_combo)
        layout.addLayout(scope_row)

        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel("Distance"))
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(4, 30)
        self.threshold_slider.setFixedWidth(90)
        self.threshold_label = QLabel("10 px")
        self.threshold_label.setFixedWidth(36)
        thresh_row.addWidget(self.threshold_slider)
        thresh_row.addWidget(self.threshold_label)
        layout.addLayout(thresh_row)

        self.beats_cb = QCheckBox("Snap to beats")
        self.frames_cb = QCheckBox("Snap to frames")
        self.centers_cb = QCheckBox("Snap to clip centers")
        self.click_cb = QCheckBox("Click feedback")
        layout.addWidget(self.beats_cb)
        layout.addWidget(self.frames_cb)
        layout.addWidget(self.centers_cb)
        layout.addWidget(self.click_cb)

        self.scope_combo.currentIndexChanged.connect(self._emit_changed)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        for cb in (self.beats_cb, self.frames_cb, self.centers_cb, self.click_cb):
            cb.toggled.connect(self._emit_changed)

    def _on_threshold_changed(self, value: int) -> None:
        self.threshold_label.setText(f"{value} px")
        self._emit_changed()

    def _emit_changed(self) -> None:
        self.changed.emit()

    def sync_from_settings(self, settings: SnapSettings) -> None:
        self.scope_combo.blockSignals(True)
        idx = self._SCOPE_VALUES.index(settings.scope) if settings.scope in self._SCOPE_VALUES else 0
        self.scope_combo.setCurrentIndex(idx)
        self.scope_combo.blockSignals(False)
        self.threshold_slider.blockSignals(True)
        self.threshold_slider.setValue(int(settings.threshold_px))
        self.threshold_slider.blockSignals(False)
        self.threshold_label.setText(f"{int(settings.threshold_px)} px")
        for cb, attr in (
            (self.beats_cb, "snap_to_beats"),
            (self.frames_cb, "snap_to_frames"),
            (self.centers_cb, "snap_to_centers"),
            (self.click_cb, "click_feedback"),
        ):
            cb.blockSignals(True)
            cb.setChecked(getattr(settings, attr))
            cb.blockSignals(False)

    def apply_to_settings(self, settings: SnapSettings) -> None:
        idx = self.scope_combo.currentIndex()
        if 0 <= idx < len(self._SCOPE_VALUES):
            settings.scope = self._SCOPE_VALUES[idx]  # type: ignore[assignment]
        settings.threshold_px = float(self.threshold_slider.value())
        settings.snap_to_beats = self.beats_cb.isChecked()
        settings.snap_to_frames = self.frames_cb.isChecked()
        settings.snap_to_centers = self.centers_cb.isChecked()
        settings.click_feedback = self.click_cb.isChecked()
