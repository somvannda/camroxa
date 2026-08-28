"""Login and register views."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)

from features.account.auth_styles import AUTH_PAGE_QSS
from features.account.widgets.login_fields import BrandMark, GradientWelcomeLabel, IconLineEdit
from features.account.widgets.login_waveform import LoginWaveform
from features.account.widgets.recent_account_card import RecentAccountCard
from shared.constants.auth import REGISTRATION_ENABLED
from shared.icons.lucide_icons import lucide_pixmap
from shared.services.account_token_store import list_saved_accounts, remove_saved_account
from shared.services.build_config import (
    build_environment,
    footer_environment_badge,
    footer_version_badge,
    get_portal_base_url,
)
from shared.lib.ui_font import studio_font
from shared.services.secure_storage import SecureStorage
from shared.widgets.shell_footer_bar import ShellFooterBar

REMEMBER_EMAIL_KEY = "camxora.auth.rememberEmail"


class AuthView(QFrame):
    """Login / register forms matching the CAMXORA studio login card."""

    login_requested = Signal(str, str)
    register_requested = Signal(str, str, str)
    switch_account_requested = Signal(str)

    def __init__(self, storage: SecureStorage | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName("auth_page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(AUTH_PAGE_QSS)
        self.setFont(studio_font(14))
        self._storage = storage or SecureStorage()

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_login_form())
        if REGISTRATION_ENABLED:
            self._stack.addWidget(self._build_register_form())

        self._error_label = QLabel()
        self._error_label.setObjectName("auth_error")
        self._error_label.setWordWrap(True)
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._error_label.hide()

        self._loading_label = QLabel()
        self._loading_label.setObjectName("auth_loading")
        self._loading_label.setWordWrap(True)
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._loading_label.hide()

        self._footer_bar = ShellFooterBar()
        self._footer_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        version_label, version_tooltip = footer_version_badge()
        self._footer_bar.set_version_badge(version_label, tooltip=version_tooltip)
        self._refresh_login_footer_badges()

        card = QFrame()
        card.setObjectName("auth_login_card")
        card.setFixedWidth(570)
        glow = QGraphicsDropShadowEffect(card)
        glow.setBlurRadius(36)
        glow.setOffset(0, 0)
        glow.setColor(QColor(109, 61, 245, 70))
        card.setGraphicsEffect(glow)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 28, 40, 28)
        card_layout.setSpacing(12)
        card_layout.addWidget(self._stack)
        card_layout.addWidget(self._loading_label)
        card_layout.addWidget(self._error_label)

        self._stage = QWidget()
        self._stage.setObjectName("auth_stage")
        self._waveform = LoginWaveform(self._stage)
        stage_layout = QVBoxLayout(self._stage)
        stage_layout.setContentsMargins(24, 16, 24, 16)
        stage_layout.addStretch(1)
        stage_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
        stage_layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._stage, stretch=1)
        outer.addWidget(self._footer_bar, stretch=0)

        self._refresh_saved_accounts()
        self._apply_remembered_email()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._waveform.setGeometry(self._stage.rect())
        self._waveform.lower()

    def get_api_base_url(self) -> str:
        return self._storage.get_api_base_url()

    def show_login_form(self) -> None:
        self._stack.setCurrentIndex(0)
        self.clear_error()
        self._refresh_login_footer_badges()
        self._refresh_saved_accounts()
        self._apply_remembered_email()

    def _refresh_saved_accounts(self) -> None:
        accounts = list_saved_accounts(self._storage)
        self._saved_accounts_host.setVisible(bool(accounts))
        while self._saved_accounts_layout.count():
            item = self._saved_accounts_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, account in enumerate(accounts):
            row = RecentAccountCard(account, index)
            row.selected.connect(self._on_recent_selected)
            row.removed.connect(self._remove_saved_account)
            self._saved_accounts_layout.addWidget(row)

    def _on_recent_selected(self, user_id: str, email: str) -> None:
        if email:
            self._login_email.setText(email)
        self._request_switch_account(user_id)

    def _remove_saved_account(self, user_id: str) -> None:
        remove_saved_account(self._storage, user_id)
        self._refresh_saved_accounts()

    def show_register_form(self) -> None:
        if not REGISTRATION_ENABLED:
            return
        self._stack.setCurrentIndex(1)
        self.clear_error()

    def _refresh_login_footer_badges(self) -> None:
        env = build_environment()
        if env == "production":
            self._footer_bar.set_environment_badge(None)
            return

        env_label, env_tooltip = footer_environment_badge()
        api_base_url = self._storage.get_api_base_url()

        if not env_label:
            api_lower = (api_base_url or "").lower()
            if env == "sandbox":
                env_label = "Sandbox API"
            elif "localhost" in api_lower or "127.0.0.1" in api_lower:
                env_label = "Local API"
            else:
                env_label = "Dev API"
            env_tooltip = api_base_url

        host = urlparse(env_tooltip).netloc if env_tooltip else ""
        tip_host = host or env_tooltip or api_base_url or env_label
        tooltip_text = f"{env_label} -> {tip_host}"

        self._footer_bar.set_environment_badge(env_label, tooltip=tooltip_text)

    def set_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()

    def show_upgrade_plans_dialog(
        self,
        message: str,
        *,
        api: object | None = None,
    ) -> None:
        """Popup plan list on the login screen after an unpaid account is blocked."""
        from features.account.views.upgrade_plans_dialog import UpgradePlansDialog
        from shared.services.platform_api import PlatformApi

        self.set_error(message)
        api_client: PlatformApi
        if isinstance(api, PlatformApi):
            api_client = api
        else:
            api_client = PlatformApi()
        dialog = UpgradePlansDialog(
            message=message,
            api=api_client,
            parent=self.window(),
        )
        dialog.exec()

    def clear_error(self) -> None:
        self._error_label.clear()
        self._error_label.hide()

    def set_loading_status(self, label: str, detail: str = "") -> None:
        text = label.strip()
        if detail.strip():
            text = f"{text} — {detail.strip()}"
        self._loading_label.setText(text)
        self._loading_label.show()

    def clear_loading_status(self) -> None:
        self._loading_label.clear()
        self._loading_label.hide()

    def set_busy(self, busy: bool) -> None:
        self._login_btn.setEnabled(not busy)
        self._login_btn.setText("Signing in…" if busy else "Sign In")
        if hasattr(self, "_create_btn"):
            self._create_btn.setEnabled(not busy)
        self._saved_accounts_host.setEnabled(not busy)
        if not busy:
            self.clear_loading_status()

    def _build_login_form(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(BrandMark(48), alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        brand = QLabel("CAMXORA")
        brand.setObjectName("auth_brand_title")
        brand.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        brand.setFont(studio_font(15, QFont.Weight.Bold, letter_spacing=118))
        layout.addWidget(brand)
        studio = QLabel("FACELESS DESKTOP STUDIO")
        studio.setObjectName("auth_brand_subtitle")
        studio.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        studio.setFont(studio_font(9, QFont.Weight.Medium, letter_spacing=120, uppercase=True))
        layout.addWidget(studio)
        layout.addSpacing(16)
        layout.addWidget(GradientWelcomeLabel("Welcome back"))
        layout.addSpacing(4)
        subtitle = QLabel("Sign in to continue to your studio")
        subtitle.setObjectName("auth_card_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        subtitle.setFont(studio_font(14))
        layout.addWidget(subtitle)
        layout.addSpacing(20)

        layout.addWidget(self._field_label("Email"))
        layout.addSpacing(6)
        self._login_email = IconLineEdit("mail", "Enter your email")
        layout.addWidget(self._login_email)
        layout.addSpacing(14)

        layout.addWidget(self._field_label("Password"))
        layout.addSpacing(6)
        self._login_password = IconLineEdit("lock", "Enter your password", password=True)
        self._login_password.returnPressed.connect(self._submit_login)
        layout.addWidget(self._login_password)
        layout.addSpacing(12)

        options = QHBoxLayout()
        options.setContentsMargins(0, 0, 0, 0)
        self._remember = QCheckBox("Remember me")
        self._remember.setObjectName("auth_remember")
        self._remember.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remember.setFont(studio_font(13))
        options.addWidget(self._remember)
        options.addStretch(1)
        forgot = QPushButton("Forgot password?")
        forgot.setObjectName("auth_forgot_button")
        forgot.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot.setFlat(True)
        forgot.setFont(studio_font(13, QFont.Weight.Medium))
        forgot.clicked.connect(self._open_forgot_password)
        options.addWidget(forgot)
        layout.addLayout(options)
        layout.addSpacing(18)

        self._saved_accounts_host = QWidget()
        saved_layout = QVBoxLayout(self._saved_accounts_host)
        saved_layout.setContentsMargins(0, 0, 0, 0)
        saved_layout.setSpacing(8)
        saved_label = QLabel("RECENT ACCOUNTS")
        saved_label.setObjectName("auth_section_label")
        saved_label.setFont(studio_font(10, QFont.Weight.DemiBold, letter_spacing=110, uppercase=True))
        saved_layout.addWidget(saved_label)
        self._saved_accounts_layout = QVBoxLayout()
        self._saved_accounts_layout.setSpacing(8)
        saved_layout.addLayout(self._saved_accounts_layout)
        self._saved_accounts_host.hide()
        layout.addWidget(self._saved_accounts_host)
        layout.addSpacing(16)

        self._login_email.returnPressed.connect(self._login_password.setFocus)

        self._login_btn = QPushButton("Sign In")
        self._login_btn.setObjectName("login_primary_button")
        self._login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_btn.setFont(studio_font(15, QFont.Weight.DemiBold))
        self._login_btn.setIcon(QIcon(lucide_pixmap("log-in", size=16, color="#FFFFFF")))
        self._login_btn.setDefault(True)
        self._login_btn.setAutoDefault(True)
        self._login_btn.clicked.connect(self._submit_login)
        layout.addWidget(self._login_btn)

        if REGISTRATION_ENABLED:
            layout.addSpacing(12)
            switch_row = QHBoxLayout()
            switch_row.addStretch()
            to_register = QPushButton("Create account")
            to_register.setObjectName("auth_switch_button")
            to_register.setCursor(Qt.CursorShape.PointingHandCursor)
            to_register.setFlat(True)
            to_register.clicked.connect(self.show_register_form)
            switch_row.addWidget(to_register)
            switch_row.addStretch()
            layout.addLayout(switch_row)

        return page

    def _build_register_form(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(BrandMark(48), alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        title = QLabel("Create account")
        title.setObjectName("auth_brand_title")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        subtitle = QLabel("Create an account to get started")
        subtitle.setObjectName("auth_card_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(20)

        layout.addWidget(self._field_label("Email"))
        layout.addSpacing(6)
        self._register_email = IconLineEdit("mail", "Enter your email")
        layout.addWidget(self._register_email)
        layout.addSpacing(14)

        layout.addWidget(self._field_label("Password"))
        layout.addSpacing(6)
        self._register_password = IconLineEdit("lock", "Choose a password", password=True)
        layout.addWidget(self._register_password)
        layout.addSpacing(14)

        layout.addWidget(self._field_label("Display Name"))
        layout.addSpacing(6)
        self._register_name = QLineEdit()
        self._register_name.setObjectName("auth_input")
        self._register_name.setPlaceholderText("Choose a display name")
        self._register_name.setMinimumHeight(48)
        self._register_name.setMaximumHeight(48)
        layout.addWidget(self._register_name)
        layout.addSpacing(16)

        switch_row = QHBoxLayout()
        switch_row.addStretch()
        to_login = QPushButton("Back to sign in")
        to_login.setObjectName("auth_switch_button")
        to_login.setCursor(Qt.CursorShape.PointingHandCursor)
        to_login.setFlat(True)
        to_login.clicked.connect(self.show_login_form)
        switch_row.addWidget(to_login)
        switch_row.addStretch()
        layout.addLayout(switch_row)
        layout.addSpacing(12)

        self._create_btn = QPushButton("Create Account")
        self._create_btn.setObjectName("login_primary_button")
        self._create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._create_btn.clicked.connect(self._submit_register)
        layout.addWidget(self._create_btn)
        return page

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("auth_field_label")
        label.setFont(studio_font(12, QFont.Weight.Medium))
        return label

    def _apply_remembered_email(self) -> None:
        email = (self._storage.get(REMEMBER_EMAIL_KEY) or "").strip()
        self._remember.setChecked(bool(email))
        if email:
            self._login_email.setText(email)

    def _persist_remembered_email(self, email: str) -> None:
        if self._remember.isChecked() and email:
            self._storage.set(REMEMBER_EMAIL_KEY, email)
        else:
            self._storage.remove(REMEMBER_EMAIL_KEY)

    def _open_forgot_password(self) -> None:
        QDesktopServices.openUrl(QUrl(f"{get_portal_base_url().rstrip('/')}/login"))

    def _request_switch_account(self, user_id: str) -> None:
        if not str(user_id).strip():
            return
        self.clear_error()
        self.set_busy(True)
        self.set_loading_status("Switching account", "Restoring your saved session.")
        self.switch_account_requested.emit(str(user_id).strip())

    def _submit_login(self) -> None:
        email = self._login_email.text().strip()
        password = self._login_password.text()
        error = _validate_login(email, password)
        if error:
            self.set_error(error)
            return
        self._persist_remembered_email(email)
        self.clear_error()
        self.login_requested.emit(email, password)

    def _submit_register(self) -> None:
        if not REGISTRATION_ENABLED:
            self.set_error("Account registration is not available. Contact your administrator.")
            return
        email = self._register_email.text().strip()
        password = self._register_password.text()
        display_name = self._register_name.text().strip()
        error = _validate_register(email, password, display_name)
        if error:
            self.set_error(error)
            return
        self.clear_error()
        self.register_requested.emit(email, password, display_name)


def _validate_login(email: str, password: str) -> str | None:
    if not _EMAIL_RE.match(email):
        return "Enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    return None


def _validate_register(email: str, password: str, display_name: str) -> str | None:
    login_error = _validate_login(email, password)
    if login_error:
        return login_error
    if len(display_name) < 2:
        return "Enter your display name."
    return None


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
