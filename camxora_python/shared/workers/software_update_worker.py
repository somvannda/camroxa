"""Download and launch a desktop software update installer."""

from __future__ import annotations

import os
import tempfile
from urllib.parse import urlparse

import httpx
from PySide6.QtCore import QThread, Signal

from shared.lib.software_update_copy import (
    STATUS_CLOSING,
    STATUS_DOWNLOAD_COMPLETE,
    STATUS_FAILED_DEFAULT,
    STATUS_INSTALLING,
    STATUS_PREPARING_INSTALLER,
    STATUS_STARTING_DOWNLOAD,
    STATUS_STARTING_INSTALLER,
    format_download_progress,
)
from shared.services.software_update_installer import (
    SoftwareUpdateInstallError,
    SoftwareUpdateInstaller,
    detect_package_kind,
)

_CHUNK_SIZE = 256 * 1024
# Leave headroom on the progress bar for install + restart phases.
_DOWNLOAD_PROGRESS_CAP = 85


class SoftwareUpdateInstallWorker(QThread):
    """Background download + launch visible-progress installer.

    ``progress`` emits ``(message, percent)`` where percent is ``0–100`` for
    determinate download/install phases, or ``-1`` for indeterminate work.

    ``succeeded`` means the installer helper was launched successfully — not that
    the new version is already installed.
    """

    progress = Signal(str, int)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, download_url: str, *, target_version: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SoftwareUpdateInstallWorker")
        self._download_url = download_url
        self._target_version = str(target_version or "").strip()

    def run(self) -> None:
        suffix = self._guess_suffix(self._download_url)
        fd, package_path = tempfile.mkstemp(prefix="camxora-update-", suffix=suffix)
        os.close(fd)
        try:
            self._download(package_path)
            kind = detect_package_kind(package_path, self._download_url)
            self.progress.emit(STATUS_PREPARING_INSTALLER, 88)
            if kind == "exe":
                self.progress.emit(STATUS_STARTING_INSTALLER, 92)
            else:
                self.progress.emit(STATUS_INSTALLING, 92)

            SoftwareUpdateInstaller().apply(
                package_path,
                download_url=self._download_url,
                parent_pid=os.getpid(),
                target_version=self._target_version,
            )
            self.progress.emit(STATUS_CLOSING, 100)
            self.succeeded.emit(package_path)
        except SoftwareUpdateInstallError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or STATUS_FAILED_DEFAULT)
        finally:
            try:
                if os.path.isfile(package_path):
                    os.remove(package_path)
            except OSError:
                pass

    def _download(self, package_path: str) -> None:
        self.progress.emit(STATUS_STARTING_DOWNLOAD, 0)
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
                            self.progress.emit(format_download_progress(percent=raw_pct), pct)
                    else:
                        mb = downloaded / (1024 * 1024)
                        self.progress.emit(format_download_progress(megabytes=mb), -1)
        self.progress.emit(STATUS_DOWNLOAD_COMPLETE, _DOWNLOAD_PROGRESS_CAP)

    @staticmethod
    def _guess_suffix(url: str) -> str:
        path = urlparse(url).path.lower()
        for suffix in (".zip", ".msi", ".exe"):
            if path.endswith(suffix):
                return suffix
        return ".zip"
