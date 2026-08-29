"""Create-page controls painted to match the studio screenshot."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QPushButton,
    QRadioButton,
    QToolButton,
    QWidget,
)

from shared.icons.lucide_icons import lucide_pixmap
from shared.lib.ui_font import studio_font

_ICON = "#8FA4BB"
_TEXT = "#E5EDF7"
_MUTED = "#60758C"
_PURPLE = "#7C3AED"
_INPUT = "#101F32"


def _draw_down_arrow(painter: QPainter, right: int, height: int, color: str = _ICON) -> None:
    """Visible ▼ chevron so Fusion's native dash/up-arrow never shows through."""
    cx = float(right - 12)
    cy = float(height) / 2.0
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor(color), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolyline(
        QPolygonF(
            [
                QPointF(cx - 5.0, cy - 2.0),
                QPointF(cx, cy + 3.5),
                QPointF(cx + 5.0, cy - 2.0),
            ]
        )
    )


class StudioComboBox(QComboBox):
    """Language / template select with a down-arrow, menu always opens below."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._explicit_tooltip = ""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(studio_font(12))
        self.setMaxVisibleItems(8)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(6)
        self.setMinimumWidth(0)
        self.currentIndexChanged.connect(self._sync_current_tooltip)

    def setToolTip(self, tip: str) -> None:  # noqa: N802
        self._explicit_tooltip = str(tip or "")
        super().setToolTip(self._explicit_tooltip)

    def sync_item_tooltips(self) -> None:
        for index in range(self.count()):
            self.setItemData(index, self.itemText(index), Qt.ItemDataRole.ToolTipRole)
        self._sync_current_tooltip()

    def _sync_current_tooltip(self, *_args: object) -> None:
        if self._explicit_tooltip:
            return
        super().setToolTip(self.currentText())

    def showPopup(self) -> None:  # noqa: N802
        super().showPopup()
        view = self.view()
        if view is None:
            return
        popup = view.window()
        metrics = self.fontMetrics()
        text_width = max(
            (metrics.horizontalAdvance(self.itemText(index)) for index in range(self.count())),
            default=0,
        )
        popup_width = max(self.width(), text_width + 36)
        screen = self.screen()
        available = screen.availableGeometry() if screen is not None else None
        if available is not None:
            popup_width = min(popup_width, max(self.width(), available.width() - 24))
        popup.resize(popup_width, popup.height())
        origin = self.mapToGlobal(QPoint(0, self.height()))
        x = origin.x()
        if available is not None and x + popup_width > available.right():
            x = max(available.left(), available.right() - popup_width)
        popup.move(x, origin.y())

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        _draw_down_arrow(painter, self.width(), self.height(), "#E5EDF7")


class StudioDateEdit(QDateEdit):
    """From / To field with a calendar icon that opens the date popup."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(False)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setDisplayFormat("MM/dd/yyyy")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(studio_font(12))

        self._popup = QCalendarWidget()
        self._popup.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._popup.setStyleSheet(CALENDAR_POPUP_QSS)
        self._popup.setGridVisible(False)
        self._popup.clicked.connect(self._pick_date)

        self._icon_btn = QToolButton(self)
        self._icon_btn.setObjectName("DateCalendarButton")
        self._icon_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_btn.setIcon(QIcon(lucide_pixmap("calendar", size=14, color=_ICON)))
        self._icon_btn.setIconSize(QSize(14, 14))
        self._icon_btn.setAutoRaise(True)
        self._icon_btn.setStyleSheet(
            "QToolButton { border: none; background: transparent; padding: 0; }"
            "QToolButton:hover { background: transparent; border: none; }"
        )
        self._icon_btn.clicked.connect(self._open_calendar)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        size = 22
        self._icon_btn.setGeometry(self.width() - size - 4, (self.height() - size) // 2, size, size)

    def _open_calendar(self) -> None:
        self._popup.setSelectedDate(self.date())
        self._popup.adjustSize()
        self._popup.move(self.mapToGlobal(QPoint(0, self.height() + 2)))
        self._popup.show()
        self._popup.raise_()

    def _pick_date(self, value) -> None:
        self.setDate(value)
        self._popup.hide()


class StudioRadioButton(QRadioButton):
    """Ring + inner purple dot, matching the Vocal Gender control."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(studio_font(12))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = self.fontMetrics()
        return QSize(16 + 8 + metrics.horizontalAdvance(self.text()) + 4, 22)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        size = 16
        y = (self.height() - size) // 2
        if self.isChecked():
            painter.setPen(QPen(QColor(_PURPLE), 2))
            painter.setBrush(QColor(_INPUT))
            painter.drawEllipse(1, y + 1, size - 2, size - 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(_PURPLE))
            painter.drawEllipse(5, y + 5, 6, 6)
        else:
            painter.setPen(QPen(QColor(_ICON), 1.5))
            painter.setBrush(QColor(_INPUT))
            painter.drawEllipse(1, y + 1, size - 2, size - 2)
        painter.setPen(QColor(_TEXT))
        painter.setFont(self.font())
        text_rect = QRect(size + 8, 0, self.width() - size - 8, self.height())
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter), self.text())


class StudioCheckBox(QCheckBox):
    """Square checkbox with a white check when selected."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(studio_font(12))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = self.fontMetrics()
        return QSize(14 + 8 + metrics.horizontalAdvance(self.text()) + 4, 22)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        box = 14
        y = (self.height() - box) // 2
        if self.isChecked():
            painter.setPen(QPen(QColor(_PURPLE), 1.5))
            painter.setBrush(QColor(_PURPLE))
            painter.drawRoundedRect(1, y, box, box, 3, 3)
            check = lucide_pixmap("check", size=10, color="#FFFFFF")
            painter.drawPixmap(3, y + 2, check)
        else:
            painter.setPen(QPen(QColor("#23415E"), 1.5))
            painter.setBrush(QColor(_INPUT))
            painter.drawRoundedRect(1, y, box, box, 3, 3)
        painter.setPen(QColor(_TEXT))
        painter.setFont(self.font())
        text_rect = QRect(box + 8, 0, self.width() - box - 8, self.height())
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter), self.text())


