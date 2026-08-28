"""Usage overview — 2x2 metric cards matching the Profile reference."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.create.widgets.studio_panel import StudioPanel
from features.profile.widgets.icons import icon_tile
from shared.lib.formatting import format_compact_number
from shared.lib.ui_font import studio_font
from shared.models.platform import DashboardOverview

SONG_PURPLE = "#8B5CF6"
IMAGE_BLUE = "#38BDF8"
VIDEO_RED = "#F43F5E"
CREDIT_GREEN = "#00C878"


class MetricCard(QFrame):
    def __init__(self, caption: str, color: str, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        mark = QLabel()
        mark.setFixedSize(32, 32)
        mark.setPixmap(icon_tile(icon_name, color=color, tile=32, icon=16))
        layout.addWidget(mark, alignment=Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(2)
        self._value = QLabel("--")
        self._value.setObjectName("MetricValue")
        self._value.setFont(studio_font(18))
        copy.addWidget(self._value)
        caption_label = QLabel(caption)
        caption_label.setObjectName("MetricCaption")
        caption_label.setFont(studio_font(11))
        caption_label.setWordWrap(True)
        copy.addWidget(caption_label)
        layout.addLayout(copy, 1)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class UsageOverview(StudioPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("USAGE OVERVIEW")
        title.setObjectName("SectionLabel")
        title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self._songs = MetricCard("Songs generated", SONG_PURPLE, "music-4")
        self._images = MetricCard("Images generated", IMAGE_BLUE, "image")
        self._videos = MetricCard("Videos generated", VIDEO_RED, "video")
        self._credits = MetricCard("Credits spent", CREDIT_GREEN, "sparkles")
        grid.addWidget(self._songs, 0, 0)
        grid.addWidget(self._images, 0, 1)
        grid.addWidget(self._videos, 1, 0)
        grid.addWidget(self._credits, 1, 1)
        layout.addLayout(grid)

    def show_loading(self) -> None:
        for field in (self._songs, self._images, self._videos, self._credits):
            field.set_value("--")

    def apply(self, data: DashboardOverview) -> None:
        stats = data.stats
        self._songs.set_value(format_compact_number(stats.songs_generated))
        self._images.set_value(format_compact_number(stats.images_generated))
        self._videos.set_value(format_compact_number(stats.videos_generated))
        self._credits.set_value(format_compact_number(stats.credits_spent))
