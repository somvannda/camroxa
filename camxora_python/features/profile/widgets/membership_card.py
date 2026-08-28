"""Membership panel for the Profile workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.create.widgets.studio_panel import StudioPanel
from features.profile.profile_format import plan_subtitle
from features.profile.widgets.info_field import InfoField
from features.profile.widgets.membership_metric_bar import MembershipMetricBar
from shared.lib.formatting import format_compact_number, format_friendly_expiry, percent_of
from shared.lib.ui_font import studio_font
from shared.models.platform import DashboardOverview


class _ValueProxy:
    def __init__(self, label: QLabel) -> None:
        self._value = label


class MembershipCard(StudioPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("MEMBERSHIP")
        title.setObjectName("SectionLabel")
        title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        header.addWidget(title)
        header.addStretch()
        self._status = QLabel("Active")
        self._status.setObjectName("StatusBadge")
        self._status.setFont(studio_font(10))
        header.addWidget(self._status)
        layout.addLayout(header)

        self._plan_name = QLabel("--")
        self._plan_name.setObjectName("PlanName")
        self._plan_name.setFont(studio_font(14))
        layout.addWidget(self._plan_name)
        self._plan_subtitle = QLabel("Monthly plan")
        self._plan_subtitle.setObjectName("PlanSubtitle")
        self._plan_subtitle.setFont(studio_font(12))
        layout.addWidget(self._plan_subtitle)

        self._plan = _ValueProxy(self._plan_name)

        self._profiles_bar = MembershipMetricBar("Monthly profiles")
        layout.addWidget(self._profiles_bar)

        resources = QGridLayout()
        resources.setHorizontalSpacing(12)
        resources.setVerticalSpacing(8)
        self._credits = InfoField("Credits balance", "--", icon_name="coins")
        self._expiry = InfoField("Plan expiry", "--", icon_name="calendar")
        resources.addWidget(self._credits, 0, 0)
        resources.addWidget(self._expiry, 0, 1)
        layout.addLayout(resources)

        addons = QGridLayout()
        addons.setHorizontalSpacing(12)
        addons.setVerticalSpacing(8)
        self._addon_active = InfoField("Active add-on channels", "--", icon_name="youtube")
        self._addon_pending = InfoField("Pending add-on channels", "--", icon_name="bell")
        addons.addWidget(self._addon_active, 0, 0)
        addons.addWidget(self._addon_pending, 0, 1)
        layout.addLayout(addons)

    def show_loading(self) -> None:
        self._profiles_bar.set_metric("--", 0)
        self._plan_name.setText("--")
        self._plan_subtitle.setText("Monthly plan")
        self._credits.set_value("--")
        self._expiry.set_value("--")
        self._addon_active.set_value("--")
        self._addon_pending.set_value("--")
        self._status.setText("Active")

    def apply(self, data: DashboardOverview) -> None:
        me = data.me
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

        wallet = (
            license_info.wallet_balance
            if license_info and license_info.wallet_balance is not None
            else me.credit_balance
        )
        plan_name = me.plan_name or "No active plan"
        self._plan_name.setText(plan_name)
        self._plan_subtitle.setText(plan_subtitle(me.plan_name))
        self._credits.set_value(format_compact_number(wallet))
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
        self._addon_active.set_value(f"+{addon_slots} channels" if addon_slots else "None")
        self._addon_pending.set_value(
            f"+{addon_pending} awaiting onboarding" if addon_pending else "None"
        )
        self._status.setText("Active")
