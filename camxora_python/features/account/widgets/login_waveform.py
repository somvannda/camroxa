"""Login stage backdrop from the packaged background image."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from shared.lib.resource_paths import get_resource_path

LOGIN_BACKGROUND_NAME = "background_login.png"


def login_background_path():
    return get_resource_path(LOGIN_BACKGROUND_NAME)


class LoginWaveform(QWidget):
    """Scaled login background; fills the stage and stays behind the card."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("auth_waveform")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._source = QPixmap(str(login_background_path()))

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._source.isNull() or self.width() <= 0 or self.height() <= 0:
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
            return
        scaled = self._source.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
