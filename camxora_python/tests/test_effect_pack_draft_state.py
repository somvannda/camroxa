"""Tests for effect pack draft apply/clear state."""

from __future__ import annotations

from features.video.lib.effect_pack_draft_state import (
    build_applied_effect_pack_draft_state,
    build_cleared_effect_pack_draft_state,
)
from features.video.lib.template_draft_domains import (
    pick_background_draft_slice,
    pick_logo_draft_slice,
    pick_particles_draft_slice,
    pick_spectrum_draft_slice,
)
from features.video.lib.video_template_draft import build_video_template_draft


def test_apply_spectrum_pack_keeps_other_domain_slices() -> None:
    current_template = {
        "style": "straight-bars",
        "spectrumEnabled": True,
        "audioSettings": {
            "inputGain": 1.5,
            "bandContrast": 1.1,
        },
        "position": {
            "anchor": "center",
            "x": 12,
            "y": -6,
        },
        "backgroundSettings": {
            "fitMode": "contain",
            "brightness": 0.7,
            "smoothing": 0.4,
        },
        "logoSettings": {
            "enabled": True,
            "size": 260,
            "opacity": 0.9,
        },
        "particlesSettings": {
            "enabled": True,
            "style": "spark",
            "maxCount": 800,
        },
        "textOverlays": [{"id": "text-1", "text": "Boss"}],
        "layers": [{"name": "Base", "thickness": 20}],
    }
    current_draft = build_video_template_draft(current_template, logo_path="D:/logo.png")

    result = build_applied_effect_pack_draft_state(
        current_draft=current_draft,
        current_template=current_template,
        logo_path="D:/logo.png",
        domain="spectrum",
        item={
            "packId": "pack.spectrum.alpha",
            "version": "1.0.0",
            "templatePatch": {
                "style": "flying-glow",
                "audioSettings": {"inputGain": 4.5},
                "layers": [{"name": "Pack Layer", "thickness": 32}],
            },
        },
    )

    spectrum_slice = pick_spectrum_draft_slice(result["nextDraft"])
    assert spectrum_slice["style"] == "ignition-flare"
    assert spectrum_slice["audioInputGain"] == 4.5
    assert result["nextDraft"]["effectPacks"]["spectrum"] == {
        "packId": "pack.spectrum.alpha",
        "version": "1.0.0",
    }
    assert pick_background_draft_slice(result["nextDraft"]) == pick_background_draft_slice(current_draft)
    assert pick_logo_draft_slice(result["nextDraft"]) == pick_logo_draft_slice(current_draft)
    assert pick_particles_draft_slice(result["nextDraft"]) == pick_particles_draft_slice(current_draft)
    assert result["nextLayers"] == [{"name": "Pack Layer", "thickness": 32}]


def test_clear_only_requested_domain_reference() -> None:
    current_draft = build_video_template_draft(
        {
            "effectPacks": {
                "particles": {"packId": "pack.particles.alpha", "version": "2.0.0"},
            },
            "particlesSettings": {"enabled": True, "style": "glow"},
            "logoSettings": {"enabled": True, "size": 240},
        },
        logo_path="",
    )

    result = build_cleared_effect_pack_draft_state(
        current_draft=current_draft,
        domain="particles",
    )

    assert result["nextDraft"]["effectPacks"]["particles"] is None
    assert result["nextDraft"]["effectPacks"].get("logo") is None
    assert pick_particles_draft_slice(result["nextDraft"]) == pick_particles_draft_slice(current_draft)
    assert result["templatePatch"] == {"effectPacks": {"particles": None}}
