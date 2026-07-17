"""Download and silently apply a desktop software update."""

from __future__ import annotations

import os
import tempfile
from urllib.parse import urlparse

import httpx
from PySide6.QtCore import QThread, Signal

from shared.services.software_update_installer import (
    SoftwareUpdateInstallError,
    SoftwareUpdateInstaller,
    detect_package_kind,
)

_CHUNK_SIZE = 1024 * 1024


class SoftwareUpdateInstallWorker(QThread):
    progress = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, download_url: str, parent=None) -> None:
        super().__init__(parent)
        self._download_url = download_url

    def run(self) -> None:
        suffix = self._guess_suffix(self._download_url)
        fd, package_path = tempfile.mkstemp(prefix="camxora-update-", suffix=suffix)
        os.close(fd)
        try:
            self.progress.emit("Downloading update…")
            with httpx.stream("GET", self._download_url, timeout=300.0, follow_redirects=True) as response:
                response.raise_for_status()
                with open(package_path, "wb") as handle:
                    for chunk in response.iter_bytes(chunk_size=_CHUNK_SIZE):
                        if chunk:
                            handle.write(chunk)

            kind = detect_package_kind(package_path, self._download_url)
            if kind == "zip":
                self.progress.emit("Installing update silently…")
            else:
                self.progress.emit("Running silent installer…")

            SoftwareUpdateInstaller().apply(
                package_path,
                download_url=self._download_url,
                parent_pid=os.getpid(),
            )
            self.progress.emit("Restarting Camxora…")
            self.succeeded.emit(package_path)
        except SoftwareUpdateInstallError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Unable to install update.")
        finally:
            try:
                if os.path.isfile(package_path):
                    os.remove(package_path)
            except OSError:
                pass

    @staticmethod
    def _guess_suffix(url: str) -> str:
        path = urlparse(url).path.lower()
        for suffix in (".zip", ".msi", ".exe"):
            if path.endswith(suffix):
                return suffix
        return ".zip"
