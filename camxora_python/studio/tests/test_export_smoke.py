from pathlib import Path

import cv2
import pytest

from studio.core.models import MediaAsset
from studio.core.project_state import ProjectState
from studio.export.ffmpeg_export import ExportCancelled, export_project
from studio.media.ffmpeg_utils import get_ffmpeg_exe


@pytest.fixture
def small_project(sample_video: Path, sample_audio: Path) -> ProjectState:
    state = ProjectState()
    video_media = MediaAsset(id="mv", name="v.mp4", type="video", path=str(sample_video), duration=2.0, width=64, height=48)
    audio_media = MediaAsset(id="ma", name="a.wav", type="audio", path=str(sample_audio), duration=1.5, sample_rate=22050)
    state.add_media(video_media)
    state.add_media(audio_media)

    video_track = state.add_track("video")
    audio_track = state.add_track("audio")
    state.add_clip_from_media(video_media, video_track, drop_time=0.0)
    state.add_clip_from_media(audio_media, audio_track, drop_time=0.0)
    # keep the export short for test speed
    state.project.duration = 1.0
    for clip in video_track.clips:
        clip.duration = 1.0
    return state


def _probe_streams(path: Path) -> str:
    from shared.lib.subprocess_utils import run_hidden

    ffmpeg_exe = get_ffmpeg_exe()
    result = run_hidden([ffmpeg_exe, "-i", str(path)], capture_output=True, timeout=30)
    return result.stderr.decode(errors="ignore")


def test_export_produces_playable_mp4_with_video_and_audio(small_project: ProjectState, tmp_path: Path):
    output_path = tmp_path / "out.mp4"
    progress_values = []

    result_path = export_project(
        small_project,
        output_path,
        fps=10,
        width=64,
        height=48,
        progress_callback=progress_values.append,
    )

    assert result_path == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 1000

    assert progress_values, "progress callback should have been called"
    assert progress_values[-1] == pytest.approx(1.0)
    assert all(0.0 < p <= 1.0 for p in progress_values)

    cap = cv2.VideoCapture(str(output_path))
    try:
        assert cap.isOpened()
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        assert frame_count >= 8  # ~1s @ 10fps
        ok, frame = cap.read()
        assert ok
        assert frame is not None
    finally:
        cap.release()

    stream_info = _probe_streams(output_path)
    assert "Video:" in stream_info
    assert "Audio:" in stream_info


def test_export_raises_on_empty_timeline(tmp_path: Path):
    state = ProjectState()
    with pytest.raises(ValueError):
        export_project(state, tmp_path / "empty.mp4")


def test_export_cancellation_stops_early(small_project: ProjectState, tmp_path: Path):
    output_path = tmp_path / "cancelled.mp4"
    calls = {"n": 0}

    def cancel_after_first_frame() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    with pytest.raises(ExportCancelled):
        export_project(small_project, output_path, fps=10, width=64, height=48, cancel_check=cancel_after_first_frame)
