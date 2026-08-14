"""Background check of the public desktop-release for mandatory updates."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from shared.services.desktop_release_client import fetch_published_desktop_release_result


class SoftwareUpdateCheckWorker(QThread):
    """Fetches published release off the UI thread.

    Emits a ``DesktopReleaseFetchResult`` so the app can tell a confirmed
    withdrawal (404) from a network failure (keep a persisted gate).
    """

    finished_with_offer = Signal(object)

    def __init__(self, api_base_url: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SoftwareUpdateCheckWorker")
        self._api_base_url = api_base_url

    def run(self) -> None:
        self.finished_with_offer.emit(
            fetch_published_desktop_release_result(self._api_base_url)
        )
