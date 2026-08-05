"""P6 particle types — 20 catalog entries; type ⊥ behavior."""

from __future__ import annotations

import pytest

from features.video.lib.composition_animations import apply_animation_behavior_to_template
from features.video.lib.composition_axes import sync_legacy_aliases_from_composition
from features.video.lib.composition_particles import (
    GPU_PARTICLE_VARIANTS,
    PARTICLE_TYPE_COUNT,
    PARTICLE_TYPE_IDS,
    apply_particle_type_to_template,
    get_particle_type,
    gpu_variant_for_particle_type,
    list_particle_type_options,
    normalize_particle_type_id,
)
from features.video.lib.composition_scene_contract import ensure_composition_on_template
from visualizer.particles import ParticleConfig, ParticleSystem

CANONICAL_13 = (
    "dust",
    "snow",
    "rain",
    "fire",
    "smoke",
    "magic",
    "electric",
    "stars",
    "bubbles",
    "ash",
    "confetti",
    "leaves",
    "sparkles",
)
FILL_7 = (
    "embers",
    "petals",
    "glitter",
    "smoke_rings",
    "energy_orbs",
    "pixel_dust",
    "feather_drift",
)


def test_particle_catalog_count_is_20() -> None:
    assert PARTICLE_TYPE_COUNT == 20
    assert len(PARTICLE_TYPE_IDS) == 20
    assert len(list_particle_type_options()) == 20
    for key in CANONICAL_13 + FILL_7:
        assert key in PARTICLE_TYPE_IDS
        assert get_particle_type(key) is not None


def test_normalize_particle_type_aliases() -> None:
    assert normalize_particle_type_id("Smoke Rings") == "smoke_rings"
    assert normalize_particle_type_id("Feather Drift") == "feather_drift"
    assert normalize_particle_type_id("unknown") is None


def test_type_and_behavior_are_independent() -> None:
    template: dict = {
        "particlesSettings": {"enabled": True, "variant": "classic"},
        "composition": {"particles": {"type": "none", "behavior": "none"}},
    }
    apply_animation_behavior_to_template(template, "pulse", targets=("particles",))
    apply_particle_type_to_template(template, "snow")
    assert template["composition"]["particles"]["type"] == "snow"
    assert template["composition"]["particles"]["behavior"] == "pulse"
    assert template["particlesSettings"]["behavior"] == "pulse"
    assert template["particlesSettings"]["variant"] == "dust"
    assert template["particlesSettings"]["travelMode"] == "fall"

    apply_particle_type_to_template(template, "electric")
    assert template["composition"]["particles"]["type"] == "electric"
    assert template["composition"]["particles"]["behavior"] == "pulse"
    assert template["particlesSettings"]["variant"] == "classic"
    assert template["particlesSettings"]["travelMode"] == "burst"


def test_canonical_type_survives_reproject() -> None:
    template: dict = {
        "particlesSettings": {"enabled": True, "variant": "classic"},
        "composition": {"particles": {"type": "rain", "behavior": "wave"}},
    }
    ensure_composition_on_template(template)
    assert template["composition"]["particles"]["type"] == "rain"
    assert template["composition"]["particles"]["behavior"] == "wave"


def test_sync_legacy_uses_gpu_safe_variant() -> None:
    template: dict = {
        "composition": {"particles": {"type": "snow", "behavior": "bounce"}},
    }
    sync_legacy_aliases_from_composition(template)
    assert template["particlesSettings"]["variant"] == "dust"
    assert template["particlesSettings"]["behavior"] == "bounce"


@pytest.mark.parametrize("type_id", CANONICAL_13 + FILL_7)
def test_every_type_has_gpu_safe_variant_and_simulates(type_id: str) -> None:
    """Exit criterion: catalog types map to renderable GPU variants and simulate."""
    template: dict = {"particlesSettings": {}, "composition": {}}
    apply_particle_type_to_template(template, type_id)
    settings = template["particlesSettings"]
    variant = str(settings["variant"])
    assert variant in GPU_PARTICLE_VARIANTS
    assert gpu_variant_for_particle_type(type_id) == variant

    cfg = ParticleConfig(
        enabled=True,
        max_count=int(settings["maxCount"]),
        spawn_rate=float(settings["spawnRate"]),
        lifetime_sec=float(settings["lifetimeSec"]),
        spawn_radius=120.0,
        size=float(settings["size"]),
        opacity=float(settings["opacity"]),
        color=(255, 255, 255),
        speed=float(settings["speed"]),
        size_jitter=float(settings["sizeJitter"]),
        drift=float(settings["drift"]),
        swirl=float(settings["swirl"]),
        spawn_area=str(settings["spawnArea"]),
        travel_mode=str(settings["travelMode"]),
    )
    system = ParticleSystem(cfg, width=640, height=360, rng_seed=7)
    system.update(1.0 / 60.0, {"kick": 1.0, "bass": 1.0})
    assert system._pos.shape[0] >= 0  # noqa: SLF001 — smoke that update runs


def test_unknown_type_raises() -> None:
    with pytest.raises(ValueError):
        apply_particle_type_to_template({}, "not-a-type")
