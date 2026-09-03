import numpy as np

from studio.core.models import Clip
from studio.render.text_renderer import _hex_to_rgb, draw_text_overlay


def _make_clip(**overrides) -> Clip:
    defaults = dict(
        id="c1", track_id="t1", kind="text", label="Hi",
        start=0.0, duration=4.0, text="HELLO", color="#ffffff", size=40, x=0.5, y=0.5,
    )
    defaults.update(overrides)
    return Clip(**defaults)


def test_hex_to_rgb_parses_valid_and_invalid():
    assert _hex_to_rgb("#ff0000") == (255, 0, 0)
    assert _hex_to_rgb("not-a-color") == (255, 255, 255)


def test_draw_text_overlay_changes_pixels():
    canvas = np.zeros((200, 300, 3), dtype=np.uint8)
    clip = _make_clip()
    draw_text_overlay(canvas, clip, opacity=1.0)
    assert canvas.max() > 0  # something was drawn


def test_draw_text_overlay_noop_when_opacity_zero():
    canvas = np.zeros((200, 300, 3), dtype=np.uint8)
    clip = _make_clip()
    draw_text_overlay(canvas, clip, opacity=0.0)
    assert canvas.max() == 0


def test_draw_text_overlay_noop_when_text_empty():
    canvas = np.zeros((200, 300, 3), dtype=np.uint8)
    clip = _make_clip(text="")
    draw_text_overlay(canvas, clip, opacity=1.0)
    assert canvas.max() == 0


def test_draw_text_overlay_respects_partial_opacity():
    canvas_full = np.zeros((200, 300, 3), dtype=np.uint8)
    canvas_half = np.zeros((200, 300, 3), dtype=np.uint8)
    clip = _make_clip(color="#ffffff")
    draw_text_overlay(canvas_full, clip, opacity=1.0)
    draw_text_overlay(canvas_half, clip, opacity=0.5)
    assert canvas_half.max() < canvas_full.max()
