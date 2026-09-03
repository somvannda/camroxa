from studio.render.clip_geometry import clip_dest_rect


def test_clip_dest_rect_fit_letterboxes_wide_image():
    from core.models import Clip

    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        fit_mode="fit",
    )
    x0, y0, w, h = clip_dest_rect(clip, 1600, 900, 1280, 720)
    assert w == 1280
    assert h == 720
    assert x0 == 0
    assert y0 == 0


def test_clip_dest_rect_cover_fills_canvas():
    from core.models import Clip

    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        fit_mode="cover",
    )
    x0, y0, w, h = clip_dest_rect(clip, 1600, 900, 1280, 720)
    assert w >= 1280
    assert h >= 720
    assert x0 <= 0
    assert y0 <= 0


def test_clip_dest_rect_fill_stretches_to_canvas():
    from core.models import Clip

    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        fit_mode="fill",
    )
    x0, y0, w, h = clip_dest_rect(clip, 1600, 900, 1280, 720)
    assert (x0, y0, w, h) == (0, 0, 1280, 720)


def test_clip_dest_rect_fill_respects_scale():
    from core.models import Clip

    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        fit_mode="fill",
        transform_scale=1.5,
    )
    x0, y0, w, h = clip_dest_rect(clip, 1600, 900, 1280, 720)
    assert w == 1920
    assert h == 1080


def test_clip_dest_rect_free_uses_contain_baseline():
    from core.models import Clip

    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        fit_mode="free",
    )
    x0, y0, w, h = clip_dest_rect(clip, 2000, 1000, 1280, 720)
    assert w == 1280
    assert h == 640

