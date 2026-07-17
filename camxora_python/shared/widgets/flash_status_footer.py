"""Transient bottom status bar — overlays content without changing layout height."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from shared.themes.deep_blue import (
    SETTINGS_FOOTER_ERROR_ID,
    SETTINGS_FOOTER_ID,
    SETTINGS_FOOTER_STATUS_ID,
    SETTINGS_FOOTER_SUCCESS_ID,
    SETTINGS_FOOTER_WARNING_ID,
)


class FlashStatusFooter(QFrame):
    """Settings-style footer that floats over the page bottom and auto-hides."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._overlay_margin = 12
        self.setObjectName(SETTINGS_FOOTER_ID)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self._label = QLabel("")
        self._label.setObjectName(SETTINGS_FOOTER_STATUS_ID)
        self._label.setWordWrap(True)
        layout.addWidget(self._label, stretch=1)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        parent.installEventFilter(self)
        self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self._reposition()
        return super().eventFilter(watched, event)

    def flash(
        self,
        message: str,
        *,
        tone: str = "neutral",
        duration_ms: int = 5000,
    ) -> None:
        text = str(message or "").strip()
        if not text:
            self.hide()
            return
        self._label.setText(text)
        self._apply_tone(tone)
        self._reposition()
        self.raise_()
        self.show()
        self._hide_timer.start(max(duration_ms, 1500))

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = self._overlay_margin
        width = max(0, parent.width() - margin * 2)
        self.setMaximumWidth(width)
        self.setMinimumWidth(width)
        self.resize(width, self.sizeHint().height())
        x = margin
        y = max(0, parent.height() - self.height() - margin)
        self.move(x, y)

    def _apply_tone(self, tone: str) -> None:
        frame_id = SETTINGS_FOOTER_ID
        if tone == "success":
            frame_id = SETTINGS_FOOTER_SUCCESS_ID
        elif tone == "error":
            frame_id = SETTINGS_FOOTER_ERROR_ID
        elif tone == "warning":
            frame_id = SETTINGS_FOOTER_WARNING_ID
        self.setObjectName(frame_id)
        self._label.setObjectName(SETTINGS_FOOTER_STATUS_ID)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        style.unpolish(self._label)
        style.polish(self._label)
        self.update()
