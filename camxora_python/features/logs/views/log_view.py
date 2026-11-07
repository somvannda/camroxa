"""Support-only runtime log console.

The Diagnostics route is hidden from end users
(``shared/constants/navigation.py`` gates it behind
``CAMXORA_SHOW_DIAGNOSTICS=1``); this page is what support opens when that flag
is set. It reads the in-memory ring buffer from ``AppLogger`` — the same
redacted records that feed the daily files and the "Send diagnostics" upload —
so it never parses log files or blocks the UI thread.
"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.create_header import CreateHeader
from features.create.widgets.studio_panel import fill_studio_canvas, paint_studio_card
from shared.lib.ui_font import ensure_inter_loaded, studio_font
from shared.services.app_logger import LogLevel, LogRecord, get_app_logger
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID

MAX_CONSOLE_LINES = 2000
# Records that arrive while the console is paused; bounded so a long pause
# cannot grow memory without limit.
MAX_PAUSED_LINES = 500

_LEVEL_FILTERS: tuple[tuple[str, LogLevel], ...] = (
    ("All levels", LogLevel.DEBUG),
    ("Info and above", LogLevel.INFO),
    ("Warnings and above", LogLevel.WARN),
    ("Errors only", LogLevel.ERROR),
)


class _FramedHeader(CreateHeader):
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        paint_studio_card(self)


class LogView(QWidget):
    """Live, redacted view of the desktop logger's in-memory buffer."""

    def __init__(self, api: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api = api  # Router passes the platform API; the console needs none.
        self._logger = get_app_logger()
        self._filter_level = LogLevel.DEBUG
        self._paused_lines: deque[LogRecord] = deque(maxlen=MAX_PAUSED_LINES)
        self._shown_count = 0

        self.setObjectName("diagnostics_workspace")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ensure_inter_loaded()
        self.setFont(studio_font(12))
        fill_studio_canvas(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(
            _FramedHeader(
                title="Diagnostics",
                subtitle=(
                    "Support-only runtime log for this PC. Records are redacted before "
                    "they are displayed. Prefer Settings → Send diagnostics for uploads."
                ),
                meta="",
                eyebrow="SUPPORT",
            )
        )
        root.addLayout(self._build_toolbar())

        self._console = QPlainTextEdit()
        self._console.setObjectName("diagnostics_console")
        self._console.setReadOnly(True)
        self._console.setUndoRedoEnabled(False)
        self._console.setMaximumBlockCount(MAX_CONSOLE_LINES)
        self._console.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._console.setPlaceholderText("No log lines yet. Reproduce the issue, then copy this log.")
        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed.setPixelSize(12)
        self._console.setFont(fixed)
        root.addWidget(self._console, stretch=1)

        self._count_label = QLabel("0 lines buffered")
        self._count_label.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(self._count_label)

        self._logger.bus.line_emitted.connect(self._on_line)
        self._logger.bus.cleared.connect(self._on_cleared)
        self._reload_from_buffer()

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)

        self._level_combo = QComboBox()
        for label, level in _LEVEL_FILTERS:
            self._level_combo.addItem(label, int(level))
        self._level_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._level_combo)

        self._auto_scroll = QCheckBox("Follow")
        self._auto_scroll.setChecked(True)
        self._auto_scroll.setCursor(Qt.CursorShape.PointingHandCursor)
        self._auto_scroll.setToolTip("Scroll to the newest line as it arrives.")
        toolbar.addWidget(self._auto_scroll)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._pause_btn.setCheckable(True)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.setToolTip("Hold new lines without losing them; resume to flush.")
        self._pause_btn.toggled.connect(self._on_pause_toggled)
        toolbar.addWidget(self._pause_btn)

        toolbar.addStretch(1)

        self._copy_btn = QPushButton("Copy all")
        self._copy_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(self._on_copy_clicked)
        toolbar.addWidget(self._copy_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        toolbar.addWidget(self._clear_btn)
        return toolbar

    # ---------------------------------------------------------------- filters

    def _on_filter_changed(self, _index: int) -> None:
        self._filter_level = LogLevel(int(self._level_combo.currentData() or LogLevel.DEBUG))
        self._reload_from_buffer()

    def _matches(self, record: LogRecord) -> bool:
        return int(record.level) >= int(self._filter_level)

    # ---------------------------------------------------------------- rendering

    def _reload_from_buffer(self) -> None:
        self._console.clear()
        self._shown_count = 0
        for record in self._logger.snapshot(max_lines=MAX_CONSOLE_LINES):
            self._append_record(record)
        self._update_count()

    def _append_record(self, record: LogRecord) -> None:
        if not self._matches(record):
            return
        self._console.appendPlainText(record.format_line())
        self._shown_count += 1
        if self._auto_scroll.isChecked():
            bar = self._console.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _update_count(self) -> None:
        total = self._logger.record_count()
        shown = min(self._shown_count, MAX_CONSOLE_LINES)
        suffix = " (paused)" if self._pause_btn.isChecked() else ""
        self._count_label.setText(
            f"{shown:,} of {total:,} buffered line(s) shown{suffix}. "
            f"The in-memory buffer keeps the newest {MAX_CONSOLE_LINES:,}."
        )

    # ------------------------------------------------------------------ signals

    def _on_line(self, record: object) -> None:
        if not isinstance(record, LogRecord):
            return
        if self._pause_btn.isChecked():
            self._paused_lines.append(record)
            self._update_count()
            return
        self._append_record(record)
        self._update_count()

    def _on_cleared(self) -> None:
        self._paused_lines.clear()
        self._console.clear()
        self._shown_count = 0
        self._update_count()

    # ------------------------------------------------------------------ actions

    def _on_pause_toggled(self, paused: bool) -> None:
        self._pause_btn.setText("Resume" if paused else "Pause")
        if paused:
            self._update_count()
            return
        while self._paused_lines:
            self._append_record(self._paused_lines.popleft())
        self._update_count()

    def _on_copy_clicked(self) -> None:
        QApplication.clipboard().setText(self._console.toPlainText())

    def _on_clear_clicked(self) -> None:
        confirmed = QMessageBox.question(
            self,
            "Clear Runtime Log",
            "Clear the in-memory log buffer? Log files already written to disk are not affected.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._logger.clear()
