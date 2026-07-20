"""Remaining This Month card."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.dashboard.widgets.progress_summary_row import ProgressSummaryRow
from shared.lib.formatting import format_compact_number
from shared.models.platform import DashboardOverview
from shared.themes.deep_blue import SUBTITLE_LABEL_ID


def _xy(remaining: int | None, quota: int | None) -> str:
    if remaining is None and quota is None:
        return "Not on plan"
    left = format_compact_number(remaining if remaining is not None else 0)
    if quota is None:
        return f"{left} left"
    return f"{left} of {format_compact_number(quota)} left"


class RemainingMonthCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(6)

        title = QLabel("REMAINING THIS MONTH")
        title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title)

        hint = QLabel("How much of your plan allowance is still available.")
        hint.setObjectName(SUBTITLE_LABEL_ID)
        hint.setWordWrap(True)
        root.addWidget(hint)

        meters = QVBoxLayout()
        meters.setContentsMargins(0, 0, 0, 0)
        meters.setSpacing(4)
        self._credits = ProgressSummaryRow("Credits", bar_color="violet")
        self._drafts = ProgressSummaryRow("Drafts", bar_color="amber")
        self._songs = ProgressSummaryRow("Suno packages", bar_color="sky")
        self._images = ProgressSummaryRow("Images", bar_color="emerald")
        self._videos = ProgressSummaryRow("Track exports", bar_color="sky")
        self._merges = ProgressSummaryRow("Merges", bar_color="violet")
        meters.addWidget(self._credits)
        meters.addWidget(self._drafts)
        meters.addWidget(self._songs)
        meters.addWidget(self._images)
        meters.addWidget(self._videos)
        meters.addWidget(self._merges)
        root.addLayout(meters)

        daily = QFrame()
        daily.setObjectName("dashboard_quota_summary")
        daily_layout = QVBoxLayout(daily)
        daily_layout.setContentsMargins(10, 8, 10, 8)
        daily_layout.setSpacing(4)
        daily_title = QLabel("TODAY (ACCOUNT)")
        daily_title.setObjectName(SUBTITLE_LABEL_ID)
        daily_layout.addWidget(daily_title)
        self._daily_videos = _SummaryLine("Track exports today", "--")
        self._daily_merges = _SummaryLine("Merges today", "--")
        daily_layout.addWidget(self._daily_videos)
        daily_layout.addWidget(self._daily_merges)
        root.addWidget(daily)

        summary = QFrame()
        summary.setObjectName("dashboard_quota_summary")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(4)
        self._wallet = _SummaryLine("Credits balance", "--")
        self._draft_quota = _SummaryLine("Drafts", "--")
        self._song_quota = _SummaryLine("Suno packages", "--")
        self._image_quota = _SummaryLine("Images", "--")
        self._video_quota = _SummaryLine("Track exports", "--")
        self._merge_quota = _SummaryLine("Merges", "--")
        summary_layout.addWidget(self._wallet)
        summary_layout.addWidget(self._draft_quota)
        summary_layout.addWidget(self._song_quota)
        summary_layout.addWidget(self._image_quota)
        summary_layout.addWidget(self._video_quota)
        summary_layout.addWidget(self._merge_quota)
        root.addWidget(summary)

    def apply_overview(self, data: DashboardOverview) -> None:
        stats = data.stats
        license_info = data.license
        quota = data.quota

        credits_total = max(stats.credits_total, 1)
        self._credits.set_amounts(stats.credits_remaining, credits_total)

        draft_quota = (quota.drafts_quota if quota else None) or stats.drafts_quota
        drafts_value = (
            quota.drafts_remaining
            if quota and quota.drafts_remaining is not None
            else stats.drafts_remaining
            if stats.drafts_remaining is not None
            else 0
        )
        self._drafts.set_amounts(drafts_value, max(draft_quota or 0, 1))

        song_quota = (license_info.monthly_song_quota if license_info else None) or stats.songs_quota
        songs_value = (
            license_info.songs_remaining
            if license_info and license_info.songs_remaining is not None
            else stats.songs_remaining
            if stats.songs_remaining is not None
            else 0
        )
        self._songs.set_amounts(songs_value, max(song_quota or 0, 1))

        image_quota = (
            (license_info.monthly_image_quota if license_info else None)
            or (quota.images_quota if quota else None)
            or stats.images_quota
        )
        images_value = (
            license_info.images_remaining
            if license_info and license_info.images_remaining is not None
            else quota.images_remaining
            if quota and quota.images_remaining is not None
            else stats.images_remaining
            if stats.images_remaining is not None
            else 0
        )
        self._images.set_amounts(images_value, max(image_quota or 0, 1))

        video_quota = quota.videos_quota if quota else None
        videos_value = (
            quota.videos_remaining if quota and quota.videos_remaining is not None else 0
        )
        if video_quota is not None:
            self._videos.set_amounts(videos_value, max(video_quota, 1))
            self._videos.show()
        else:
            self._videos.set_amounts(0, 1)
            self._videos.show()

        merge_quota = quota.merges_quota if quota else None
        merges_value = (
            quota.merges_remaining if quota and quota.merges_remaining is not None else 0
        )
        if merge_quota is not None:
            self._merges.set_amounts(merges_value, max(merge_quota, 1))
            self._merges.show()
        else:
            self._merges.set_amounts(0, 1)
            self._merges.show()

        daily_videos_rem = quota.daily_videos_remaining if quota else None
        daily_videos_lim = quota.daily_videos_limit if quota else None
        daily_merges_rem = quota.daily_merges_remaining if quota else None
        daily_merges_lim = quota.daily_merges_limit if quota else None
        self._daily_videos.set_value(_xy(daily_videos_rem, daily_videos_lim))
        self._daily_merges.set_value(_xy(daily_merges_rem, daily_merges_lim))

        wallet = (
            license_info.wallet_balance
            if license_info and license_info.wallet_balance is not None
            else data.me.credit_balance
        )
        self._wallet.set_value(format_compact_number(wallet))
        self._draft_quota.set_value(_xy(drafts_value if draft_quota is not None else None, draft_quota))
        self._song_quota.set_value(_xy(songs_value if song_quota is not None else None, song_quota))
        self._image_quota.set_value(_xy(images_value if image_quota is not None else None, image_quota))
        self._video_quota.set_value(
            _xy(videos_value if video_quota is not None else None, video_quota)
        )
        self._merge_quota.set_value(
            _xy(merges_value if merge_quota is not None else None, merge_quota)
        )


class _SummaryLine(QFrame):
    def __init__(self, label: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(label)
        self._label.setObjectName(SUBTITLE_LABEL_ID)
        self._value = QLabel(value)
        layout.addWidget(self._label)
        layout.addStretch()
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)
