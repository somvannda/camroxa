"""Spectrum motion zoom helper."""

from __future__ import annotations

from features.video.lib.spectrum_settings import (
    SPECTRUM_MOTION_OPTIONS,
    spectrum_audio_zoom_scale,
)


def test_spectrum_motion_options_include_zoom() -> None:
    values = {value for value, _label in SPECTRUM_MOTION_OPTIONS}
    assert values == {"none", "zoom"}


def test_spectrum_audio_zoom_scale_none_is_identity() -> None:
    assert spectrum_audio_zoom_scale(mode="none", zoom_strength=10.0, audio_env=1.0) == 1.0
    assert spectrum_audio_zoom_scale(mode="", zoom_strength=10.0, audio_env=1.0) == 1.0


def test_spectrum_audio_zoom_scale_grows_with_audio() -> None:
    idle = spectrum_audio_zoom_scale(mode="zoom", zoom_strength=1.0, audio_env=0.0)
    hot = spectrum_audio_zoom_scale(mode="zoom", zoom_strength=1.0, audio_env=1.0)
    assert idle == 1.0
    assert hot > idle
    stronger = spectrum_audio_zoom_scale(mode="zoom", zoom_strength=5.0, audio_env=1.0)
    assert stronger > hot


def test_spectrum_zoom_env_higher_speed_is_snappier() -> None:
    from features.video.lib.spectrum_settings import step_spectrum_zoom_env

    slow = 0.0
    fast = 0.0
    for _ in range(4):
        slow = step_spectrum_zoom_env(slow, target=1.0, speed=0.5, dt=1.0 / 60.0)
        fast = step_spectrum_zoom_env(fast, target=1.0, speed=6.0, dt=1.0 / 60.0)
    assert fast > slow
