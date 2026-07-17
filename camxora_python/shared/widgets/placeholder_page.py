"""Placeholder page content for routes not yet implemented."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from shared.constants.navigation import ShellRouteMeta
from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID


class PlaceholderPage(QFrame):
    """Simple placeholder matching Electron PlaceholderPage.tsx."""

    def __init__(self, route: ShellRouteMeta, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._route = route

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        eyebrow = QLabel(route.eyebrow.upper())
        eyebrow.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(eyebrow)

        title = QLabel(route.title)
        title.setObjectName(TITLE_LABEL_ID)
        layout.addWidget(title)

        description = QLabel(route.description)
        description.setObjectName(SUBTITLE_LABEL_ID)
        description.setWordWrap(True)
        layout.addWidget(description)

        if route.is_placeholder:
            badge = QLabel("Coming in a future phase")
            badge.setObjectName(SUBTITLE_LABEL_ID)
            layout.addWidget(badge)
        else:
            badge = QLabel("Phase 1 placeholder — workspace UI arrives in later phases")
            badge.setObjectName(SUBTITLE_LABEL_ID)
            layout.addWidget(badge)

        layout.addStretch()

    @property
    def route(self) -> ShellRouteMeta:
        return self._route
