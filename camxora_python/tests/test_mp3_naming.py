"""Tests for on-disk MP3 naming helpers."""

from __future__ import annotations

from shared.lib.channel_asset_paths import count_channel_mp3_files
from shared.lib.mp3_naming import mp3_naming_hint, mp3_suffix_for_role


def test_mp3_suffix_for_ok_and_alt_roles() -> None:
    assert mp3_suffix_for_role("OK") == "_OK.mp3"
    assert mp3_suffix_for_role("ok") == "_OK.mp3"
    assert mp3_suffix_for_role("PRIMARY") == "_OK.mp3"
    assert mp3_suffix_for_role("ALT") == "_Alt.mp3"
    assert mp3_suffix_for_role("secondary") == "_Alt.mp3"


def test_mp3_naming_hint_uses_disk_suffix() -> None:
    assert mp3_naming_hint("OK").endswith("_OK.mp3")
    assert mp3_naming_hint("ALT").endswith("_Alt.mp3")


def test_count_channel_mp3_files_respects_role_suffix(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "1. Song_OK.mp3").write_bytes(b"a")
    (run_dir / "2. Song_Alt.mp3").write_bytes(b"b")

    assert count_channel_mp3_files(str(run_dir), "OK") == 1
    assert count_channel_mp3_files(str(run_dir), "ALT") == 1
    assert count_channel_mp3_files(str(run_dir), "ok") == 1
