"""Regression: multi-bolt export flash floor (1.2.3)."""

from __future__ import annotations

from features.video.lib.lightning_render import (
    apply_lightning_flash_floor,
    sample_lightning_layer_peaks_over_interval,
)
from features.video.lib.lightning_style_registry import default_lightning_layer


def test_apply_lightning_flash_floor_does_not_double_scale() -> None:
    """Sampler peaks already include opacity; floor must stay drawable (>0.02)."""
    # Mid-interval peak stored as final flash (envelope * intensity * opacity).
    peak_floor = 0.096  # e.g. low intensity/opacity strike
    opacity_base = 0.2
    # Envelope off at exact encode frame → flash 0 before floor.
    raised = apply_lightning_flash_floor(0.0, peak_floor=peak_floor, opacity_base=opacity_base)
    assert raised > 0.02
    # opacity_base * raised ≈ peak_floor (pre-opacity flash space).
    assert abs(opacity_base * raised - peak_floor) < 1e-6


def test_global_flash_override_floors_all_layers_when_one_peaks() -> None:
    """Legacy export path: one peaking bolt raises flash floors for every layer index."""
    layers = []
    for i in range(5):
        layer = default_lightning_layer(index=i + 1)
        layer["x"] = float(i * 80)
        layer["seed"] = float(i + 1)
        layer["flashRate"] = 0.4
        layers.append(layer)
    template = {"lightningEnabled": True, "lightningLayers": layers}

    # Find a window where at least one layer peaks.
    global_peak = 0.0
    for fi in range(180):
        t = fi / 30.0
        peak, by_layer = sample_lightning_layer_peaks_over_interval(
            template,
            time_sec=t,
            encode_dt=1.0 / 30.0,
            bass=0.7,
            kick=0.5,
            beat=0.6,
            onset=0.4,
            audio_env=0.7,
            sample_hz=60.0,
        )
        if peak > 0.05 and len(by_layer) == 1:
            global_peak = peak
            break
    else:
        # Fallback: any non-empty peak window is fine.
        for fi in range(180):
            t = fi / 30.0
            peak, by_layer = sample_lightning_layer_peaks_over_interval(
                template,
                time_sec=t,
                encode_dt=1.0 / 30.0,
                bass=0.7,
                kick=0.5,
                beat=0.6,
                onset=0.4,
                audio_env=0.7,
                sample_hz=60.0,
            )
            if peak > 0.05:
                global_peak = peak
                break
    assert global_peak > 0.05

    # Simulate legacy global floor assignment used by run_gpu_render.
    per_layer_floor = {idx: global_peak for idx in range(len(layers))}
    opacity = 0.85
    raised_count = 0
    for idx in range(5):
        flash = apply_lightning_flash_floor(
            0.0,
            peak_floor=per_layer_floor[idx],
            opacity_base=opacity,
        )
        if flash > 0.02:
            raised_count += 1
    assert raised_count == 5
