"""Tests for Fill Circle / Floor Reflection / Peak Caps behavior."""

from __future__ import annotations

import numpy as np

from visualizer_video._spectrum_fast import mirror_spectrum_points_vertical


def test_floor_reflection_shifts_below_circle() -> None:
    # Unit circle sample points around origin — origin flip alone would look identical.
    angles = np.linspace(0.0, 2.0 * np.pi, 16, endpoint=False).astype(np.float32)
    px = np.cos(angles) * 40.0
    py = np.sin(angles) * 40.0
    dx = np.cos(angles)
    dy = np.sin(angles)
    r_px, r_py, r_dx, r_dy = mirror_spectrum_points_vertical(px, py, dx, dy, floor_gap=10.0)
    assert r_px.shape == px.shape
    # Reflection must sit strictly below the original lowest point.
    assert float(np.max(r_py)) < float(np.min(py)) - 1.0
    assert float(np.min(r_py)) < float(np.min(py))


def test_floor_reflection_linear_row_also_shifts() -> None:
    px = np.linspace(-50.0, 50.0, 8).astype(np.float32)
    py = np.zeros(8, dtype=np.float32)
    dx = np.zeros(8, dtype=np.float32)
    dy = np.ones(8, dtype=np.float32)
    _r_px, r_py, _r_dx, r_dy = mirror_spectrum_points_vertical(px, py, dx, dy, floor_gap=8.0)
    assert float(np.max(r_py)) < -1.0
    assert np.allclose(r_dy, -dy)
