from pathlib import Path

from studio.media.video_source import VideoSource, VideoSourceCache


def test_video_source_reads_frame(sample_video: Path):
    source = VideoSource(str(sample_video))
    try:
        assert source.is_open
        frame = source.get_frame_rgb(0.5)
        assert frame is not None
        assert frame.shape == (48, 64, 3)
    finally:
        source.release()


def test_video_source_sequential_reads_do_not_reseek(sample_video: Path):
    source = VideoSource(str(sample_video))
    try:
        first = source.get_frame_rgb(0.0)
        second = source.get_frame_rgb(1.0 / source.fps)
        assert first is not None
        assert second is not None
    finally:
        source.release()


def test_video_source_cache_reuses_instance(sample_video: Path):
    cache = VideoSourceCache()
    a = cache.get("m1", str(sample_video))
    b = cache.get("m1", str(sample_video))
    assert a is b
    cache.release_all()
