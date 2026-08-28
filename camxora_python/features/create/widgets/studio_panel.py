"""Studio card frame — paints even when ancestor QSS cannot reach the widget."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QFrame, QWidget

from features.create.create_styles import STUDIO_BG, STUDIO_BORDER_STRONG, STUDIO_PANEL


def paint_studio_card(widget: QWidget) -> None:
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rect = QRectF(widget.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
    painter.setPen(QPen(QColor(STUDIO_BORDER_STRONG), 1))
    painter.setBrush(QColor(STUDIO_PANEL))
    painter.drawRoundedRect(rect, 6, 6)
    painter.end()


def fill_studio_canvas(widget: QWidget) -> None:
    """Page/column fill that does not install a stylesheet (avoids Qt QSS barriers)."""
    widget.setAutoFillBackground(True)
    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(STUDIO_BG))
    widget.setPalette(palette)


class StudioPanel(QFrame):
    """Create-style card: #0D1B2E fill, #23415E border, 6px radius."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def paintEvent(self, event: QPaintEvent) -> None:
        paint_studio_card(self)
