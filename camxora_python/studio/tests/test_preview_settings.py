from studio.core.models import MediaAsset, Project, Track, Clip
from studio.core.preview_settings import (
    apply_aspect_ratio,
    preview_render_size,
    preview_quality_label,
    aspect_ratio_label,
)
from studio.core.project_state import ProjectState


def test_apply_aspect_ratio_9_16():
    project = Project()
    w, h = apply_aspect_ratio(project, "9:16")
    assert w == 720
    assert h == 1280
    assert project.aspect_ratio_id == "9:16"


def test_preview_render_size_half():
    w, h = preview_render_size(1280, 720, "half")
    assert w == 640
    assert h == 360


def test_preview_render_size_full():
    w, h = preview_render_size(1280, 720, "full")
    assert w == 1280
    assert h == 720


def test_original_canvas_uses_first_clip_media():
    project = Project(
        media_library=[
            MediaAsset(id="m1", name="v", type="video", path="/v.mp4", duration=5.0, width=1920, height=1080),
        ],
        tracks=[
            Track(id="t1", type="video", name="V1", clips=[
                Clip(id="c1", track_id="t1", kind="video", label="v", start=0.0, duration=5.0, media_id="m1"),
            ]),
        ],
    )
    w, h = apply_aspect_ratio(project, "original")
    assert w == 1920
    assert h == 1080


def test_project_state_canvas_size():
    state = ProjectState()
    assert state.canvas_size() == (1280, 720)


def test_aspect_ratio_label_original():
    assert aspect_ratio_label("original") == "Original"


def test_preview_quality_label():
    assert preview_quality_label("quarter") == "1/4"
