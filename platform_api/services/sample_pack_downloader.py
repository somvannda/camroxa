"""Download sample-pack ZIP archives from Google Drive or direct URLs."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, urlparse

import httpx

from platform_api.config import get_settings
from platform_api.exceptions import ValidationError

_CHUNK_SIZE = 8 * 1024
_GDRIVE_FILE_PATTERN = re.compile(r"drive\.google\.com/file/d/([^/]+)")
_GDRIVE_FOLDER_PATTERN = re.compile(r"drive\.google\.com/(?:drive/)?folders/")
_GDRIVE_ID_PATTERN = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")
_CONFIRM_INPUT_PATTERN = re.compile(r'name="confirm"\s+value="([^"]+)"', re.I)
_UUID_INPUT_PATTERN = re.compile(r'name="uuid"\s+value="([^"]+)"', re.I)
_CONFIRM_QUERY_PATTERN = re.compile(r"confirm=([0-9A-Za-z_-]+)")
_DOWNLOAD_HREF_PATTERNS = (
    re.compile(r'id="uc-download-link"[^>]*href="([^"]+)"', re.I),
    re.compile(r'class="[^"]*uc-download-link[^"]*"[^>]*href="([^"]+)"', re.I),
    re.compile(r'id="download-form"[^>]*action="([^"]+)"', re.I),
    re.compile(r'href="(/uc\?[^"]*confirm=[^"]+)"', re.I),
)


def get_url_import_max_bytes() -> int:
    settings = get_settings()
    return max(int(settings.sample_pack_url_import_max_mb), 1) * 1024 * 1024


def extract_google_drive_id(url: str) -> str | None:
    text = str(url or "").strip()
    if _GDRIVE_FOLDER_PATTERN.search(text):
        return None
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


def validate_google_drive_source(source_value: str) -> None:
    text = str(source_value or "").strip()
    if _GDRIVE_FOLDER_PATTERN.search(text):
        raise ValidationError(
            "Google Drive folder links are not supported. "
            "Use a direct ZIP file link or upload a ZIP on the Upload ZIP tab.",
            details={"field": "source_value", "reason": "google_drive_folder"},
        )


def parse_gdrive_confirm_params(html: str, file_id: str) -> dict[str, str]:
    """Extract Google Drive virus-scan confirm params from an HTML interstitial."""
    params: dict[str, str] = {"id": file_id, "export": "download"}

    confirm_match = _CONFIRM_INPUT_PATTERN.search(html)
    if confirm_match:
        params["confirm"] = unescape(confirm_match.group(1))
    else:
        for pattern in (
            r'href="[^"]*confirm=([^&"\']+)',
            r"download_warning[^=]*=\s*['\"]?([0-9A-Za-z_-]+)",
        ):
            match = re.search(pattern, html, re.I)
            if match:
                params["confirm"] = unescape(match.group(1))
                break
        if "confirm" not in params:
            query_match = _CONFIRM_QUERY_PATTERN.search(html)
            if query_match:
                params["confirm"] = unescape(query_match.group(1))

    uuid_match = _UUID_INPUT_PATTERN.search(html)
    if uuid_match:
        params["uuid"] = unescape(uuid_match.group(1))

    if "confirm" not in params:
        params["confirm"] = "t"

    return params


def extract_gdrive_download_href(html: str) -> str | None:
    """Return a direct download URL from Google Drive confirm HTML, if present."""
    for pattern in _DOWNLOAD_HREF_PATTERNS:
        match = pattern.search(html)
        if not match:
            continue
        href = unescape(match.group(1)).replace("&amp;", "&")
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if href.startswith("/"):
            return f"https://drive.google.com{href}"
    return None


def _gdrive_html_error_message(html: str) -> str:
    lowered = html.lower()
    if "sign in" in lowered or "accounts.google.com" in lowered:
        return (
            "Google Drive file is not publicly accessible. "
            "Share it as 'Anyone with the link can view' and use a file link, not a folder link."
        )
    if "can't scan this file for viruses" in lowered or "download anyway" in lowered:
        return (
            "Google Drive returned a download confirmation page instead of the ZIP. "
            "Retry the import; if it persists, use a direct download URL."
        )
    if "sorry" in lowered and ("can't access" in lowered or "cannot access" in lowered):
        return (
            "Google Drive denied access to this file. "
            "Ensure sharing is set to 'Anyone with the link can view'."
        )
    if "file not found" in lowered or "doesn't exist" in lowered:
        return "Google Drive file was not found. Check the file link and sharing settings."
    return (
        "Google Drive returned an HTML page instead of a ZIP. "
        "Ensure the file is shared as 'Anyone with the link can view' and use a file link."
    )


def _ensure_zip_bytes(data: bytes, *, max_bytes: int) -> None:
    if not data:
        raise ValidationError("Download returned empty content.", details={"field": "source_value"})
    if len(data) > max_bytes:
        raise ValidationError(
            f"Download exceeds {max_bytes // (1024 * 1024)} MB URL import limit.",
            details={"field": "source_value", "max_bytes": max_bytes, "reason": "size_limit"},
        )
    header = data[:15]
    if header.startswith(b"<!DOCTYPE") or header.startswith(b"<html"):
        raise ValidationError(
            "Download returned HTML instead of a ZIP. Check sharing permissions or URL.",
            details={"field": "source_value", "reason": "html_response"},
        )
    if not header.startswith(b"PK"):
        raise ValidationError(
            "Download is not a ZIP archive.",
            details={"field": "source_value", "reason": "not_zip"},
        )


async def _read_stream_with_limit(response: httpx.Response, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes(_CHUNK_SIZE):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError(
                f"Download exceeds {max_bytes // (1024 * 1024)} MB URL import limit.",
                details={"field": "source_value", "max_bytes": max_bytes, "reason": "size_limit"},
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _stream_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str] | None = None,
    max_bytes: int,
) -> tuple[bytes | None, str | None]:
    async with client.stream("GET", url, params=params) as response:
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" in content_type:
            html_bytes = await response.aread()
            if len(html_bytes) > max_bytes:
                raise ValidationError(
                    f"Download exceeds {max_bytes // (1024 * 1024)} MB URL import limit.",
                    details={"field": "source_value", "max_bytes": max_bytes, "reason": "size_limit"},
                )
            return None, html_bytes.decode("utf-8", errors="replace")
        body = await _read_stream_with_limit(response, max_bytes=max_bytes)
        return body, None


def _merge_query_params(url: str, file_id: str) -> dict[str, str]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    params = {key: values[-1] for key, values in query.items() if values}
    params.setdefault("id", file_id)
    params.setdefault("export", "download")
    return params


async def _download_google_drive(file_id: str, *, timeout: float = 300.0) -> bytes:
    max_bytes = get_url_import_max_bytes()
    uc_url = "https://drive.google.com/uc"
    usercontent_url = "https://drive.usercontent.google.com/download"
    uc_params = {"export": "download", "id": file_id}

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        body, html = await _stream_get(client, uc_url, params=uc_params, max_bytes=max_bytes)
        if body is not None:
            _ensure_zip_bytes(body, max_bytes=max_bytes)
            return body

        assert html is not None
        attempts: list[tuple[str, dict[str, str] | None]] = []
        confirm_params = parse_gdrive_confirm_params(html, file_id)
        attempts.append((usercontent_url, confirm_params))

        href = extract_gdrive_download_href(html)
        if href:
            if href.startswith("https://drive.usercontent.google.com"):
                attempts.append((href, _merge_query_params(href, file_id)))
            else:
                attempts.append((href, None))

        attempts.append((uc_url, {**uc_params, "confirm": "t"}))
        attempts.append((usercontent_url, {"id": file_id, "export": "download", "confirm": "t"}))

        last_html = html
        for url, params in attempts:
            if params is None:
                attempt_body, attempt_html = await _stream_get(client, url, max_bytes=max_bytes)
            else:
                attempt_body, attempt_html = await _stream_get(
                    client,
                    url,
                    params=params,
                    max_bytes=max_bytes,
                )
            if attempt_body is not None:
                _ensure_zip_bytes(attempt_body, max_bytes=max_bytes)
                return attempt_body
            if attempt_html:
                last_html = attempt_html

        raise ValidationError(
            _gdrive_html_error_message(last_html),
            details={"field": "source_value", "reason": "google_drive_html"},
        )


async def _stream_download(url: str, *, timeout: float = 300.0) -> bytes:
    max_bytes = get_url_import_max_bytes()
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        body, html = await _stream_get(client, url, max_bytes=max_bytes)
        if html is not None:
            raise ValidationError(
                "Download returned HTML instead of a ZIP. Check the URL or sharing permissions.",
                details={"field": "source_value", "reason": "html_response"},
            )
        assert body is not None
        _ensure_zip_bytes(body, max_bytes=max_bytes)
        return body


async def download_zip_from_url(source_type: str, source_value: str) -> bytes:
    """Download a ZIP archive from Google Drive or a direct URL."""
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
        validate_google_drive_source(value)
        file_id = extract_google_drive_id(value)
        if not file_id:
            raise ValidationError(
                "Unable to parse Google Drive file id from source_value.",
                details={"field": "source_value"},
            )
        return await _download_google_drive(file_id)

    return await _stream_download(value)
