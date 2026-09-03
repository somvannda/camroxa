import numpy as np

from studio.render.visualizer import _hex_to_rgb, _lerp_color, draw_visualizer


def test_hex_to_rgb_and_lerp():
    assert _hex_to_rgb("#00ff00") == (0, 255, 0)
    mid = _lerp_color((0, 0, 0), (100, 100, 100), 0.5)
    assert mid == (50, 50, 50)


def _bands(n=24, value=0.8):
    return np.full(n, value, dtype=np.float32)


def _wave(n=48):
    return np.sin(np.linspace(0, np.pi * 4, n)).astype(np.float32)


def test_draw_visualizer_bars_changes_pixels():
    canvas = np.zeros((200, 300, 3), dtype=np.uint8)
    draw_visualizer(canvas, "bars", _bands(), _wave(), "#7c5cff", "#26d6a4", opacity=1.0)
    assert canvas.max() > 0


def test_draw_visualizer_mirror_bars_changes_pixels():
    canvas = np.zeros((200, 300, 3), dtype=np.uint8)
    draw_visualizer(canvas, "mirror-bars", _bands(), _wave(), "#ff5470", "#ffb648", opacity=1.0)
    assert canvas.max() > 0


def test_draw_visualizer_wave_changes_pixels():
    canvas = np.zeros((200, 300, 3), dtype=np.uint8)
    draw_visualizer(canvas, "wave", _bands(0), _wave(), "#26d6a4", "#5cc9ff", opacity=1.0)
    assert canvas.max() > 0


def test_draw_visualizer_circle_changes_pixels():
    canvas = np.zeros((200, 300, 3), dtype=np.uint8)
    draw_visualizer(canvas, "circle", _bands(), _wave(), "#ffb648", "#ff5470", opacity=1.0)
    assert canvas.max() > 0


def test_draw_visualizer_noop_when_opacity_zero():
    canvas = np.zeros((200, 300, 3), dtype=np.uint8)
    draw_visualizer(canvas, "bars", _bands(), _wave(), "#7c5cff", "#26d6a4", opacity=0.0)
    assert canvas.max() == 0


def test_draw_visualizer_unknown_style_noop():
    canvas = np.zeros((200, 300, 3), dtype=np.uint8)
    draw_visualizer(canvas, "not-a-style", _bands(), _wave(), "#7c5cff", "#26d6a4", opacity=1.0)
    assert canvas.max() == 0
