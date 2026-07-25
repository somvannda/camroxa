"""Music top settings strip."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from shared.lib.formatting import today_ymd
from shared.lib.music_settings import DEFAULT_LANGUAGE_OPTIONS
from shared.themes.deep_blue import SUBTITLE_LABEL_ID
from shared.widgets.shell_date_edit import make_shell_date_edit


class MusicSettingsStrip(QFrame):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        today = QDate.fromString(today_ymd(), "yyyy-MM-dd")
        self._from_date = make_shell_date_edit(initial=today)
        self._to_date = make_shell_date_edit(initial=today)
        self._language = QComboBox()
        self._language_options: list[tuple[str, str]] = list(DEFAULT_LANGUAGE_OPTIONS)
        self._language_label = QLabel("Language")
        self._secondary_language_label = QLabel("Secondary")
        self._secondary_language = QComboBox()
        self._secondary_language.hide()
        self._secondary_language_label.hide()
        self._apply_language_options(self._language_options)
        self._configure_language_dropdowns()
        self._creativity = QSlider()
        self._creativity.setOrientation(Qt.Orientation.Horizontal)
        self._creativity.setRange(0, 100)
        self._creativity.setValue(55)
        self._creativity_label = QLabel("55")
        self._unique_opening = QCheckBox("Unique opening")
        self._use_content_pools = QCheckBox("Use content pools")
        self._strict = QComboBox()
        for value in range(1, 6):
            self._strict.addItem(str(value), value)
        self._strict.setCurrentIndex(2)
        self._history = QComboBox()
        for value in (50, 100, 200, 500, 1500):
            self._history.addItem(str(value), value)
        self._history.setCurrentIndex(1)
        self._count = QSpinBox()
        self._count.setRange(1, 50)
        self._count.setValue(4)
        self._planned_days = QLabel("1 planned day")
        self._planned_days.setObjectName(SUBTITLE_LABEL_ID)

        for label, widget in (
            ("From", self._from_date),
            ("To", self._to_date),
        ):
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)
        layout.addWidget(self._language_label)
        layout.addWidget(self._language)
        layout.addWidget(self._secondary_language_label)
        layout.addWidget(self._secondary_language)
        for label, widget in (
            ("Strict", self._strict),
            ("History", self._history),
            ("Count", self._count),
        ):
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)
        layout.addWidget(QLabel("Creativity"))
        creativity_box = QVBoxLayout()
        creativity_row = QHBoxLayout()
        creativity_row.addWidget(self._creativity, stretch=1)
        creativity_row.addWidget(self._creativity_label)
        creativity_box.addLayout(creativity_row)
        layout.addLayout(creativity_box, stretch=1)
        layout.addWidget(self._unique_opening)
        layout.addWidget(self._use_content_pools)
        layout.addWidget(self._planned_days)
        layout.addStretch()

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
