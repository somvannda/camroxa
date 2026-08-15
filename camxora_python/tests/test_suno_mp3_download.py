"""Suno CDN MP3 preference and MPEG sniffing."""

from __future__ import annotations

from pathlib import Path

from shared.lib.suno_mp3_download import (
    file_looks_like_mpeg_audio,
    payload_is_mpeg_audio,
    prefer_suno_mpeg_cdn_url,
)


def test_prefer_suno_mpeg_cdn_url_rewrites_m4a() -> None:
    clip_id = "441cb4bf-f013-4c88-8ea1-9d17499b1762"
    assert prefer_suno_mpeg_cdn_url(f"https://cdn1.suno.ai/{clip_id}.m4a") == (
        f"https://cdn1.suno.ai/{clip_id}.mp3"
    )
    assert prefer_suno_mpeg_cdn_url(f"https://cdn1.suno.ai/{clip_id}.mp3") == (
        f"https://cdn1.suno.ai/{clip_id}.mp3"
    )
    assert prefer_suno_mpeg_cdn_url("https://cdn.example.com/clip.m4a") == (
        "https://cdn.example.com/clip.m4a"
    )


def test_payload_is_mpeg_audio(tmp_path: Path) -> None:
    mpeg = b"ID3" + b"\x00" * 300
    opus = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 300
    assert payload_is_mpeg_audio(mpeg) is True
    assert payload_is_mpeg_audio(opus) is False
    mpeg_path = tmp_path / "ok.mp3"
    mpeg_path.write_bytes(mpeg)
    opus_path = tmp_path / "opus.mp3"
    opus_path.write_bytes(opus)
    assert file_looks_like_mpeg_audio(mpeg_path) is True
    assert file_looks_like_mpeg_audio(opus_path) is False
    assert file_looks_like_mpeg_audio(tmp_path / "missing.mp3") is False
