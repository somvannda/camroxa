"""Spectrum audio dial mapping — port of SpectrumInspector.tsx helpers."""

from __future__ import annotations

SPECTRUM_AUDIO_DIAL_MAX = 20
FLYING_GLOW_WING_SPEED_DIAL_MAX = 100


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def to_spectrum_audio_dial(
    value: float,
    minimum: float,
    maximum: float,
    dial_max: int = SPECTRUM_AUDIO_DIAL_MAX,
) -> int:
    if maximum <= minimum:
        return 0
    return round((_clamp(value, minimum, maximum) - minimum) / (maximum - minimum) * dial_max)


def from_spectrum_audio_dial(
    dial: int,
    minimum: float,
    maximum: float,
    dial_max: int = SPECTRUM_AUDIO_DIAL_MAX,
) -> float:
    if maximum <= minimum:
        return minimum
    return minimum + (_clamp(float(dial), 0, dial_max) / dial_max) * (maximum - minimum)
