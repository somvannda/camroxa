from __future__ import annotations

from platform_api.clients.suno_client import _extract_clip_download_url


def test_prefers_real_mp3_over_dead_stream_host() -> None:
    # audiostream.api.box answers 200 audio/mpeg with a 0-byte body, so the real
    # tempfile MP3 (same clip id) wins even though the stream host looks durable.
    clip = {
        "id": "abc",
        "audio_url": "https://tempfile.aiquickdraw.com/r/abc.mp3",
        "stream_audio_url": "https://audiostream.api.box/stream/abc.mp3",
        "source_stream_audio_url": "https://audiostream.api.box/stream/abc.mp3",
    }
    assert _extract_clip_download_url(clip) == "https://tempfile.aiquickdraw.com/r/abc.mp3"


def test_stream_host_only_synthesizes_tempfile() -> None:
    clip = {"id": "abc", "stream_audio_url": "https://audiostream.api.box/stream/abc.mp3"}
    assert _extract_clip_download_url(clip) == "https://tempfile.aiquickdraw.com/r/abc.mp3"


def test_keeps_primary_when_not_a_tempfile_host() -> None:
    clip = {"id": "abc", "audio_url": "https://cdn.example.com/abc.mp3"}
    assert _extract_clip_download_url(clip) == "https://cdn.example.com/abc.mp3"


def test_falls_back_to_tempfile_when_no_stream_host() -> None:
    clip = {"id": "abc", "audio_url": "https://tempfile.aiquickdraw.com/r/abc.mp3"}
    assert _extract_clip_download_url(clip) == "https://tempfile.aiquickdraw.com/r/abc.mp3"
