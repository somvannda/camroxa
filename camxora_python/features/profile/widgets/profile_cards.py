"""Profile page section cards."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from features.profile.widgets.membership_metric_bar import MembershipMetricBar
from shared.lib.formatting import format_compact_number, format_friendly_expiry, format_optional, percent_of
from shared.models.auth import ProfileResponse
from shared.models.platform import DashboardOverview, profile_image_mode, profile_visibility
from shared.services.local_user_scope import get_user_workspace_dir
from shared.themes.badge_pills import BADGE_MUTED, BADGE_SUCCESS, apply_badge_pill
from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID
from shared.widgets.data_table import create_data_table
from shared.widgets.metric_bar import SummaryField

PROFILES_SUBTITLE = "Profiles available for generation and publication workflows."
LOADING_PROFILES = "Loading profiles..."
EMPTY_PROFILES = "No channel profiles found yet."

# Account info tiles — modest padding so values aren't flush to edges.
_ACCOUNT_TILE_MARGINS = (12, 8, 12, 8)
_ACCOUNT_TILE_SPACING = 3
# Membership tiles/meters — tighter than Account.
_MEMBERSHIP_TILE_MARGINS = (8, 4, 8, 4)
_MEMBERSHIP_TILE_SPACING = 1


def _short_list(values: list[str], *, empty: str = "None yet", limit: int = 3) -> str:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        return empty
    if len(cleaned) <= limit:
        return ", ".join(cleaned)
    return ", ".join(cleaned[:limit]) + f" (+{len(cleaned) - limit})"


def _profile_names_summary(profiles: list[ProfileResponse]) -> str:
    return _short_list([profile.name for profile in profiles])


def _profile_folders_summary(profiles: list[ProfileResponse]) -> str:
    folders: list[str] = []
    for profile in profiles:
        folder = (profile.folder_name or profile.run_prefix or "").strip()
        if folder and folder not in folders:
            folders.append(folder)
    return _short_list(folders, empty="Not set")


def _local_data_hint(user_id: str) -> str:
    path = get_user_workspace_dir(user_id)
    parts = Path(path).parts
    if "Camxora" in parts:
        index = parts.index("Camxora")
        return "/".join(parts[index:])
    return str(path)


class AccountCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        left = QVBoxLayout()
        title = QLabel("ACCOUNT")
        title.setObjectName(SUBTITLE_LABEL_ID)
        left.addWidget(title)
        self._display_name = QLabel("Loading account...")
        self._display_name.setObjectName(TITLE_LABEL_ID)
        left.addWidget(self._display_name)
        self._email = QLabel("Loading account email...")
        self._email.setObjectName(SUBTITLE_LABEL_ID)
        left.addWidget(self._email)
        header.addLayout(left, stretch=1)

        badge = QFrame()
        badge.setObjectName("dashboard_plan_badge")
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(10, 8, 10, 8)
        badge_layout.setSpacing(4)
        badge_label = QLabel("VERIFICATION")
        badge_label.setObjectName(SUBTITLE_LABEL_ID)
        badge_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        badge_layout.addWidget(badge_label)
        self._verification = QLabel()
        apply_badge_pill(self._verification, BADGE_MUTED, label="Pending")
        badge_layout.addWidget(self._verification, alignment=Qt.AlignmentFlag.AlignRight)
        header.addWidget(badge)
        layout.addLayout(header)

        fields = QGridLayout()
        fields.setHorizontalSpacing(8)
        fields.setVerticalSpacing(8)
        self._user_id = SummaryField("User ID", "--")
        self._session = SummaryField("Session", "Active")
        self._email_status = SummaryField("Email status", "--")
        self._linked_profiles = SummaryField("Linked profiles", "--")
        self._folders = SummaryField("Profile folders", "--")
        self._local_data = SummaryField("Local data", "--")
        for field in (
            self._user_id,
            self._session,
            self._email_status,
            self._linked_profiles,
            self._folders,
            self._local_data,
        ):
            field_layout = field.layout()
            if field_layout is not None:
                field_layout.setContentsMargins(*_ACCOUNT_TILE_MARGINS)
                field_layout.setSpacing(_ACCOUNT_TILE_SPACING)
        fields.addWidget(self._user_id, 0, 0)
        fields.addWidget(self._session, 0, 1)
        fields.addWidget(self._email_status, 1, 0)
        fields.addWidget(self._linked_profiles, 1, 1)
        fields.addWidget(self._folders, 2, 0)
        fields.addWidget(self._local_data, 2, 1)
        layout.addLayout(fields)

    def show_loading(self) -> None:
        self._display_name.setText("Loading account...")
        self._email.setText("Loading account email...")
        self._user_id.set_value("--")
        self._session.set_value("Active")
        self._email_status.set_value("--")
        self._linked_profiles.set_value("--")
        self._folders.set_value("--")
        self._local_data.set_value("--")
        apply_badge_pill(self._verification, BADGE_MUTED, label="Pending")

    def show_error(self) -> None:
        self._display_name.setText("Loading account...")
        self._email.setText("Unable to load account information.")
        self._session.set_value("Needs attention")

    def apply(self, data: DashboardOverview, *, is_error: bool = False) -> None:
        me = data.me
        profiles = data.profiles
        self._display_name.setText(me.display_name.strip() or me.email)
        self._email.setText(me.email if not is_error else "Unable to load account information.")
        self._user_id.set_value(me.id)
        self._session.set_value("Needs attention" if is_error else "Active")
        if me.email_confirmed:
            apply_badge_pill(self._verification, BADGE_SUCCESS, label="Verified")
            self._email_status.set_value("Confirmed")
        else:
            apply_badge_pill(self._verification, BADGE_MUTED, label="Pending")
            self._email_status.set_value("Awaiting confirmation")
        self._linked_profiles.set_value(_profile_names_summary(profiles))
        self._folders.set_value(_profile_folders_summary(profiles))
        self._local_data.set_value(_local_data_hint(me.id))


class MembershipCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("MEMBERSHIP")
        title.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(title)

        meters = QVBoxLayout()
        meters.setContentsMargins(0, 0, 0, 0)
        meters.setSpacing(4)
        self._profiles_bar = MembershipMetricBar("Monthly profiles", bar_color="emerald")
        self._songs_bar = MembershipMetricBar("Monthly songs", bar_color="sky")
        meters.addWidget(self._profiles_bar)
        meters.addWidget(self._songs_bar)
        layout.addLayout(meters)

        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        self._plan = SummaryField("Plan", "--")
        self._credits = SummaryField("Credits balance", "--")
        self._song_quota = SummaryField("Song quota", "--")
        self._expiry = SummaryField("Plan expiry", "--")
        self._addon_active = SummaryField("Active add-on channels", "--")
        self._addon_pending = SummaryField("Pending add-on channels", "--")
        for field in (
            self._plan,
            self._credits,
            self._song_quota,
            self._expiry,
            self._addon_active,
            self._addon_pending,
        ):
            field_layout = field.layout()
            if field_layout is not None:
                field_layout.setContentsMargins(*_MEMBERSHIP_TILE_MARGINS)
                field_layout.setSpacing(_MEMBERSHIP_TILE_SPACING)
        grid.addWidget(self._plan, 0, 0)
        grid.addWidget(self._credits, 0, 1)
        grid.addWidget(self._song_quota, 1, 0)
        grid.addWidget(self._expiry, 1, 1)
        grid.addWidget(self._addon_active, 2, 0)
        grid.addWidget(self._addon_pending, 2, 1)
        layout.addLayout(grid)

    def show_loading(self) -> None:
        self._profiles_bar.set_metric("--", 0)
        self._songs_bar.set_metric("--", 0)
        self._plan.set_value("--")
        self._credits.set_value("--")
        self._song_quota.set_value("--")
        self._expiry.set_value("--")
        self._addon_active.set_value("--")
        self._addon_pending.set_value("--")

    def apply(self, data: DashboardOverview) -> None:
        me = data.me
        stats = data.stats
        license_info = data.license
        profiles = data.profiles

        allowance = (
            f"{me.channel_profile_count} / {me.effective_profile_allowance or me.profile_allowance}"
            if me.effective_profile_allowance is not None or me.profile_allowance is not None
            else str(len(profiles))
        )
        profile_allowance = max(
            me.effective_profile_allowance or me.profile_allowance or len(profiles) or 1,
            1,
        )
        profile_used = me.channel_profile_count or len(profiles)
        self._profiles_bar.set_metric(allowance, percent_of(profile_used, profile_allowance))

        quota = data.quota
        song_quota = None
        for candidate in (
            quota.songs_quota if quota is not None else None,
            stats.songs_quota,
            license_info.monthly_song_quota if license_info else None,
        ):
            if candidate is not None:
                song_quota = int(candidate)
                break
        songs_remaining = None
        for candidate in (
            quota.songs_remaining if quota is not None else None,
            stats.songs_remaining,
            license_info.songs_remaining if license_info else None,
        ):
            if candidate is not None:
                songs_remaining = int(candidate)
                break
        if song_quota is None:
            songs_used = 0
            songs_value = "Not on plan"
            songs_pct = 0
        else:
            rem = 0 if songs_remaining is None else max(0, songs_remaining)
            songs_used = max(0, song_quota - rem)
            songs_value = (
                f"{format_compact_number(songs_used)} / {format_compact_number(song_quota)}"
            )
            songs_pct = percent_of(songs_used, max(song_quota, 1))
        self._songs_bar.set_metric(songs_value, songs_pct)

        wallet = (
            license_info.wallet_balance
            if license_info and license_info.wallet_balance is not None
            else me.credit_balance
        )
        self._plan.set_value(me.plan_name or "No active plan")
        self._credits.set_value(format_compact_number(wallet))
        self._song_quota.set_value(
            format_compact_number(song_quota) if song_quota is not None else "Not provided"
        )
        expiry = license_info.expiration_date if license_info else None
        self._expiry.set_value(format_friendly_expiry(expiry))
        addon_slots = (
            license_info.profile_addon_slots
            if license_info is not None
            else me.profile_addon_slots
        )
        addon_pending = (
            license_info.profile_addon_pending
            if license_info is not None
            else me.profile_addon_pending
        )
        self._addon_active.set_value(
            f"+{addon_slots} channels" if addon_slots else "None"
        )
        self._addon_pending.set_value(
            f"+{addon_pending} awaiting onboarding" if addon_pending else "None"
        )


class ChannelProfilesCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        left = QVBoxLayout()
        title = QLabel("CHANNEL PROFILES")
        title.setObjectName(SUBTITLE_LABEL_ID)
        left.addWidget(title)
        subtitle = QLabel(PROFILES_SUBTITLE)
        subtitle.setObjectName(SUBTITLE_LABEL_ID)
        subtitle.setWordWrap(True)
        left.addWidget(subtitle)
        header.addLayout(left, stretch=1)
        self._allowance = QLabel("--")
        header.addWidget(self._allowance, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self._table = create_data_table(
            ["Name", "Run Prefix", "Output resolution", "Image mode", "Visibility"]
        )
        layout.addWidget(self._table)

    def show_loading(self, allowance: str = "--") -> None:
        self._allowance.setText(allowance)
        self._set_message(LOADING_PROFILES)

    def show_empty(self, allowance: str = "0") -> None:
        self._allowance.setText(allowance)
        self._set_message(EMPTY_PROFILES)

    def apply(self, data: DashboardOverview) -> None:
        me = data.me
        profiles = data.profiles
        allowance = (
            f"{me.channel_profile_count} / {me.effective_profile_allowance or me.profile_allowance}"
            if me.effective_profile_allowance is not None or me.profile_allowance is not None
            else str(len(profiles))
        )
        self._allowance.setText(allowance)
        if not profiles:
            self._set_message(EMPTY_PROFILES)
            return
        self._table.clearSpans()
        self._table.setRowCount(len(profiles))
        for row_index, profile in enumerate(profiles):
            values = [
                profile.name,
                format_optional(profile.run_prefix),
                profile.output_resolution or "--",
                profile_image_mode(profile),
                profile_visibility(profile),
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row_index, col_index, item)

    def _set_message(self, message: str) -> None:
        self._table.clearSpans()
        self._table.setRowCount(1)
        self._table.setSpan(0, 0, 1, 5)
        item = QTableWidgetItem(message)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(0, 0, item)


class ActivityCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("ACTIVITY")
        title.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(title)

        self._songs = SummaryField("Songs generated", "--")
        self._images = SummaryField("Images generated", "--")
        self._videos = SummaryField("Videos generated", "--")
        self._credits = SummaryField("Credits spent", "--")
        for field in (self._songs, self._images, self._videos, self._credits):
            layout.addWidget(field)
        layout.addStretch()

    def show_loading(self) -> None:
        for field in (self._songs, self._images, self._videos, self._credits):
            field.set_value("--")

    def apply(self, data: DashboardOverview) -> None:
        stats = data.stats
        self._songs.set_value(format_compact_number(stats.songs_generated))
        self._images.set_value(format_compact_number(stats.images_generated))
        self._videos.set_value(format_compact_number(stats.videos_generated))
        self._credits.set_value(format_compact_number(stats.credits_spent))
