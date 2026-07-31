"""Login and register views."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)

from shared.constants.auth import REGISTRATION_ENABLED
from shared.services.account_token_store import list_saved_accounts, remove_saved_account
from shared.services.build_config import (
    build_environment,
    footer_environment_badge,
    footer_version_badge,
)
from shared.services.secure_storage import SecureStorage
from shared.widgets.shell_footer_bar import ShellFooterBar
from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID
from shared.widgets.window_title_bar import _WindowControlButton


class AuthView(QFrame):
    """Login / register forms matching Electron auth pages."""

    login_requested = Signal(str, str)
    register_requested = Signal(str, str, str)
    switch_account_requested = Signal(str)

    def __init__(self, storage: SecureStorage | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName("startup_page")
        self._storage = storage or SecureStorage()

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_login_form())
        if REGISTRATION_ENABLED:
            self._stack.addWidget(self._build_register_form())

        self._error_label = QLabel()
        self._error_label.setObjectName(SUBTITLE_LABEL_ID)
        self._error_label.setWordWrap(True)
        self._error_label.hide()

        self._loading_label = QLabel()
        self._loading_label.setObjectName(SUBTITLE_LABEL_ID)
        self._loading_label.setWordWrap(True)
        self._loading_label.hide()

        # Use the same footer widget as the post-login app shell so the
        # environment is visible even when auth fails.
        self._footer_bar = ShellFooterBar()
        self._footer_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        version_label, version_tooltip = footer_version_badge()
        self._footer_bar.set_version_badge(version_label, tooltip=version_tooltip)
        self._refresh_login_footer_badges()

        card = QFrame()
        card.setObjectName("startup_loading_card")
        card.setFixedWidth(420)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.addWidget(self._stack)
        card_layout.addWidget(self._loading_label)
        card_layout.addWidget(self._error_label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # Center the login card within the available space above the footer.
        top = QVBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addStretch()
        top.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
        top.addStretch()
        outer.addLayout(top, stretch=1)
        outer.addWidget(self._footer_bar, stretch=0)

    def get_api_base_url(self) -> str:
        return self._storage.get_api_base_url()

    def show_login_form(self) -> None:
        self._stack.setCurrentIndex(0)
        self.clear_error()
        self._refresh_login_footer_badges()
        self._refresh_saved_accounts()

    def _refresh_saved_accounts(self) -> None:
        accounts = list_saved_accounts(self._storage)
        self._saved_accounts_host.setVisible(bool(accounts))
        while self._saved_accounts_layout.count():
            item = self._saved_accounts_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for account in accounts:
            label = account.display_name or account.email or account.user_id
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            row_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            button = QPushButton(label)
            button.setToolTip(account.email or account.user_id)
            button.setObjectName("saved_account_button")
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked=False, uid=account.user_id: self._request_switch_account(uid))
            row_layout.addWidget(button, stretch=1)

            remove_btn = _WindowControlButton("close", row)
            remove_btn.setToolTip("Remove this pinned profile")
            # Header close is larger; shrink for the pinned-profile row.
            remove_btn.setFixedSize(28, 28)
            remove_btn.clicked.connect(lambda _checked=False, uid=account.user_id: self._remove_saved_account(uid))
            row_layout.addWidget(remove_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

            self._saved_accounts_layout.addWidget(row)

    def _remove_saved_account(self, user_id: str) -> None:
        remove_saved_account(self._storage, user_id)
        self._refresh_saved_accounts()

    def show_register_form(self) -> None:
        if not REGISTRATION_ENABLED:
            return
        self._stack.setCurrentIndex(1)
        self.clear_error()

    def _refresh_login_footer_badges(self) -> None:
        # In production builds `footer_environment_badge()` returns (None, "").
        # For login diagnostics we still show a label so users know which
        # endpoint the app is calling.
        env_label, env_tooltip = footer_environment_badge()
        api_base_url = self._storage.get_api_base_url()
        env = build_environment()

        if not env_label:
            api_lower = (api_base_url or "").lower()
            if env == "sandbox":
                env_label = "Sandbox API"
            elif env == "production":
                env_label = "Production API"
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
        if hasattr(self, "_create_btn"):
            self._create_btn.setEnabled(not busy)
        if not busy:
            self.clear_loading_status()

    def _build_login_form(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        title = QLabel("Welcome back")
        title.setObjectName(TITLE_LABEL_ID)
        layout.addWidget(title)

        subtitle = QLabel("Sign in to continue to your studio")
        subtitle.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(subtitle)

        layout.addWidget(QLabel("Email"))
        self._login_email = QLineEdit()
        self._login_email.setPlaceholderText("Enter your email")
        layout.addWidget(self._login_email)

        layout.addWidget(QLabel("Password"))
        self._login_password = QLineEdit()
        self._login_password.setPlaceholderText("Enter your password")
        self._login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._login_password.returnPressed.connect(self._submit_login)
        layout.addWidget(self._login_password)

        self._saved_accounts_host = QWidget()
        saved_layout = QVBoxLayout(self._saved_accounts_host)
        saved_layout.setContentsMargins(0, 0, 0, 0)
        saved_layout.setSpacing(6)
        saved_label = QLabel("Continue as")
        saved_label.setObjectName(SUBTITLE_LABEL_ID)
        saved_layout.addWidget(saved_label)
        self._saved_accounts_layout = QVBoxLayout()
        self._saved_accounts_layout.setSpacing(6)
        saved_layout.addLayout(self._saved_accounts_layout)
        self._saved_accounts_host.hide()
        layout.addWidget(self._saved_accounts_host)

        self._login_email.returnPressed.connect(self._login_password.setFocus)

        if REGISTRATION_ENABLED:
            switch_row = QHBoxLayout()
            switch_row.addStretch()
            to_register = QPushButton("Create account")
            to_register.clicked.connect(self.show_register_form)
            switch_row.addWidget(to_register)
            layout.addLayout(switch_row)

        # Give breathing room between the password field and the primary CTA.
        layout.addSpacing(12)

        self._login_btn = QPushButton("Sign In")
        self._login_btn.setObjectName("login_primary_button")
        self._login_btn.setDefault(True)
        self._login_btn.setAutoDefault(True)
        self._login_btn.clicked.connect(self._submit_login)
        layout.addWidget(self._login_btn)

        return page

    def _build_register_form(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        title = QLabel("Create account")
        title.setObjectName(TITLE_LABEL_ID)
        layout.addWidget(title)

        subtitle = QLabel("Create an account to get started")
        subtitle.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(subtitle)

        layout.addWidget(QLabel("Email"))
        self._register_email = QLineEdit()
        self._register_email.setPlaceholderText("Enter your email")
        layout.addWidget(self._register_email)

        layout.addWidget(QLabel("Password"))
        self._register_password = QLineEdit()
        self._register_password.setPlaceholderText("Choose a password")
        self._register_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._register_password)

        layout.addWidget(QLabel("Display Name"))
        self._register_name = QLineEdit()
        self._register_name.setPlaceholderText("Choose a display name")
        layout.addWidget(self._register_name)

        switch_row = QHBoxLayout()
        switch_row.addStretch()
        to_login = QPushButton("Back to sign in")
        to_login.clicked.connect(self.show_login_form)
        switch_row.addWidget(to_login)
        layout.addLayout(switch_row)

        self._create_btn = QPushButton("Create Account")
        self._create_btn.setObjectName("login_primary_button")
        self._create_btn.clicked.connect(self._submit_register)
        layout.addWidget(self._create_btn)

        return page

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
