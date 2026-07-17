"""Per-channel daily song/image quota card."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from shared.models.platform import ChannelDailyQuota, DashboardOverview, QuotaStatusResponse
from shared.themes.deep_blue import SUBTITLE_LABEL_ID


class DailyChannelQuotaCard(QFrame):
    SUBTITLE = "Remaining song and image capacity per channel for today."

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("DAILY CHANNEL LIMITS")
        title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title)

        subtitle = QLabel(self.SUBTITLE)
        subtitle.setObjectName(SUBTITLE_LABEL_ID)
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self._empty = QLabel("No channel quota data available yet.")
        self._empty.setObjectName(SUBTITLE_LABEL_ID)
        self._empty.hide()
        root.addWidget(self._empty)

        self._rows_host = QWidget()
        self._rows = QVBoxLayout(self._rows_host)
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(8)
        root.addWidget(self._rows_host)

    def apply_quota(self, quota: QuotaStatusResponse | None) -> None:
        self._clear_rows()
        channels = list(quota.channels) if quota is not None else []
        if not channels:
            self._empty.show()
            return
        self._empty.hide()
        for channel in channels:
            self._rows.addWidget(self._build_row(channel))

    def apply_overview(self, data: DashboardOverview) -> None:
        if data.quota is not None and data.quota.channels:
            self.apply_quota(data.quota)
            return

        license_info = data.license
        songs_limit = (
            license_info.daily_song_limit_per_channel if license_info is not None else None
        ) or 0
        images_limit = (
            license_info.daily_image_limit_per_channel if license_info is not None else None
        ) or 0
        profiles = list(data.profiles)
        if not profiles or (songs_limit <= 0 and images_limit <= 0):
            self.apply_quota(None)
            return

        fallback = QuotaStatusResponse(
            channels=[
                ChannelDailyQuota(
                    profile_id=profile.id,
                    profile_name=profile.name,
                    daily_songs_limit=songs_limit,
                    daily_songs_remaining=songs_limit,
                    daily_images_limit=images_limit,
                    daily_images_remaining=images_limit,
                )
                for profile in profiles
            ]
        )
        self.apply_quota(fallback)

    def _build_row(self, channel: ChannelDailyQuota) -> QFrame:
        row = QFrame()
        row.setObjectName("dashboard_quota_summary")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        name = QLabel(channel.profile_name)
        name.setStyleSheet("font-weight: 600;")
        header.addWidget(name)
        header.addStretch()
        layout.addLayout(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        grid.addWidget(self._metric_label("Songs today"), 0, 0)
        grid.addWidget(
            self._value_label(channel.daily_songs_remaining, channel.daily_songs_limit),
            0,
            1,
        )
        grid.addWidget(self._metric_label("Images today"), 1, 0)
        grid.addWidget(
            self._value_label(channel.daily_images_remaining, channel.daily_images_limit),
            1,
            1,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        layout.addLayout(grid)
        return row

    @staticmethod
    def _metric_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(SUBTITLE_LABEL_ID)
        return label

    @staticmethod
    def _value_label(remaining: int, limit: int) -> QLabel:
        label = QLabel(f"{max(remaining, 0)} / {max(limit, 0)} remaining")
        return label

    def _clear_rows(self) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
