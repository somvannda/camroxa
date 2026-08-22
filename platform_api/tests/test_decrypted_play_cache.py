"""Tests for server-side licensed play stream helpers."""

from platform_api.services.decrypted_play_cache import clear_decrypted_cache, get_decrypted, put_decrypted


def test_decrypted_play_cache_round_trip() -> None:
    clear_decrypted_cache()
    put_decrypted("storage:key", b"mp3-bytes")
    assert get_decrypted("storage:key") == b"mp3-bytes"
    assert get_decrypted("missing") is None
