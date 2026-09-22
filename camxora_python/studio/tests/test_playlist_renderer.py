import numpy as np

from studio.core.models import MediaAsset, Project
from studio.core.playlist_layout import default_component_layout, resolve_component_layout
from studio.core.playlist_settings import PlaylistSettings
from studio.core.playlist_style import apply_style_to_settings
from studio.core.project_state import ProjectState
from studio.render.compositor import render_frame
from studio.render.playlist_renderer import draw_playlist
from studio.media.video_source import VideoSourceCache


def test_default_component_layout_respects_list_side():
    right = PlaylistSettings(list_side="right")
    left = PlaylistSettings(list_side="left")
    right_layout = default_component_layout(right)
    left_layout = default_component_layout(left)
    assert right_layout["cover"]["x"] < left_layout["cover"]["x"]


def test_resolve_component_layout_merges_custom():
    settings = PlaylistSettings()
    settings.component_layout = {"cover": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}}
    layout = resolve_component_layout(settings)
    assert layout["cover"]["x"] == 0.1
    assert layout["cover"]["h"] == 0.4
    assert "title" in layout


def test_minimal_white_layout_is_track_list_only():
    from core.playlist_layout import is_minimal_white_layout, resolve_component_layout

    settings = PlaylistSettings(sub_template_id="minimal-white")
    assert is_minimal_white_layout(settings)
    layout = resolve_component_layout(settings, canvas_w=1280, canvas_h=720)
    assert set(layout.keys()) == {"song_list"}
    card = layout["song_list"]
    assert 0.26 <= card["w"] <= 0.34
    assert card["h"] >= 0.85
    assert card["x"] >= 0.58  # default right placement


def test_minimal_white_layout_left_side():
    settings = PlaylistSettings(sub_template_id="minimal-white", list_side="left")
    layout = resolve_component_layout(settings, canvas_w=1280, canvas_h=720)
    assert layout["song_list"]["x"] < 0.12


def test_draw_playlist_idle_skips_audio_decode():
    """Playlist preview while paused must not synchronously decode audio."""
    state = ProjectState()
    state.playlist_preview_active = True
    state.is_playing = False
    state.project.playlist = PlaylistSettings(
        template_id="glass-romance",
        sub_template_id="minimal-white",
        song_ids=["m1"],
    )
    apply_style_to_settings(state.project.playlist)
    state.add_media(
        MediaAsset(
            id="m1",
            name="song.wav",
            type="audio",
            path="/song.wav",
            duration=120.0,
        )
    )

    class _FailCache:
        def get(self, *_args, **_kwargs):
            raise AssertionError("audio decode should not run for idle playlist preview")

    canvas = np.zeros((240, 320, 3), dtype=np.uint8)
    draw_playlist(canvas, state, 0.0, audio_cache=_FailCache())
    assert canvas.mean() > 0


def test_draw_playlist_minimal_white_no_cover_block():
    state = ProjectState()
    state.playlist_preview_active = True
    state.project.playlist = PlaylistSettings(
        template_id="glass-romance",
        sub_template_id="minimal-white",
    )
    apply_style_to_settings(state.project.playlist)
    canvas = np.zeros((240, 320, 3), dtype=np.uint8)
    draw_playlist(canvas, state, 0.0, audio_cache=None)
    left_mean = canvas[120, 20].mean()
    assert left_mean > 100


def test_build_playlist_background_uses_bundled_png():
    from core.playlist_assets import bundled_background_path
    from render.playlist_renderer import _build_playlist_background

    path = bundled_background_path("minimal-white")
    assert path is not None
    canvas = _build_playlist_background(
        120,
        160,
        colors={"bg_from": "#000000", "bg_to": "#ffffff"},
        bg_path=str(path),
    )
    gradient_only = _build_playlist_background(
        120,
        160,
        colors={"bg_from": "#000000", "bg_to": "#ffffff"},
        bg_path=None,
    )
    assert not np.array_equal(canvas, gradient_only)


def test_draw_playlist_renders_gradient_background():
    state = ProjectState()
    state.playlist_preview_active = True
    state.project.playlist = PlaylistSettings(
        template_id="neon-cyber",
        sub_template_id="cyberpunk",
        colors={
            "bg_from": "#ff0000",
            "bg_to": "#0000ff",
            "accent": "#00ff00",
            "accent2": "#00ff00",
            "surface": "#ffffff22",
            "text": "#ffffff",
            "muted": "#888888",
        },
    )
    canvas = np.zeros((120, 160, 3), dtype=np.uint8)
    draw_playlist(canvas, state, 0.0, audio_cache=None)
    assert canvas[0, 0, 0] > 200  # red top
    assert canvas[-1, 0, 2] > 200  # blue bottom


def test_render_frame_draws_playlist_when_active():
    state = ProjectState()
    state.playlist_preview_active = True
    state.project.playlist = PlaylistSettings(
        template_id="glass-romance",
        album_title="Test Album",
        colors={
            "bg_from": "#101020",
            "bg_to": "#050510",
            "accent": "#aabbcc",
            "accent2": "#ccddee",
            "surface": "#ffffff22",
            "text": "#ffffff",
            "muted": "#888888",
        },
    )
    cache = VideoSourceCache()
    try:
        frame = render_frame(state, 0.0, cache, width=160, height=120)
    finally:
        cache.release_all()
    assert frame.shape == (120, 160, 3)
    assert not np.all(frame == 0)


def test_draw_playlist_shows_song_names(sample_audio):
    state = ProjectState()
    media = MediaAsset(
        id="song1",
        name="My Track",
        type="audio",
        path=str(sample_audio),
        duration=2.0,
    )
    state.add_media(media)
    state.project.playlist = PlaylistSettings(
        template_id="midnight-vinyl",
        song_ids=["song1"],
        colors={
            "bg_from": "#141414",
            "bg_to": "#080808",
            "accent": "#ffffff",
            "accent2": "#888888",
            "surface": "#22222288",
            "text": "#ffffff",
            "muted": "#aaaaaa",
        },
    )
    canvas = np.zeros((200, 320, 3), dtype=np.uint8)
    draw_playlist(canvas, state, 0.5, audio_cache=None)
    assert canvas.mean() > 5
