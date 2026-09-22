import json
from pathlib import Path

import pytest

from studio.core.models import MediaAsset
from studio.core.project_io import ProjectLoadError, load_project, save_project
from studio.core.project_state import ProjectState


@pytest.fixture
def populated_state() -> ProjectState:
    state = ProjectState()
    state.project.name = "My Movie"
    media = MediaAsset(id="m_video", name="clip.mp4", type="video", path="/clip.mp4", duration=6.0)
    state.add_media(media)
    track = state.add_track("video")
    state.add_clip_from_media(media, track, drop_time=0.0)
    text_track = state.add_track("overlay")
    state.add_text_clip(text_track, "title", drop_time=1.0)
    return state


def test_save_project_writes_json_file(populated_state: ProjectState, tmp_path: Path):
    out_path = tmp_path / "project.camxora"
    result_path = save_project(populated_state, out_path)

    assert result_path == out_path
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["format_version"] == 1
    assert payload["project"]["name"] == "My Movie"
    assert len(payload["project"]["tracks"]) == 2


def test_save_project_creates_parent_directories(populated_state: ProjectState, tmp_path: Path):
    out_path = tmp_path / "nested" / "dir" / "project.camxora"
    save_project(populated_state, out_path)
    assert out_path.exists()


def test_load_project_round_trips_tracks_clips_and_media(populated_state: ProjectState, tmp_path: Path):
    out_path = tmp_path / "project.camxora"
    save_project(populated_state, out_path)

    loaded = load_project(out_path)

    assert loaded.project.name == "My Movie"
    assert len(loaded.project.tracks) == 2
    assert len(loaded.project.media_library) == 1
    assert loaded.project.media_library[0].path == "/clip.mp4"

    video_track = next(t for t in loaded.project.tracks if t.type == "video")
    assert len(video_track.clips) == 1
    assert video_track.clips[0].media_id == "m_video"

    overlay_track = next(t for t in loaded.project.tracks if t.type == "overlay")
    assert overlay_track.clips[0].text == "Your Title Here"


def test_load_project_recalculates_duration(populated_state: ProjectState, tmp_path: Path):
    out_path = tmp_path / "project.camxora"
    save_project(populated_state, out_path)

    loaded = load_project(out_path)

    assert loaded.project.duration == pytest.approx(populated_state.project.duration)


def test_load_project_starts_with_fresh_undo_state(populated_state: ProjectState, tmp_path: Path):
    out_path = tmp_path / "project.camxora"
    save_project(populated_state, out_path)

    loaded = load_project(out_path)

    assert loaded.can_undo() is False
    assert loaded.can_redo() is False
    assert loaded.selected_clip_id is None


def test_load_project_missing_file_raises(tmp_path: Path):
    with pytest.raises(ProjectLoadError):
        load_project(tmp_path / "does_not_exist.camxora")


def test_load_project_invalid_json_raises(tmp_path: Path):
    bad_path = tmp_path / "bad.camxora"
    bad_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ProjectLoadError):
        load_project(bad_path)


def test_load_project_missing_project_key_raises(tmp_path: Path):
    bad_path = tmp_path / "bad.camxora"
    bad_path.write_text(json.dumps({"format_version": 1}), encoding="utf-8")
    with pytest.raises(ProjectLoadError):
        load_project(bad_path)


def test_load_project_malformed_project_raises(tmp_path: Path):
    bad_path = tmp_path / "bad.camxora"
    bad_path.write_text(json.dumps({"project": {"tracks": [{"id": "trk1"}]}}), encoding="utf-8")
    with pytest.raises(ProjectLoadError):
        load_project(bad_path)
