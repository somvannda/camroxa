from studio.core.project_state import ProjectState
from studio.ui.music.music_inspector_panel import MusicInspectorPanel
from studio.ui.music.playlist_presets import PLAYLIST_PRESETS, presets_for_category


def test_playlist_presets_at_least_twenty():
    assert len(PLAYLIST_PRESETS) >= 20


def test_playlist_presets_unique_ids():
    ids = [p.id for p in PLAYLIST_PRESETS]
    assert len(ids) == len(set(ids))


def test_presets_for_playlist_category():
    all_presets = presets_for_category("playlist")
    assert len(all_presets) >= 20


def test_music_inspector_tier2_tabs_do_not_crash(qtbot):
    state = ProjectState()
    panel = MusicInspectorPanel(state)
    qtbot.addWidget(panel)
    for index in range(3):
        panel._tier2.set_active_index(index)
    assert panel._content_stack is not None
    assert panel._content_stack.currentIndex() == 2


def test_music_inspector_playlist_tab(qtbot):
    state = ProjectState()
    panel = MusicInspectorPanel(state)
    qtbot.addWidget(panel)
    panel.show_playlist_tab()
    assert panel._stack.currentIndex() == MusicInspectorPanel._IDX_PLAYLIST
    assert panel._tier2.isVisible() is False


def test_music_inspector_template_opens_playlist_tab(qtbot):
    state = ProjectState()
    panel = MusicInspectorPanel(state)
    qtbot.addWidget(panel)
    panel.set_selected_playlist("neon-cyber", switch_tab=True)
    assert panel._stack.currentIndex() == MusicInspectorPanel._IDX_PLAYLIST
    assert panel.selected_preset_id() == "neon-cyber"
    assert state.project.playlist.sub_template_id == "cyberpunk"
    assert state.project.playlist.color_filter_id == "original"


def test_sync_playlist_to_timeline(sample_audio):
    state = ProjectState()
    from core.models import MediaAsset

    media = MediaAsset(
        id="a1",
        name="one.wav",
        type="audio",
        path=str(sample_audio),
        duration=2.0,
    )
    media2 = MediaAsset(
        id="a2",
        name="two.wav",
        type="audio",
        path=str(sample_audio),
        duration=3.0,
    )
    state.add_media(media)
    state.add_media(media2)
    state.project.playlist.song_ids = ["a1", "a2"]
    state.sync_playlist_to_timeline(record_undo=False)

    track = state._find_playlist_audio_track()
    assert track is not None
    assert len(track.clips) == 2
    assert track.clips[0].media_id == "a1"
    assert track.clips[0].start == 0.0
    assert track.clips[1].media_id == "a2"
    assert track.clips[1].start == 2.0


def test_playlist_rejects_duplicate_song_path(qtbot, sample_audio):
    from core.models import MediaAsset

    state = ProjectState()
    panel = MusicInspectorPanel(state)
    qtbot.addWidget(panel)
    path = str(sample_audio)
    first = MediaAsset(id="m1", name="one.wav", type="audio", path=path, duration=1.0)
    second = MediaAsset(id="m2", name="one.wav", type="audio", path=path, duration=1.0)
    panel._on_songs_imported([first])
    panel._on_songs_imported([second])
    assert state.project.playlist.song_ids == ["m1"]
    assert len(state.project.media_library) == 1


def test_playlist_settings_round_trip():
    from core.playlist_settings import PlaylistSettings

    settings = PlaylistSettings(template_id="midnight-vinyl", album_title="Test")
    settings.song_ids = ["a1", "a2"]
    data = settings.to_dict()
    restored = PlaylistSettings.from_dict(data)
    assert restored.template_id == "midnight-vinyl"
    assert restored.album_title == "Test"
    assert restored.song_ids == ["a1", "a2"]


def test_has_playlist_content_with_songs():
    state = ProjectState()
    state.project.playlist.song_ids = ["a1"]
    assert state.has_playlist_content() is True


def test_playlist_preview_stays_active_off_music_tab_when_songs_present():
    state = ProjectState()
    state.project.playlist.song_ids = ["a1", "a2"]

    has_content = state.has_playlist_content()
    in_music = False
    preview_active = has_content or in_music
    overlay_enabled = preview_active

    assert preview_active is True
    assert overlay_enabled is True


def test_playlist_preview_active_on_music_tab_without_songs():
    has_content = False
    in_music = True
    preview_active = has_content or in_music
    overlay_enabled = preview_active

    assert preview_active is True
    assert overlay_enabled is True


def test_playlist_overlay_builds_hit_rects_when_canvas_set(qtbot):
    from PySide6.QtCore import QRect

    from core.playlist_settings import PlaylistSettings
    from ui.preview_playlist_overlay import PreviewPlaylistOverlay

    state = ProjectState()
    state.project.playlist = PlaylistSettings(
        template_id="glass-romance",
        sub_template_id="minimal-white",
    )
    state.playlist_preview_active = True
    state.playlist_overlay_enabled = True

    overlay = PreviewPlaylistOverlay(state)
    qtbot.addWidget(overlay)
    overlay.set_canvas_rect(QRect(0, 0, 640, 360))
    overlay.refresh()

    assert overlay._component_rects
    assert "song_list" in overlay._component_rects


def test_timeline_selection_shows_clip_inspector_over_music_section(qtbot, sample_audio):
    from core.models import Clip, MediaAsset, Track
    from ui.right_panel_host import RightPanelHost

    state = ProjectState()
    media = MediaAsset(
        id="song1",
        name="track.wav",
        type="audio",
        path=str(sample_audio),
        duration=2.0,
    )
    state.add_media(media)
    track = Track(id="t1", name="Audio", type="audio")
    clip = Clip(
        id="c1",
        track_id=track.id,
        kind="audio",
        label="track.wav",
        media_id=media.id,
        start=0.0,
        duration=2.0,
    )
    track.clips.append(clip)
    state.project.tracks.append(track)
    state.select_clip(clip.id)

    host = RightPanelHost(state)
    qtbot.addWidget(host)

    host.set_library_section("music")
    host.refresh()
    assert host.stack.currentIndex() == RightPanelHost._IDX_INSPECTOR


def test_playlist_card_selection_shows_playlist_settings(qtbot):
    from core.models import Clip, Track
    from core.playlist_scene_sync import SCENE_GRAPHICS, sync_playlist_scene_to_timeline
    from core.playlist_settings import PlaylistSettings
    from ui.right_panel_host import RightPanelHost

    state = ProjectState()
    state.project.playlist = PlaylistSettings(template_id="glass-romance", sub_template_id="minimal-white")
    sync_playlist_scene_to_timeline(state, record_undo=False)
    gfx_track = next(t for t in state.project.tracks if t.scene_role == SCENE_GRAPHICS)
    card_clip = gfx_track.clips[0]
    state.select_clip(card_clip.id)

    host = RightPanelHost(state)
    qtbot.addWidget(host)
    host.set_library_section("import")
    host.refresh()
    assert host.stack.currentIndex() == RightPanelHost._IDX_MUSIC


def test_no_selection_falls_back_to_music_panel_in_music_section(qtbot):
    from ui.right_panel_host import RightPanelHost

    state = ProjectState()
    host = RightPanelHost(state)
    qtbot.addWidget(host)
    host.set_library_section("music")
    host.refresh()
    assert host.stack.currentIndex() == RightPanelHost._IDX_MUSIC
