"""REQ-P2: allowlisted preview scrub patches."""

from __future__ import annotations

from features.video.lib.preview_scrub_patch import (
    PREVIEW_SCRUB_LAYER_KEYS,
    PREVIEW_SCRUB_PARTICLE_DRAFT_KEYS,
    clamp_layer_scrub_value,
    clamp_particle_scrub_value,
    draft_patch_is_scrub_allowlisted,
    layer_patch_is_scrub_allowlisted,
    layer_scrub_values,
    particle_draft_to_settings_patch,
)


def test_allowlists_cover_required_high_churn_fields() -> None:
    assert "glow" in PREVIEW_SCRUB_LAYER_KEYS
    assert "opacity" in PREVIEW_SCRUB_LAYER_KEYS
    assert "barWidth" in PREVIEW_SCRUB_LAYER_KEYS
    assert "particlesOpacity" in PREVIEW_SCRUB_PARTICLE_DRAFT_KEYS
    assert "particlesSize" in PREVIEW_SCRUB_PARTICLE_DRAFT_KEYS


def test_draft_patch_allowlist_rejects_unknown_keys() -> None:
    assert draft_patch_is_scrub_allowlisted({"particlesOpacity": 0.5})
    assert draft_patch_is_scrub_allowlisted({"particlesOpacity": 0.5, "particlesSize": 3})
    assert not draft_patch_is_scrub_allowlisted({"particlesOpacity": 0.5, "particlesEnabled": True})
    assert not draft_patch_is_scrub_allowlisted({"style": "orbit-spikes"})


def test_layer_patch_allowlist_rejects_structural_keys() -> None:
    assert layer_patch_is_scrub_allowlisted({"glow": 40})
    assert layer_patch_is_scrub_allowlisted({"glow": 40, "opacity": 0.8, "barWidth": 6})
    assert not layer_patch_is_scrub_allowlisted({"glow": 40, "curved": True})


def test_clamps_match_normalize_ranges() -> None:
    assert clamp_layer_scrub_value("glow", 150) == 100.0
    assert clamp_layer_scrub_value("opacity", 2) == 1.0
    assert clamp_layer_scrub_value("barWidth", 0.1) == 0.5
    assert clamp_particle_scrub_value("particlesOpacity", -1) == 0.0
    assert clamp_particle_scrub_value("particlesSize", 99) == 20.0


def test_particle_draft_maps_to_particles_settings() -> None:
    assert particle_draft_to_settings_patch({"particlesOpacity": 0.4, "particlesSize": 3}) == {
        "opacity": 0.4,
        "size": 3.0,
    }


def test_layer_scrub_values_only_allowlisted() -> None:
    assert layer_scrub_values({"glow": 42, "curved": True}) == {"glow": 42.0}
