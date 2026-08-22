"""Tests for AES-128 HLS packaging helpers."""

from platform_api.services.audio_packager import new_content_key
from platform_api.services.hls_packager import (
    derive_hls_aes_key,
    derive_hls_iv,
    rewrite_hls_playlist,
)


def test_derive_hls_key_material_is_stable() -> None:
    key = new_content_key()
    assert len(derive_hls_aes_key(key)) == 16
    assert len(derive_hls_iv(key)) == 16
    assert derive_hls_aes_key(key) == derive_hls_aes_key(key)
    assert derive_hls_iv(key) != derive_hls_aes_key(key)


def test_rewrite_hls_playlist_replaces_key_and_segments() -> None:
    manifest = "\n".join(
        [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            '#EXT-X-KEY:METHOD=AES-128,URI="https://camxora.invalid/hls-key",IV=0xabc',
            "#EXTINF:6.0,",
            "seg000.ts",
            "#EXT-X-ENDLIST",
        ]
    )
    out = rewrite_hls_playlist(
        manifest,
        key_url="/api/v1/web-music/licenses/hls-key/tok",
        segment_url_prefix="/api/v1/web-music/licenses/hls/tok",
    )
    assert 'URI="/api/v1/web-music/licenses/hls-key/tok"' in out
    assert "IV=0xabc" in out
    assert "/api/v1/web-music/licenses/hls/tok/seg000.ts" in out
