"""Phase 4: particle motion trails."""

from __future__ import annotations

import numpy as np

from features.video.lib.video_template_draft import build_particle_settings_state
from features.video.lib.video_template_save import build_particles_template_patch
from visualizer.particles import ParticleConfig, ParticleSystem, clamp_particle_trail_length
from visualizer.template_runtime import default_renderer_template, normalize_renderer_template


def _cfg(**overrides) -> ParticleConfig:
    base = dict(
        enabled=True,
        max_count=200,
        spawn_rate=80.0,
        lifetime_sec=2.0,
        spawn_radius=40.0,
        size=3.0,
        opacity=0.8,
        color=(255, 200, 80),
        speed=120.0,
        trail_enabled=True,
        trail_length=8,
        trail_fade=0.7,
        trail_width=0.5,
    )
    base.update(overrides)
    return ParticleConfig(**base)


def test_clamp_trail_length() -> None:
    assert clamp_particle_trail_length(1) == 2
    assert clamp_particle_trail_length(100) == 24
    assert clamp_particle_trail_length(8) == 8


def test_template_normalizes_trail_fields() -> None:
    tpl = default_renderer_template()
    tpl["particlesSettings"]["trailEnabled"] = True
    tpl["particlesSettings"]["trailLength"] = 99
    tpl["particlesSettings"]["trailFade"] = 2.0
    out = normalize_renderer_template(tpl)
    ps = out["particlesSettings"]
    assert ps["trailEnabled"] is True
    assert ps["trailLength"] == 24
    assert abs(ps["trailFade"] - 0.98) < 1e-6
    assert 0.1 <= ps["trailWidth"] <= 1.0


def test_draft_round_trip_trail_fields() -> None:
    tpl = default_renderer_template()
    tpl["particlesSettings"]["trailEnabled"] = True
    tpl["particlesSettings"]["trailLength"] = 12
    tpl["particlesSettings"]["trailFade"] = 0.55
    tpl["particlesSettings"]["trailWidth"] = 0.3
    draft = build_particle_settings_state(tpl)
    assert draft["particlesTrailEnabled"] is True
    assert draft["particlesTrailLength"] == 12
    patch = build_particles_template_patch(tpl, draft)
    ps = patch["particlesSettings"]
    assert ps["trailEnabled"] is True
    assert int(ps["trailLength"]) == 12
    assert abs(float(ps["trailFade"]) - 0.55) < 1e-6


def test_trail_history_advances_and_draws() -> None:
    sys = ParticleSystem(_cfg(spawn_rate=200.0, speed=200.0), width=640, height=360, rng_seed=3)
    for _ in range(12):
        sys.update(1.0 / 30.0, {})
    assert sys._pos.shape[0] > 0
    assert sys._trail_pos.shape[0] == sys._pos.shape[0]
    assert sys._trail_pos.shape[1] == 8
    # Newest sample matches current position.
    assert np.allclose(sys._trail_pos[:, 0, :], sys._pos, atol=1e-4)

    head_colors = np.tile(np.array([[1.0, 0.5, 0.2, 0.8]], dtype=np.float32), (sys._pos.shape[0], 1))
    batch = sys.build_trail_draw_arrays(w=640, h=360, head_colors_rgba=head_colors)
    assert batch is not None
    pts, cols = batch
    assert pts.shape[0] > 0
    assert pts.shape[1] == 3
    assert cols.shape == (pts.shape[0], 4)
    # Older segments should be dimmer than head alpha on average.
    assert float(np.mean(cols[:, 3])) < 0.8


def test_trail_disabled_returns_no_batch() -> None:
    sys = ParticleSystem(_cfg(trail_enabled=False, spawn_rate=200.0), width=320, height=180, rng_seed=1)
    for _ in range(8):
        sys.update(1.0 / 30.0, {})
    assert sys.build_trail_draw_arrays(w=320, h=180, head_colors_rgba=None) is None
