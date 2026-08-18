"""Proxy origin audio through the API so browsers never see Suno/B2 URLs."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from urllib.parse import urlparse
import re

import httpx
from fastapi.responses import StreamingResponse

from platform_api.exceptions import NotFoundError

_CHUNK_SIZE = 64 * 1024
_PROXY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Camxora-Platform/1.0)",
    "Accept": "audio/mpeg,application/octet-stream,*/*;q=0.8",
}
_CAMXORA_AUDIO_PROXY_RE = re.compile(
    r"^/api/v1/(?:"
    r"web-music/play/[A-Za-z0-9._-]+"
    r"|web-music/generations/[0-9a-fA-F-]+/stream(?:/(?:ok|alt))?(?:\?variant=(?:ok|alt))?"
    r"|public/streaming/tracks/[0-9a-fA-F-]+/stream"
    r")$"
)


def is_camxora_audio_proxy_url(url: str | None) -> bool:
    """True when the URL is a Camxora play/stream proxy, not Suno/B2."""
    text = str(url or "").strip()
    if not text:
        return False
    path = text
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        path = parsed.path
        if parsed.query:
            path = f"{path}?{parsed.query}"
    return bool(_CAMXORA_AUDIO_PROXY_RE.match(path))


def is_initial_play_range(range_header: str | None) -> bool:
    """True when this request is the start of a play (not a mid-file seek)."""
    if not range_header:
        return True
    return range_header.strip().lower().startswith("bytes=0-")


def _safe_response_headers(origin_headers: Mapping[str, str]) -> dict[str, str]:
    headers: dict[str, str] = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
        "Accept-Ranges": "bytes",
    }
    mapping = {
        "content-range": "Content-Range",
        "content-length": "Content-Length",
        "accept-ranges": "Accept-Ranges",
    }
    for source_key, dest_key in mapping.items():
        value = origin_headers.get(source_key)
        if value:
            headers[dest_key] = value
    return headers


async def proxy_origin_audio(
    origin_url: str,
    *,
    range_header: str | None = None,
) -> StreamingResponse:
    """Stream origin bytes to the client without exposing the origin URL."""
    url = str(origin_url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise NotFoundError("Playback source is not available.")

    request_headers = dict(_PROXY_HEADERS)
    if range_header:
        request_headers["Range"] = range_header

    client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
        headers=_PROXY_HEADERS,
    )
    try:
        request = client.build_request("GET", url, headers=request_headers)
        response = await client.send(request, stream=True)
    except Exception:
        await client.aclose()
        raise NotFoundError("Playback source is not available.") from None

    if response.status_code not in {200, 206, 416}:
        await response.aclose()
        await client.aclose()
        raise NotFoundError("Playback source is not available.")

    media_type = str(response.headers.get("content-type") or "audio/mpeg").split(";")[0].strip()
    if not media_type or media_type == "application/octet-stream":
        media_type = "audio/mpeg"
    out_headers = _safe_response_headers(response.headers)
    status_code = response.status_code

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_bytes(chunk_size=_CHUNK_SIZE):
                if chunk:
                    yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        body(),
        status_code=status_code,
        media_type=media_type,
        headers=out_headers,
    )
