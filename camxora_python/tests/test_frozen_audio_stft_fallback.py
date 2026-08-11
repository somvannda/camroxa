"""Frozen audio analysis: NumPy STFT fallback when SciPy is unavailable."""

from __future__ import annotations

import numpy as np

from visualizer.audio import _spectrum_mag_frozen, _spectrum_mag_numpy


def test_spectrum_mag_numpy_shape() -> None:
    rng = np.random.default_rng(0)
    y = rng.standard_normal(16_000).astype(np.float32)
    mag = _spectrum_mag_numpy(y, n_fft=512, hop_length=256)
    assert mag.ndim == 2
    assert mag.shape[0] == 512 // 2 + 1
    assert mag.shape[1] > 0
    assert np.isfinite(mag).all()


def test_spectrum_mag_frozen_falls_back_when_scipy_missing(monkeypatch) -> None:
    import visualizer.audio as audio_mod

    real_import = __import__

    def _block_scipy(name, *args, **kwargs):
        if name == "scipy" or name.startswith("scipy."):
            raise ImportError("simulated missing scipy")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _block_scipy)
    y = np.linspace(-1.0, 1.0, 4096, dtype=np.float32)
    mag = audio_mod._spectrum_mag_frozen(y, n_fft=256, hop_length=128)
    assert mag.shape[0] == 256 // 2 + 1
    assert mag.shape[1] > 0
