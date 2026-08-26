"""Public desktop release endpoints (no authentication)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from platform_api.dependencies import get_db_pool, get_desktop_release_upload_service
from platform_api.services.desktop_notification_admin_service import get_published_desktop_release
from platform_api.services.desktop_release_download_stats import (
    get_download_count_for_version,
    get_total_downloads,
    increment_download_for_filename,
)

_INSTALLER_MEDIA_TYPES = {
    ".zip": "application/zip",
    ".exe": "application/vnd.microsoft.portable-executable",
    ".msi": "application/octet-stream",
}

router = APIRouter(prefix="/public", tags=["public-desktop"])


class PublicDesktopReleaseResponse(BaseModel):
    version: str
    download_url: str
    release_notes: str
    mandatory: bool = False
    published_at: str
    download_count: int = 0
    total_downloads: int = 0


@router.get(
    "/desktop-release",
    response_model=PublicDesktopReleaseResponse,
    summary="Get the latest published desktop release",
)
async def get_public_desktop_release() -> PublicDesktopReleaseResponse:
    pool = get_db_pool()
    config = await get_published_desktop_release(pool)
    if config is None:
        raise HTTPException(status_code=404, detail="No published desktop release is available.")

    version = config.version.strip()
    download_count = await get_download_count_for_version(pool, version)
    total_downloads = await get_total_downloads(pool)

    return PublicDesktopReleaseResponse(
        version=version,
        download_url=config.download_url.strip(),
        release_notes=config.release_notes.strip(),
        mandatory=config.mandatory,
        published_at=config.published_at or "",
        download_count=download_count,
        total_downloads=total_downloads,
    )


@router.get(
    "/desktop-release/files/{filename}",
    summary="Download a hosted desktop installer package",
)
async def download_desktop_release_file(filename: str) -> FileResponse:
    service = get_desktop_release_upload_service()
    path = service.resolve_existing_file(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Installer file not found.")

    try:
        await increment_download_for_filename(get_db_pool(), filename)
    except Exception:
        # Never block the download if stats persistence fails.
        pass

    extension = Path(filename).suffix.lower()
    media_type = _INSTALLER_MEDIA_TYPES.get(extension, "application/octet-stream")
    return FileResponse(
        path,
        media_type=media_type,
        filename=Path(filename).name,
    )
