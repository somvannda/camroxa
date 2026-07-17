"""Preview particle spawn + coordinate helpers."""

from __future__ import annotations

import numpy as np

from visualizer.particles import ParticleConfig, ParticleSystem
from visualizer.preview_widget import VideoSpectrumPreview


def test_reactive_only_preview_idle_spawn_rate() -> None:
    preview = VideoSpectrumPreview.__new__(VideoSpectrumPreview)
    preview.audio_playing = False
    preview.p_trigger_env = 0.0
    preview.particle_audio_env = 0.0
    ps = {"spawnMode": "reactiveOnly", "spawnThreshold": 0.15}
    rate = VideoSpectrumPreview._resolve_particle_spawn_rate(preview, ps=ps, ps_spawn=400.0, prb=0.5)
    assert rate >= 12.0


def test_reactive_only_playback_below_threshold_still_ambient() -> None:
    preview = VideoSpectrumPreview.__new__(VideoSpectrumPreview)
    preview.audio_playing = True
    preview.p_trigger_env = 0.0
    preview.particle_audio_env = 0.0
    ps = {"spawnMode": "reactiveOnly", "spawnThreshold": 0.15}
    rate = VideoSpectrumPreview._resolve_particle_spawn_rate(preview, ps=ps, ps_spawn=400.0, prb=0.5)
    assert rate >= 12.0


def test_particle_system_spawns_with_ambient_rate() -> None:
    w, h = 782, 440
    cfg = ParticleConfig(
        enabled=True,
        max_count=200,
        spawn_rate=40.0,
        lifetime_sec=1.6,
        spawn_radius=50.0,
        size=2.0,
        opacity=1.0,
        color=(255, 255, 255),
        speed=120.0,
        spawn_area="centerRing",
    )
    ps = ParticleSystem(cfg, w, h)
    for _ in range(90):
        ps.update(1.0 / 60.0, {"bass": 0.0, "beat": 0.0, "onset": 0.0})
    assert ps._pos.shape[0] > 0
    ys2 = ps._pos[:, 1] / float(h) * 2.0 - 1.0
    assert float(ys2.min()) >= -1.05
    assert float(ys2.max()) <= 1.05
