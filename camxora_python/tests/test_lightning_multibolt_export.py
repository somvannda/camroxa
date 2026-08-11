"""Regression: multi-bolt lightning export floors (timing + visibility)."""

from __future__ import annotations

from features.video.lib.lightning_render import (
    apply_lightning_flash_floor,
    sample_lightning_layer_peaks_over_interval,
)
from features.video.lib.lightning_style_registry import default_lightning_layer


def test_apply_lightning_flash_floor_does_not_double_scale() -> None:
    """Sampler peaks already include opacity; floor must stay drawable (>0.02)."""
    peak_floor = 0.096
    opacity_base = 0.2
    raised = apply_lightning_flash_floor(0.0, peak_floor=peak_floor, opacity_base=opacity_base)
    assert raised > 0.02
    assert abs(opacity_base * raised - peak_floor) < 1e-6


def test_sparse_per_layer_floor_only_raises_peaking_bolts() -> None:
    """Parity-branch timing: only layers present in the peak map get a floor."""
    layers = [default_lightning_layer(index=i + 1) for i in range(5)]
    for i, layer in enumerate(layers):
        layer["x"] = float(i * 80)
        layer["seed"] = float(i + 1)
        layer["flashRate"] = 0.35
        layer["opacity"] = 0.25
        layer["intensity"] = 0.25
    template = {"lightningEnabled": True, "lightningLayers": layers}

    sparse_peaks: dict[int, float] = {}
    for fi in range(240):
        t = fi / 30.0
        _peak, by_layer = sample_lightning_layer_peaks_over_interval(
            template,
            time_sec=t,
            encode_dt=1.0 / 30.0,
            bass=0.8,
            kick=0.6,
            beat=0.7,
            onset=0.5,
            audio_env=0.8,
            sample_hz=60.0,
        )
        if by_layer:
            sparse_peaks = dict(by_layer)
            if 0 < len(sparse_peaks) < 5:
                break
    assert sparse_peaks, "expected at least one peaking layer in the window"

    # Sparse floor: only peaking indices rise above draw threshold from a cold frame.
    for idx in range(5):
        floor = float(sparse_peaks.get(idx, 0.0))
        flash = apply_lightning_flash_floor(0.0, peak_floor=floor, opacity_base=0.25)
        if idx in sparse_peaks:
            assert flash > 0.02, f"peaking layer {idx} should remain drawable"
        else:
            assert flash <= 0.02, f"non-peaking layer {idx} must not get a global floor"


def test_sparse_floor_keeps_low_opacity_peak_drawable() -> None:
    """Double-scale bug would crush this peak below 0.02; fixed floor keeps it."""
    peak_floor = 0.05  # already intensity×opacity
    flash = apply_lightning_flash_floor(0.0, peak_floor=peak_floor, opacity_base=0.3)
    assert flash > 0.02
    # Old bug: peak_floor * intensity_factor * opacity ≈ 0.05 * 0.5 * 0.3 = 0.0075
    old_buggy = peak_floor * (0.35 + 0.65 * 0.25) * 0.3
    assert old_buggy < 0.02
    assert flash > old_buggy
