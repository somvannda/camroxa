"""Bottom shell footer matching the Electron workspace chrome."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget


class ShellFooterBar(QFrame):
    """Compact footer with status text, credits, and profile allowance summary."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("shell_footer_bar")
        self._full_message = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(16)

        self._message = QLabel()
        self._message.setObjectName("shell_footer_message")
        self._message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._message.setMinimumWidth(0)
        self._message.setWordWrap(False)
        layout.addWidget(self._message, stretch=1)

        self._env_badge = QLabel("")
        self._env_badge.setObjectName("shell_footer_env_badge")
        self._env_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self._env_badge.hide()
        layout.addWidget(self._env_badge)

        self._credits = QLabel("Credits: --")
        self._credits.setObjectName("shell_footer_metric")
        layout.addWidget(self._credits)

        self._allowance = QLabel("Profiles: --")
        self._allowance.setObjectName("shell_footer_metric")
        layout.addWidget(self._allowance)

        self.set_message("Ready", tone="neutral")

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._refresh_message_text()

    def set_message(self, message: str, *, tone: str = "neutral") -> None:
        self._full_message = str(message or "").strip()
        self._message.setToolTip(self._full_message or "")
        self._message.setProperty("tone", tone)
        self._message.style().unpolish(self._message)
        self._message.style().polish(self._message)
        self._refresh_message_text()

    def set_summary(self, *, credits: str, allowance: str) -> None:
        self._credits.setText(credits)
        self._allowance.setText(allowance)

    def set_environment_badge(self, label: str | None, *, tooltip: str = "") -> None:
        text = str(label or "").strip()
        if not text:
            self._env_badge.hide()
            self._env_badge.setText("")
            self._env_badge.setToolTip("")
            return
        self._env_badge.setText(text)
        self._env_badge.setToolTip(str(tooltip or "").strip())
        self._env_badge.show()

    def _refresh_message_text(self) -> None:
        if not self._full_message:
            self._message.setText("")
            return
        metrics = QFontMetrics(self._message.font())
        width = max(0, self._message.width() - 4)
        self._message.setText(metrics.elidedText(self._full_message, Qt.TextElideMode.ElideRight, width))
