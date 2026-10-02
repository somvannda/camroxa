"""Asymmetric FFT envelope smoothing."""

from __future__ import annotations

import numpy as np

from visualizer_video._spectrum_fast import smooth_fft_envelope


def test_fft_envelope_rises_instantly_even_with_sticky_release() -> None:
    prev = np.zeros(8, dtype=np.float32)
    target_up = np.ones(8, dtype=np.float32)
    up = smooth_fft_envelope(prev, target_up, 0.9)
    assert np.allclose(up, target_up, atol=1e-5)

    high = np.ones(8, dtype=np.float32)
    target_down = np.zeros(8, dtype=np.float32)
    down = smooth_fft_envelope(high, target_down, 0.9)
    # Sticky release keeps most of the previous energy on the way down.
    assert float(np.mean(down)) > 0.8


def test_fft_envelope_zero_smoothing_tracks_target() -> None:
    prev = np.full(4, 0.2, dtype=np.float32)
    target = np.full(4, 0.9, dtype=np.float32)
    out = smooth_fft_envelope(prev, target, 0.0)
    assert np.allclose(out, target, atol=1e-5)
