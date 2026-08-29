"""Music top settings strip."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.studio_controls import StudioCheckBox, StudioComboBox, StudioDateEdit
from features.create.widgets.studio_panel import StudioPanel
from shared.lib.formatting import today_ymd
from shared.lib.music_settings import DEFAULT_LANGUAGE_OPTIONS


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


def _stacked_field(label: QLabel, widget: QWidget) -> QWidget:
    host = QWidget()
    host.setObjectName("TransparentBlock")
    host.setAutoFillBackground(False)
    box = QVBoxLayout(host)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(2)
    box.addWidget(label)
    box.addWidget(widget)
    return host


class MusicSettingsStrip(StudioPanel):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        today = QDate.fromString(today_ymd(), "yyyy-MM-dd")
        self._from_date = StudioDateEdit()
        self._from_date.setDate(today)
        self._from_date.setFixedWidth(132)
        self._from_date.setToolTip("Plan dates for the next generate run — not the History table.")
        self._to_date = StudioDateEdit()
        self._to_date.setDate(today)
        self._to_date.setFixedWidth(132)
        self._to_date.setToolTip("Plan dates for the next generate run — not the History table.")
        self._language = StudioComboBox()
        self._language.setMinimumWidth(110)
        self._language_options: list[tuple[str, str]] = list(DEFAULT_LANGUAGE_OPTIONS)
        self._language_label = _field_label("Language")
        self._secondary_language_label = _field_label("Secondary")
        self._secondary_language = StudioComboBox()
        self._secondary_language.setMinimumWidth(110)
        self._language_field = _stacked_field(self._language_label, self._language)
        self._secondary_language_field = _stacked_field(
            self._secondary_language_label, self._secondary_language
        )
        self._secondary_language_field.hide()
        self._apply_language_options(self._language_options)
        self._configure_language_dropdowns()
        self._creativity = QSlider()
        self._creativity.setOrientation(Qt.Orientation.Horizontal)
        self._creativity.setRange(0, 100)
        self._creativity.setValue(55)
        self._creativity_label = QLabel("55")
        self._creativity_label.setObjectName("FieldLabel")
        self._unique_opening = StudioCheckBox("Unique opening")
        self._use_content_pools = StudioCheckBox("Use content pools")
        self._strict = StudioComboBox()
        for value in range(1, 6):
            self._strict.addItem(str(value), value)
        self._strict.setCurrentIndex(2)
        self._history = StudioComboBox()
        for value in (50, 100, 200, 500, 1500):
            self._history.addItem(str(value), value)
        self._history.setCurrentIndex(1)
        self._count = QSpinBox()
        self._count.setRange(1, 50)
        self._count.setValue(4)
        self._strict.sync_item_tooltips()
        self._history.sync_item_tooltips()
        self._strict.setToolTip("How tightly lyrics follow the description, structure, and mood.")
        self._history.setToolTip("Recent titles to avoid repeating. This is not the History table.")
        self._count.setToolTip("Songs generated per planned day.")
        self._creativity.setToolTip("Higher writes more freely. Lower stays closer to the brief.")
        self._planned_days = QLabel("1 planned day")
        self._planned_days.setObjectName("PageSubtitle")

        bottom = Qt.AlignmentFlag.AlignBottom
        for label, widget in (
            ("Plan from", self._from_date),
            ("Plan to", self._to_date),
        ):
            layout.addWidget(_stacked_field(_field_label(label), widget), alignment=bottom)
        layout.addWidget(self._language_field, alignment=bottom)
        layout.addWidget(self._secondary_language_field, alignment=bottom)
        for label, widget in (
            ("Strict", self._strict),
            ("History", self._history),
            ("Count", self._count),
        ):
            layout.addWidget(_stacked_field(_field_label(label), widget), alignment=bottom)

        creativity_host = QWidget()
        creativity_host.setObjectName("TransparentBlock")
        creativity_host.setAutoFillBackground(False)
        creativity_row = QHBoxLayout(creativity_host)
        creativity_row.setContentsMargins(0, 0, 0, 0)
        creativity_row.setSpacing(8)
        creativity_caption = _field_label("Creativity")
        creativity_caption.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        creativity_row.addWidget(creativity_caption, alignment=Qt.AlignmentFlag.AlignVCenter)
        creativity_row.addWidget(self._creativity, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)
        creativity_row.addWidget(self._creativity_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(creativity_host, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)

        options_host = QWidget()
        options_host.setObjectName("TransparentBlock")
        options_host.setAutoFillBackground(False)
        options = QHBoxLayout(options_host)
        options.setContentsMargins(0, 0, 0, 0)
        options.setSpacing(12)
        options.addStretch(1)
        options.addWidget(self._unique_opening)
        options.addWidget(self._use_content_pools)
        options.addWidget(self._planned_days)
        options.addStretch(1)
        layout.addWidget(options_host, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._from_date.dateChanged.connect(lambda *_: self._emit_changed())
        self._to_date.dateChanged.connect(lambda *_: self._emit_changed())
        self._language.currentIndexChanged.connect(self._on_primary_language_changed)
        self._secondary_language.currentIndexChanged.connect(lambda *_: self._emit_changed())
        self._creativity.valueChanged.connect(self._on_creativity_changed)
        self._unique_opening.stateChanged.connect(lambda *_: self._emit_changed())
        self._use_content_pools.stateChanged.connect(lambda *_: self._emit_changed())
        self._strict.currentIndexChanged.connect(lambda *_: self._emit_changed())
        self._history.currentIndexChanged.connect(lambda *_: self._emit_changed())
        self._count.valueChanged.connect(lambda *_: self._emit_changed())

    def _on_creativity_changed(self, value: int) -> None:
        self._creativity_label.setText(str(value))
        self._emit_changed()

    def _emit_changed(self) -> None:
        self.changed.emit()

    def set_language_options(self, options: list[tuple[str, str]]) -> None:
        self._apply_language_options(options or list(DEFAULT_LANGUAGE_OPTIONS))
        self._configure_language_dropdowns()

    def set_bilingual_mode(self, enabled: bool, *, default_secondary: str | None = None) -> None:
        """Apply description defaults for secondary language when dual-dropdown mode is active."""
        if not self._secondary_language.isVisible():
            return
        if default_secondary:
            index = self._secondary_language.findData(default_secondary)
            if index >= 0:
                self._secondary_language.setCurrentIndex(index)

    def _on_primary_language_changed(self, _index: int) -> None:
        if self._secondary_language.isVisible():
            self._refresh_secondary_language_options()
        self._emit_changed()

    def _configure_language_dropdowns(self) -> None:
        """One enabled language → single dropdown; two or more → Primary + Secondary."""
        dual_mode = len(self._language_options) >= 2
        self._language_label.setText("Primary" if dual_mode else "Language")
        self._secondary_language_label.setVisible(dual_mode)
        self._secondary_language.setVisible(dual_mode)
        self._secondary_language_field.setVisible(dual_mode)
        if not dual_mode:
            if self._language.count() > 0:
                self._language.setCurrentIndex(0)
            return
        self._refresh_secondary_language_options()

    def _refresh_secondary_language_options(self) -> None:
        primary = str(self._language.currentData() or "").strip()
        secondary_options: list[tuple[str, str]] = [("", "None")]
        secondary_options.extend(
            (code, label)
            for code, label in self._language_options
            if code != primary
        )
        current_secondary = str(self._secondary_language.currentData() or "").strip()
        self._apply_language_options_to_combo(self._secondary_language, secondary_options)
        if current_secondary and current_secondary != primary:
            index = self._secondary_language.findData(current_secondary)
            if index >= 0:
                self._secondary_language.setCurrentIndex(index)
                return
        none_index = self._secondary_language.findData("")
        if none_index >= 0:
            self._secondary_language.setCurrentIndex(none_index)

    def _apply_language_options_to_combo(
        self,
        combo: QComboBox,
        options: list[tuple[str, str]],
    ) -> None:
        current = str(combo.currentData() or "")
        combo.blockSignals(True)
        combo.clear()
        for code, label in options:
            combo.addItem(label, code)
        index = combo.findData(current)
        if index < 0:
            index = 0
        if combo.count() > 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)
        if hasattr(combo, "sync_item_tooltips"):
            combo.sync_item_tooltips()

    def _apply_language_options(self, options: list[tuple[str, str]]) -> None:
        current = str(self._language.currentData() or "")
        self._language_options = list(options)
        self._apply_language_options_to_combo(self._language, self._language_options)
        index = self._language.findData(current)
        if index < 0:
            index = 0
        if self._language.count() > 0:
            self._language.setCurrentIndex(index)

    def from_date(self) -> str:
        return self._from_date.date().toString("yyyy-MM-dd")

    def to_date(self) -> str:
        return self._to_date.date().toString("yyyy-MM-dd")

    def set_planned_days_text(self, text: str) -> None:
        self._planned_days.setText(text)

    def apply_dates(self, from_date: str, to_date: str) -> None:
        from_value = QDate.fromString(from_date, "yyyy-MM-dd")
        to_value = QDate.fromString(to_date, "yyyy-MM-dd")
        if not from_value.isValid() or not to_value.isValid():
            return
        self._from_date.blockSignals(True)
        self._to_date.blockSignals(True)
        self._from_date.setDate(from_value)
        self._to_date.setDate(to_value)
        self._from_date.blockSignals(False)
        self._to_date.blockSignals(False)

    def values(self) -> dict[str, object]:
        secondary = str(self._secondary_language.currentData() or "").strip()
        return {
            "from_date": self.from_date(),
            "to_date": self.to_date(),
            "language": self._language.currentData(),
            "secondary_language": secondary if self._secondary_language.isVisible() and secondary else "",
            "creativity": self._creativity.value(),
            "unique_opening": self._unique_opening.isChecked(),
            "use_content_pools": self._use_content_pools.isChecked(),
            "strict_level": self._strict.currentData(),
            "history_window": self._history.currentData(),
            "song_count": self._count.value(),
        }

    def apply_settings(
        self,
        *,
        language: str,
        secondary_language: str = "",
        creativity: int,
        unique_opening: bool,
        use_content_pools: bool,
        strict_level: int,
        history_window: int,
        song_count: int,
    ) -> None:
        self.blockSignals(True)
        index = self._language.findData(language)
        if index >= 0:
            self._language.setCurrentIndex(index)
        secondary_index = self._secondary_language.findData(secondary_language or "")
        if secondary_index >= 0:
            self._secondary_language.setCurrentIndex(secondary_index)
        self._creativity.setValue(creativity)
        self._unique_opening.setChecked(unique_opening)
        self._use_content_pools.setChecked(use_content_pools)
        strict_index = self._strict.findData(strict_level)
        if strict_index >= 0:
            self._strict.setCurrentIndex(strict_index)
        history_index = self._history.findData(history_window)
        if history_index >= 0:
            self._history.setCurrentIndex(history_index)
        self._count.setValue(song_count)
        self.blockSignals(False)
