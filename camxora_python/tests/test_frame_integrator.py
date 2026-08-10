from __future__ import annotations



from visualizer_video.frame_integrator import (

    BgVibrateConfig,

    BgVibrateState,

    BgVibrateStepInput,

    CameraShakeConfig,

    CameraShakeState,

    CameraShakeStepInput,

    KickBassEnvelopeConfig,

    KickBassEnvelopeState,

    KickBassEnvelopeStepInput,

    integrate_bg_vibrate,

    integrate_camera_shake,

    integrate_kick_bass_envelopes,

    integrate_particle_audio,

    ParticleAudioConfig,

    ParticleAudioState,

    ParticleAudioStepInput,

    smooth_env,

)





def test_smooth_env_dt_scales_retention_for_lower_export_fps() -> None:

    """24 fps export should reach the same target in similar wall time as 60 Hz preview."""

    target = 1.0

    prev = 0.0

    preview_s = 0.8

    encode_dt = 1.0 / 24.0



    preview_after_one_sec = prev

    for _ in range(60):

        preview_after_one_sec = smooth_env(preview_after_one_sec, target, preview_s)



    export_after_one_sec = prev

    for _ in range(24):

        export_after_one_sec = smooth_env(export_after_one_sec, target, preview_s, dt=encode_dt)



    assert abs(preview_after_one_sec - export_after_one_sec) < 0.08





def test_smooth_env_without_dt_differs_at_same_frame_count() -> None:

    target = 1.0

    prev = 0.0

    smoothing = 0.8

    encode_dt = 1.0 / 24.0



    scaled = prev

    raw = prev

    for _ in range(24):

        scaled = smooth_env(scaled, target, smoothing, dt=encode_dt)

        raw = smooth_env(raw, target, smoothing)



    assert scaled > raw





def test_kick_bass_envelope_rises_on_sustained_bass() -> None:

    state = KickBassEnvelopeState()

    config = KickBassEnvelopeConfig(bg_smoothing=0.8, logo_smoothing=0.75)

    dt = 1.0 / 60.0



    last = integrate_kick_bass_envelopes(

        state,

        KickBassEnvelopeStepInput(bass=0.0),

        config,

        dt=dt,

    )

    for _ in range(30):

        last = integrate_kick_bass_envelopes(

            state,

            KickBassEnvelopeStepInput(bass=0.9),

            config,

            dt=dt,

        )



    assert last.kick_pow > 0.0

    assert last.bg_audio_env > 0.0

    assert last.logo_audio_env > 0.0





def test_kick_bass_envelope_kick_pow_matches_clamped_square() -> None:

    state = KickBassEnvelopeState()

    state.p_kick_env = 0.5

    config = KickBassEnvelopeConfig(bg_smoothing=0.0, logo_smoothing=0.0)



    out = integrate_kick_bass_envelopes(

        state,

        KickBassEnvelopeStepInput(bass=0.0),

        config,

        dt=1.0 / 60.0,

    )



    expected = float(max(0.0, min(1.0, state.p_kick_env))) ** 2

    assert abs(out.kick_pow - expected) < 1e-9





def test_kick_bass_envelope_export_dt_matches_preview_steps() -> None:

    """One 24 fps export step should match 2.5 preview steps at 60 Hz (wall time)."""

    preview_state = KickBassEnvelopeState()

    export_state = KickBassEnvelopeState()

    config = KickBassEnvelopeConfig(bg_smoothing=0.8, logo_smoothing=0.75)

    preview_dt = 1.0 / 60.0

    encode_dt = 1.0 / 24.0

    bass = 0.7



    preview_out = integrate_kick_bass_envelopes(

        preview_state,

        KickBassEnvelopeStepInput(bass=bass),

        config,

        dt=preview_dt,

    )

    for _ in range(2):

        preview_out = integrate_kick_bass_envelopes(

            preview_state,

            KickBassEnvelopeStepInput(bass=bass),

            config,

            dt=preview_dt,

        )



    export_out = integrate_kick_bass_envelopes(

        export_state,

        KickBassEnvelopeStepInput(bass=bass),

        config,

        dt=encode_dt,

    )



    assert abs(preview_out.kick_pow - export_out.kick_pow) < 0.05

    assert abs(preview_out.bg_audio_env - export_out.bg_audio_env) < 0.08





