from pathlib import Path

import pytest

from studio.media.media_loader import (
    build_video_filmstrip,
    guess_media_type,
    import_files,
    probe_and_import,
)


def test_guess_media_type_by_extension():
    assert guess_media_type(Path("clip.mp4")) == "video"
    assert guess_media_type(Path("song.mp3")) == "audio"
    assert guess_media_type(Path("photo.png")) == "image"
    assert guess_media_type(Path("doc.pdf")) is None


def test_probe_video_asset(sample_video: Path, tmp_path: Path):
    asset = probe_and_import(sample_video, cache_dir=tmp_path)
    assert asset is not None
    assert asset.type == "video"
    assert asset.duration > 1.5
    assert asset.width == 64
    assert asset.height == 48
    assert asset.thumb_path is not None
    assert Path(asset.thumb_path).exists()


def test_probe_audio_asset(sample_audio: Path, tmp_path: Path):
    asset = probe_and_import(sample_audio, cache_dir=tmp_path)
    assert asset is not None
    assert asset.type == "audio"
    assert asset.duration == pytest.approx(1.5, rel=0.05)
    assert asset.sample_rate == 22050


def test_probe_image_asset(sample_image: Path, tmp_path: Path):
    asset = probe_and_import(sample_image, cache_dir=tmp_path)
    assert asset is not None
    assert asset.type == "image"
    assert asset.width == 200
    assert asset.height == 100
    assert asset.duration == 5.0
    assert asset.thumb_path is not None


def test_import_files_skips_unsupported(sample_video: Path, tmp_path: Path):
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("hello")
    assets = import_files([sample_video, unsupported], cache_dir=tmp_path)
    assert len(assets) == 1
    assert assets[0].type == "video"


def test_import_files_preserves_input_order(sample_audio: Path, sample_video: Path, tmp_path: Path):
    assets = import_files([sample_audio, sample_video], cache_dir=tmp_path)
    assert [a.type for a in assets] == ["audio", "video"]


def test_build_video_filmstrip(sample_video: Path, tmp_path: Path):
    strip = build_video_filmstrip(sample_video, duration=2.0, cache_dir=tmp_path, frames=3)
    assert len(strip) == 3
    for p in strip:
        assert Path(p).exists()
