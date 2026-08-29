"""Usage this month — credits plus plan meters from dashboard quota."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.create.widgets.studio_panel import StudioPanel
from features.dashboard.widgets.progress_summary_row import ProgressSummaryRow
from shared.lib.formatting import format_compact_number
from shared.lib.ui_font import studio_font
from shared.models.platform import DashboardOverview, QuotaStatusResponse

_NESTED_BG = "#0A1628"
_NESTED_BORDER = "#18304A"


class NestedPanel(QFrame):
    """Compact inset panel that still paints when ancestor QSS cannot reach it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NestedPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(_NESTED_BORDER), 1))
        painter.setBrush(QColor(_NESTED_BG))
        painter.drawRoundedRect(rect, 6, 6)
        painter.end()


class RemainingMonthCard(StudioPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        title = QLabel("USAGE THIS MONTH")
        title.setObjectName("SectionLabel")
        title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        root.addWidget(title)
        hint = QLabel("Used vs your plan allowance this billing period.")
        hint.setObjectName("PageSubtitle")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._credits = ProgressSummaryRow("Credits", bar_color="violet")
        self._drafts = ProgressSummaryRow("Drafts", bar_color="sky")
        self._songs = ProgressSummaryRow("Song packages", bar_color="emerald")
        self._images = ProgressSummaryRow("Images", bar_color="sky")
        self._exports = ProgressSummaryRow("Track exports", bar_color="amber")
        self._merges = ProgressSummaryRow("Merges", bar_color="rose")
        for row in (
            self._credits,
            self._drafts,
            self._songs,
            self._images,
            self._exports,
            self._merges,
        ):
            root.addWidget(row)

        today = NestedPanel()
        today_layout = QVBoxLayout(today)
        today_layout.setContentsMargins(10, 8, 10, 8)
        today_layout.setSpacing(4)
        today_title = QLabel("TODAY (ACCOUNT)")
        today_title.setObjectName("FieldLabel")
        today_layout.addWidget(today_title)
        self._today_exports = _SummaryLine("Track exports today", "Not on plan")
        self._today_merges = _SummaryLine("Merges today", "Not on plan")
        today_layout.addWidget(self._today_exports)
        today_layout.addWidget(self._today_merges)
        root.addWidget(today)

        summary = NestedPanel()
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(4)
        self._wallet = _SummaryLine("Credits balance", "--")
        self._spent = _SummaryLine("Spent this month", "--")
        self._drafts_line = _SummaryLine("Drafts", "--")
        self._songs_line = _SummaryLine("Song packages", "--")
        self._images_line = _SummaryLine("Images", "--")
        self._exports_line = _SummaryLine("Track exports", "Not on plan")
        self._merges_line = _SummaryLine("Merges", "Not on plan")
        for line in (
            self._wallet,
            self._spent,
            self._drafts_line,
            self._songs_line,
            self._images_line,
            self._exports_line,
            self._merges_line,
        ):
            summary_layout.addWidget(line)
        root.addWidget(summary)
        root.addStretch()

    def apply_overview(self, data: DashboardOverview) -> None:
        stats = data.stats
        quota = data.quota
        license_info = data.license
        wallet = (
            license_info.wallet_balance
            if license_info and license_info.wallet_balance is not None
            else data.me.credit_balance
        )
        self._wallet.set_value(format_compact_number(wallet))
        self._spent.set_value(format_compact_number(stats.credits_spent))

        credit_total = stats.credits_total or (stats.credits_spent + stats.credits_remaining)
        self._credits.set_amounts(int(stats.credits_spent), int(credit_total))

        drafts_used, drafts_total = _used_total(
            stats.drafts_quota,
            stats.drafts_remaining,
            quota.drafts_quota if quota else None,
            quota.drafts_remaining if quota else None,
        )
        songs_used, songs_total = _used_total(
            stats.songs_quota,
            stats.songs_remaining,
            quota.songs_quota if quota else None,
            quota.songs_remaining if quota else None,
            fallback_total=license_info.monthly_song_quota if license_info else None,
            fallback_remaining=license_info.songs_remaining if license_info else None,
        )
        images_used, images_total = _used_total(
            stats.images_quota,
            stats.images_remaining,
            quota.images_quota if quota else None,
            quota.images_remaining if quota else None,
            fallback_total=license_info.monthly_image_quota if license_info else None,
            fallback_remaining=license_info.images_remaining if license_info else None,
        )
        exports_used, exports_total = _used_total(
            None,
            None,
            quota.videos_quota if quota else None,
            quota.videos_remaining if quota else None,
        )
        merges_used, merges_total = _used_total(
            None,
            None,
            quota.merges_quota if quota else None,
            quota.merges_remaining if quota else None,
        )

        channels = list(quota.channels) if quota is not None else []
        self._apply_meter(
            self._drafts,
            self._drafts_line,
            drafts_used,
            drafts_total,
            daily=any(channel.daily_drafts_limit for channel in channels),
        )
        self._apply_meter(
            self._songs,
            self._songs_line,
            songs_used,
            songs_total,
            daily=any(channel.daily_songs_limit for channel in channels),
        )
        self._apply_meter(
            self._images,
            self._images_line,
            images_used,
            images_total,
            daily=any(channel.daily_images_limit for channel in channels),
        )
        self._apply_meter(
            self._exports,
            self._exports_line,
            exports_used,
            exports_total,
            daily=bool(quota and quota.daily_videos_limit),
        )
        self._apply_meter(
            self._merges,
            self._merges_line,
            merges_used,
            merges_total,
            daily=bool(quota and quota.daily_merges_limit),
        )

        self._today_exports.set_value(_today_label(quota, "videos"))
        self._today_merges.set_value(_today_label(quota, "merges"))

    def _apply_meter(
        self,
        row: ProgressSummaryRow,
        line: _SummaryLine,
        used: int | None,
        total: int | None,
        *,
        daily: bool = False,
    ) -> None:
        if total is not None and total > 0:
            row.show()
            line.show()
            row.set_amounts(used or 0, total)
            line.set_value(f"{format_compact_number(used or 0)} of {format_compact_number(total)} used")
            return
        if daily:
            row.show()
            line.show()
            row.set_unmetered("Daily cap only")
            line.set_value("Daily cap only")
            return
        row.hide()
        line.hide()


class _SummaryLine(QFrame):
    def __init__(self, label: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(label)
        self._label.setObjectName("FieldLabel")
        self._value = QLabel(value)
        self._value.setObjectName("PageSubtitle")
        layout.addWidget(self._label)
        layout.addStretch()
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


def _used_total(
    *pairs: int | None,
    fallback_total: int | None = None,
    fallback_remaining: int | None = None,
) -> tuple[int | None, int | None]:
    quota = None
    remaining = None
    values = list(pairs)
    if fallback_total is not None or fallback_remaining is not None:
        values.extend([fallback_total, fallback_remaining])
    for index in range(0, len(values), 2):
        total = values[index]
        left = values[index + 1] if index + 1 < len(values) else None
        if total is not None and int(total) > 0:
            quota = int(total)
            remaining = int(left) if left is not None else None
            break
    if quota is None:
        return None, None
    used = quota - remaining if remaining is not None else 0
    return max(used, 0), quota


def _today_label(quota: QuotaStatusResponse | None, kind: str) -> str:
    if quota is None:
        return "Not on plan"
    if kind == "videos":
        limit = quota.daily_videos_limit
        remaining = quota.daily_videos_remaining
    else:
        limit = quota.daily_merges_limit
        remaining = quota.daily_merges_remaining
    if not limit:
        return "Not on plan"
    used = max(int(limit) - int(remaining or 0), 0)
    return f"{format_compact_number(used)} / {format_compact_number(limit)}"
