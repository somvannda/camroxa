from studio.core.models import Clip, MediaAsset, Project, Track, new_id


def test_new_id_has_prefix_and_is_unique():
    a, b = new_id("clip"), new_id("clip")
    assert a.startswith("clip_")
    assert a != b


def test_clip_end_property():
    clip = Clip(id="c1", track_id="t1", kind="video", label="x", start=2.0, duration=3.5)
    assert clip.end == 5.5


def test_media_asset_round_trip():
    media = MediaAsset(id="m1", name="clip.mp4", type="video", path="/tmp/clip.mp4", duration=12.3, width=1920, height=1080)
    data = media.to_dict()
    restored = MediaAsset.from_dict(data)
    assert restored == media


def test_track_round_trip_with_clips():
    clip = Clip(id="c1", track_id="t1", kind="text", label="Hi", start=0.0, duration=4.0, text="Hi", color="#fff", size=40, x=0.5, y=0.5)
    track = Track(id="t1", type="overlay", name="Overlay 1", clips=[clip])
    data = track.to_dict()
    restored = Track.from_dict(data)
    assert restored.id == track.id
    assert restored.clips[0].text == "Hi"
    assert restored.clips[0].size == 40


def test_project_round_trip():
    media = MediaAsset(id="m1", name="a.mp4", type="video", path="/a.mp4", duration=5.0)
    clip = Clip(id="c1", track_id="t1", kind="video", label="a.mp4", start=0.0, duration=5.0, media_id="m1")
    track = Track(id="t1", type="video", name="Video 1", clips=[clip])
    project = Project(name="My Project", tracks=[track], media_library=[media], px_per_sec=90.0, duration=5.0)

    data = project.to_dict()
    restored = Project.from_dict(data)

    assert restored.name == "My Project"
    assert restored.px_per_sec == 90.0
    assert len(restored.tracks) == 1
    assert len(restored.media_library) == 1
    assert restored.tracks[0].clips[0].media_id == "m1"
