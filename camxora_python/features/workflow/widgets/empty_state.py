"""Workflow empty state — standard account_card, fills remaining height."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID

LOADING_TITLE = "Loading workflow runs..."
LOADING_SUBTITLE = "Refreshing the visual pipeline board."
EMPTY_TITLE = "No runs found"
EMPTY_SUBTITLE = (
    "Try widening the date range or disabling `Active only` to see historical lanes here."
)


class WorkflowEmptyState(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addStretch(1)

        self._title = QLabel(LOADING_TITLE)
        self._title.setObjectName(TITLE_LABEL_ID)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        self._subtitle = QLabel(LOADING_SUBTITLE)
        self._subtitle.setObjectName(SUBTITLE_LABEL_ID)
        self._subtitle.setWordWrap(True)
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._subtitle)

        layout.addStretch(1)

    def show_loading(self) -> None:
        self._title.setText(LOADING_TITLE)
        self._subtitle.setText(LOADING_SUBTITLE)

    def show_empty(self) -> None:
        self._title.setText(EMPTY_TITLE)
        self._subtitle.setText(EMPTY_SUBTITLE)
