"""Bottom shell footer matching the Electron workspace chrome."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from shared.lib.ui_font import studio_font


class ShellFooterBar(QFrame):
    """Compact footer with status text, credits, and profile allowance summary."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("shell_footer_bar")
        self.setFixedHeight(40)
        self._full_message = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._message = QLabel()
        self._message.setObjectName("shell_footer_message")
        self._message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._message.setMinimumWidth(0)
        self._message.setWordWrap(False)
        self._message.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._message.setFont(studio_font(12))
        layout.addWidget(self._message, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._env_badge = self._make_badge("shell_footer_env_badge")
        self._env_divider = self._add_divider(layout)
        layout.addWidget(self._env_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._version_badge = self._make_badge("shell_footer_version_badge")
        self._version_divider = self._add_divider(layout)
        layout.addWidget(self._version_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._credits_divider = self._add_divider(layout)
        self._credits = QLabel("Credits: --")
        self._credits.setObjectName("shell_footer_metric")
        self._credits.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._credits.setFont(studio_font(12))
        layout.addWidget(self._credits, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._allowance_divider = self._add_divider(layout)
        self._allowance = QLabel("Profiles: --")
        self._allowance.setObjectName("shell_footer_metric")
        self._allowance.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._allowance.setFont(studio_font(12))
        layout.addWidget(self._allowance, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.set_message("Ready", tone="neutral")
        self._sync_dividers()

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
            self._sync_dividers()
            return
        self._env_badge.setText(text)
        self._env_badge.setToolTip(str(tooltip or "").strip())
        self._env_badge.show()
        self._sync_dividers()

    def set_version_badge(self, label: str | None, *, tooltip: str = "") -> None:
        text = str(label or "").strip()
        if not text:
            self._version_badge.hide()
            self._version_badge.setText("")
            self._version_badge.setToolTip("")
            self._sync_dividers()
            return
        self._version_badge.setText(text)
        self._version_badge.setToolTip(str(tooltip or "").strip())
        self._version_badge.show()
        self._sync_dividers()

    @staticmethod
    def _make_badge(object_name: str) -> QLabel:
        badge = QLabel("")
        badge.setObjectName(object_name)
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        badge.setFixedHeight(22)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(studio_font(12))
        badge.hide()
        return badge

    @staticmethod
    def _add_divider(layout: QHBoxLayout) -> QLabel:
        divider = QLabel("│")
        divider.setObjectName("shell_footer_divider")
        divider.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        divider.setFont(studio_font(12))
        divider.hide()
        layout.addWidget(divider, alignment=Qt.AlignmentFlag.AlignVCenter)
        return divider

    def _sync_dividers(self) -> None:
        pairs = (
            (self._env_divider, self._env_badge),
            (self._version_divider, self._version_badge),
            (self._credits_divider, self._credits),
            (self._allowance_divider, self._allowance),
        )
        seen_visible = False
        for divider, widget in pairs:
            visible = not widget.isHidden()
            divider.setVisible(visible and seen_visible)
            if visible:
                seen_visible = True

    def _refresh_message_text(self) -> None:
        if not self._full_message:
            self._message.setText("")
            return
        metrics = QFontMetrics(self._message.font())
        width = max(0, self._message.width() - 4)
        self._message.setText(metrics.elidedText(self._full_message, Qt.TextElideMode.ElideRight, width))
