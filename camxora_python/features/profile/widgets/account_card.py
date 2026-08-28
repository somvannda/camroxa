"""Account panel for the Profile workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.create.create_styles import STUDIO_SUCCESS, STUDIO_TEXT_DIM
from features.create.widgets.studio_panel import StudioPanel
from features.profile.profile_format import local_data_hint, profile_folders_summary, profile_names_summary
from features.profile.widgets.icons import initials_from_name, paint_initials_avatar
from features.profile.widgets.info_field import InfoField
from shared.lib.ui_font import studio_font
from shared.models.platform import DashboardOverview


class AccountCard(StudioPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        title = QLabel("ACCOUNT")
        title.setObjectName("SectionLabel")
        title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        layout.addWidget(title)

        identity = QHBoxLayout()
        identity.setSpacing(12)
        self._avatar = QLabel()
        self._avatar.setFixedSize(40, 40)
        self._set_avatar("?")
        identity.addWidget(self._avatar, alignment=Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(2)
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        self._display_name = QLabel("Loading account...")
        self._display_name.setObjectName("DisplayName")
        self._display_name.setFont(studio_font(13, QFont.Weight.DemiBold))
        name_row.addWidget(self._display_name, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._verification = QLabel("Pending")
        self._verification.setObjectName("StatusBadge")
        self._verification.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._verification.setFont(studio_font(10, QFont.Weight.DemiBold))
        name_row.addWidget(self._verification, alignment=Qt.AlignmentFlag.AlignVCenter)
        name_row.addStretch(1)
        copy.addLayout(name_row)

        self._email = QLabel("Loading account email...")
        self._email.setObjectName("AccountEmail")
        self._email.setFont(studio_font(12))
        copy.addWidget(self._email)

        self._plan_line = QLabel("")
        self._plan_line.setObjectName("AccountPlan")
        self._plan_line.setTextFormat(Qt.TextFormat.RichText)
        self._plan_line.setFont(studio_font(12))
        copy.addWidget(self._plan_line)
        identity.addLayout(copy, 1)
        layout.addLayout(identity)

        grid = QFrame()
        grid.setObjectName("InfoGrid")
        grid.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fields = QGridLayout(grid)
        fields.setContentsMargins(1, 1, 1, 1)
        fields.setSpacing(1)
        self._user_id = InfoField("User ID", "--", icon_name="user-round")
        self._session = InfoField("Session", "Active", icon_name="activity")
        self._email_status = InfoField("Email status", "--", icon_name="mail")
        self._linked_profiles = InfoField("Linked profiles", "--", icon_name="user-round")
        self._folders = InfoField("Profile folders", "--", icon_name="folder-open")
        self._local_data = InfoField("Local data", "--", icon_name="hard-drive")
        fields.addWidget(self._user_id, 0, 0)
        fields.addWidget(self._session, 0, 1)
        fields.addWidget(self._email_status, 1, 0)
        fields.addWidget(self._linked_profiles, 1, 1)
        fields.addWidget(self._folders, 2, 0)
        fields.addWidget(self._local_data, 2, 1)
        layout.addWidget(grid)

    def _set_avatar(self, initials: str) -> None:
        self._avatar.setPixmap(paint_initials_avatar(40, initials))

    def _set_verified(self, verified: bool) -> None:
        self._verification.setText("Verified" if verified else "Pending")
        self._verification.setVisible(True)

    def _set_plan_line(self, plan: str, *, active: bool) -> None:
        if not plan:
            self._plan_line.clear()
            return
        status = (
            f'<span style="color:{STUDIO_SUCCESS}">Active</span>'
            if active
            else f'<span style="color:{STUDIO_TEXT_DIM}">Inactive</span>'
        )
        self._plan_line.setText(f"{plan} · {status}")

    def show_loading(self) -> None:
        self._set_avatar("?")
        self._display_name.setText("Loading account...")
        self._email.setText("Loading account email...")
        self._plan_line.clear()
        self._user_id.set_value("--")
        self._session.set_value("Active")
        self._email_status.set_value("--")
        self._linked_profiles.set_value("--")
        self._folders.set_value("--")
        self._local_data.set_value("--")
        self._set_verified(False)

    def show_error(self) -> None:
        self._display_name.setText("Loading account...")
        self._email.setText("Unable to load account information.")
        self._session.set_value("Needs attention")
        self._set_verified(False)

    def apply(self, data: DashboardOverview, *, is_error: bool = False) -> None:
        me = data.me
        profiles = data.profiles
        name = me.display_name.strip() or me.email
        self._display_name.setText(name)
        self._set_avatar(initials_from_name(name))
        self._email.setText(me.email if not is_error else "Unable to load account information.")
        self._user_id.set_value(me.id)
        self._session.set_value("Needs attention" if is_error else "Active")
        if me.email_confirmed:
            self._set_verified(True)
            self._email_status.set_value("Confirmed", success=True)
        else:
            self._set_verified(False)
            self._email_status.set_value("Awaiting confirmation")
        self._linked_profiles.set_value(profile_names_summary(profiles))
        self._folders.set_value(profile_folders_summary(profiles))
        self._local_data.set_value(local_data_hint(me.id))
        self._set_plan_line(me.plan_name or "No active plan", active=not is_error)
