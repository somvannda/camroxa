"""Onboarding gate views — profile setup happens in the web portal only."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from shared.services.build_config import get_onboarding_url, get_portal_base_url
from shared.themes.deep_blue import START_BUTTON_ID, SUBTITLE_LABEL_ID, TITLE_LABEL_ID


class OnboardingWelcomeView(QFrame):
    """Email confirmation gate — mirrors onboarding welcome entry."""

    continue_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch()

        card = QFrame()
        card.setObjectName("account_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Confirm your email")
        title.setObjectName(TITLE_LABEL_ID)
        card_layout.addWidget(title)

        detail = QLabel(
            "Your account was created. Confirm your email in the account portal "
            f"({get_portal_base_url()}) before continuing to channel setup."
        )
        detail.setObjectName(SUBTITLE_LABEL_ID)
        detail.setWordWrap(True)
        card_layout.addWidget(detail)

        portal_btn = QPushButton("Open account portal")
        portal_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(get_portal_base_url())))
        card_layout.addWidget(portal_btn)

        btn = QPushButton("Back to Sign In")
        btn.clicked.connect(self.continue_clicked.emit)
        card_layout.addWidget(btn)

        layout.addWidget(card)
        layout.addStretch()


class OnboardingWizardView(QFrame):
    """Directs users to the web portal for channel onboarding — not available on desktop."""

    refresh_requested = Signal()
    skip_to_app = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch()

        card = QFrame()
        card.setObjectName("account_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Complete setup in your browser")
        title.setObjectName(TITLE_LABEL_ID)
        card_layout.addWidget(title)

        detail = QLabel(
            "Channel profiles, logos, covers, and onboarding are managed in the "
            "CamXora account portal — not in the desktop app. Purchase a plan or "
            "add-on in the portal, then finish onboarding there. After profiles "
            "exist, return here and sign in again."
        )
        detail.setObjectName(SUBTITLE_LABEL_ID)
        detail.setWordWrap(True)
        card_layout.addWidget(detail)

        portal_btn = QPushButton("Open onboarding portal")
        portal_btn.setObjectName(START_BUTTON_ID)
        portal_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(get_onboarding_url()))
        )
        card_layout.addWidget(portal_btn)

        refresh_btn = QPushButton("I completed setup — refresh")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        card_layout.addWidget(refresh_btn)

        skip_btn = QPushButton("Open studio anyway")
        skip_btn.clicked.connect(self.skip_to_app.emit)
        card_layout.addWidget(skip_btn)

        layout.addWidget(card)
        layout.addStretch()