class ModeTab(QPushButton):
    """Simple / Advanced box tab with a purple fill when active."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("ModeTab")
        self.setCheckable(True)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFont(studio_font(12, QFont.Weight.Medium))
        self.setFixedHeight(36)
        self.setMinimumWidth(96)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        box = self.rect().adjusted(1, 1, -1, -1)
        active = self.isChecked()
        if active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#6335D9"))
            painter.drawRoundedRect(box, 5, 5)
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(studio_font(12, QFont.Weight.DemiBold))
        else:
            painter.setPen(QPen(QColor("#23415E"), 1))
            painter.setBrush(QColor("#101F32"))
            painter.drawRoundedRect(box, 5, 5)
            painter.setPen(QColor(_TEXT if self.underMouse() else _MUTED))
            painter.setFont(self.font())
        painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self.text())


CALENDAR_POPUP_QSS = """
QCalendarWidget {
    background-color: #0D1B2E;
    color: #E5EDF7;
    border: 1px solid #23415E;
}
QCalendarWidget QWidget {
    background-color: #0D1B2E;
    color: #E5EDF7;
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
}
QCalendarWidget QToolButton {
    color: #E5EDF7;
    background: transparent;
    border: none;
    padding: 4px 8px;
    font-size: 12px;
}
QCalendarWidget QToolButton:hover {
    color: #ffffff;
    background: rgba(124, 58, 237, 0.22);
    border-radius: 4px;
}
QCalendarWidget QAbstractItemView:enabled {
    background-color: #0D1B2E;
    color: #E5EDF7;
    selection-background-color: #6335D9;
    selection-color: #ffffff;
    outline: none;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #60758C;
}
QCalendarWidget QSpinBox {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #18304A;
}
"""
