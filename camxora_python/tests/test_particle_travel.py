"""Particle travel direction tests."""

from __future__ import annotations

import numpy as np

from features.video.lib.particle_settings import (
    build_particle_motion_preset_patch,
    is_particle_preset_active,
)
from visualizer_video.particles import ParticleConfig, ParticleSystem


def test_bottom_spawn_with_rise_travels_toward_top_of_frame() -> None:
    """Sim is top-left (y down): rise = negative vy, spawn near bottom (high y)."""
    system = ParticleSystem(
        ParticleConfig(
            enabled=True,
            max_count=40,
            spawn_rate=2000.0,
            lifetime_sec=2.0,
            spawn_radius=40.0,
            size=4.0,
            opacity=1.0,
            color=(255, 255, 255),
            speed=80.0,
            spawn_area="bottom",
            travel_mode="rise",
        ),
        width=800,
        height=450,
        rng_seed=7,
    )
    system.update(0.2, {})
    assert system._pos.shape[0] > 0
    assert float(np.mean(system._vel[:, 1])) < 0.0
    assert float(np.mean(system._pos[:, 1])) <= 450.0
    visible = int(np.sum((system._pos[:, 1] >= 0.0) & (system._pos[:, 1] <= 450.0)))
    assert visible > 0


def test_particle_ndc_y_flip_maps_bottom_spawn_to_screen_bottom() -> None:
    """Bottom-arc particles (high sim y) must map to OpenGL NDC bottom (negative y)."""
    h = 450.0
    sim_y_bottom = h * 0.95
    sim_y_top = h * 0.05
    ndc_bottom = 1.0 - (sim_y_bottom / h * 2.0)
    ndc_top = 1.0 - (sim_y_top / h * 2.0)
    assert ndc_bottom < 0.0
    assert ndc_top > 0.0
    assert ndc_bottom < ndc_top


def test_fall_travel_mode_moves_toward_bottom_of_frame() -> None:
    system = ParticleSystem(
        ParticleConfig(
            enabled=True,
            max_count=40,
            spawn_rate=2000.0,
            lifetime_sec=2.0,
            spawn_radius=40.0,
            size=4.0,
            opacity=1.0,
            color=(255, 255, 255),
            speed=80.0,
            spawn_area="screenCenter",
            travel_mode="fall",
        ),
        width=800,
        height=450,
        rng_seed=11,
    )
    system.update(0.2, {})
    assert system._pos.shape[0] > 0
    assert float(np.mean(system._vel[:, 1])) > 0.0


def test_spawn_flow_uses_spawn_area_direction() -> None:
    system = ParticleSystem(
        ParticleConfig(
            enabled=True,
            max_count=60,
            spawn_rate=3000.0,
            lifetime_sec=2.0,
            spawn_radius=80.0,
            size=4.0,
            opacity=1.0,
            color=(255, 255, 255),
            speed=80.0,
            spawn_area="centerRing",
            travel_mode="spawnFlow",
        ),
        width=800,
        height=450,
        rng_seed=3,
    )
    system.update(0.2, {})
    assert system._pos.shape[0] > 0
    assert float(np.std(system._vel[:, 0])) > 0.05
    assert float(np.std(system._vel[:, 1])) > 0.05


def test_embers_preset_stays_active_after_round_trip() -> None:
    patch = build_particle_motion_preset_patch("embers")
    assert is_particle_preset_active(patch, "embers")
    # Empty palette must remain empty in solid mode (do not invent stops).
    assert patch["particlesPaletteColors"] == []
    assert patch["particlesColorMode"] == "solid"


def test_switching_spawn_area_clears_live_particles() -> None:
    system = ParticleSystem(
        ParticleConfig(
            enabled=True,
            max_count=80,
            spawn_rate=3000.0,
            lifetime_sec=4.0,
            spawn_radius=40.0,
            size=4.0,
            opacity=1.0,
            color=(255, 255, 255),
            speed=40.0,
            spawn_area="full",
            travel_mode="spawnFlow",
        ),
        width=800,
        height=450,
        rng_seed=5,
    )
    system.update(0.2, {})
    assert system._pos.shape[0] > 0
    system.update_cfg(
        ParticleConfig(
            enabled=True,
            max_count=80,
            spawn_rate=3000.0,
            lifetime_sec=4.0,
            spawn_radius=40.0,
            size=4.0,
            opacity=1.0,
            color=(255, 154, 60),
            speed=40.0,
            spawn_area="bottom",
            travel_mode="rise",
        )
    )
    assert system._pos.shape[0] == 0
