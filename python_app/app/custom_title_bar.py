"""Custom frameless title bar with minimize, maximize, close buttons.

Renders a sleek dark title bar with Lucide icons matching the app theme.
Supports window dragging and double-click to maximize/restore.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtGui import QMouseEvent, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)

from python_app.app.resources import icon_path, lucide_icon_path
from python_app.app.window_config import toggle_maximize
from python_app.design_system.tokens import DEFAULT_DARK_THEME
from python_app.views.helpers.style_helper import render_svg_icon

_COLORS = DEFAULT_DARK_THEME.colors
_BAR_HEIGHT = 38


class CustomTitleBar(QWidget):
    """A frameless custom title bar with min/max/close and window drag."""

    def __init__(self, parent_window: QWidget, *, target_window: QWidget | None = None) -> None:
        super().__init__(parent_window)
        self._window = target_window or parent_window
        self._dragging = False
        self._drag_pos = QPoint()

        self.setFixedHeight(_BAR_HEIGHT)
        self.setStyleSheet(
            "CustomTitleBar { background: transparent; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(0)

        # App logo icon
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(QSize(18, 18))
        self._icon_label.setStyleSheet("background: transparent;")
        logo_pixmap = self._render_logo(18)
        self._icon_label.setPixmap(logo_pixmap)
        layout.addWidget(self._icon_label)
        layout.addSpacing(8)

        # Title label
        self._title_label = QLabel("Music Generator")
        self._title_label.setStyleSheet(
            f"color: {_COLORS.text_secondary};"
            "font-size: 13px;"
            "font-weight: 500;"
            "background: transparent;"
        )
        layout.addWidget(self._title_label)
        layout.addStretch(1)

        # Window control buttons
        self._btn_minimize = self._make_control_btn("minus", _COLORS.text_muted)
        self._btn_maximize = self._make_control_btn("maximize-2", _COLORS.text_muted)
        self._btn_close = self._make_control_btn("x", "#ef4444")

        self._btn_minimize.clicked.connect(self._on_minimize)
        self._btn_maximize.clicked.connect(self._on_maximize)
        self._btn_close.clicked.connect(self._on_close)

        layout.addWidget(self._btn_minimize)
        layout.addWidget(self._btn_maximize)
        layout.addWidget(self._btn_close)

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def _make_control_btn(self, icon_name: str, color: str) -> QToolButton:
        btn = QToolButton()
        btn.setFixedSize(QSize(32, 28))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIcon(render_svg_icon(lucide_icon_path(icon_name), 16, color))
        btn.setIconSize(QSize(16, 16))
        btn.setStyleSheet(
            "QToolButton {"
            "    background: transparent;"
            "    border: none;"
            "    border-radius: 4px;"
            "}"
            "QToolButton:hover {"
            "    background: rgba(255, 255, 255, 0.08);"
            "}"
        )
        return btn

    # --- Window actions ---

    def _on_minimize(self) -> None:
        self._window.showMinimized()

    def _on_maximize(self) -> None:
        toggle_maximize(self._window)

    def _on_close(self) -> None:
        self._window.close()

    # --- Dragging ---

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event and self._dragging:
            # If maximized, restore on drag (keep cursor position relative to window)
            if self._window.isMaximized():
                from PyQt6.QtCore import QRect
                prev = self._window.property("_pre_maximize_geo")
                if isinstance(prev, QRect) and prev.isValid():
                    ratio = event.position().x() / max(self._window.width(), 1)
                    new_x = int(event.globalPosition().x() - ratio * prev.width())
                    new_y = int(event.globalPosition().y() - event.position().y())
                    self._window.setGeometry(new_x, new_y, prev.width(), prev.height())
                    self._window.setProperty("_pre_maximize_geo", None)
                else:
                    self._window.showNormal()
                # Recalculate drag offset after resize
                self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        self._dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        self._on_maximize()

    # --- Helpers ---

    @staticmethod
    def _render_logo(size: int) -> QPixmap:
        """Render the app-logo SVG preserving its original colors."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(icon_path("app-logo.svg"))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return pixmap
