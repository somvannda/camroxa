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

_CHUNK_SIZE = 256 * 1024
# Leave headroom on the progress bar for install + restart phases.
_DOWNLOAD_PROGRESS_CAP = 85


class SoftwareUpdateInstallWorker(QThread):
    """Background download + silent install.

    ``progress`` emits ``(message, percent)`` where percent is ``0–100`` for
    determinate download/install phases, or ``-1`` for indeterminate work.
    """

    progress = Signal(str, int)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, download_url: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SoftwareUpdateInstallWorker")
        self._download_url = download_url

    def run(self) -> None:
        suffix = self._guess_suffix(self._download_url)
        fd, package_path = tempfile.mkstemp(prefix="camxora-update-", suffix=suffix)
        os.close(fd)
        try:
            self._download(package_path)
            kind = detect_package_kind(package_path, self._download_url)
            self.progress.emit("Preparing installer…", 88)
            if kind == "zip":
                self.progress.emit("Installing update…", 92)
            else:
                self.progress.emit("Installing update…", 92)

            SoftwareUpdateInstaller().apply(
                package_path,
                download_url=self._download_url,
                parent_pid=os.getpid(),
            )
            # Helper script waits for this process to exit, then finishes install
            # and relaunches Camxora. The gate shows this message before quit.
            self.progress.emit(
                "Install ready — Camxora will restart to finish updating…",
                100,
            )
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

    def _download(self, package_path: str) -> None:
        self.progress.emit("Starting download…", 0)
        with httpx.stream("GET", self._download_url, timeout=300.0, follow_redirects=True) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length") or 0)
            downloaded = 0
            last_pct = -1
            with open(package_path, "wb") as handle:
                for chunk in response.iter_bytes(chunk_size=_CHUNK_SIZE):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        raw_pct = min(100, int(downloaded * 100 / total))
                        pct = min(_DOWNLOAD_PROGRESS_CAP, int(downloaded * _DOWNLOAD_PROGRESS_CAP / total))
                        if pct != last_pct:
                            last_pct = pct
                            self.progress.emit(f"Downloading update… {raw_pct}%", pct)
                    else:
                        mb = downloaded / (1024 * 1024)
                        self.progress.emit(f"Downloading update… {mb:.1f} MB", -1)
        if total > 0:
            self.progress.emit("Download complete — starting install…", _DOWNLOAD_PROGRESS_CAP)
        else:
            self.progress.emit("Download complete — starting install…", _DOWNLOAD_PROGRESS_CAP)

    @staticmethod
    def _guess_suffix(url: str) -> str:
        path = urlparse(url).path.lower()
        for suffix in (".zip", ".msi", ".exe"):
            if path.endswith(suffix):
                return suffix
        return ".zip"
