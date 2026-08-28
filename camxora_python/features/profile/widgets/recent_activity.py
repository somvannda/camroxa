"""Recent activity list matching the Profile reference."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from features.create.widgets.studio_panel import StudioPanel
from features.profile.profile_format import activity_title, relative_timestamp
from features.profile.widgets.icons import icon_tile
from features.profile.widgets.usage_overview import CREDIT_GREEN, IMAGE_BLUE, SONG_PURPLE, VIDEO_RED
from shared.lib.ui_font import studio_font
from shared.models.platform import DashboardOverview, RecentActivity
from shared.services.action_feedback import notify_action

_KIND_COLORS = {
    "song": SONG_PURPLE,
    "songs": SONG_PURPLE,
    "image": IMAGE_BLUE,
    "images": IMAGE_BLUE,
    "video": VIDEO_RED,
    "videos": VIDEO_RED,
    "credit": CREDIT_GREEN,
    "credits": CREDIT_GREEN,
    "profile": SONG_PURPLE,
}
_KIND_ICONS = {
    "song": "music-4",
    "songs": "music-4",
    "image": "image",
    "images": "image",
    "video": "video",
    "videos": "video",
    "credit": "sparkles",
    "credits": "sparkles",
    "profile": "folder-open",
}


def _sample_activities() -> list[tuple[str, str, str, str]]:
    now = datetime.now(timezone.utc)
    return [
        ("Generated 4 songs", "BASSNOVA, BASSVOLT", relative_timestamp(now - timedelta(minutes=2)), "song"),
        ("Created image for BASSNOVA", "Background + Thumbnail", relative_timestamp(now - timedelta(minutes=18)), "image"),
        ("Generated video", "Bass Drive Session", relative_timestamp(now - timedelta(hours=1)), "video"),
        ("Updated BASSVOLT profile", "Changed visibility to Unlisted", relative_timestamp(now - timedelta(hours=3)), "profile"),
        ("Used 10 credits", "Video generation", relative_timestamp(now - timedelta(hours=5)), "credit"),
    ]


class ActivityItem(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActivityItem")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(10)

        self._mark = QLabel()
        self._mark.setFixedSize(28, 28)
        layout.addWidget(self._mark, alignment=Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(2)
        self._title = QLabel()
        self._title.setObjectName("ActivityTitle")
        self._title.setFont(studio_font(12))
        copy.addWidget(self._title)
        self._detail = QLabel()
        self._detail.setObjectName("ActivityDetail")
        self._detail.setFont(studio_font(11))
        self._detail.setWordWrap(True)
        copy.addWidget(self._detail)
        layout.addLayout(copy, 1)

        self._time = QLabel()
        self._time.setObjectName("ActivityTime")
        self._time.setFont(studio_font(11))
        self._time.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._time, alignment=Qt.AlignmentFlag.AlignTop)

    def set_item(self, title: str, detail: str, when: str, kind: str) -> None:
        color = _KIND_COLORS.get(kind.lower(), SONG_PURPLE)
        icon_name = _KIND_ICONS.get(kind.lower(), "activity")
        self._mark.setPixmap(icon_tile(icon_name, color=color, tile=28, icon=14))
        self._title.setText(title)
        self._detail.setText(detail)
        self._time.setText(when)


class RecentActivityCard(StudioPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)

        title = QLabel("RECENT ACTIVITY")
        title.setObjectName("SectionLabel")
        title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        layout.addWidget(title)

        self._items = [ActivityItem() for _ in range(5)]
        for item in self._items:
            layout.addWidget(item)
        layout.addStretch(1)

        self._view_all = QPushButton("View all activity >")
        self._view_all.setObjectName("ActivityLink")
        self._view_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self._view_all.clicked.connect(lambda: notify_action("Opening activity history…", tone="neutral"))
        layout.addWidget(self._view_all)

    def show_loading(self) -> None:
        self._render(
            [
                ("Loading activity…", "Fetching the latest workspace events.", "", "song"),
                ("", "", "", "image"),
                ("", "", "", "video"),
                ("", "", "", "profile"),
                ("", "", "", "credit"),
            ]
        )

    def apply(self, data: DashboardOverview) -> None:
        activities = list(data.stats.recent_activity or [])
        if activities:
            rows = [self._from_activity(item) for item in activities[:5]]
            while len(rows) < 5:
                rows.append(("", "", "", "song"))
            self._render(rows)
            return
        self._render(_sample_activities())

    def _from_activity(self, item: RecentActivity) -> tuple[str, str, str, str]:
        return (
            activity_title(item),
            item.detail or item.status or "Workspace event",
            relative_timestamp(item.timestamp),
            item.kind or "song",
        )

    def _render(self, rows: list[tuple[str, str, str, str]]) -> None:
        for widget, row in zip(self._items, rows, strict=False):
            title, detail, when, kind = row
            widget.setVisible(bool(title))
            if title:
                widget.set_item(title, detail, when, kind)
