"""Desktop software update state and install flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from shared.constants.app_version import get_app_version
from shared.lib.software_update_persistence import (
    PersistedSoftwareUpdate,
    clear_all_update_markers,
    clear_update_status,
    load_pending_update,
    load_update_status,
    save_pending_update,
)
from shared.lib.version_compare import is_remote_version_newer


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
    install_progress = Signal(str, int)  # message, percent (-1 = indeterminate)
    # Emitted when the Setup helper has been launched and Camxora is about to quit —
    # NOT when the new version is already installed.
    install_succeeded = Signal()
    install_failed = Signal(str)
    # Emitted when a previous Setup may still be running after restart.
    install_finishing = Signal()

    _instance: SoftwareUpdateService | None = None

    def __init__(self) -> None:
        super().__init__()
        self._pending: SoftwareUpdateOffer | None = None
        self._install_worker: QObject | None = None
        self._install_in_progress = False
        self._status_poll_timer: QTimer | None = None

    @classmethod
    def instance(cls) -> SoftwareUpdateService:
        if cls._instance is None:
            cls._instance = SoftwareUpdateService()
        return cls._instance

    @property
    def pending(self) -> SoftwareUpdateOffer | None:
        return self._pending

    @property
    def install_in_progress(self) -> bool:
        return self._install_in_progress

    def restore_from_disk(self) -> SoftwareUpdateOffer | None:
        """Reload a mandatory update left over from a previous session."""
        persisted = load_pending_update()
        if persisted is None:
            return None

        if not is_remote_version_newer(get_app_version(), persisted.version):
            clear_all_update_markers()
            self._install_in_progress = False
            self._stop_status_poll()
            if self._pending is not None:
                self.clear_pending()
            return None

        offer = SoftwareUpdateOffer(
            version=persisted.version,
            download_url=persisted.download_url,
            mandatory=persisted.mandatory,
            release_notes=persisted.release_notes,
            notification_id=persisted.notification_id,
        )
        self._pending = offer
        self.update_changed.emit(offer)

        status = load_update_status()
        if persisted.install_in_progress and status is not None and status.is_active:
            self._install_in_progress = True
            self.install_finishing.emit()
            self._start_status_poll()
        elif status is not None and status.is_failed:
            self._install_in_progress = False
            self._persist_pending(install_in_progress=False)
            clear_update_status()
            message = status.error or "The previous update did not finish. Try again."
            self.install_failed.emit(message)
        elif persisted.install_in_progress:
            # Marker said in progress but helper status is missing/stale.
            self._install_in_progress = False
            self._persist_pending(install_in_progress=False)
            clear_update_status()
            self.install_failed.emit(
                "The previous update did not finish. If a Setup window is still open, "
                "wait for it — otherwise try again."
            )
        return offer

    def apply_push_payload(self, payload: dict[str, Any]) -> SoftwareUpdateOffer | None:
        offer = SoftwareUpdateOffer.from_payload(payload)
        if offer is None:
            # Already on this version (or newer) — drop any stale blocking offer.
            self.reconcile_with_installed_version()
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
        self._persist_pending(install_in_progress=self._install_in_progress and offer.mandatory)
        self.update_changed.emit(offer)
        return offer

    def reconcile_with_installed_version(self) -> None:
        """Clear pending updates that the running install already satisfies."""
        if self._pending is None:
            persisted = load_pending_update()
            if persisted is not None and not is_remote_version_newer(
                get_app_version(), persisted.version
            ):
                clear_all_update_markers()
            return
        if not is_remote_version_newer(get_app_version(), self._pending.version):
            self.clear_pending()

    def should_block_app(self) -> bool:
        self.reconcile_with_installed_version()
        return self._pending is not None and self._pending.mandatory

    def can_dismiss(self, notification_id: str) -> bool:
        if self._pending is None:
            return True
        if self._pending.mandatory and self._pending.notification_id == notification_id:
            return False
        return True

    def clear_pending(self, notification_id: str | None = None) -> None:
        if self._pending is None:
            clear_all_update_markers()
            self._install_in_progress = False
            self._stop_status_poll()
            return
        if notification_id and self._pending.notification_id != notification_id:
            return
        self._pending = None
        self._install_in_progress = False
        self._stop_status_poll()
        clear_all_update_markers()
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

        clear_update_status()
        self._install_in_progress = True
        self._persist_pending(install_in_progress=True)

        worker = SoftwareUpdateInstallWorker(
            self._pending.download_url,
            target_version=self._pending.version,
            parent=parent or self,
        )
        worker.progress.connect(self.install_progress.emit)
        worker.succeeded.connect(self._on_installer_launched)
        worker.failed.connect(self._on_install_failed)
        worker.finished.connect(lambda: setattr(self, "_install_worker", None))
        self._install_worker = worker
        self.install_started.emit()
        worker.start()
        return True

    def _on_installer_launched(self, _installer_path: object) -> None:
        from PySide6.QtWidgets import QApplication

        # Keep pending + in-progress on disk so a mid-Setup reopen can re-gate.
        self._persist_pending(install_in_progress=True)
        self.install_succeeded.emit()

        def _quit_for_setup() -> None:
            app = QApplication.instance()
            if app is not None:
                app.quit()

        # Give the gate time to show the honest closing message; the orphan
        # helper waits for this process to exit, then runs Setup and relaunches.
        QTimer.singleShot(1800, _quit_for_setup)

    def _on_install_failed(self, message: str) -> None:
        self._install_in_progress = False
        self._persist_pending(install_in_progress=False)
        clear_update_status()
        self.install_failed.emit(str(message or "Unable to install update."))

    def _persist_pending(self, *, install_in_progress: bool) -> None:
        if self._pending is None:
            return
        if not self._pending.mandatory:
            # Optional updates stay in-memory only.
            return
        save_pending_update(
            PersistedSoftwareUpdate(
                version=self._pending.version,
                download_url=self._pending.download_url,
                mandatory=self._pending.mandatory,
                release_notes=self._pending.release_notes,
                notification_id=self._pending.notification_id,
                install_in_progress=install_in_progress,
            )
        )

    def _start_status_poll(self) -> None:
        self._stop_status_poll()
        timer = QTimer(self)
        timer.setInterval(2000)
        timer.timeout.connect(self._poll_helper_status)
        self._status_poll_timer = timer
        timer.start()

    def _stop_status_poll(self) -> None:
        if self._status_poll_timer is not None:
            self._status_poll_timer.stop()
            self._status_poll_timer.deleteLater()
            self._status_poll_timer = None

    def _poll_helper_status(self) -> None:
        if self._pending is None:
            self._stop_status_poll()
            return

        if not is_remote_version_newer(get_app_version(), self._pending.version):
            self.clear_pending()
            return

        status = load_update_status()
        if status is None:
            return
        if status.is_active:
            self._install_in_progress = True
            self.install_progress.emit(
                "Setup is still installing. Keep waiting for the Setup window to finish…",
                -1,
            )
            return
        if status.is_done:
            # New process should already be on the target version; if not, re-gate.
            if not is_remote_version_newer(get_app_version(), self._pending.version):
                self.clear_pending()
            else:
                self._install_in_progress = False
                self._persist_pending(install_in_progress=False)
                clear_update_status()
                self.install_failed.emit(
                    "Setup finished but Camxora is still on the old version. Try again."
                )
            self._stop_status_poll()
            return
        if status.is_failed:
            self._install_in_progress = False
            self._persist_pending(install_in_progress=False)
            clear_update_status()
            self.install_failed.emit(
                status.error or "The previous update did not finish. Try again."
            )
            self._stop_status_poll()
