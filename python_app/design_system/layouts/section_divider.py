"""Section divider layout component.

Provides a horizontal separator line widget using the design system separator token color.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QPaintEvent
from PyQt6.QtCore import Qt

from python_app.design_system.tokens import DEFAULT_DARK_THEME


class SectionDivider(QWidget):
    """A horizontal line divider using the separator token color.

    Renders a 1px horizontal line across the full widget width,
    colored with the design system separator token (#27354b).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(DEFAULT_DARK_THEME.colors.separator)
        self.setFixedHeight(DEFAULT_DARK_THEME.shape.border_width_thin)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw a horizontal line across the widget width."""
        painter = QPainter(self)
        try:
            pen = QPen(self._color)
            pen.setWidth(DEFAULT_DARK_THEME.shape.border_width_thin)
            painter.setPen(pen)
            # Draw line at the vertical center of the widget
            y = self.height() // 2
            painter.drawLine(0, y, self.width(), y)
        finally:
            painter.end()
