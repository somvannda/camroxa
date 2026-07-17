"""Startup splash — mirrors StartupPage.tsx."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID

# Matches Electron `createSplashWindow()` content size (camxora/src/main/index.ts).
SPLASH_CARD_WIDTH = 380
SPLASH_CARD_HEIGHT = 176


class StartupProgressBar(QFrame):
    """Pill-shaped progress track — QProgressBar chunk rounding is unreliable on Windows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("startup_progress_track")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(8)
        self._value = 10

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._fill = QFrame()
        self._fill.setObjectName("startup_progress_fill")
        self._fill.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._fill.setFixedHeight(8)
        layout.addWidget(self._fill)
        layout.addStretch()

        self._update_fill_width()

    def value(self) -> int:
        return self._value

    def set_value(self, value: int) -> None:
        self._value = max(0, min(100, value))
        self._update_fill_width()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_fill_width()

    def _update_fill_width(self) -> None:
        fill_width = max(0, int(self.width() * self._value / 100))
        self._fill.setFixedWidth(fill_width)


class StartupView(QFrame):
    """Loading screen shown while session bootstrap runs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("startup_page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addStretch()

        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.setSpacing(0)
        center_row.addStretch()

        card = QFrame()
        card.setObjectName("startup_loading_card")
        card.setFixedSize(SPLASH_CARD_WIDTH, SPLASH_CARD_HEIGHT)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(8)

        loading = QLabel("LOADING")
        loading.setObjectName(SUBTITLE_LABEL_ID)
        card_layout.addWidget(loading)

        self._title = QLabel("Starting Camxora")
        self._title.setObjectName(TITLE_LABEL_ID)
        self._title.setWordWrap(True)
        card_layout.addWidget(self._title)

        self._detail = QLabel("Launching the desktop studio.")
        self._detail.setObjectName(SUBTITLE_LABEL_ID)
        self._detail.setWordWrap(True)
        card_layout.addWidget(self._detail)

        card_layout.addStretch()

        self._progress = StartupProgressBar()
        card_layout.addWidget(self._progress)

        center_row.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        center_row.addStretch()
        outer.addLayout(center_row)
        outer.addStretch()

    def progress_value(self) -> int:
        return self._progress.value()

    def reset_progress(self, value: int = 10) -> None:
        """Allow a fresh loading pass (e.g. after login from the auth screen)."""
        self._progress.set_value(max(0, min(100, value)))

    def set_progress(self, label: str, detail: str, value: int) -> None:
        self._title.setText(label)
        self._detail.setText(detail)
        # Never jump backward — avoids the "reload" feel between bootstrap and warmup.
        next_value = max(0, min(100, value))
        self._progress.set_value(max(self._progress.value(), next_value))
