"""Unit tests for DistroKid album scanning + settings."""

from __future__ import annotations

from pathlib import Path

from features.distrokid.lib.album_scanner import clean_track_title, scan_album_directory
from features.distrokid.lib.distrokid_settings import DistroKidSettings, DistroKidSettingsStore
from features.distrokid.lib.upload_history import UploadHistory
from features.video.lib.pipeline_merge import is_auto_merge_enabled_for_branch


def test_clean_track_title_strips_ok_alt() -> None:
    assert clean_track_title("1. Neon Drive_OK") == "Neon Drive"
    assert clean_track_title("2. Neon Drive_Alt") == "Neon Drive"


def test_scan_album_directory_pairs_wav(tmp_path: Path) -> None:
    (tmp_path / "1. Song_OK.mp3").write_bytes(b"mp3")
    (tmp_path / "1. Song_OK.wav").write_bytes(b"RIFF....WAVE")
    (tmp_path / "cover_th.png").write_bytes(b"png")
    album = scan_album_directory(tmp_path, album_name="Test Album")
    assert album is not None
    assert album.name == "Test Album"
    assert album.track_count == 1
    assert album.tracks[0].wav_exists
    assert album.has_thumbnail


def test_upload_history_duplicate(tmp_path: Path) -> None:
    history = UploadHistory(history_file=tmp_path / "history.json")
    history.record_success(
        directory_path=str(tmp_path / "album"),
        album_name="Night Drive",
        track_count=1,
        tracks=[{"title": "Neon", "wav_byte_size": 1000, "wav_sha256": "abc"}],
    )
    hit = history.find_duplicate(album_name="Night Drive", track_title="Neon", wav_byte_size=1000)
    assert hit is not None


def test_settings_roundtrip(tmp_path: Path) -> None:
    store = DistroKidSettingsStore(path=tmp_path / "settings.json")
    settings = DistroKidSettings(artist_name="Camxora Artist", auto_submit=True)
    settings.upload_form.primary_genre = "Pop"
    store.save(settings)
    loaded = store.load()
    assert loaded.artist_name == "Camxora Artist"
    assert loaded.auto_submit is True
    assert loaded.upload_form.primary_genre == "Pop"


def test_reel_never_auto_merges() -> None:
    settings = {"autoMergeAfterVideo": True, "autoReelAfterVideo": True}
    assert is_auto_merge_enabled_for_branch(settings, "long") is True
    assert is_auto_merge_enabled_for_branch(settings, "reel") is False
