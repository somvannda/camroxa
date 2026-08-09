"""Header software-update affordance (non-blocking mid-session notice)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QPushButton, QWidget

from shared.icons.lucide_icons import lucide_pixmap
from shared.services.software_update_service import SoftwareUpdateOffer, SoftwareUpdateService

# Emerald on near-black header (#060b20) — readable, not neon.
_ICON_COLOR = "#4ade80"
_ICON_HOVER_COLOR = "#86efac"
_HOVER_FILL = QColor(74, 222, 128, 28)
_PRESS_FILL = QColor(74, 222, 128, 48)


class SoftwareUpdateHeaderButton(QPushButton):
    """Green arrow-up-circle shown when a newer desktop build is available."""

    update_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("software_update_header_button")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFlat(True)
        self.setFixedSize(40, 32)
        self.setToolTip("Update available")
        self.hide()
        self.clicked.connect(self.update_requested.emit)

        service = SoftwareUpdateService.instance()
        service.update_changed.connect(self._on_update_changed)
        self._on_update_changed(service.pending)

    def _on_update_changed(self, offer: object) -> None:
        visible = isinstance(offer, SoftwareUpdateOffer)
        self.setVisible(visible)
        if not visible:
            return
        version = offer.version.strip()
        if version:
            self.setToolTip(f"Update available — v{version}")
        else:
            self.setToolTip("Update available")

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.isDown():
            fill = _PRESS_FILL
        elif self.underMouse():
            fill = _HOVER_FILL
        else:
            fill = QColor(0, 0, 0, 0)
        if fill.alpha() > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)

        color = _ICON_HOVER_COLOR if self.underMouse() or self.isDown() else _ICON_COLOR
        icon = lucide_pixmap("arrow-up-circle", size=16, color=color)
        x = (self.width() - icon.width()) // 2
        y = (self.height() - icon.height()) // 2
        painter.drawPixmap(x, y, icon)
