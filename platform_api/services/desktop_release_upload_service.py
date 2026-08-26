"""Store desktop installer packages uploaded from the admin portal."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from platform_api.exceptions import ValidationError

_ALLOWED_EXTENSIONS = {".zip", ".exe", ".msi"}
_DEFAULT_MAX_BYTES = 500 * 1024 * 1024
_VERSION_PATTERN = re.compile(r"^(\d+(?:\.\d+){0,2})$")
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
# Accept Inno Setup names (CamxoraSetup-1.0.15.exe) and optional env suffixes
# (-production / -sandbox), plus the older Camxora-1.0.15.zip shape.
_INSTALLER_VERSION_FILENAME = re.compile(
    r"^(?:CamxoraSetup-|Camxora-Setup-|Camxora-)"
    r"(\d+(?:\.\d+){0,2})"
    r"(?:-(?:production|sandbox))?"
    r"\.[^.]+$",
    re.IGNORECASE,
)


def extract_version_from_installer_filename(filename: str) -> str | None:
    match = _INSTALLER_VERSION_FILENAME.match(Path(str(filename or "")).name)
    if not match:
        return None
    return match.group(1)


@dataclass(frozen=True, slots=True)
class DesktopReleaseUploadResult:
    filename: str
    download_url: str
    size_bytes: int
    stored_path: str


@dataclass(frozen=True, slots=True)
class DesktopInstallerFileRecord:
    filename: str
    download_url: str
    size_bytes: int
    modified_at: str


class DesktopReleaseUploadService:
    """Write installer binaries to disk and mint public download URLs."""

    def __init__(
        self,
        *,
        storage_root: str,
        public_base_url: str = "",
        api_download_base_url: str = "",
        max_bytes: int = _DEFAULT_MAX_BYTES,
    ) -> None:
        self._storage_root = Path(str(storage_root or "./desktop_release_storage")).expanduser()
        self._public_base_url = str(public_base_url or "").strip().rstrip("/")
        self._api_download_base_url = str(api_download_base_url or "").strip().rstrip("/")
        self._max_bytes = max(1, int(max_bytes))
        self._storage_root.mkdir(parents=True, exist_ok=True)

    def with_download_bases(
        self,
        *,
        public_base_url: str | None = None,
        api_download_base_url: str | None = None,
    ) -> "DesktopReleaseUploadService":
        return DesktopReleaseUploadService(
            storage_root=str(self._storage_root),
            public_base_url=public_base_url if public_base_url is not None else self._public_base_url,
            api_download_base_url=(
                api_download_base_url
                if api_download_base_url is not None
                else self._api_download_base_url
            ),
            max_bytes=self._max_bytes,
        )

    @property
    def storage_root(self) -> Path:
        return self._storage_root

    def validate_upload(self, file_content: bytes, original_filename: str) -> str:
        if not file_content:
            raise ValidationError("Installer file is empty.", details={"field": "file"})
        if len(file_content) > self._max_bytes:
            limit_mb = self._max_bytes // (1024 * 1024)
            raise ValidationError(
                f"Installer exceeds {limit_mb} MB limit.",
                details={"field": "file", "max_bytes": self._max_bytes},
            )

        extension = Path(str(original_filename or "")).suffix.lower()
        if extension not in _ALLOWED_EXTENSIONS:
            raise ValidationError(
                "Installer must be a .zip, .exe, or .msi file.",
                details={"field": "file", "allowed_extensions": sorted(_ALLOWED_EXTENSIONS)},
            )
        return extension

    def build_filename(self, *, version: str | None, extension: str, original_filename: str) -> str:
        normalized_version = str(version or "").strip()
        if normalized_version and _VERSION_PATTERN.match(normalized_version):
            return f"Camxora-{normalized_version}{extension}"

        stem = Path(str(original_filename or "Camxora")).stem
        cleaned_stem = _UNSAFE_FILENAME.sub("-", stem).strip("-._") or "Camxora"
        return f"{cleaned_stem}{extension}"

    def build_download_url(self, filename: str) -> str:
        safe_name = Path(filename).name
        encoded = quote(safe_name, safe="")
        if self._public_base_url:
            return f"{self._public_base_url}/{encoded}"
        if self._api_download_base_url:
            return f"{self._api_download_base_url}/{encoded}"
        return f"/api/v3/public/desktop-release/files/{encoded}"

    def list_installers(self) -> list[DesktopInstallerFileRecord]:
        records: list[DesktopInstallerFileRecord] = []
        if not self._storage_root.is_dir():
            return records
        for entry in self._storage_root.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in _ALLOWED_EXTENSIONS:
                continue
            stat = entry.stat()
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            records.append(
                DesktopInstallerFileRecord(
                    filename=entry.name,
                    download_url=self.build_download_url(entry.name),
                    size_bytes=int(stat.st_size),
                    modified_at=modified,
                )
            )
        records.sort(key=lambda item: item.modified_at, reverse=True)
        return records

    def delete_installer(self, filename: str) -> None:
        path = self.resolve_existing_file(filename)
        if path is None:
            raise ValidationError("Installer file not found.", details={"field": "filename"})
        path.unlink(missing_ok=False)

    def store_installer(
        self,
        file_content: bytes,
        *,
        original_filename: str,
        version: str | None = None,
    ) -> DesktopReleaseUploadResult:
        extension = self.validate_upload(file_content, original_filename)
        filename = self.build_filename(
            version=version,
            extension=extension,
            original_filename=original_filename,
        )
        destination = self._resolve_destination(filename)
        destination.write_bytes(file_content)
        return DesktopReleaseUploadResult(
            filename=filename,
            download_url=self.build_download_url(filename),
            size_bytes=len(file_content),
            stored_path=str(destination),
        )

    def resolve_existing_file(self, filename: str) -> Path | None:
        try:
            destination = self._resolve_destination(filename)
        except ValidationError:
            return None
        if destination.is_file():
            return destination
        return None

    def _resolve_destination(self, filename: str) -> Path:
        safe_name = Path(str(filename or "")).name
        if safe_name != filename or ".." in safe_name or safe_name in {".", ".."}:
            raise ValidationError("Invalid installer filename.", details={"field": "file"})
        if Path(safe_name).suffix.lower() not in _ALLOWED_EXTENSIONS:
            raise ValidationError("Invalid installer filename.", details={"field": "file"})
        destination = (self._storage_root / safe_name).resolve()
        root = self._storage_root.resolve()
        try:
            destination.relative_to(root)
        except ValueError as exc:
            raise ValidationError("Invalid installer filename.", details={"field": "file"}) from exc
        return destination
