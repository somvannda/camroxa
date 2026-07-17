"""Download and extract admin-managed image sample packs."""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from html import unescape

import httpx

_IMAGE_EXTENSIONS = frozenset((".png", ".jpg", ".jpeg", ".webp"))
_CHUNK_SIZE = 8 * 1024
_GDRIVE_FILE_PATTERN = re.compile(r"drive\.google\.com/file/d/([^/]+)")
_GDRIVE_ID_PATTERN = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")


@dataclass(frozen=True, slots=True)
class SamplePackInstallResult:
    ok: bool
    installed_count: int = 0
    error: str = ""


class SamplePackInstaller:
    def __init__(self, timeout: float = 300.0) -> None:
        self._timeout = timeout

    def install(self, url: str, destination_dir: str) -> SamplePackInstallResult:
        tmp_path: str | None = None
        try:
            os.makedirs(destination_dir, exist_ok=True)
            file_id = self._extract_google_drive_id(url)
            tmp_path = (
                self._download_google_drive(file_id)
                if file_id
                else self._stream_download(str(url or "").strip())
            )
            if not zipfile.is_zipfile(tmp_path):
                return SamplePackInstallResult(
                    ok=False,
                    error="Install failed: archive is corrupt or not a valid ZIP.",
                )
            installed = self._extract_images(tmp_path, destination_dir)
            if installed <= 0:
                return SamplePackInstallResult(
                    ok=False,
                    error="Install failed: ZIP contained no supported image files.",
                )
            return SamplePackInstallResult(ok=True, installed_count=installed)
        except Exception as exc:
            return SamplePackInstallResult(ok=False, error=str(exc) or "Unable to install sample pack.")
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _extract_google_drive_id(self, url: str) -> str | None:
        text = str(url or "").strip()
        match = _GDRIVE_FILE_PATTERN.search(text)
        if match:
            return match.group(1)
        if "drive.google.com" in text or "drive.usercontent.google.com" in text:
            id_match = _GDRIVE_ID_PATTERN.search(text)
            if id_match:
                return id_match.group(1)
        # Bare file id
        if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", text):
            return text
        return None

    def _download_google_drive(self, file_id: str) -> str:
        """Download a Google Drive file, including large files that need virus-scan confirm."""
        fd, tmp_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)

        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            # First hit the classic uc endpoint; small files download directly.
            first = client.get(
                "https://drive.google.com/uc",
                params={"export": "download", "id": file_id},
            )
            first.raise_for_status()
            content_type = (first.headers.get("content-type") or "").lower()

            if "text/html" in content_type:
                html = first.text
                uuid_match = re.search(r'name="uuid"\s+value="([^"]+)"', html)
                confirm_match = re.search(r'name="confirm"\s+value="([^"]+)"', html)
                params = {
                    "id": file_id,
                    "export": "download",
                    "confirm": confirm_match.group(1) if confirm_match else "t",
                }
                if uuid_match:
                    params["uuid"] = unescape(uuid_match.group(1))

                response = client.get(
                    "https://drive.usercontent.google.com/download",
                    params=params,
                )
                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "").lower()
                if "text/html" in content_type:
                    raise RuntimeError(
                        "Download failed: Google Drive returned an HTML page instead of a ZIP. "
                        "Ensure the file is shared as 'Anyone with the link can view'."
                    )
                body = response.content
            else:
                body = first.content

            with open(tmp_path, "wb") as handle:
                handle.write(body)

        with open(tmp_path, "rb") as handle:
            header = handle.read(15)
        if header.startswith(b"<!DOCTYPE") or header.startswith(b"<html"):
            os.remove(tmp_path)
            raise RuntimeError(
                "Download failed: received an HTML page instead of a ZIP file. "
                "Ensure the file is shared as 'Anyone with the link can view'."
            )
        return tmp_path

    def _stream_download(self, url: str) -> str:
        fd, tmp_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(tmp_path, "wb") as handle:
                    for chunk in response.iter_bytes(_CHUNK_SIZE):
                        if chunk:
                            handle.write(chunk)
        return tmp_path

    def _extract_images(self, zip_path: str, destination_dir: str) -> int:
        installed = 0
        with zipfile.ZipFile(zip_path, "r") as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                suffix = os.path.splitext(member.filename)[1].lower()
                if suffix not in _IMAGE_EXTENSIONS:
                    continue
                target_name = os.path.basename(member.filename)
                if not target_name:
                    continue
                target_path = os.path.join(destination_dir, target_name)
                with archive.open(member) as source, open(target_path, "wb") as dest:
                    dest.write(source.read())
                installed += 1
        return installed
