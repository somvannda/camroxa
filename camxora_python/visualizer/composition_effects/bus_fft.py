"""Per-layer audio-bus → FFT shaping (bass≠treble visually)."""

from __future__ import annotations

import numpy as np

from visualizer.presets.audio_buses import normalize_audio_bus_id


def bus_bin_weights(n: int, bus_id: str | None) -> np.ndarray:
    """Return per-bin weights so bus choice changes *which* bars move."""
    count = max(1, int(n))
    t = np.linspace(0.0, 1.0, count, dtype=np.float32)
    key = normalize_audio_bus_id(bus_id)
    if key is None:
        return np.ones(count, dtype=np.float32)
    if key == "bass":
        # Strong low-end focus — high bins nearly silent.
        w = np.clip(1.55 - t * 2.35, 0.02, 1.55) ** 1.35
    elif key == "treble":
        w = np.clip(0.02 + t * 1.85, 0.02, 1.55) ** 1.25
    elif key in ("melody", "vocals"):
        # Mid / presence focus
        center = 0.38 if key == "melody" else 0.66
        w = np.clip(1.35 - np.abs(t - center) * 3.2, 0.03, 1.4) ** 1.2
    elif key in ("kick", "beat"):
        w = np.clip(1.45 - t * 1.55, 0.06, 1.5) ** 1.3
    elif key == "snare":
        w = np.clip(1.25 - np.abs(t - 0.55) * 2.8, 0.04, 1.4) ** 1.2
    elif key == "overall_loudness":
        w = np.ones(count, dtype=np.float32)
    else:
        w = np.ones(count, dtype=np.float32)
    return w.astype(np.float32)


def apply_layer_audio_bus(
    sampled_fft: np.ndarray,
    *,
    bus_id: str | None,
    bus_levels: dict[str, float] | None,
    audio_gain: float = 1.0,
) -> np.ndarray:
    """Shape + drive FFT bins from a named layer bus.

    When a bus is selected, quiet bus levels nearly silence the layer so
    Bass vs Treble is obvious. Overall/shared (bus_id None) leaves FFT alone
    aside from gain.
    """
    arr = np.asarray(sampled_fft, dtype=np.float32)
    if arr.size == 0:
        return arr
    try:
        gain = float(max(0.0, min(3.0, audio_gain)))
    except (TypeError, ValueError):
        gain = 1.0
    key = normalize_audio_bus_id(bus_id)
    if key is None:
        if abs(gain - 1.0) <= 1e-3:
            return arr
        return np.clip(arr * gain, 0.0, 3.5).astype(np.float32)

    levels = bus_levels if isinstance(bus_levels, dict) else {}
    drive = float(levels.get(key, 0.0) or 0.0)
    drive = max(0.0, min(1.0, drive))
    # Strong mute when bus is quiet — otherwise every bus looks the same.
    # Curve drive so mid levels still leave headroom for weight contrast.
    drive_curved = drive ** 0.85
    amp = (0.02 + 0.98 * drive_curved) * gain
    weights = bus_bin_weights(int(arr.shape[0]), key)
    return np.clip(arr * weights * amp, 0.0, 3.5).astype(np.float32)
