"""Module-level widget-styling utility functions.

Extracted from MainWindow to allow independent testing and reuse without
instantiating the full application window.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QPushButton, QLabel, QWidget


# ---------------------------------------------------------------------------
# Core styling helpers
# ---------------------------------------------------------------------------


def refresh_widget_style(widget: QWidget | None) -> None:
    """Re-polish the widget so that dynamic property changes take effect."""
    if widget is None:
        return
    try:
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
        widget.update()
    except RuntimeError:
        return


def set_widget_property(widget: QWidget | None, name: str, value: str) -> None:
    """Set a dynamic Qt property and refresh the widget style."""
    if widget is None:
        return
    try:
        widget.setProperty(name, value)
        refresh_widget_style(widget)
    except RuntimeError:
        return


def set_panel_role(widget: QWidget | None, role: str) -> None:
    """Mark *widget* as a styled panel with the given role."""
    if widget is None:
        return
    try:
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        set_widget_property(widget, "uiPanel", role)
    except RuntimeError:
        return


def set_label_role(label: QLabel | None, role: str) -> None:
    """Apply a UI role to a QLabel via dynamic property."""
    if label is None:
        return
    try:
        set_widget_property(label, "uiRole", role)
    except RuntimeError:
        return


def set_button_role(button: QPushButton | None, role: str) -> None:
    """Apply a UI role to a QPushButton via dynamic property."""
    if button is None:
        return
    try:
        set_widget_property(button, "uiRole", role)
    except RuntimeError:
        return


def set_field_role(widget: QWidget | None, role: str) -> None:
    """Apply a UI field role to a widget via dynamic property."""
    if widget is None:
        return
    try:
        set_widget_property(widget, "uiField", role)
    except RuntimeError:
        return


def apply_cta_button(button: QPushButton | None, variant: str, tokens: dict[str, str]) -> None:
    """Style *button* as a CTA — now purely via property role (no inline QSS).

    Supported variants: ``"primary"``, ``"success"``, ``"warning"``.
    """
    if button is None:
        return
    try:
        role_map = {
            "primary": "gradientPrimary",
            "success": "success",
            "warning": "warning",
        }
        role = role_map.get(str(variant or "primary"), "gradientPrimary")
        set_button_role(button, role)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(max(40, button.minimumHeight()))
    except RuntimeError:
        return


def apply_card_field(widget: QWidget | None) -> None:
    """Apply the 'card' field role to *widget*."""
    if widget is None:
        return
    try:
        set_field_role(widget, "card")
    except RuntimeError:
        return


def render_svg_icon(
    svg_path: str,
    size: int,
    color: str,
    *,
    cache: dict[tuple[str, int, str], QIcon] | None = None,
) -> QIcon:
    """Render an SVG file as a QIcon tinted to *color*.

    If *cache* is provided, previously rendered icons are reused. The cache is
    cleared when it exceeds 256 entries to prevent unbounded memory growth.
    """
    try:
        px_size = max(12, int(size))
        icon_path = Path(str(svg_path or ""))
        if not icon_path.exists():
            return QIcon()

        key = (str(icon_path), int(px_size), str(color))

        if cache is not None:
            cached = cache.get(key)
            if cached is not None:
                return cached

        renderer = QSvgRenderer(str(icon_path))
        pixmap = QPixmap(px_size, px_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(str(color)))
        painter.end()
        icon = QIcon(pixmap)

        if cache is not None:
            if len(cache) >= 256:
                cache.clear()
            cache[key] = icon

        return icon
    except RuntimeError:
        return QIcon()
