"""Defensive theft-vector suite for protected playback.

These cases try the same *classes* of scrape a Range-stitcher or DevTools
save-as would use (open-ended Range, download/lyrics URLs, ciphertext
concatenation, origin URL leaks). They assert the API does **not** hand back
a playable MP3/WAV/LRC/SRT.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.exceptions import ForbiddenError, NotFoundError, ValidationError
from platform_api.main import create_app
from platform_api.middleware.auth import _is_unconfirmed_path_allowed
from platform_api.services.audio_origin_proxy import (
    bounded_mp3_response,
    clamp_stream_range,
    is_camxora_audio_proxy_url,
)
from platform_api.services.audio_packager import (
    MAGIC_ORIGINAL,
    MAGIC_PACKAGE,
    decrypt_original,
    encrypt_original,
    iter_encrypted_chunks,
    looks_like_camxora_audio,
    new_content_key,
    package_chunks,
)
from platform_api.services.content_license_service import ContentLicenseService
from platform_api.services.streaming_catalog_service import StreamingCatalogService
from platform_api.services.web_music_service import WebMusicService

_PLAY_CHUNK = 256 * 1024
_TASK_ID = "1aa9fa4b-dc50-4650-9291-becdd9c4882f"
_TRACK_ID = "441cb4bf-f013-4c88-8ea1-9d17499b1762"

# 512 start offsets × 2 Range shapes = 1024 clamp cases (the stitcher loop).
_RANGE_STARTS = tuple(range(0, 1_048_576, 2048))
_RANGE_HEADERS = tuple(
    header
    for start in _RANGE_STARTS
    for header in (f"bytes={start}-", f"bytes={start}-{start + 10_000_000}")
)


def _looks_like_playable_audio(data: bytes) -> bool:
    if len(data) < 3:
        return False
    if data.startswith((b"ID3", b"RIFF", b"OggS", b"fLaC", b"\x1aE\xdf\xa3")):
        return True
    if data[4:8] == b"ftyp":
        return True
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True
    return False


def _looks_like_lyrics_export(data: bytes) -> bool:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    stripped = text.lstrip("\ufeff \t\r\n")
    if stripped.startswith("[") and ":" in stripped[:16]:
        return True
    return " --> " in stripped[:120]


def _assert_not_stolen_media(data: bytes) -> None:
    assert not _looks_like_playable_audio(data), "ciphertext looked like MP3/WAV"
    assert not _looks_like_lyrics_export(data), "ciphertext looked like LRC/SRT"
    assert not data.startswith(b"ID3")
    assert b"cdn1.suno.ai" not in data


# ---------------------------------------------------------------------------
# Range stitcher: each request is clamped; one shot cannot take the whole file
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("range_header", _RANGE_HEADERS)
def test_range_stitcher_headers_are_clamped_to_256kib(range_header: str) -> None:
    clamped = clamp_stream_range(range_header)
    assert clamped.lower().startswith("bytes=")
    spec = clamped.split("=", 1)[1]
    start_s, end_s = spec.split("-", 1)
    start, end = int(start_s), int(end_s)
    assert end >= start
    assert (end - start + 1) <= _PLAY_CHUNK


def test_one_shot_get_cannot_exfiltrate_full_plaintext_mp3() -> None:
    mp3 = b"ID3" + b"\x00" * 20 + b"\xff\xfb" + (b"frame" * 80_000)
    assert len(mp3) > _PLAY_CHUNK
    for header in (None, "", "bytes=0-", f"bytes=0-{len(mp3) - 1}", "bytes=0-999999999"):
        response = bounded_mp3_response(mp3, header)
        assert response.status_code == 206
        assert len(response.body) <= _PLAY_CHUNK
        assert len(response.body) < len(mp3)


def test_packaged_ciphertext_is_not_a_playable_file_after_chunk_save() -> None:
    """Saving license segments (or the whole CXA1 object) is not an MP3/WAV."""
    key = new_content_key()
    mp3 = b"ID3\x04\x00\x00" + b"\x00" * 30 + b"\xff\xfb" + (b"mpeg-fake-" * 40_000)
    wav = b"RIFF" + (400_000).to_bytes(4, "little") + b"WAVEfmt " + b"\x00" * 400_000
    lrc = ("[00:14.84]Verse one\n[00:18.10]Verse two\n" * 2000).encode()
    srt = ("1\n00:00:01,000 --> 00:00:04,000\nHello\n\n" * 2000).encode()
    key_id = str(uuid4())
    for plaintext in (mp3, wav, lrc, srt):
        original = encrypt_original(plaintext, key)
        package = package_chunks(plaintext, key, key_id=key_id)
        assert original.startswith(MAGIC_ORIGINAL)
        assert package.startswith(MAGIC_PACKAGE)
        assert looks_like_camxora_audio(original)
        assert looks_like_camxora_audio(package)
        _assert_not_stolen_media(original)
        _assert_not_stolen_media(package)
        glued = b"".join(iter_encrypted_chunks(package))
        _assert_not_stolen_media(glued)
        assert decrypt_original(original, key) == plaintext


def test_wrong_content_key_cannot_recover_mp3() -> None:
    key = new_content_key()
    other = new_content_key()
    mp3 = b"ID3" + b"\xff\xfb" + b"x" * 4000
    blob = encrypt_original(mp3, key)
    with pytest.raises(Exception):
        decrypt_original(blob, other)


# ---------------------------------------------------------------------------
# Play URL allowlist: download / lyrics must never be treated as playable src
# ---------------------------------------------------------------------------


_THEFT_URLS = (
    "https://cdn1.suno.ai/secret.mp3",
    "https://cdn2.suno.ai/secret.wav",
    "https://audiopipe.suno.ai/clip.mp3",
    "https://s3.us-west-004.backblazeb2.com/bucket/track.mp3",
    "https://f004.backblazeb2.com/file/camxora/track.wav",
    "https://media-sandbox.camxora.com/user/track.mp3",
    "https://music.camxora.com/static/track.mp3",
    "https://music.sandbox.camxora.com/song.wav",
    f"https://music.camxora.com/api/v1/web-music/generations/{_TASK_ID}/download",
    f"https://music.camxora.com/api/v1/web-music/generations/{_TASK_ID}/download?variant=ok",
    f"https://music.camxora.com/api/v1/web-music/generations/{_TASK_ID}/download?variant=alt",
    f"https://music.camxora.com/api/v1/web-music/generations/{_TASK_ID}/download-wav",
    f"https://music.camxora.com/api/v1/web-music/generations/{_TASK_ID}/download-wav?variant=ok",
    f"https://music.camxora.com/api/v1/web-music/generations/{_TASK_ID}/timed-lyrics",
    f"https://music.camxora.com/api/v1/web-music/generations/{_TASK_ID}/timed-lyrics?format=lrc",
    f"https://music.camxora.com/api/v1/web-music/generations/{_TASK_ID}/timed-lyrics?format=srt",
    f"/api/v1/web-music/generations/{_TASK_ID}/download",
    f"/api/v1/web-music/generations/{_TASK_ID}/download-wav",
    f"/api/v1/web-music/generations/{_TASK_ID}/timed-lyrics?format=lrc",
    f"/api/v1/web-music/generations/{_TASK_ID}/timed-lyrics?format=srt",
    "/api/v1/web-music/generations/x/download",
    "/static/track.mp3",
    "/media/track.wav",
    "blob:https://music.camxora.com/abc",
    "data:audio/mpeg;base64,SUQz",
)


@pytest.mark.parametrize("url", _THEFT_URLS)
def test_theft_urls_are_not_trusted_play_sources(url: str) -> None:
    assert is_camxora_audio_proxy_url(url) is False


@pytest.mark.parametrize(
    "url",
    (
        f"/api/v1/web-music/generations/{_TASK_ID}/stream/ok",
        f"/api/v1/web-music/generations/{_TASK_ID}/stream/alt",
        f"/api/v1/web-music/generations/{_TASK_ID}/stream?variant=ok",
        f"/api/v1/public/streaming/tracks/{_TRACK_ID}/stream",
        "/api/v1/web-music/licenses/segments/abc_DEF-123",
        "/api/v1/web-music/play/abc_DEF-123",
    ),
)
def test_player_may_only_point_at_camxora_play_paths(url: str) -> None:
    assert is_camxora_audio_proxy_url(url) is True


# ---------------------------------------------------------------------------
# Unconfirmed users cannot hit play or export
# ---------------------------------------------------------------------------


_BLOCKED_UNCONFIRMED = (
    ("GET", f"/api/v1/web-music/generations/{_TASK_ID}/stream/ok"),
    ("GET", f"/api/v1/web-music/generations/{_TASK_ID}/stream/alt"),
    ("GET", f"/api/v1/web-music/generations/{_TASK_ID}/download"),
    ("GET", f"/api/v1/web-music/generations/{_TASK_ID}/download-wav"),
    ("GET", f"/api/v1/web-music/generations/{_TASK_ID}/timed-lyrics"),
    ("GET", f"/api/v1/public/streaming/tracks/{_TRACK_ID}/stream"),
    ("GET", f"/api/v1/public/streaming/tracks/{_TRACK_ID}/play-url"),
    ("POST", "/api/v1/web-music/licenses/sessions"),
    ("POST", "/api/v1/web-music/licenses/devices/register"),
    ("GET", "/api/v1/web-music/licenses/segments/tok"),
    ("HEAD", f"/api/v1/web-music/generations/{_TASK_ID}/stream/ok"),
    ("GET", "/api/v1/web-music/play/token"),
)


@pytest.mark.parametrize(("method", "path"), _BLOCKED_UNCONFIRMED)
def test_unconfirmed_cannot_play_or_export(method: str, path: str) -> None:
    assert _is_unconfirmed_path_allowed(method, path) is False


# ---------------------------------------------------------------------------
# Export policy: other people's files, catalog, unpaid owner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_owner_cannot_export_someone_elses_task() -> None:
    pool = AsyncMock()
    task_id = uuid4()
    pool.fetchrow = AsyncMock(
        return_value={"id": task_id, "user_id": uuid4(), "source": "web_music"}
    )
    service = ContentLicenseService(pool)
    with pytest.raises(ForbiddenError, match="your own tracks"):
        await service.assert_export_access(uuid4(), task_id)


@pytest.mark.asyncio
async def test_unpaid_owner_cannot_export() -> None:
    pool = AsyncMock()
    task_id = uuid4()
    owner_id = uuid4()
    pool.fetchrow = AsyncMock(
        return_value={"id": task_id, "user_id": owner_id, "source": "web_music"}
    )
    service = ContentLicenseService(pool)
    service._active_paid = AsyncMock(return_value=False)
    with pytest.raises(ForbiddenError, match="paid subscription"):
        await service.assert_export_access(owner_id, task_id)


@pytest.mark.asyncio
async def test_packaged_create_stream_refuses_plaintext_mp3() -> None:
    service = WebMusicService.__new__(WebMusicService)
    row = {"package_status_ok": "ready", "status": "SUCCESS"}
    with pytest.raises(ValidationError, match="encrypted player"):
        await service._proxy_row(row, task_id=uuid4(), variant_key="ok", range_header="bytes=0-")


@pytest.mark.asyncio
async def test_unpackaged_create_stream_is_not_playable() -> None:
    service = WebMusicService.__new__(WebMusicService)
    row = {"package_status_ok": "none", "status": "SUCCESS"}
    with pytest.raises(ValidationError, match="still finishing"):
        await service._proxy_row(row, task_id=uuid4(), variant_key="ok", range_header="bytes=0-")


@pytest.mark.asyncio
async def test_packaged_catalog_stream_refuses_plaintext_mp3() -> None:
    service = StreamingCatalogService(pool=AsyncMock())
    service._repo.get_published_track = AsyncMock(
        return_value={"storage_key": "secret.mp3", "package_status": "ready"}
    )
    with pytest.raises(NotFoundError, match="encrypted player"):
        await service.proxy_track_audio(uuid4(), range_header="bytes=0-999999")


# ---------------------------------------------------------------------------
# JSON must not leak origin URLs (many payload shapes)
# ---------------------------------------------------------------------------


_LEAK_SNIPPETS = (
    "cdn1.suno.ai",
    "cdn2.suno.ai",
    "audiopipe.suno.ai",
    "backblazeb2.com",
    "audio_url_ok",
    "audio_url_alt",
    "suno_audio_id",
)


@pytest.mark.asyncio
async def test_task_json_strips_suno_and_storage_secrets() -> None:
    service = WebMusicService(pool=AsyncMock(), generation_service=AsyncMock(), redis=None)
    user_id = uuid4()
    task_id = uuid4()
    row = {
        "id": task_id,
        "title": "Night Drive",
        "lyrics": "[00:14.84]secret verse",
        "style": "edm",
        "model": "V5",
        "instrumental": False,
        "status": "SUCCESS",
        "error_message": None,
        "created_at": None,
        "negative_tags": None,
        "vocal_gender": None,
        "style_weight": None,
        "weirdness_constraint": None,
        "audio_weight": None,
        "image_url_ok": None,
        "image_url_alt": None,
        "duration_ok": 180,
        "duration_alt": 180,
        "package_status_ok": "ready",
        "package_status_alt": "ready",
        "packaged_storage_key_ok": "web-music/x.cxa",
        "packaged_storage_key_alt": "web-music/y.cxa",
        "b2_storage_key_ok": "web-music/x.mp3",
        "b2_storage_key_alt": "web-music/y.mp3",
        "audio_url_ok": "https://cdn1.suno.ai/stolen.mp3",
        "audio_url_alt": "https://cdn1.suno.ai/stolen-alt.wav",
    }
    payload = await service._task_payload(row, user_id)
    blob = str(payload)
    for snippet in _LEAK_SNIPPETS:
        assert snippet not in blob
    for clip in payload["clips"]:
        assert clip["audio_url"].startswith("/api/v1/web-music/generations/")
        assert "download" not in clip["audio_url"]
        assert clip["package_status"] == "ready"


# ---------------------------------------------------------------------------
# HTTP: anonymous scrape of export endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    (
        f"/api/v1/web-music/generations/{_TASK_ID}/download",
        f"/api/v1/web-music/generations/{_TASK_ID}/download?variant=ok",
        f"/api/v1/web-music/generations/{_TASK_ID}/download-wav",
        f"/api/v1/web-music/generations/{_TASK_ID}/download-wav?variant=alt",
        f"/api/v1/web-music/generations/{_TASK_ID}/timed-lyrics?format=lrc",
        f"/api/v1/web-music/generations/{_TASK_ID}/timed-lyrics?format=srt",
        f"/api/v1/web-music/generations/{_TASK_ID}/stream/ok",
        f"/api/v1/public/streaming/tracks/{_TRACK_ID}/stream",
        "/api/v1/web-music/licenses/segments/not-a-real-token",
    ),
)
async def test_anonymous_cannot_fetch_audio_or_lyrics(path: str) -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path, headers={"Range": "bytes=0-"})
    assert response.status_code in {401, 403, 404}
    _assert_not_stolen_media(response.content)


def test_range_case_count_covers_stitcher_volume() -> None:
    assert len(_RANGE_HEADERS) >= 1000
