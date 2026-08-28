"""Login card helpers: gradient title, icon fields, brand lockup."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QLabel, QLineEdit, QToolButton, QWidget

from shared.icons.lucide_icons import lucide_pixmap
from shared.lib.ui_font import studio_font
from shared.widgets.window_title_bar import _load_logo_pixmap


class GradientWelcomeLabel(QLabel):
    """'Welcome back' with a cyan-to-blue fill."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("auth_welcome")
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.setFont(studio_font(28, QFont.Weight.DemiBold))
        self.setMinimumHeight(36)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = self.font()
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text = self.text()
        text_width = metrics.horizontalAdvance(text)
        x = max(0, (self.width() - text_width) // 2)
        y = metrics.ascent() + max(0, (self.height() - metrics.height()) // 2)
        gradient = QLinearGradient(x, 0, x + max(1, text_width), 0)
        gradient.setColorAt(0.0, QColor("#22D3EE"))
        gradient.setColorAt(1.0, QColor("#38BDF8"))
        painter.setPen(QPen(gradient, 0))
        painter.drawText(x, y, text)


class BrandMark(QLabel):
    def __init__(self, size: int = 48, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("auth_brand_mark")
        self.setFixedSize(size, size)
        self.setPixmap(_load_logo_pixmap(size))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class IconLineEdit(QLineEdit):
    """48px input with a leading lucide icon and optional trailing action."""

    def __init__(
        self,
        icon_name: str,
        placeholder: str,
        parent: QWidget | None = None,
        *,
        password: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("auth_input")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(False)
        self.setFont(studio_font(14))
        self.setMinimumHeight(48)
        self.setMaximumHeight(48)
        leading = self.addAction(
            QIcon(lucide_pixmap(icon_name, size=16, color="#65748F")),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        leading.setEnabled(False)
        self._eye_button: QToolButton | None = None
        if password:
            self.setEchoMode(QLineEdit.EchoMode.Password)
            self._eye_button = QToolButton(self)
            self._eye_button.setObjectName("auth_eye_button")
            self._eye_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._eye_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._eye_button.setAutoRaise(True)
            self._eye_button.clicked.connect(self._toggle_password)
            self._sync_eye_icon()
            self._place_eye()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._place_eye()

    def _place_eye(self) -> None:
        if self._eye_button is None:
            return
        size = 28
        self._eye_button.setFixedSize(size, size)
        self._eye_button.move(self.width() - size - 10, (self.height() - size) // 2)

    def _toggle_password(self) -> None:
        hidden = self.echoMode() == QLineEdit.EchoMode.Password
        self.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self._sync_eye_icon()

    def _sync_eye_icon(self) -> None:
        if self._eye_button is None:
            return
        name = "eye-off" if self.echoMode() == QLineEdit.EchoMode.Normal else "eye"
        self._eye_button.setIcon(QIcon(lucide_pixmap(name, size=16, color="#65748F")))
        self._eye_button.setToolTip("Hide password" if name == "eye-off" else "Show password")
