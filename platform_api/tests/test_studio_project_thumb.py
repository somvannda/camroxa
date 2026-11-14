"""S04: project-card mini-timeline payload."""

from platform_api.services.web_music_service import WebMusicService


def test_thumb_maps_track_colours_and_clip_spans():
    data = {
        "lanes": [
            {"id": "a", "start": 0, "duration": 4},
            {"id": "b", "start": 4, "duration": 2},
            {"id": "c", "start": 99, "duration": 1},
        ],
        "tracks": [
            {"color": "#ff0000", "clipIds": ["a", "b"]},
            {"color": "#00ff00", "clipIds": ["missing"]},
        ],
    }
    thumb = WebMusicService._studio_thumb(data)
    assert thumb["end"] == 6
    assert thumb["tracks"][0] == {
        "c": "#ff0000",
        "clips": [{"s": 0, "d": 4}, {"s": 4, "d": 2}],
    }
    assert thumb["tracks"][1]["clips"] == []
    # A clip no track owns does not stretch the preview.
    assert thumb["end"] == 6


def test_thumb_is_bounded_and_tolerates_junk():
    tracks = [
        {"color": "#123456", "clipIds": [f"c{index}" for index in range(40)]}
        for _ in range(20)
    ]
    lanes = [
        {"id": f"c{index}", "start": index, "duration": 1} for index in range(40)
    ]
    thumb = WebMusicService._studio_thumb({"tracks": tracks, "lanes": lanes})
    assert len(thumb["tracks"]) == 12
    assert all(len(row["clips"]) <= 24 for row in thumb["tracks"])

    assert WebMusicService._studio_thumb({}) == {"tracks": [], "end": 0}
    assert WebMusicService._studio_thumb({"tracks": "no", "lanes": 7}) == {
        "tracks": [],
        "end": 0,
    }
