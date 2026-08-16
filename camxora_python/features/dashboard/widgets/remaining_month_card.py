"""Usage This Month card."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.dashboard.widgets.progress_summary_row import ProgressSummaryRow
from shared.lib.formatting import format_compact_number
from shared.models.platform import DashboardOverview
from shared.themes.deep_blue import SUBTITLE_LABEL_ID


def _first_int(*values: int | None) -> int | None:
    for value in values:
        if value is not None:
            return int(value)
    return None


def _used_of_quota(remaining: int | None, quota: int | None) -> tuple[int, int | None]:
    """Return (used, quota) so meters read consumed / allowance."""
    if quota is None:
        return 0, None
    rem = 0 if remaining is None else max(0, int(remaining))
    used = max(0, int(quota) - rem)
    return used, int(quota)


def _xy_used(used: int | None, quota: int | None) -> str:
    if used is None and quota is None:
        return "Not on plan"
    amount = format_compact_number(used if used is not None else 0)
    if quota is None:
        return f"{amount} used"
    return f"{amount} of {format_compact_number(quota)} used"


class RemainingMonthCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(6)

        title = QLabel("USAGE THIS MONTH")
        title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title)

        hint = QLabel("Used vs your plan allowance this billing period.")
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
        self._credits.set_amounts(int(stats.credits_spent), credits_total)

        draft_quota = _first_int(
            quota.drafts_quota if quota else None,
            stats.drafts_quota,
        )
        drafts_remaining = _first_int(
            quota.drafts_remaining if quota else None,
            stats.drafts_remaining,
        )
        drafts_used, draft_quota = _used_of_quota(drafts_remaining, draft_quota)
        self._drafts.set_amounts(drafts_used, max(draft_quota or 0, 1))

        # Prefer /quota-status (add-on scaled) over /licenses/validate (base plan).
        song_quota = _first_int(
            quota.songs_quota if quota else None,
            stats.songs_quota,
            license_info.monthly_song_quota if license_info else None,
        )
        songs_remaining = _first_int(
            quota.songs_remaining if quota else None,
            stats.songs_remaining,
            license_info.songs_remaining if license_info else None,
        )
        songs_used, song_quota = _used_of_quota(songs_remaining, song_quota)
        self._songs.set_amounts(songs_used, max(song_quota or 0, 1))

        image_quota = _first_int(
            quota.images_quota if quota else None,
            stats.images_quota,
            license_info.monthly_image_quota if license_info else None,
        )
        images_remaining = _first_int(
            quota.images_remaining if quota else None,
            stats.images_remaining,
            license_info.images_remaining if license_info else None,
        )
        images_used, image_quota = _used_of_quota(images_remaining, image_quota)
        self._images.set_amounts(images_used, max(image_quota or 0, 1))

        video_quota = quota.videos_quota if quota else None
        videos_remaining = (
            quota.videos_remaining if quota and quota.videos_remaining is not None else None
        )
        videos_used, video_quota = _used_of_quota(videos_remaining, video_quota)
        self._videos.set_amounts(videos_used, max(video_quota or 0, 1))
        self._videos.show()

        merge_quota = quota.merges_quota if quota else None
        merges_remaining = (
            quota.merges_remaining if quota and quota.merges_remaining is not None else None
        )
        merges_used, merge_quota = _used_of_quota(merges_remaining, merge_quota)
        self._merges.set_amounts(merges_used, max(merge_quota or 0, 1))
        self._merges.show()

        daily_videos_lim = quota.daily_videos_limit if quota else None
        daily_videos_rem = quota.daily_videos_remaining if quota else None
        daily_merges_lim = quota.daily_merges_limit if quota else None
        daily_merges_rem = quota.daily_merges_remaining if quota else None
        daily_videos_used, daily_videos_lim = _used_of_quota(daily_videos_rem, daily_videos_lim)
        daily_merges_used, daily_merges_lim = _used_of_quota(daily_merges_rem, daily_merges_lim)
        self._daily_videos.set_value(_xy_used(
            daily_videos_used if daily_videos_lim is not None else None,
            daily_videos_lim,
        ))
        self._daily_merges.set_value(_xy_used(
            daily_merges_used if daily_merges_lim is not None else None,
            daily_merges_lim,
        ))

        wallet = (
            license_info.wallet_balance
            if license_info and license_info.wallet_balance is not None
            else data.me.credit_balance
        )
        self._wallet.set_value(format_compact_number(wallet))
        self._draft_quota.set_value(_xy_used(
            drafts_used if draft_quota is not None else None, draft_quota
        ))
        self._song_quota.set_value(_xy_used(
            songs_used if song_quota is not None else None, song_quota
        ))
        self._image_quota.set_value(_xy_used(
            images_used if image_quota is not None else None, image_quota
        ))
        self._video_quota.set_value(_xy_used(
            videos_used if video_quota is not None else None, video_quota
        ))
        self._merge_quota.set_value(_xy_used(
            merges_used if merge_quota is not None else None, merge_quota
        ))


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
