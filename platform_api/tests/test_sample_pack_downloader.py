from __future__ import annotations

import io
import zipfile
from typing import Any

import httpx
import pytest

from platform_api.config import Settings
from platform_api.exceptions import ValidationError
from platform_api.services import sample_pack_downloader as downloader


def _zip_bytes(payload: bytes = b"png") -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr("one.png", payload)
    return out.getvalue()


class _FakeStreamResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        content_type: str = "application/zip",
        body: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._content_type = content_type
        self._body = body
        self.headers = {"content-type": content_type, **(headers or {})}
        self.request = httpx.Request("GET", "https://example.com")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request)
            raise httpx.HTTPStatusError("error", request=self.request, response=response)

    async def aread(self) -> bytes:
        return self._body

    async def aiter_bytes(self, chunk_size: int = 8192):
        for index in range(0, len(self._body), chunk_size):
            yield self._body[index : index + chunk_size]


class _FakeStreamContext:
    def __init__(self, response: _FakeStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeStreamResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeAsyncClient:
    def __init__(self, handler) -> None:
        self._handler = handler

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def stream(self, method: str, url: str, *, params: dict[str, str] | None = None):
        response = self._handler(method, url, params or {})
        return _FakeStreamContext(response)


def test_parse_gdrive_confirm_params_from_input_fields() -> None:
    html = """
    <form>
      <input type="hidden" name="confirm" value="abc123">
      <input type="hidden" name="uuid" value="uuid-1">
    </form>
    """
    params = downloader.parse_gdrive_confirm_params(html, "file123")
    assert params == {
        "id": "file123",
        "export": "download",
        "confirm": "abc123",
        "uuid": "uuid-1",
    }


def test_parse_gdrive_confirm_params_from_href_and_download_warning() -> None:
    html = """
    <a id="uc-download-link"
       href="/uc?export=download&amp;confirm=token456&amp;id=file123">Download</a>
    """
    params = downloader.parse_gdrive_confirm_params(html, "file123")
    assert params["confirm"] == "token456"
    assert params["id"] == "file123"


def test_parse_gdrive_confirm_params_defaults_to_t() -> None:
    params = downloader.parse_gdrive_confirm_params("<html></html>", "file123")
    assert params["confirm"] == "t"


def test_extract_gdrive_download_href_from_uc_download_link() -> None:
    html = """
    <a id="uc-download-link"
       href="https://drive.usercontent.google.com/download?id=file123&amp;confirm=t">
      Download
    </a>
    """
    href = downloader.extract_gdrive_download_href(html)
    assert href == "https://drive.usercontent.google.com/download?id=file123&confirm=t"


def test_gdrive_html_error_message_detects_permission_issue() -> None:
    message = downloader._gdrive_html_error_message(
        "<html>Sign in to continue to Google Drive</html>"
    )
    assert "not publicly accessible" in message


def test_get_url_import_max_bytes_uses_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        downloader,
        "get_settings",
        lambda: Settings(sample_pack_url_import_max_mb=256),
    )
    assert downloader.get_url_import_max_bytes() == 256 * 1024 * 1024


@pytest.mark.asyncio
async def test_download_google_drive_small_file_direct(monkeypatch) -> None:
    zip_body = _zip_bytes()

    def handler(method: str, url: str, params: dict[str, str]) -> _FakeStreamResponse:
        assert url == "https://drive.google.com/uc"
        assert params["id"] == "abc123"
        return _FakeStreamResponse(content_type="application/zip", body=zip_body)

    monkeypatch.setattr(downloader.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(handler))
    body = await downloader._download_google_drive("abc123")
    assert body == zip_body


@pytest.mark.asyncio
async def test_download_google_drive_large_file_uses_confirm_token(monkeypatch) -> None:
    zip_body = _zip_bytes(b"x" * 1024)
    calls: list[tuple[str, dict[str, str]]] = []
    confirm_html = """
    <html><body>
      <input type="hidden" name="confirm" value="bigfile-token">
      <input type="hidden" name="uuid" value="scan-uuid">
    </body></html>
    """

    def handler(method: str, url: str, params: dict[str, str]) -> _FakeStreamResponse:
        calls.append((url, dict(params)))
        if url == "https://drive.google.com/uc" and "confirm" not in params:
            return _FakeStreamResponse(content_type="text/html", body=confirm_html.encode())
        if url == "https://drive.usercontent.google.com/download":
            assert params.get("confirm") == "bigfile-token"
            assert params.get("uuid") == "scan-uuid"
            return _FakeStreamResponse(content_type="application/zip", body=zip_body)
        return _FakeStreamResponse(content_type="text/html", body=b"<html>unexpected</html>")

    monkeypatch.setattr(downloader.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(handler))
    body = await downloader._download_google_drive("abc123")
    assert body == zip_body
    assert calls[0][0] == "https://drive.google.com/uc"
    assert calls[1][0] == "https://drive.usercontent.google.com/download"


@pytest.mark.asyncio
async def test_download_google_drive_enforces_size_limit(monkeypatch) -> None:
    monkeypatch.setattr(
        downloader,
        "get_settings",
        lambda: Settings(sample_pack_url_import_max_mb=1),
    )
    oversized = _zip_bytes(b"x" * (2 * 1024 * 1024))

    def handler(method: str, url: str, params: dict[str, str]) -> _FakeStreamResponse:
        return _FakeStreamResponse(content_type="application/zip", body=oversized)

    monkeypatch.setattr(downloader.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(handler))

    with pytest.raises(ValidationError, match="1 MB URL import limit"):
        await downloader._download_google_drive("abc123")


@pytest.mark.asyncio
async def test_download_google_drive_html_permission_error(monkeypatch) -> None:
    html = "<html>Sign in to continue to Google Drive</html>"

    def handler(method: str, url: str, params: dict[str, str]) -> _FakeStreamResponse:
        return _FakeStreamResponse(content_type="text/html", body=html.encode())

    monkeypatch.setattr(downloader.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(handler))

    with pytest.raises(ValidationError, match="not publicly accessible"):
        await downloader._download_google_drive("abc123")


def test_assert_public_http_url_rejects_private_and_bad_schemes() -> None:
    for bad in (
        "http://127.0.0.1/x",
        "http://10.0.0.5/x",
        "http://192.168.1.1/x",
        "http://169.254.169.254/latest/meta-data",
        "ftp://example.com/x",
        "file:///etc/passwd",
    ):
        with pytest.raises(ValidationError):
            downloader._assert_public_http_url(bad)


def test_assert_public_http_url_accepts_public_ip() -> None:
    downloader._assert_public_http_url("https://1.1.1.1/pack.zip")


@pytest.mark.asyncio
async def test_stream_download_rejects_html(monkeypatch) -> None:
    def handler(method: str, url: str, params: dict[str, str]) -> _FakeStreamResponse:
        return _FakeStreamResponse(content_type="text/html", body=b"<html>nope</html>")

    monkeypatch.setattr(downloader, "_assert_public_http_url", lambda url: None)
    monkeypatch.setattr(downloader.httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(handler))

    with pytest.raises(ValidationError, match="HTML instead of a ZIP"):
        await downloader._stream_download("https://example.com/pack.zip")
