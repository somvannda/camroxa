"""Move Speed 0 = no idle cruise; reactivity still drives drift."""

from __future__ import annotations

from features.video.lib.particle_settings import resolve_particle_motion_speed


def test_speed_zero_silent_is_frozen() -> None:
    assert resolve_particle_motion_speed(speed=0.0, reactivity=1.0, audio_env=0.0) == 0.0


def test_speed_zero_reactivity_moves() -> None:
    out = resolve_particle_motion_speed(speed=0.0, reactivity=1.0, audio_env=1.0, scale_factor=1.0)
    assert out > 0.0
    assert out == 90.0  # base reactive gain at full prb/env


def test_speed_scales_reactive_and_idle() -> None:
    slow = resolve_particle_motion_speed(speed=1.0, reactivity=0.5, audio_env=1.0)
    fast = resolve_particle_motion_speed(speed=5.0, reactivity=0.5, audio_env=1.0)
    assert fast > slow


def test_idle_cruise_scales_with_speed_when_silent() -> None:
    assert resolve_particle_motion_speed(speed=2.0, reactivity=0.0, audio_env=0.0) == 36.0
    assert resolve_particle_motion_speed(speed=0.0, reactivity=0.0, audio_env=1.0) == 0.0