def test_camera_shake_disabled_resets_state() -> None:

    state = CameraShakeState(x=12.0, y=-8.0)

    out = integrate_camera_shake(

        state,

        CameraShakeStepInput(frame_index=0, bass=1.0, beat=1.0, intensity=8.0),

        CameraShakeConfig(enabled=False, smoothing=0.85),

    )

    assert out.x == 0.0

    assert out.y == 0.0

    assert state.x == 0.0

    assert state.y == 0.0





def test_camera_shake_enabled_moves_toward_target(monkeypatch) -> None:
    import visualizer_video.frame_integrator as fi

    monkeypatch.setattr(fi.time, "time", lambda: 0.0)
    state = CameraShakeState()
    out = integrate_camera_shake(
        state,
        CameraShakeStepInput(frame_index=10, bass=1.0, beat=1.0, intensity=8.0),
        CameraShakeConfig(enabled=True, smoothing=0.85),
    )
    assert abs(out.x) > 0.0 or abs(out.y) > 0.0





def test_bg_vibrate_disabled_resets_state() -> None:

    state = BgVibrateState(x=5.0, y=-3.0)

    out = integrate_bg_vibrate(

        state,

        BgVibrateStepInput(frame_index=0, bg_audio_env=1.0),

        BgVibrateConfig(

            motion_mode="none",

            react_bass=1.0,

            smoothing=0.8,

            vibrate_strength=1.0,

            scale_factor=1.0,

        ),

    )

    assert out.x == 0.0

    assert out.y == 0.0

    assert state.x == 0.0

    assert state.y == 0.0





def test_bg_vibrate_enabled_produces_offset() -> None:

    state = BgVibrateState()

    out = integrate_bg_vibrate(

        state,

        BgVibrateStepInput(frame_index=12, bg_audio_env=1.0),

        BgVibrateConfig(

            motion_mode="vibrate",

            react_bass=1.0,

            smoothing=0.0,

            vibrate_strength=1.0,

            scale_factor=1.0,

        ),

    )

    assert abs(out.x) > 0.0 or abs(out.y) > 0.0


def test_particle_audio_rises_on_beat_and_onset() -> None:
    state = ParticleAudioState()
    config = ParticleAudioConfig(smoothing=0.0, spawn_trigger="both")
    dt = 1.0 / 60.0

    out = integrate_particle_audio(
        state,
        ParticleAudioStepInput(bass=0.0, kick_pow=0.0, onset=0.0, beat=0.0),
        config,
        dt=dt,
    )
    assert out.particle_audio_env == 0.0
    assert out.p_trigger_env == 0.0

    out = integrate_particle_audio(
        state,
        ParticleAudioStepInput(bass=0.2, kick_pow=0.0, onset=0.9, beat=0.95),
        config,
        dt=dt,
    )
    assert out.particle_audio_env > 0.0
    assert out.p_trigger_env > 0.0


def test_particle_audio_spawn_trigger_kick_vs_bass() -> None:
    kick_state = ParticleAudioState()
    bass_state = ParticleAudioState()
    config_kick = ParticleAudioConfig(smoothing=0.0, spawn_trigger="kick")
    config_bass = ParticleAudioConfig(smoothing=0.0, spawn_trigger="bass")
    step = ParticleAudioStepInput(bass=0.8, kick_pow=0.1, onset=0.0, beat=0.0)

    kick_out = integrate_particle_audio(kick_state, step, config_kick)
    bass_out = integrate_particle_audio(bass_state, step, config_bass)

    assert kick_out.p_trigger_env == 0.1
    assert bass_out.p_trigger_env == 0.8


def test_particle_audio_export_dt_matches_preview_steps() -> None:
    preview_state = ParticleAudioState()
    export_state = ParticleAudioState()
    config = ParticleAudioConfig(smoothing=0.8, spawn_trigger="both")
    preview_dt = 1.0 / 60.0
    encode_dt = 1.0 / 24.0
    step = ParticleAudioStepInput(bass=0.7, kick_pow=0.5, onset=0.2, beat=0.4)

    preview_out = integrate_particle_audio(preview_state, step, config, dt=preview_dt)
    for _ in range(2):
        preview_out = integrate_particle_audio(preview_state, step, config, dt=preview_dt)

    export_out = integrate_particle_audio(export_state, step, config, dt=encode_dt)

    assert abs(preview_out.particle_audio_env - export_out.particle_audio_env) < 0.08
    assert abs(preview_out.p_trigger_env - export_out.p_trigger_env) < 0.08

