"""Progress summary stat cards — Create studio KPI chrome with semantic accents."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.create.widgets.icons import create_icon
from features.create.widgets.studio_panel import StudioPanel
from shared.lib.ui_font import studio_font


class ProgressStatCard(StudioPanel):
    def __init__(
        self,
        title: str,
        *,
        symbol: str,
        accent: str,
        caption: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(78)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 10)
        root.setSpacing(6)

        bar = QFrame()
        bar.setObjectName("ProgressStatAccent")
        bar.setFixedHeight(2)
        bar.setStyleSheet(f"background-color: {accent}; border: none; border-radius: 1px;")
        root.addWidget(bar)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        label = QLabel(title)
        label.setObjectName("FieldLabel")
        label.setFont(studio_font(11))
        text.addWidget(label)
        self._value = QLabel("0")
        self._value.setObjectName("KpiValue")
        self._value.setFont(studio_font(20))
        text.addWidget(self._value)
        hint = QLabel(caption)
        hint.setObjectName("PageSubtitle")
        hint.setFont(studio_font(11))
        text.addWidget(hint)
        row.addLayout(text, 1)
        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        icon.setPixmap(create_icon(symbol, size=16, color=accent).pixmap(16, 16))
        row.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(row)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class ProgressStatsRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._active_card = ProgressStatCard(
            "Active Runs", symbol="activity", accent="#7C3AED", caption="In-flight pipelines"
        )
        self._converter_card = ProgressStatCard(
            "Export / Merge", symbol="video", accent="#38BDF8", caption="Video work queued"
        )
        self._waiting_card = ProgressStatCard(
            "Waiting On User", symbol="clock", accent="#F59E0B", caption="Needs a decision"
        )
        self._failed_card = ProgressStatCard(
            "Failed / Blocked", symbol="triangle-alert", accent="#F43F5E", caption="Needs recovery"
        )
        for card in (
            self._active_card,
            self._converter_card,
            self._waiting_card,
            self._failed_card,
        ):
            layout.addWidget(card, stretch=1)

    def set_summary_counts(
        self,
        *,
        active: int,
        converter: int,
        waiting: int,
        failed: int,
    ) -> None:
        self._active_card.set_value(str(active))
        self._converter_card.set_value(str(converter))
        self._waiting_card.set_value(str(waiting))
        self._failed_card.set_value(str(failed))
