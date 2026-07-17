"""Download sample-pack ZIP archives from Google Drive or direct URLs."""

from __future__ import annotations

import re
from html import unescape

import httpx

from platform_api.exceptions import ValidationError

_CHUNK_SIZE = 8 * 1024
_MAX_URL_IMPORT_BYTES = 100 * 1024 * 1024
_GDRIVE_FILE_PATTERN = re.compile(r"drive\.google\.com/file/d/([^/]+)")
_GDRIVE_ID_PATTERN = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")


def extract_google_drive_id(url: str) -> str | None:
    text = str(url or "").strip()
    match = _GDRIVE_FILE_PATTERN.search(text)
    if match:
        return match.group(1)
    if "drive.google.com" in text or "drive.usercontent.google.com" in text:
        id_match = _GDRIVE_ID_PATTERN.search(text)
        if id_match:
            return id_match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", text):
        return text
    return None


def _ensure_zip_bytes(data: bytes) -> None:
    if not data:
        raise ValidationError("Download returned empty content.", details={"field": "source_value"})
    if len(data) > _MAX_URL_IMPORT_BYTES:
        raise ValidationError(
            f"Download exceeds {_MAX_URL_IMPORT_BYTES // (1024 * 1024)} MB URL import limit.",
            details={"field": "source_value", "max_bytes": _MAX_URL_IMPORT_BYTES},
        )
    header = data[:15]
    if header.startswith(b"<!DOCTYPE") or header.startswith(b"<html"):
        raise ValidationError(
            "Download returned HTML instead of a ZIP. Check sharing permissions or URL.",
            details={"field": "source_value"},
        )


async def _download_google_drive(file_id: str, *, timeout: float = 300.0) -> bytes:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        first = await client.get(
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

            response = await client.get(
                "https://drive.usercontent.google.com/download",
                params=params,
            )
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            if "text/html" in content_type:
                raise ValidationError(
                    "Google Drive returned an HTML page instead of a ZIP. "
                    "Ensure the file is shared as 'Anyone with the link can view'.",
                    details={"field": "source_value"},
                )
            body = response.content
        else:
            body = first.content

    _ensure_zip_bytes(body)
    return body


async def _stream_download(url: str, *, timeout: float = 300.0) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(_CHUNK_SIZE):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _MAX_URL_IMPORT_BYTES:
                    raise ValidationError(
                        f"Download exceeds {_MAX_URL_IMPORT_BYTES // (1024 * 1024)} MB URL import limit.",
                        details={"field": "source_value", "max_bytes": _MAX_URL_IMPORT_BYTES},
                    )
                chunks.append(chunk)
    body = b"".join(chunks)
    _ensure_zip_bytes(body)
    return body


async def download_zip_from_url(source_type: str, source_value: str) -> bytes:
    """Download a ZIP archive from Google Drive or a direct URL (max 100 MB)."""
    normalized_type = str(source_type or "").strip().lower()
    value = str(source_value or "").strip()
    if not value:
        raise ValidationError("source_value is required.", details={"field": "source_value"})
    if normalized_type not in {"google_drive", "url"}:
        raise ValidationError(
            "source_type must be google_drive or url.",
            details={"field": "source_type"},
        )

    if normalized_type == "google_drive":
        file_id = extract_google_drive_id(value)
        if not file_id:
            raise ValidationError(
                "Unable to parse Google Drive file id from source_value.",
                details={"field": "source_value"},
            )
        return await _download_google_drive(file_id)

    return await _stream_download(value)
