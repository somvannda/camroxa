"""Blocking overlay when a mandatory software update is required."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from shared.constants.app_version import get_app_version
from shared.services.software_update_service import SoftwareUpdateOffer, SoftwareUpdateService
from shared.themes.deep_blue import SUBTITLE_LABEL_ID, TITLE_LABEL_ID


class SoftwareUpdateGateOverlay(QFrame):
    update_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("software_update_gate")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(12)
        layout.addStretch(1)

        self._title = QLabel("Update required")
        self._title.setObjectName(TITLE_LABEL_ID)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        self._message = QLabel("")
        self._message.setObjectName(SUBTITLE_LABEL_ID)
        self._message.setWordWrap(True)
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._message)

        self._current_version = QLabel("")
        self._current_version.setObjectName(SUBTITLE_LABEL_ID)
        self._current_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._current_version)

        self._update_button = QPushButton("Install update now")
        self._update_button.clicked.connect(self.update_requested.emit)
        layout.addWidget(self._update_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self._status = QLabel("")
        self._status.setObjectName(SUBTITLE_LABEL_ID)
        self._status.setWordWrap(True)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        layout.addStretch(2)

        service = SoftwareUpdateService.instance()
        service.update_changed.connect(self._on_update_changed)
        service.install_started.connect(self._on_install_started)
        service.install_progress.connect(self._on_install_progress)
        service.install_failed.connect(self._on_install_failed)
        self._on_update_changed(service.pending)

    def _on_update_changed(self, offer: object) -> None:
        if not isinstance(offer, SoftwareUpdateOffer) or not offer.mandatory:
            self.hide()
            return
        self._title.setText("Update required")
        self._message.setText(
            f"Camxora {offer.version} is required before you can continue.\n{offer.release_notes}".strip()
        )
        self._current_version.setText(f"Current version: {get_app_version()}")
        self._status.setText("")
        self._update_button.setEnabled(True)
        self.show()
        self.raise_()

    def _on_install_started(self) -> None:
        self._status.setText("Preparing silent update…")
        self._update_button.setEnabled(False)

    def _on_install_progress(self, message: str) -> None:
        self._status.setText(message)

    def _on_install_failed(self, message: str) -> None:
        self._status.setText(message)
        self._update_button.setEnabled(True)

    def set_status(self, message: str) -> None:
        self._status.setText(message)
