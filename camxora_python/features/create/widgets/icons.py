"""Icon helper for the Create workspace."""

from __future__ import annotations

from PySide6.QtGui import QIcon

from shared.icons.lucide_icons import lucide_pixmap


def create_icon(name: str, *, size: int = 16, color: str = "#8FA4BB") -> QIcon:
    return QIcon(lucide_pixmap(name, size=size, color=color))
