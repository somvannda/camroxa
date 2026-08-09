"""Background check of the public desktop-release for mandatory updates."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from shared.services.desktop_release_client import fetch_published_desktop_release
from shared.services.software_update_service import SoftwareUpdateOffer


class SoftwareUpdateCheckWorker(QThread):
    """Fetches published release off the UI thread.

    Emits a ``SoftwareUpdateOffer`` only when the release is newer than the
    running build **and** marked mandatory. Otherwise emits ``None`` (fail-open
    on network/404 so startup is not bricked).
    """

    finished_with_offer = Signal(object)

    def __init__(self, api_base_url: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SoftwareUpdateCheckWorker")
        self._api_base_url = api_base_url

    def run(self) -> None:
        release = fetch_published_desktop_release(self._api_base_url)
        if release is None or not release.mandatory:
            self.finished_with_offer.emit(None)
            return
        offer = SoftwareUpdateOffer.from_payload(release.as_update_payload())
        self.finished_with_offer.emit(offer)
