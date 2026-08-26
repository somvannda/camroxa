"""Proxy origin audio through the API so browsers never see Suno/B2 URLs."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from urllib.parse import urlparse
import re

import httpx
from fastapi.responses import Response, StreamingResponse

from platform_api.exceptions import NotFoundError

_CHUNK_SIZE = 64 * 1024
_PLAY_CHUNK_BYTES = 256 * 1024
_RANGE_RE = re.compile(r"bytes=(\d+)-(\d*)", re.I)
_CONTENT_RANGE_RE = re.compile(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", re.I)
_PROXY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Camxora-Platform/1.0)",
    "Accept": "audio/mpeg,application/octet-stream,*/*;q=0.8",
}
_CAMXORA_AUDIO_PROXY_RE = re.compile(
    r"^/api/v3/(?:"
    r"web-music/play/[A-Za-z0-9._-]+"
    r"|web-music/generations/[0-9a-fA-F-]+/stream(?:/(?:ok|alt))?(?:\?variant=(?:ok|alt))?"
    r"|web-music/licenses/segments/[A-Za-z0-9._-]+"
    r"|web-music/licenses/play/[A-Za-z0-9._-]+"
    r"|web-music/licenses/hls/[A-Za-z0-9._-]+(?:/index\.m3u8|/seg[0-9]+\.ts)?"
    r"|web-music/licenses/hls-key/[A-Za-z0-9._-]+"
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


def is_missing_range(range_header: str | None) -> bool:
    """True when the client asked for the whole file with no Range header."""
    return not str(range_header or "").strip()


def clamp_stream_range(range_header: str | None) -> str:
    """Bound play ranges so a scraper cannot one-shot the full MP3.

    Real players send Range and follow up 206 responses. A bare GET, or
    ``bytes=0-`` with no end, is rewritten to the first 256 KiB.
    """
    raw = str(range_header or "").strip()
    match = _RANGE_RE.search(raw) if raw else None
    if match is None:
        return f"bytes=0-{_PLAY_CHUNK_BYTES - 1}"
    start = int(match.group(1))
    end_raw = match.group(2)
    max_end = start + _PLAY_CHUNK_BYTES - 1
    if end_raw == "":
        return f"bytes={start}-{max_end}"
    end = int(end_raw)
    if end < start or end > max_end:
        end = max_end
    return f"bytes={start}-{end}"


def parse_clamped_range(range_header: str | None) -> tuple[int, int]:
    """Inclusive start/end after clamp_stream_range."""
    match = _RANGE_RE.search(clamp_stream_range(range_header))
    if match is None:
        return 0, _PLAY_CHUNK_BYTES - 1
    return int(match.group(1)), int(match.group(2))


def _playback_headers(*, start: int, end: int, total: int | str, length: int) -> dict[str, str]:
    headers = {
        "Cache-Control": "private, no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
        "Surrogate-Control": "no-store",
        "X-Accel-Buffering": "no",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{total}",
    }
    if length >= 0:
        headers["Content-Length"] = str(length)
    return headers


def slice_audio_bytes(
    data: bytes,
    range_header: str | None,
) -> tuple[bytes, dict[str, str], int]:
    """Return a 256 KiB-max slice of in-memory audio for a play request."""
    total = len(data)
    start, end = parse_clamped_range(range_header)
    if start >= total:
        headers = _playback_headers(start=0, end=0, total=total, length=0)
        headers["Content-Range"] = f"bytes */{total}"
        return b"", headers, 416
    end = min(end, total - 1)
    chunk = data[start : end + 1]
    return chunk, _playback_headers(start=start, end=end, total=total, length=len(chunk)), 206


def bounded_mp3_response(
    data: bytes,
    range_header: str | None,
    *,
    media_type: str = "audio/mpeg",
) -> Response:
    """Serve in-memory MP3 bytes as a clamped 206 play window."""
    body, headers, status = slice_audio_bytes(data, range_header)
    return Response(content=body, status_code=status, media_type=media_type, headers=headers)


async def _limited_bytes(
    response: httpx.Response,
    client: httpx.AsyncClient,
    *,
    skip: int,
    limit: int,
) -> AsyncIterator[bytes]:
    skipped = 0
    sent = 0
    try:
        async for chunk in response.aiter_bytes(chunk_size=_CHUNK_SIZE):
            if not chunk or sent >= limit:
                if sent >= limit:
                    break
                continue
            if skipped < skip:
                needed = skip - skipped
                if len(chunk) <= needed:
                    skipped += len(chunk)
                    continue
                chunk = chunk[needed:]
                skipped = skip
            remaining = limit - sent
            if len(chunk) > remaining:
                yield chunk[:remaining]
                break
            yield chunk
            sent += len(chunk)
    finally:
        await response.aclose()
        await client.aclose()


def _parse_origin_window(origin_headers: Mapping[str, str]) -> tuple[int, int | None]:
    content_range = origin_headers.get("content-range") or origin_headers.get("Content-Range")
    if content_range:
        match = _CONTENT_RANGE_RE.search(str(content_range))
        if match:
            origin_start = int(match.group(1))
            origin_total = None if match.group(3) == "*" else int(match.group(3))
            return origin_start, origin_total
    content_length = origin_headers.get("content-length") or origin_headers.get("Content-Length")
    if content_length and str(content_length).isdigit():
        return 0, int(content_length)
    return 0, None


async def proxy_origin_audio(
    origin_url: str,
    *,
    range_header: str | None = None,
) -> StreamingResponse:
    """Stream a bounded origin window to the client without exposing the origin URL."""
    url = str(origin_url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise NotFoundError("Playback source is not available.")

    start, requested_end = parse_clamped_range(range_header)
    request_headers = dict(_PROXY_HEADERS)
    request_headers["Range"] = f"bytes={start}-{requested_end}"

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

    if response.status_code == 416:
        out_headers = {
            "Cache-Control": "private, no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
            "Accept-Ranges": "bytes",
        }
        content_range = response.headers.get("content-range")
        if content_range:
            out_headers["Content-Range"] = content_range

        async def empty() -> AsyncIterator[bytes]:
            try:
                yield b""
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(empty(), status_code=416, media_type=media_type, headers=out_headers)

    origin_start, origin_total = _parse_origin_window(response.headers)
    if origin_total is not None and start >= origin_total:
        await response.aclose()
        await client.aclose()
        headers = _playback_headers(start=0, end=0, total=origin_total, length=0)
        headers["Content-Range"] = f"bytes */{origin_total}"
        return Response(content=b"", status_code=416, media_type=media_type, headers=headers)

    if origin_total is not None:
        requested_end = min(requested_end, origin_total - 1)
    limit = max(0, requested_end - start + 1)
    skip = max(0, start - origin_start)
    total_s: int | str = origin_total if origin_total is not None else "*"
    out_headers = _playback_headers(
        start=start,
        end=requested_end,
        total=total_s,
        length=limit if origin_total is not None else -1,
    )
    if origin_total is None:
        out_headers.pop("Content-Length", None)

    return StreamingResponse(
        _limited_bytes(response, client, skip=skip, limit=limit),
        status_code=206,
        media_type=media_type,
        headers=out_headers,
    )
