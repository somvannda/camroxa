"""Blocking overlay when a mandatory software update is required."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from shared.constants.app_version import get_app_version
from shared.icons.chrome_assets import CHROME_SVG_BY_NAME
from shared.lib.resource_paths import get_resource_path
from shared.lib.software_update_copy import format_update_summary, format_whats_new
from shared.services.software_update_service import SoftwareUpdateOffer, SoftwareUpdateService


def _load_logo_pixmap(size: int) -> QPixmap:
    path = get_resource_path("app-logo.svg")
    raw = ""
    if path.is_file():
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            raw = ""
    if not raw.strip():
        raw = CHROME_SVG_BY_NAME.get("app-logo.svg", "")
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    if not raw.strip():
        return pixmap
    renderer = QSvgRenderer(QByteArray(raw.encode("utf-8")))
    if not renderer.isValid():
        return pixmap
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


class SoftwareUpdateGateOverlay(QFrame):
    update_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("software_update_gate")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.addStretch(1)

        center_row = QHBoxLayout()
        center_row.addStretch(1)

        self._card = QFrame()
        self._card.setObjectName("software_update_card")
        self._card.setFixedWidth(440)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(32, 32, 32, 28)
        card_layout.setSpacing(14)

        logo = QLabel()
        logo.setObjectName("software_update_logo")
        logo.setPixmap(_load_logo_pixmap(48))
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)

        brand = QLabel("Camxora")
        brand.setObjectName("software_update_brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(brand)

        self._title = QLabel("Update required")
        self._title.setObjectName("software_update_title")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._title)

        self._message = QLabel("")
        self._message.setObjectName("software_update_body")
        self._message.setWordWrap(True)
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._message)

        self._version_row = QLabel("")
        self._version_row.setObjectName("software_update_versions")
        self._version_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._version_row)

        self._whats_new_label = QLabel("What’s new")
        self._whats_new_label.setObjectName("software_update_section")
        self._whats_new_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._whats_new_label.hide()
        card_layout.addWidget(self._whats_new_label)

        self._whats_new = QLabel("")
        self._whats_new.setObjectName("software_update_whats_new")
        self._whats_new.setWordWrap(True)
        self._whats_new.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._whats_new.hide()
        card_layout.addWidget(self._whats_new)

        self._progress_wrap = QWidget()
        self._progress_wrap.setObjectName("software_update_progress_wrap")
        progress_layout = QVBoxLayout(self._progress_wrap)
        progress_layout.setContentsMargins(0, 8, 0, 0)
        progress_layout.setSpacing(8)

        self._progress = QProgressBar()
        self._progress.setObjectName("software_update_progress")
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(8)
        progress_layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setObjectName("software_update_status")
        self._status.setWordWrap(True)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self._status)

        self._progress_wrap.hide()
        card_layout.addWidget(self._progress_wrap)

        self._update_button = QPushButton("Update now")
        self._update_button.setObjectName("software_update_primary")
        self._update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_button.setMinimumHeight(40)
        self._update_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._update_button.clicked.connect(self.update_requested.emit)
        card_layout.addWidget(self._update_button)

        center_row.addWidget(self._card)
        center_row.addStretch(1)
        root.addLayout(center_row)
        root.addStretch(1)

        service = SoftwareUpdateService.instance()
        service.update_changed.connect(self._on_update_changed)
        service.install_started.connect(self._on_install_started)
        service.install_progress.connect(self._on_install_progress)
        service.install_succeeded.connect(self._on_installer_launched)
        service.install_finishing.connect(self._on_install_finishing)
        service.install_failed.connect(self._on_install_failed)
        self._on_update_changed(service.pending)
        if service.install_in_progress:
            self._on_install_finishing()

    def _on_update_changed(self, offer: object) -> None:
        service = SoftwareUpdateService.instance()
        service.reconcile_with_installed_version()
        offer = service.pending
        # Soft mid-session notices use the header icon only — gate is mandatory
        # (or install progress after the user chooses Update from the header).
        if not isinstance(offer, SoftwareUpdateOffer):
            self.hide()
            return
        if not offer.mandatory and not service.install_in_progress:
            self.hide()
            return

        current = get_app_version()
        self._title.setText("Update required" if offer.mandatory else "Update available")
        self._message.setText(
            format_update_summary(required_version=offer.version, current_version=current)
        )
        label = "Required" if offer.mandatory else "Available"
        self._version_row.setText(f"{label}  v{offer.version}    ·    Current  v{current}")

        bullets = format_whats_new(offer.release_notes)
        if bullets:
            self._whats_new.setText("\n".join(f"•  {item}" for item in bullets))
            self._whats_new_label.show()
            self._whats_new.show()
        else:
            self._whats_new.clear()
            self._whats_new_label.hide()
            self._whats_new.hide()

        self._progress_wrap.hide()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._status.setText("")
        self._update_button.setText("Update now")
        self._update_button.setEnabled(True)
        self._update_button.show()
        self.show()
        self.raise_()

    def _on_install_started(self) -> None:
        service = SoftwareUpdateService.instance()
        offer = service.pending
        if isinstance(offer, SoftwareUpdateOffer) and not self.isVisible():
            # Header-initiated install: show progress overlay without a prior mandatory gate.
            self._on_update_changed(offer)
        self._update_button.hide()
        self._progress_wrap.show()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._status.setText("Preparing update…")
        self._title.setText("Updating Camxora")
        self.show()
        self.raise_()

    def _on_install_progress(self, message: str, percent: int = -1) -> None:
        self._progress_wrap.show()
        self._update_button.hide()
        text = str(message or "").strip()
        if text:
            self._status.setText(text)
            lower = text.lower()
            if "download" in lower:
                self._title.setText("Downloading update")
            elif "closing" in lower or "setup" in lower:
                self._title.setText("Starting Setup")
            elif "install" in lower or "preparing installer" in lower:
                self._title.setText("Installing update")
            elif "restart" in lower:
                self._title.setText("Starting Setup")
        if percent is None or int(percent) < 0:
            # Indeterminate install / unknown download size
            if self._progress.maximum() != 0:
                self._progress.setRange(0, 0)
            return
        if self._progress.maximum() == 0:
            self._progress.setRange(0, 100)
        self._progress.setValue(max(0, min(100, int(percent))))

    def _on_installer_launched(self) -> None:
        self._progress_wrap.show()
        self._update_button.hide()
        if self._progress.maximum() == 0:
            self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self._title.setText("Starting Setup")
        self._status.setText(
            "Closing Camxora so Setup can update files. "
            "Wait for the Setup progress window to finish — this can take a few minutes."
        )

    def _on_install_finishing(self) -> None:
        if not self.isVisible():
            # Ensure mandatory gate is visible while Setup may still be running.
            service = SoftwareUpdateService.instance()
            if service.should_block_app():
                self.show()
                self.raise_()
        self._progress_wrap.show()
        self._update_button.hide()
        self._progress.setRange(0, 0)
        self._title.setText("Finishing update")
        self._status.setText(
            "Setup is still installing. Keep waiting for the Setup window to finish, "
            "or leave Camxora closed until it relaunches."
        )

    def _on_install_failed(self, message: str) -> None:
        self._progress_wrap.show()
        if self._progress.maximum() == 0:
            self._progress.setRange(0, 100)
        self._title.setText("Update required")
        self._status.setText(str(message or "Unable to install update."))
        self._update_button.setText("Try again")
        self._update_button.setEnabled(True)
        self._update_button.show()

    def set_status(self, message: str) -> None:
        self._status.setText(message)
        if message:
            self._progress_wrap.show()
