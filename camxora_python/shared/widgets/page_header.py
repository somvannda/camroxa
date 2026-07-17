"""Page header with eyebrow, title, and description."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from shared.constants.navigation import ShellRouteMeta
from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID


class PageHeader(QFrame):
    """Header bar shown above workspace pages (hidden on video workspace)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page_header")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self._eyebrow = QLabel()
        self._eyebrow.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(self._eyebrow)

        self._title = QLabel()
        self._title.setObjectName(TITLE_LABEL_ID)
        layout.addWidget(self._title)

        self._description = QLabel()
        self._description.setObjectName(SUBTITLE_LABEL_ID)
        self._description.setWordWrap(True)
        layout.addWidget(self._description)

    def set_route(self, route: ShellRouteMeta) -> None:
        self._eyebrow.setText(route.eyebrow.upper())
        self._title.setText(route.title)
        self._description.setText(route.description)
