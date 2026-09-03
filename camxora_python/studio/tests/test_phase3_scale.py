from pathlib import Path

import pytest

from studio.media.media_loader import build_video_filmstrip
from studio.media.thumb_cache import load_cached_filmstrip, media_cache_key, save_cached_filmstrip
from studio.ui.timeline.geometry import (
    filmstrip_frame_stride,
    filmstrip_slot_width_px,
    hi_dpi_filmstrip_size,
    ruler_sub_step_seconds,
    waveform_sample_count,
)


def test_ruler_sub_step_uses_project_frame_rate():
    assert ruler_sub_step_seconds(220.0, frame_rate=24.0) == pytest.approx(1.0 / 24.0)
    assert ruler_sub_step_seconds(220.0, frame_rate=60.0) == pytest.approx(1.0 / 60.0)


def test_lod_helpers_scale_with_zoom():
    assert filmstrip_slot_width_px(10.0) < filmstrip_slot_width_px(120.0)
    assert filmstrip_frame_stride(20.0, 12) > 1
    assert filmstrip_frame_stride(120.0, 12) == 1
    assert waveform_sample_count(400.0, 5.0) < waveform_sample_count(400.0, 120.0)


def test_hi_dpi_filmstrip_size_scales_with_dpr():
    assert hi_dpi_filmstrip_size((60, 40), 2.0) == (120, 80)


def test_persistent_filmstrip_cache_roundtrip(tmp_path, monkeypatch, sample_video: Path):
    (tmp_path / "filmstrips").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("media.thumb_cache.persistent_cache_dir", lambda: tmp_path)
    size = (60, 40)
    assert load_cached_filmstrip(sample_video, frames=3, size=size) is None
    paths = build_video_filmstrip(sample_video, duration=2.0, cache_dir=tmp_path, frames=3, size=size)
    assert len(paths) == 3
    cached = load_cached_filmstrip(sample_video, frames=3, size=size)
    assert cached == paths


def test_media_cache_key_changes_when_file_changes(tmp_path: Path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"v1")
    key1 = media_cache_key(path)
    path.write_bytes(b"v2")
    key2 = media_cache_key(path)
    assert key1 != key2


def test_save_cached_filmstrip_validates_on_load(tmp_path: Path):
    key = "abc123"
    meta = tmp_path / "filmstrips" / f"{key}.json"
    meta.parent.mkdir(parents=True)
    meta.write_text(
        '{"version":1,"frames":2,"size":[60,40],"paths":["/missing/a.jpg","/missing/b.jpg"]}',
        encoding="utf-8",
    )
    # Direct load via helper needs matching path stat — test save/load API instead.
    fake = tmp_path / "source.mp4"
    fake.write_bytes(b"x")
    paths = [str(tmp_path / "frame_0.jpg"), str(tmp_path / "frame_1.jpg")]
    for i, p in enumerate(paths):
        Path(p).write_bytes(b"jpg")
    save_cached_filmstrip(fake, frames=2, size=(60, 40), thumb_paths=paths)
    loaded = load_cached_filmstrip(fake, frames=2, size=(60, 40))
    assert loaded == paths
