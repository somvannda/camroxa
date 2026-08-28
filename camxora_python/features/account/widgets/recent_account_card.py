"""Recent-account row matching the login screenshot."""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from shared.icons.lucide_icons import lucide_pixmap
from shared.lib.settings_workspace import get_profile_initials
from shared.lib.ui_font import studio_font
from shared.services.account_token_store import SavedAccount


_AVATAR_COLORS = ("#6D3DF5", "#2563EB")


class _InitialsAvatar(QWidget):
    def __init__(self, initials: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._initials = initials
        self._color = color
        self.setFixedSize(36, 36)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(self.rect())
        painter.setPen(QColor("#F1F5F9"))
        painter.setFont(studio_font(12, QFont.Weight.DemiBold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._initials)


class RecentAccountCard(QFrame):
    selected = Signal(str, str)
    removed = Signal(str)

    def __init__(self, account: SavedAccount, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("auth_recent_card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(64)
        self._user_id = account.user_id
        self._email = account.email
        name = account.display_name or account.email or account.user_id

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 8, 10)
        row.setSpacing(10)

        row.addWidget(
            _InitialsAvatar(get_profile_initials(name), _AVATAR_COLORS[index % 2]),
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(1)
        name_label = QLabel(name)
        name_label.setObjectName("auth_recent_name")
        name_label.setFont(studio_font(13, QFont.Weight.DemiBold))
        email_label = QLabel(account.email or account.user_id)
        email_label.setObjectName("auth_recent_email")
        email_label.setFont(studio_font(11))
        copy.addWidget(name_label)
        copy.addWidget(email_label)
        row.addLayout(copy, 1)

        chevron = QLabel()
        chevron.setPixmap(lucide_pixmap("chevron-right", size=16, color="#65748F"))
        row.addWidget(chevron, alignment=Qt.AlignmentFlag.AlignVCenter)

        remove = QToolButton()
        remove.setObjectName("auth_recent_remove")
        remove.setCursor(Qt.CursorShape.PointingHandCursor)
        remove.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        remove.setToolTip("Remove this pinned profile")
        remove.setIcon(QIcon(lucide_pixmap("x", size=14, color="#65748F")))
        remove.setAutoRaise(True)
        remove.clicked.connect(lambda: self.removed.emit(self._user_id))
        row.addWidget(remove, alignment=Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._user_id, self._email)
            event.accept()
            return
        super().mousePressEvent(event)
