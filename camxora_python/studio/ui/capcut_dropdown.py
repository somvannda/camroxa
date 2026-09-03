"""CapCut-style popup menus — checkmark, grouped sections, shape icons."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QSizePolicy, QWidget, QWidgetAction

from studio.app.theme import PALETTE


class _ShapeIcon(QWidget):
    """Small rectangle hint matching CapCut ratio menu icons."""

    def __init__(self, shape: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._shape = shape
        self.setFixedSize(18, 18)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(PALETTE.text_dim))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        w, h = self.width(), self.height()
        pad = 2
        if self._shape == "landscape":
            rw, rh = w - pad * 2, int((w - pad * 2) * 0.56)
        elif self._shape == "portrait":
            rh, rw = h - pad * 2, int((h - pad * 2) * 0.56)
        elif self._shape == "square":
            rw = rh = min(w, h) - pad * 2
        elif self._shape == "ultrawide":
            rw, rh = w - pad * 2, max(4, int((w - pad * 2) * 0.38))
        elif self._shape == "wide":
            rw, rh = w - pad * 2, max(5, int((w - pad * 2) * 0.48))
        elif self._shape == "phone":
            rw, rh = int((w - pad * 2) * 0.52), h - pad * 2
        else:
            rw, rh = w - pad * 2, int((w - pad * 2) * 0.56)
        x = (w - rw) // 2
        y = (h - rh) // 2
        painter.drawRoundedRect(x, y, rw, rh, 2, 2)
        painter.end()


class _MenuRow(QFrame):
    clicked = Signal()

    def __init__(
        self,
        label: str,
        *,
        item_id: str,
        checked: bool = False,
        enabled: bool = True,
        icon_shape: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self.setObjectName("CapCutMenuRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
        self.setEnabled(enabled)
        if not enabled:
            self.setProperty("disabled", "true")

        self._checked = checked
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self._check = QLabel("✓" if checked else "")
        self._check.setObjectName("CapCutMenuCheck")
        self._check.setFixedWidth(14)
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._check)

        self._text = QLabel(label)
        self._text.setObjectName("CapCutMenuLabel")
        layout.addWidget(self._text, 1)

        if icon_shape:
            layout.addWidget(_ShapeIcon(icon_shape))

        self._apply_row_style()

    def _apply_row_style(self) -> None:
        if self._checked:
            self.setStyleSheet(
                f"QFrame#CapCutMenuRow {{ background-color: {PALETTE.accent}; border-radius: 4px; }}"
            )
            self._text.setStyleSheet("color: #ffffff; background: transparent;")
            self._check.setStyleSheet("color: #ffffff; background: transparent;")
        else:
            self.setStyleSheet("QFrame#CapCutMenuRow { background: transparent; border: none; }")
            self._text.setStyleSheet(f"color: {PALETTE.text}; background: transparent;")
            self._check.setStyleSheet(f"color: {PALETTE.accent}; background: transparent;")

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class CapCutDropdown(QMenu):
    """Dark grouped menu with cyan checkmarks (CapCut preview toolbar style)."""

    item_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CapCutDropdown")

    def set_items(
        self,
        sections: list[list[tuple[str, str, str | None, bool]]],
        *,
        selected_id: str,
    ) -> None:
        """Each section is a list of (id, label, icon_shape|None, enabled)."""
        self.clear()
        for section_index, section in enumerate(sections):
            if section_index > 0:
                self.addSeparator()
            for item_id, label, icon_shape, enabled in section:
                row = _MenuRow(
                    label,
                    item_id=item_id,
                    checked=(item_id == selected_id),
                    enabled=enabled,
                    icon_shape=icon_shape,
                )
                row.clicked.connect(lambda iid=item_id: self._pick(iid))
                action = QWidgetAction(self)
                action.setDefaultWidget(row)
                self.addAction(action)

    def _pick(self, item_id: str) -> None:
        self.item_selected.emit(item_id)
        self.close()
