"""Daily channel limits table using Create table chrome."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont

from shared.lib.ui_font import studio_font
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.studio_panel import StudioPanel
from shared.lib.formatting import format_compact_number
from shared.lib.ui_font import studio_font
from shared.models.platform import ChannelDailyQuota, DashboardOverview, QuotaStatusResponse

HEADERS = (
    "Channel",
    "Drafts",
    "Songs",
    "Images",
    "Track Exports",
    "Merges",
    "Remaining This Month",
    "Status",
)


class ChannelLimitsModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[list[str]] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(HEADERS)

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        value = self._rows[index.row()][index.column()]
        if role in {Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole}:
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() == 0:
                return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if index.column() == 7:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def set_rows(self, rows: list[list[str]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


class _StatusDelegate(QStyledItemDelegate):
    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if index.column() != 7:
            super().paint(painter, option, index)
            return
        status = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        color = {
            "Within limits": "#00C878",
            "Near limit": "#F59E0B",
            "Over limit": "#F43F5E",
        }.get(status, "#8FA4BB")
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#6335D9"))
        else:
            painter.fillRect(option.rect, option.palette.base())
        painter.setFont(studio_font(10, QFont.Weight.DemiBold))
        text_width = painter.fontMetrics().horizontalAdvance(status) + 14
        x = option.rect.x() + 8
        y = option.rect.y() + max((option.rect.height() - 16) // 2, 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(x, y, text_width, 16, 3, 3)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(x, y, text_width, 16, int(Qt.AlignmentFlag.AlignCenter), status)
        painter.restore()


class DailyChannelQuotaCard(StudioPanel):
    SUBTITLE = (
        "Per-channel draft · song · image capacity today. "
        "Account track export / merge daily caps are on Remaining This Month."
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("DAILY CHANNEL LIMITS")
        title.setObjectName("SectionLabel")
        title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        titles.addWidget(title)
        subtitle = QLabel(self.SUBTITLE)
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        root.addLayout(header)

        self._empty = QLabel("No channel quota data available yet.")
        self._empty.setObjectName("PageSubtitle")
        self._empty.hide()
        root.addWidget(self._empty)

        self._model = ChannelLimitsModel(self)
        self._table = QTableView()
        self._table.setObjectName("ChannelTable")
        self._table.setModel(self._model)
        self._table.setItemDelegate(_StatusDelegate(self._table))
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            self._table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setMinimumHeight(120)
        root.addWidget(self._table)

    def apply_quota(self, quota: QuotaStatusResponse | None) -> None:
        channels = list(quota.channels) if quota is not None else []
        if not channels:
            self._empty.show()
            self._table.hide()
            self._model.set_rows([])
            return
        self._empty.hide()
        self._table.show()
        month = _month_remaining(quota)
        exports, merges = _daily_account_caps(quota)
        rows = [
            _combined_row(channels, month, exports, merges),
            *[_channel_row(channel, month, exports, merges) for channel in channels],
        ]
        self._model.set_rows(rows)

    def apply_overview(self, data: DashboardOverview) -> None:
        if data.quota is not None and data.quota.channels:
            self.apply_quota(data.quota)
            return
        license_info = data.license
        songs_limit = (license_info.daily_song_limit_per_channel if license_info is not None else None) or 0
        images_limit = (license_info.daily_image_limit_per_channel if license_info is not None else None) or 0
        drafts_limit = int(getattr(license_info, "daily_draft_limit_per_channel", 0) or 0) if license_info else 0
        profiles = list(data.profiles)
        if not profiles or (songs_limit <= 0 and images_limit <= 0 and drafts_limit <= 0):
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
                    daily_drafts_limit=drafts_limit,
                    daily_drafts_remaining=drafts_limit,
                )
                for profile in profiles
            ]
        )
        self.apply_quota(fallback)


def _ratio(used: int, limit: int) -> str:
    if limit <= 0:
        return "—"
    return f"{format_compact_number(max(used, 0))} / {format_compact_number(limit)}"


def _status(channels: list[ChannelDailyQuota]) -> str:
    worst = "Within limits"
    for channel in channels:
        for used, limit in (
            (channel.daily_drafts_used, channel.daily_drafts_limit),
            (channel.daily_songs_used, channel.daily_songs_limit),
            (channel.daily_images_used, channel.daily_images_limit),
        ):
            if limit <= 0:
                continue
            remaining = max(limit - used, 0)
            if remaining <= 0:
                return "Over limit"
            if remaining / limit <= 0.2:
                worst = "Near limit"
    return worst


def _month_remaining(quota: QuotaStatusResponse | None) -> str:
    if quota is None:
        return "Exports — · Merges —"
    videos = (
        "—"
        if not quota.videos_quota
        else f"{format_compact_number(quota.videos_remaining or 0)} / {format_compact_number(quota.videos_quota)}"
    )
    merges = (
        "—"
        if not quota.merges_quota
        else f"{format_compact_number(quota.merges_remaining or 0)} / {format_compact_number(quota.merges_quota)}"
    )
    return f"Exports {videos} · Merges {merges}"


def _account_ratio(used: int | None, limit: int | None) -> str:
    if not limit:
        return "—"
    return _ratio(max(int(used or 0), 0), int(limit))


def _daily_account_caps(quota: QuotaStatusResponse | None) -> tuple[str, str]:
    if quota is None:
        return "—", "—"
    exports_used = None
    if quota.daily_videos_limit:
        exports_used = max(int(quota.daily_videos_limit) - int(quota.daily_videos_remaining or 0), 0)
    merges_used = None
    if quota.daily_merges_limit:
        merges_used = max(int(quota.daily_merges_limit) - int(quota.daily_merges_remaining or 0), 0)
    return (
        _account_ratio(exports_used, quota.daily_videos_limit),
        _account_ratio(merges_used, quota.daily_merges_limit),
    )


def _channel_row(
    channel: ChannelDailyQuota,
    month: str,
    exports: str,
    merges: str,
) -> list[str]:
    return [
        channel.profile_name,
        _ratio(channel.daily_drafts_used, channel.daily_drafts_limit),
        _ratio(channel.daily_songs_used, channel.daily_songs_limit),
        _ratio(channel.daily_images_used, channel.daily_images_limit),
        exports,
        merges,
        month,
        _status([channel]),
    ]


def _combined_row(
    channels: list[ChannelDailyQuota],
    month: str,
    exports: str,
    merges: str,
) -> list[str]:
    drafts_used = sum(ch.daily_drafts_used for ch in channels)
    drafts_limit = sum(ch.daily_drafts_limit for ch in channels)
    songs_used = sum(ch.daily_songs_used for ch in channels)
    songs_limit = sum(ch.daily_songs_limit for ch in channels)
    images_used = sum(ch.daily_images_used for ch in channels)
    images_limit = sum(ch.daily_images_limit for ch in channels)
    return [
        "All Channels (Combined)",
        _ratio(drafts_used, drafts_limit),
        _ratio(songs_used, songs_limit),
        _ratio(images_used, images_limit),
        exports,
        merges,
        month,
        _status(channels),
    ]
