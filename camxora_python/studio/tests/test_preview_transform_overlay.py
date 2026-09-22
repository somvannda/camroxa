"""Preview transform overlay — canvas hit targets and drag selection."""

from __future__ import annotations

from PySide6.QtCore import QRect

from studio.core.models import Clip, MediaAsset, Track, new_id
from studio.core.playlist_scene_sync import SCENE_BACKGROUND
from studio.ui.preview_transform_overlay import PreviewTransformOverlay


def test_transform_overlay_uses_selected_image_without_playhead_active(qtbot, tmp_path):
    from core.project_state import ProjectState

    png = tmp_path / "bg.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10"
        b"\x08\x02\x00\x00\x00\x90\x91h6\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    state = ProjectState()
    media = MediaAsset(
        id="img1",
        name="bg",
        type="image",
        path=str(png),
        width=16,
        height=16,
    )
    state.add_media(media)
    track = Track(id="t1", name="Background", type="video", scene_role=SCENE_BACKGROUND)
    clip = Clip(
        id="c1",
        track_id=track.id,
        kind="image",
        label="Scene background",
        media_id=media.id,
        start=0.0,
        duration=10.0,
        scene_role=SCENE_BACKGROUND,
        fit_mode="cover",
    )
    track.clips.append(clip)
    state.project.tracks.append(track)
    state.select_clip(clip.id)
    state.playhead = 5.0

    overlay = PreviewTransformOverlay(state)
    qtbot.addWidget(overlay)
    overlay.set_canvas_rect(QRect(0, 0, 640, 360))

    selected = overlay._selected_visual_clip()
    assert selected is not None
    assert selected.id == clip.id
    assert not overlay._clip_rect.isEmpty()
