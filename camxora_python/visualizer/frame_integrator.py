"""Pure-Python per-frame motion/audio integration shared by preview and export.

REQ-2.1 slice 1: kick/bass envelopes + ``smooth_env`` (dt-aware 60 Hz parity).
Slice 2: camera shake + background vibrate integration.
Slice 3: particle reactive audio + spawn trigger envelopes.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

PREVIEW_REF_FPS = 60.0


def smooth_env(
    prev: float,
    target: float,
    smoothing: float,
    *,
    dt: float | None = None,
    ref_fps: float = PREVIEW_REF_FPS,
    clamp_target: bool = True,
) -> float:
    """Exponential envelope smooth.

    ``smoothing`` is the per-frame retention coeff as tuned in live preview (60 Hz).
    When ``dt`` is provided (export at 24 fps), convert so wall-clock response matches preview.
    Set ``clamp_target=False`` for pixel-offset targets (camera/bg shake).
    """
    s = float(max(0.0, min(0.99, smoothing)))
    if dt is not None and float(dt) > 0.0 and float(ref_fps) > 0.0:
        s = float(s ** (float(ref_fps) * float(dt)))
        s = float(max(0.0, min(0.99, s)))
    t = float(target)
    if clamp_target:
        t = float(max(0.0, min(1.0, t)))
    return float((float(prev) * s) + (t * (1.0 - s)))


@dataclass
class KickBassEnvelopeState:
    """Stateful kick/bass follower used by preview and export."""

    p_bass_fast: float = 0.0
    p_bass_slow: float = 0.0
    p_kick_env: float = 0.0
    bg_audio_env: float = 0.0
    logo_audio_env: float = 0.0


@dataclass(frozen=True)
class KickBassEnvelopeConfig:
    """Template-derived smoothing coeffs for one integrator session."""

    bg_smoothing: float
    logo_smoothing: float


@dataclass(frozen=True)
class KickBassEnvelopeStepInput:
    """Per-frame audio features."""

    bass: float


@dataclass(frozen=True)
class KickBassEnvelopeStepOutput:
    """Derived envelope values for bg/logo/spectrum/particles."""

    kick_pow: float
    bg_audio_env: float
    logo_audio_env: float


def _kick_time_constants(dt: float) -> tuple[float, float, float]:
    dt_safe = float(max(1e-9, dt))
    kick_fast_a = 1.0 - math.exp(-dt_safe / 0.06)
    kick_slow_a = 1.0 - math.exp(-dt_safe / 0.35)
    kick_decay = math.exp(-dt_safe / 0.18)
    return kick_fast_a, kick_slow_a, kick_decay


def integrate_kick_bass_envelopes(
    state: KickBassEnvelopeState,
    step: KickBassEnvelopeStepInput,
    config: KickBassEnvelopeConfig,
    *,
    dt: float,
) -> KickBassEnvelopeStepOutput:
    """Advance kick/bass followers and bg/logo audio envelopes for one frame."""
    bass = float(step.bass)
    kick_fast_a, kick_slow_a, kick_decay = _kick_time_constants(dt)

    state.p_bass_fast = state.p_bass_fast * (1.0 - kick_fast_a) + bass * kick_fast_a
    state.p_bass_slow = state.p_bass_slow * (1.0 - kick_slow_a) + bass * kick_slow_a
    raw_kick = float(max(0.0, state.p_bass_fast - state.p_bass_slow))
    kick0 = float(max(0.0, min(1.0, raw_kick * 4.0)))
    state.p_kick_env = float(max(kick0, state.p_kick_env * kick_decay))
    kick_pow = float(max(0.0, min(1.0, state.p_kick_env))) ** 2

    bg_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.6))))
    state.bg_audio_env = smooth_env(state.bg_audio_env, bg_audio_raw, config.bg_smoothing, dt=dt)

    logo_audio_raw = float(max(0.0, min(1.0, max(bass, kick_pow * 0.8))))
    state.logo_audio_env = smooth_env(
        state.logo_audio_env, logo_audio_raw, config.logo_smoothing, dt=dt
    )

    return KickBassEnvelopeStepOutput(
        kick_pow=kick_pow,
        bg_audio_env=state.bg_audio_env,
        logo_audio_env=state.logo_audio_env,
    )


@dataclass
class CameraShakeState:
    """Stateful camera-shake follower used by preview and export."""

    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True)
class CameraShakeConfig:
    """Template-derived camera shake settings."""

    enabled: bool
    smoothing: float


@dataclass(frozen=True)
class CameraShakeStepInput:
    """Per-frame audio features for camera shake."""

    frame_index: int
    bass: float
    beat: float
    intensity: float


@dataclass(frozen=True)
class CameraShakeStepOutput:
    """Smoothed camera offset in pixels."""

    x: float
    y: float


def integrate_camera_shake(
    state: CameraShakeState,
    step: CameraShakeStepInput,
    config: CameraShakeConfig,
    *,
    dt: float | None = None,
    wall_time: float | None = None,
) -> CameraShakeStepOutput:
    """Advance camera shake offset for one frame."""
    if not config.enabled:
        state.x = 0.0
        state.y = 0.0
        return CameraShakeStepOutput(x=0.0, y=0.0)

    target = float(step.intensity) * (
        0.35 + float(step.bass) * 1.2 + float(step.beat) * 1.5
    )
    fi = int(step.frame_index)
    wt = float(wall_time if wall_time is not None else time.time())
    jitter_x = (wt * 0.9 + fi * 0.013) % 1.0
    jitter_y = (wt * 0.9 + fi * 0.017) % 1.0
    tx = (jitter_x * 2.0 - 1.0) * target
    ty = (jitter_y * 2.0 - 1.0) * target
    state.x = smooth_env(state.x, tx, config.smoothing, dt=dt, clamp_target=False)
    state.y = smooth_env(state.y, ty, config.smoothing, dt=dt, clamp_target=False)
    return CameraShakeStepOutput(x=state.x, y=state.y)


@dataclass
class BgVibrateState:
    """Stateful background vibrate offset in pixels."""

    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True)
class BgVibrateConfig:
    """Template-derived background motion settings."""

    motion_mode: str
    react_bass: float
    smoothing: float
    vibrate_strength: float
    scale_factor: float


@dataclass(frozen=True)
class BgVibrateStepInput:
    """Per-frame bg audio envelope input."""

    frame_index: int
    bg_audio_env: float


@dataclass(frozen=True)
class BgVibrateStepOutput:
    """Smoothed background vibrate offset in pixels."""

    x: float
    y: float


def integrate_bg_vibrate(
    state: BgVibrateState,
    step: BgVibrateStepInput,
    config: BgVibrateConfig,
    *,
    dt: float | None = None,
    wall_time: float | None = None,
) -> BgVibrateStepOutput:
    """Advance background vibrate offset for one frame."""
    if config.motion_mode not in ("vibrate", "both"):
        state.x = 0.0
        state.y = 0.0
        return BgVibrateStepOutput(x=0.0, y=0.0)

    bg_shake_target = float(
        max(0.0, config.react_bass)
        * float(step.bg_audio_env)
        * 18.0
        * config.scale_factor
        * config.vibrate_strength
    )
    fi = int(step.frame_index)
    wt = float(wall_time if wall_time is not None else time.time())
    bg_jx = (wt * 0.81 + fi * 0.013) % 1.0
    bg_jy = (wt * 0.83 + fi * 0.017) % 1.0
    state.x = smooth_env(state.x, (bg_jx * 2.0 - 1.0) * bg_shake_target, config.smoothing, dt=dt, clamp_target=False)
    state.y = smooth_env(state.y, (bg_jy * 2.0 - 1.0) * bg_shake_target, config.smoothing, dt=dt, clamp_target=False)
    return BgVibrateStepOutput(x=state.x, y=state.y)


@dataclass
class ParticleAudioState:
    """Stateful particle audio/trigger followers used by preview and export."""

    particle_audio_env: float = 0.0
    p_trigger_env: float = 0.0


@dataclass(frozen=True)
class ParticleAudioConfig:
    """Template-derived particle audio smoothing settings."""

    smoothing: float
    spawn_trigger: str = "both"


@dataclass(frozen=True)
class ParticleAudioStepInput:
    """Per-frame audio features for particle reactivity and spawn gating."""

    bass: float
    kick_pow: float
    onset: float = 0.0
    beat: float = 0.0


@dataclass(frozen=True)
class ParticleAudioStepOutput:
    """Smoothed particle reactive and spawn trigger envelopes."""

    particle_audio_env: float
    p_trigger_env: float


def integrate_particle_audio(
    state: ParticleAudioState,
    step: ParticleAudioStepInput,
    config: ParticleAudioConfig,
    *,
    dt: float | None = None,
) -> ParticleAudioStepOutput:
    """Advance particle reactive audio and spawn trigger envelopes for one frame."""
    ps_smooth = float(max(0.0, min(0.99, config.smoothing)))
    bass = float(step.bass)
    kick_pow = float(step.kick_pow)
    onset = float(step.onset)
    beat = float(step.beat)

    # Match Electron: sustain from bass/kick plus onset/beat so react color
    # still flashes when band energy is flat but the track hits.
    particle_audio_raw = float(
        max(
            0.0,
            min(
                1.0,
                max(kick_pow, bass, onset * 0.9, beat * 0.95),
            ),
        )
    )
    state.particle_audio_env = smooth_env(
        state.particle_audio_env, particle_audio_raw, ps_smooth, dt=dt
    )

    spawn_trigger = str(config.spawn_trigger or "both")
    kick_like = float(max(kick_pow, beat))
    bass_like = float(max(bass, onset * 0.85, particle_audio_raw * 0.65))
    if spawn_trigger == "kick":
        trig_raw = kick_like
    elif spawn_trigger == "bass":
        trig_raw = bass_like
    else:
        trig_raw = float(max(kick_like, bass_like))
    trig_raw = float(max(0.0, min(1.0, trig_raw)))
    state.p_trigger_env = smooth_env(state.p_trigger_env, trig_raw, ps_smooth, dt=dt)

    return ParticleAudioStepOutput(
        particle_audio_env=state.particle_audio_env,
        p_trigger_env=state.p_trigger_env,
    )
