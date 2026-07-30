"""Raise Scroll shifts spectrum spike energy along the path."""

from __future__ import annotations

import numpy as np

from visualizer._spectrum_fast import clamp_frequency_scroll, scroll_spectrum_heights
from visualizer.template_runtime import default_renderer_template, normalize_renderer_template


def test_clamp_frequency_scroll_wraps() -> None:
    assert clamp_frequency_scroll(0.0) == 0.0
    assert clamp_frequency_scroll(0.25) == 0.25
    assert clamp_frequency_scroll(1.0) == 0.0
    assert clamp_frequency_scroll(1.25) == 0.25
    assert clamp_frequency_scroll(None) == 0.0


def test_scroll_zero_is_identity() -> None:
    src = np.linspace(0.0, 1.0, 64, dtype=np.float32)
    out = scroll_spectrum_heights(src, 0.0)
    assert np.allclose(out, src)


def test_scroll_moves_bass_peak_right() -> None:
    src = np.zeros(64, dtype=np.float32)
    src[0] = 1.0  # bass peak at left
    mid = scroll_spectrum_heights(src, 0.5)
    assert float(np.argmax(mid)) == 32
    near_end = scroll_spectrum_heights(src, 0.75)
    assert float(np.argmax(near_end)) == 48


def test_normalize_keeps_frequency_scroll() -> None:
    tpl = default_renderer_template()
    tpl["layers"][0]["frequencyScroll"] = 0.37
    out = normalize_renderer_template(tpl)
    assert abs(float(out["layers"][0]["frequencyScroll"]) - 0.37) < 1e-6
