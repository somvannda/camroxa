"""Tests for particle preset registry."""

from __future__ import annotations

from features.video.lib.effect_pack_draft_state import apply_particle_pack_as_preset
from features.video.lib.particle_settings import PARTICLE_MOTION_PRESETS
from features.video.lib.particle_style_registry import (
    build_builtin_particle_preset_patch,
    build_unified_particle_preset_options,
    encode_pack_preset_key,
    resolve_active_particle_preset_key,
)


def test_build_unified_particle_preset_options_includes_installed_packs() -> None:
    catalog = [
        {
            "domain": "particles",
            "packId": "neon-particles",
            "version": "1.0.0",
            "name": "Neon Particles",
            "status": "ready",
        },
        {
            "domain": "spectrum",
            "packId": "neon-pack",
            "version": "1.0.0",
            "name": "Neon Pack",
            "status": "ready",
        },
    ]
    options = build_unified_particle_preset_options(catalog)
    assert options[: len(PARTICLE_MOTION_PRESETS)] == PARTICLE_MOTION_PRESETS
    assert encode_pack_preset_key("neon-particles", "1.0.0") in [value for value, _label in options]
    assert all("neon-pack" not in value for value, _label in options)


def test_build_builtin_particle_preset_patch_returns_recipe() -> None:
    patch = build_builtin_particle_preset_patch("dreamy_bokeh")
    assert patch is not None
    assert patch["particlesStyle"] == "bokeh"
    assert build_builtin_particle_preset_patch("pack:foo::1.0.0") is None


def test_resolve_active_particle_preset_key() -> None:
    patch = build_builtin_particle_preset_patch("soap_orbit")
    assert patch is not None
    draft = {**patch, "particlesSwirl": 0.99}
    assert resolve_active_particle_preset_key(draft) is None
    assert resolve_active_particle_preset_key(patch) == "soap_orbit"


def test_apply_particle_pack_keeps_other_domain_slices() -> None:
    from features.video.lib.template_draft_domains import (
        pick_particles_draft_slice,
        pick_spectrum_draft_slice,
    )

    current_draft = {
        "spectrumEnabled": True,
        "style": "classic-vertical",
        "particlesEnabled": False,
        "particlesStyle": "dot",
        "effectPacks": {"particles": {"packId": "pack.particles.alpha", "version": "2.0.0"}},
    }
    current_template = {
        "style": "classic-vertical",
        "layers": [],
        "particlesSettings": {"enabled": True, "style": "glow"},
    }
    item = {
        "templatePatch": {
            "particlesSettings": {
                "enabled": True,
                "style": "ring",
                "spawnArea": "full",
            }
        }
    }
    result = apply_particle_pack_as_preset(
        current_draft=current_draft,
        current_template=current_template,
        logo_path="",
        item=item,
    )
    assert pick_spectrum_draft_slice(result["nextDraft"]) == pick_spectrum_draft_slice(current_draft)
    assert result["nextDraft"]["particlesStyle"] == "ring"
    assert result["nextDraft"]["effectPacks"]["particles"]["packId"] == "pack.particles.alpha"
