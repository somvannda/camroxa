"""Tests for logo spectrum bindings and particle presets."""

from __future__ import annotations

from features.video.lib.logo_spectrum_bindings import (
    apply_logo_shape_draft_change,
    apply_spectrum_attach_to_logo_draft_change,
)
from features.video.lib.particle_settings import (
    PARTICLE_MOTION_PRESETS,
    build_particle_motion_preset_patch,
    is_particle_preset_active,
)


def test_apply_logo_shape_updates_gap_when_attached() -> None:
    draft = {
        "logoShape": "circle",
        "logoSizeStep": 2,
        "spectrumAttachToLogo": True,
        "spectrumLogoGap": 10,
    }
    next_draft = apply_logo_shape_draft_change(draft, "square")
    assert next_draft["logoShape"] == "square"
    assert next_draft["spectrumLogoGap"] != 10


def test_apply_logo_shape_keeps_gap_when_not_attached() -> None:
    draft = {
        "logoShape": "circle",
        "logoSizeStep": 2,
        "spectrumAttachToLogo": False,
        "spectrumLogoGap": 10,
    }
    next_draft = apply_logo_shape_draft_change(draft, "square")
    assert next_draft["spectrumLogoGap"] == 10


def test_toggle_spectrum_attachment_sets_recommended_gap() -> None:
    draft = {
        "logoShape": "circle",
        "logoSizeStep": 2,
        "spectrumAttachToLogo": False,
        "spectrumLogoGap": 10,
    }
    next_draft = apply_spectrum_attach_to_logo_draft_change(draft, True)
    assert next_draft["spectrumAttachToLogo"] is True
    assert next_draft["spectrumLogoGap"] != 10


def test_particle_presets_apply_and_detect_active_state() -> None:
    for preset_id, _label in PARTICLE_MOTION_PRESETS:
        patch = build_particle_motion_preset_patch(preset_id)
        draft = {"particlesEnabled": False}
        merged = {**draft, **patch}
        assert is_particle_preset_active(merged, preset_id)
