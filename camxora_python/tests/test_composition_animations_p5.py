"""P5 animation behaviors — Layer 4 shared motion library (12)."""

from __future__ import annotations

import pytest

from features.video.lib.composition_animations import (
    ANIMATION_BEHAVIOR_COUNT,
    ANIMATION_BEHAVIOR_IDS,
    ANIMATION_TARGETS,
    apply_animation_behavior_to_template,
    apply_spectrum_animation_to_template,
    get_animation_behavior,
    list_animation_behavior_options,
    normalize_animation_behavior_id,
)
from features.video.lib.composition_materials import apply_spectrum_material_to_template
from features.video.lib.composition_scene_contract import ensure_composition_on_template
from features.video.lib.composition_spectrum_shapes import apply_spectrum_shape_to_template

CANONICAL_12 = (
    "pulse",
    "bounce",
    "rotate",
    "expand",
    "contract",
    "ripple",
    "wave",
    "twist",
    "elastic",
    "fade",
    "flash",
    "breathing",
)


def test_animation_catalog_count_is_12() -> None:
    assert ANIMATION_BEHAVIOR_COUNT == 12
    assert len(ANIMATION_BEHAVIOR_IDS) == 12
    assert len(list_animation_behavior_options()) == 12
    for key in CANONICAL_12:
        assert key in ANIMATION_BEHAVIOR_IDS
        assert get_animation_behavior(key) is not None


def test_normalize_behavior_aliases() -> None:
    assert normalize_animation_behavior_id("Breathing") == "breathing"
    assert normalize_animation_behavior_id("unknown") is None


def test_spectrum_animation_preserves_shape_and_material() -> None:
    template: dict = {"layers": [], "composition": {"spectrum": {"animation": "none"}}}
    apply_spectrum_shape_to_template(template, "circle")
    apply_spectrum_material_to_template(template, "neon")
    apply_spectrum_animation_to_template(template, "pulse")
    assert template["composition"]["spectrum"]["shape"] == "circle"
    assert template["composition"]["spectrum"]["material"] == "neon"
    assert template["composition"]["spectrum"]["animation"] == "pulse"
    assert template["layers"][0]["pathMode"] == "circle"
    assert float(template["audioSettings"]["kickImpact"]) == pytest.approx(0.55)


def test_same_behavior_id_on_multiple_objects() -> None:
    template: dict = {
        "layers": [],
        "logoSettings": {"enabled": True},
        "overlaySettings": {"enabled": True, "items": []},
        "particlesSettings": {"enabled": True, "variant": "dust"},
        "composition": {
            "spectrum": {"shape": "none", "material": "none", "animation": "none"},
            "particles": {"type": "dust", "behavior": "none"},
        },
    }
    apply_spectrum_shape_to_template(template, "hexagon")
    apply_animation_behavior_to_template(template, "bounce", targets=ANIMATION_TARGETS)
    scene = template["composition"]
    assert scene["spectrum"]["animation"] == "bounce"
    assert scene["logo"]["animation"] == "bounce"
    assert scene["overlay"]["animation"] == "bounce"
    assert scene["particles"]["behavior"] == "bounce"
    assert scene["spectrum"]["shape"] == "hexagon"
    assert scene["particles"]["type"] == "dust"
    assert template["logoSettings"]["motionMode"] == "both"
    assert template["overlaySettings"]["animation"] == "bounce"
    assert template["particlesSettings"]["behavior"] == "bounce"


@pytest.mark.parametrize("behavior_id", CANONICAL_12)
def test_every_behavior_applies_on_spectrum(behavior_id: str) -> None:
    template: dict = {"layers": [], "composition": {"spectrum": {"material": "glass"}}}
    apply_spectrum_shape_to_template(template, "circle")
    apply_spectrum_material_to_template(template, "glass")
    apply_spectrum_animation_to_template(template, behavior_id)
    assert template["composition"]["spectrum"]["animation"] == behavior_id
    assert template["composition"]["spectrum"]["shape"] == "circle"
    assert template["composition"]["spectrum"]["material"] == "glass"


def test_canonical_logo_animation_survives_reproject() -> None:
    template: dict = {
        "logoSettings": {"enabled": True, "spinEnabled": True},
        "composition": {"logo": {"enabled": True, "animation": "breathing"}},
    }
    ensure_composition_on_template(template)
    assert template["composition"]["logo"]["animation"] == "breathing"


def test_unknown_behavior_raises() -> None:
    with pytest.raises(ValueError):
        apply_animation_behavior_to_template({}, "not-a-behavior")


def test_empty_targets_raises() -> None:
    with pytest.raises(ValueError):
        apply_animation_behavior_to_template({"composition": {}}, "pulse", targets=())
