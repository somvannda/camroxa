"""Remaining This Month card."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.dashboard.widgets.progress_summary_row import ProgressSummaryRow
from shared.lib.formatting import format_compact_number
from shared.models.platform import DashboardOverview
from shared.themes.deep_blue import SUBTITLE_LABEL_ID


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

        meters = QVBoxLayout()
        meters.setContentsMargins(0, 0, 0, 0)
        meters.setSpacing(4)
        self._credits = ProgressSummaryRow("Credits", bar_color="violet")
        self._drafts = ProgressSummaryRow("Drafts", bar_color="amber")
        self._songs = ProgressSummaryRow("Suno packages", bar_color="sky")
        self._images = ProgressSummaryRow("Images", bar_color="emerald")
        self._videos = ProgressSummaryRow("Videos", bar_color="sky")
        self._merges = ProgressSummaryRow("Merges", bar_color="violet")
        meters.addWidget(self._credits)
        meters.addWidget(self._drafts)
        meters.addWidget(self._songs)
        meters.addWidget(self._images)
        meters.addWidget(self._videos)
        meters.addWidget(self._merges)
        root.addLayout(meters)

        summary = QFrame()
        summary.setObjectName("dashboard_quota_summary")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(4)
        self._wallet = _SummaryLine("Credits balance", "--")
        self._draft_quota = _SummaryLine("Draft quota", "--")
        self._song_quota = _SummaryLine("Suno package quota", "--")
        self._image_quota = _SummaryLine("Image quota", "0")
        self._video_quota = _SummaryLine("Video quota", "--")
        self._merge_quota = _SummaryLine("Merge quota", "--")
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

        credits_total = max(stats.credits_total, 1)
        self._credits.set_amounts(stats.credits_remaining, credits_total)

        draft_total = max(
            (data.quota.drafts_quota if data.quota else None) or stats.drafts_quota or 0,
            1,
        )
        drafts_value = (
            data.quota.drafts_remaining
            if data.quota and data.quota.drafts_remaining is not None
            else stats.drafts_remaining
            if stats.drafts_remaining is not None
            else 0
        )
        self._drafts.set_amounts(drafts_value, draft_total)

        song_total = max(
            (license_info.monthly_song_quota if license_info else None) or stats.songs_quota or 0,
            1,
        )
        songs_value = (
            license_info.songs_remaining
            if license_info and license_info.songs_remaining is not None
            else stats.songs_remaining
            if stats.songs_remaining is not None
            else 0
        )
        self._songs.set_amounts(songs_value, song_total)

        image_total = max(
            (license_info.monthly_image_quota if license_info else None)
            or (data.quota.images_quota if data.quota else None)
            or stats.images_quota
            or 0,
            1,
        )
        images_value = (
            license_info.images_remaining
            if license_info and license_info.images_remaining is not None
            else data.quota.images_remaining
            if data.quota and data.quota.images_remaining is not None
            else stats.images_remaining
            if stats.images_remaining is not None
            else 0
        )
        self._images.set_amounts(images_value, image_total)

        video_total = max((data.quota.videos_quota if data.quota else None) or 0, 1)
        videos_value = (
            data.quota.videos_remaining
            if data.quota and data.quota.videos_remaining is not None
            else 0
        )
        if data.quota and data.quota.videos_quota is not None:
            self._videos.set_amounts(videos_value, video_total)
            self._videos.show()
        else:
            self._videos.hide()

        merge_total = max((data.quota.merges_quota if data.quota else None) or 0, 1)
        merges_value = (
            data.quota.merges_remaining
            if data.quota and data.quota.merges_remaining is not None
            else 0
        )
        if data.quota and data.quota.merges_quota is not None:
            self._merges.set_amounts(merges_value, merge_total)
            self._merges.show()
        else:
            self._merges.hide()

        wallet = (
            license_info.wallet_balance
            if license_info and license_info.wallet_balance is not None
            else data.me.credit_balance
        )
        self._wallet.set_value(format_compact_number(wallet))
        self._draft_quota.set_value(
            format_compact_number(draft_total)
            if ((data.quota and data.quota.drafts_quota is not None) or stats.drafts_quota is not None)
            else "Not provided"
        )
        self._song_quota.set_value(
            format_compact_number(license_info.monthly_song_quota)
            if license_info and license_info.monthly_song_quota is not None
            else "Not provided"
        )
        image_quota = (
            stats.images_quota
            if stats.images_quota is not None
            else data.quota.images_quota
            if data.quota and data.quota.images_quota is not None
            else license_info.monthly_image_quota
            if license_info and license_info.monthly_image_quota is not None
            else None
        )
        self._image_quota.set_value(
            format_compact_number(image_quota)
            if image_quota is not None
            else "Not provided"
        )
        video_quota = data.quota.videos_quota if data.quota else None
        self._video_quota.set_value(
            format_compact_number(video_quota) if video_quota is not None else "Not provided"
        )
        merge_quota = data.quota.merges_quota if data.quota else None
        self._merge_quota.set_value(
            format_compact_number(merge_quota) if merge_quota is not None else "Not provided"
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
