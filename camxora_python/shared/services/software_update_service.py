"""Desktop software update state and install flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Signal

from shared.constants.app_version import get_app_version
from shared.lib.version_compare import is_remote_version_newer
from shared.models.push_events import SOFTWARE_UPDATE_AVAILABLE


@dataclass(slots=True)
class SoftwareUpdateOffer:
    version: str
    download_url: str
    mandatory: bool
    release_notes: str
    notification_id: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SoftwareUpdateOffer | None:
        version = str(payload.get("version") or "").strip()
        if not version:
            return None
        if not is_remote_version_newer(get_app_version(), version):
            return None
        return cls(
            version=version,
            download_url=str(payload.get("download_url") or "").strip(),
            mandatory=bool(payload.get("mandatory")),
            release_notes=str(payload.get("release_notes") or "").strip(),
            notification_id=str(payload.get("notification_id") or "").strip(),
        )


class SoftwareUpdateService(QObject):
    """Tracks pending desktop updates and whether the app should be blocked."""

    update_changed = Signal(object)
    install_started = Signal()
    install_progress = Signal(str)
    install_failed = Signal(str)

    _instance: SoftwareUpdateService | None = None

    def __init__(self) -> None:
        super().__init__()
        self._pending: SoftwareUpdateOffer | None = None
        self._install_worker: QObject | None = None

    @classmethod
    def instance(cls) -> SoftwareUpdateService:
        if cls._instance is None:
            cls._instance = SoftwareUpdateService()
        return cls._instance

    @property
    def pending(self) -> SoftwareUpdateOffer | None:
        return self._pending

    def apply_push_payload(self, payload: dict[str, Any]) -> SoftwareUpdateOffer | None:
        offer = SoftwareUpdateOffer.from_payload(payload)
        if offer is None:
            return None
        notification_id = str(payload.get("notification_id") or offer.notification_id or "").strip()
        offer = SoftwareUpdateOffer(
            version=offer.version,
            download_url=offer.download_url,
            mandatory=offer.mandatory,
            release_notes=offer.release_notes,
            notification_id=notification_id,
        )
        if self._pending is not None:
            from shared.lib.version_compare import parse_version

            if parse_version(offer.version) < parse_version(self._pending.version):
                return self._pending
            if (
                parse_version(offer.version) == parse_version(self._pending.version)
                and self._pending.mandatory
            ):
                offer = SoftwareUpdateOffer(
                    version=offer.version,
                    download_url=offer.download_url or self._pending.download_url,
                    mandatory=True,
                    release_notes=offer.release_notes or self._pending.release_notes,
                    notification_id=notification_id or self._pending.notification_id,
                )
        self._pending = offer
        self.update_changed.emit(offer)
        return offer

    def should_block_app(self) -> bool:
        return self._pending is not None and self._pending.mandatory

    def can_dismiss(self, notification_id: str) -> bool:
        if self._pending is None:
            return True
        if self._pending.mandatory and self._pending.notification_id == notification_id:
            return False
        return True

    def clear_pending(self, notification_id: str | None = None) -> None:
        if self._pending is None:
            return
        if notification_id and self._pending.notification_id != notification_id:
            return
        self._pending = None
        self.update_changed.emit(None)

    def start_install(self, parent: QObject | None = None) -> bool:
        if self._pending is None:
            self.install_failed.emit("No software update is available.")
            return False
        if not self._pending.download_url:
            self.install_failed.emit("This update does not include a download URL yet.")
            return False
        if self._install_worker is not None:
            return False

        from shared.workers.software_update_worker import SoftwareUpdateInstallWorker

        worker = SoftwareUpdateInstallWorker(self._pending.download_url, parent=parent or self)
        worker.progress.connect(self.install_progress.emit)
        worker.succeeded.connect(self._on_install_succeeded)
        worker.failed.connect(self._on_install_failed)
        worker.finished.connect(lambda: setattr(self, "_install_worker", None))
        self._install_worker = worker
        self.install_started.emit()
        worker.start()
        return True

    def _on_install_succeeded(self, _installer_path: object) -> None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _on_install_failed(self, message: str) -> None:
        self.install_failed.emit(str(message or "Unable to install update."))
