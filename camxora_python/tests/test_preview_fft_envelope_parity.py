"""Preview FFT envelope advances like export (no per-paint re-smooth / seek catch-up)."""

from __future__ import annotations

import numpy as np

from visualizer._spectrum_fast import smooth_fft_envelope


def test_smooth_fft_envelope_converges_to_target() -> None:
    prev = np.zeros(64, dtype=np.float32)
    target = np.ones(64, dtype=np.float32)
    # One step from zero stays below target when smoothing is high.
    one = smooth_fft_envelope(prev, target, 0.8)
    assert float(one.mean()) < 0.3
    # Many steps on the same target (paused preview bug) converge near target.
    cur = prev
    for _ in range(120):
        cur = smooth_fft_envelope(cur, target, 0.8)
    assert float(cur.mean()) > 0.95


def test_preview_widget_has_fft_catchup_helpers() -> None:
    import visualizer.preview_widget as pw

    src = open(pw.__file__, encoding="utf-8").read()
    assert "_advance_fft_envelope" in src
    assert "_resync_fft_envelope_to_time" in src
    assert "self._advance_fft_envelope(frame_idx" in src
    assert "self._resync_fft_envelope_to_time(target)" in src
    # Must not re-smooth every paint when analysis idx is unchanged.
    assert "if analysis_idx == int(self._fft_analysis_idx)" in src
