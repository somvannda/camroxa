import numpy as np

from studio.core.models import Clip
from studio.render.clip_geometry import align_clip_transform
from studio.render.mask import build_clip_mask


def test_align_clip_transform_left():
    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        transform_scale=0.5,
        transform_x=0.8,
        transform_y=0.5,
    )
    tx, ty = align_clip_transform(clip, "left", 200, 100, 400, 300)
    assert tx < 0.26
    assert ty == 0.5


def test_align_clip_transform_center():
    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        transform_x=0.1,
        transform_y=0.1,
    )
    tx, ty = align_clip_transform(clip, "center_h", 200, 100, 400, 300)
    assert abs(tx - 0.5) < 0.001


def test_build_clip_mask_disabled_is_full():
    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        mask_enabled=False,
    )
    mask = build_clip_mask(clip, 64, 48)
    assert mask.shape == (48, 64)
    assert np.allclose(mask, 1.0)


def test_build_clip_mask_circle_reduces_edges():
    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        mask_enabled=True,
        mask_shape="circle",
        mask_x=0.5,
        mask_y=0.5,
        mask_width=0.6,
        mask_height=0.6,
    )
    mask = build_clip_mask(clip, 100, 100)
    assert mask[0, 0] < 0.05
    assert mask[50, 50] > 0.95


def test_build_clip_mask_feather_softens_edge():
    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        mask_enabled=True,
        mask_shape="rectangle",
        mask_width=0.5,
        mask_height=0.5,
        mask_feather=40.0,
    )
    mask = build_clip_mask(clip, 80, 80)
    assert 0.0 < mask[22, 40] < 1.0


def test_build_clip_mask_invert_flips_alpha():
    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        mask_enabled=True,
        mask_shape="circle",
        mask_width=0.8,
        mask_height=0.8,
        mask_invert=False,
    )
    normal = build_clip_mask(clip, 100, 100)
    clip.mask_invert = True
    inverted = build_clip_mask(clip, 100, 100)
    assert normal[0, 0] < 0.1
    assert inverted[0, 0] > 0.9
    assert normal[50, 50] > 0.9
    assert inverted[50, 50] < 0.1


def test_build_clip_mask_split_is_triangular():
    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        mask_enabled=True,
        mask_shape="split",
        mask_width=1.0,
        mask_height=1.0,
    )
    mask = build_clip_mask(clip, 100, 100)
    assert mask[90, 90] < 0.05
    assert mask[10, 10] > 0.95


def test_build_clip_mask_filmstrip_alternates_bands():
    clip = Clip(
        id="c1",
        track_id="t1",
        kind="image",
        label="img",
        start=0.0,
        duration=5.0,
        mask_enabled=True,
        mask_shape="filmstrip",
        mask_width=1.0,
        mask_height=1.0,
    )
    mask = build_clip_mask(clip, 100, 100)
    assert mask[10, 50] > 0.95
    assert mask[30, 50] < 0.05
