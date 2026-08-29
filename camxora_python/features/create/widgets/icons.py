"""Icon helper for the Create workspace."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QWidget

from shared.icons.lucide_icons import lucide_pixmap
from shared.lib.ui_font import studio_font


def create_icon(name: str, *, size: int = 16, color: str = "#8FA4BB") -> QIcon:
    return QIcon(lucide_pixmap(name, size=size, color=color))


def apply_button_icon(
    button: QAbstractButton,
    name: str,
    *,
    size: int = 14,
    color: str = "#E5EDF7",
) -> None:
    button.setIcon(create_icon(name, size=size, color=color))
    button.setIconSize(QSize(size, size))


def icon_label(name: str, *, size: int = 14, color: str = "#8FA4BB") -> QLabel:
    label = QLabel()
    label.setObjectName("TransparentBlock")
    label.setAutoFillBackground(False)
    label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    label.setPixmap(create_icon(name, size=size, color=color).pixmap(size, size))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def section_heading(text: str, icon: str, parent: QWidget | None = None) -> QWidget:
    row = QWidget(parent)
    row.setObjectName("TransparentBlock")
    row.setAutoFillBackground(False)
    row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    icon = icon_label(icon, size=14)
    icon.setAutoFillBackground(False)
    layout.addWidget(icon)
    title = QLabel(text)
    title.setObjectName("SectionLabel")
    title.setAutoFillBackground(False)
    title.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
    layout.addWidget(title)
    layout.addStretch()
    return row
