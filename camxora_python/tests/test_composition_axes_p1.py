"""P1 orthogonal composition axes."""

from __future__ import annotations

from features.video.lib.composition_axes import (
    apply_lighting_axes,
    apply_particles_axes,
    apply_spectrum_axes,
    apply_spectrum_preset_convenience,
    sync_legacy_aliases_from_composition,
)
from features.video.lib.composition_scene_contract import (
    composition_from_legacy_template,
    ensure_composition_on_template,
)
from features.video.lib.spectrum_style_registry import build_spectrum_preset_template


def test_spectrum_shape_does_not_force_material() -> None:
    scene = apply_spectrum_axes(None, material="neon", animation="pulse")
    assert scene["spectrum"]["material"] == "neon"
    assert scene["spectrum"]["animation"] == "pulse"
    scene = apply_spectrum_axes(scene, shape="circle")
    assert scene["spectrum"]["shape"] == "circle"
    assert scene["spectrum"]["material"] == "neon"
    assert scene["spectrum"]["animation"] == "pulse"


def test_spectrum_material_does_not_change_shape() -> None:
    scene = apply_spectrum_axes(None, shape="double-circle")
    scene = apply_spectrum_axes(scene, material="glass")
    assert scene["spectrum"]["shape"] == "double-circle"
    assert scene["spectrum"]["material"] == "glass"


def test_particles_and_lighting_axes_independent() -> None:
    scene = apply_particles_axes(None, type="dust", behavior="pulse")
    scene = apply_particles_axes(scene, type="snow")
    assert scene["particles"]["type"] == "snow"
    assert scene["particles"]["behavior"] == "pulse"

    scene = apply_lighting_axes(scene, effect="lightning", trigger="bass")
    scene = apply_lighting_axes(scene, effect="halo")
    assert scene["lighting"]["effect"] == "halo"
    assert scene["lighting"]["trigger"] == "bass"


def test_legacy_reproject_preserves_orthogonal_axes() -> None:
    template = {
        "style": "orbit-spikes",
        "composition": {
            "version": 1,
            "spectrum": {"shape": "orbit-spikes", "material": "neon", "animation": "pulse"},
            "particles": {"type": "dust", "behavior": "bounce"},
            "audio": {"mapping": {"logo": "vocals"}},
        },
    }
    scene = composition_from_legacy_template(template)
    assert scene["spectrum"]["shape"] == "orbit-spikes"
    assert scene["spectrum"]["material"] == "neon"
    assert scene["spectrum"]["animation"] == "pulse"
    assert scene["particles"]["behavior"] == "bounce"
    assert scene["audio"]["mapping"] == {"logo": "vocals"}

    template["style"] = "plasma-bloom"
    ensure_composition_on_template(template)
    assert template["composition"]["spectrum"]["shape"] == "plasma-bloom"
    assert template["composition"]["spectrum"]["material"] == "neon"
    assert template["composition"]["spectrum"]["animation"] == "pulse"


def test_preset_convenience_sets_shape_keeps_material() -> None:
    scene = apply_spectrum_axes(None, material="neon", animation="breathing")
    scene = apply_spectrum_preset_convenience(scene, "straight-bars")
    # alias → orbit-spikes
    assert scene["spectrum"]["shape"] == "orbit-spikes"
    assert scene["spectrum"]["material"] == "neon"
    assert scene["spectrum"]["animation"] == "breathing"


def test_build_spectrum_preset_template_attaches_composition_shape() -> None:
    template = {
        "composition": {
            "version": 1,
            "spectrum": {"shape": "none", "material": "glass", "animation": "pulse"},
        }
    }
    patched = build_spectrum_preset_template(template, "ignition-flare")
    assert patched["style"] == "ignition-flare"
    assert patched["composition"]["spectrum"]["shape"] == "ignition-flare"
    assert patched["composition"]["spectrum"]["material"] == "glass"
    assert patched["composition"]["spectrum"]["animation"] == "pulse"


def test_sync_legacy_style_alias_from_composition_shape() -> None:
    template = {
        "style": "orbit-spikes",
        "composition": {
            "version": 1,
            "spectrum": {"shape": "circle", "material": "neon", "animation": "none"},
            "particles": {"type": "embers", "behavior": "none"},
        },
    }
    sync_legacy_aliases_from_composition(template)
    assert template["style"] == "circle"
    # P6: composition type id stays semantic; GPU variant is classic/bokeh/soap/dust.
    assert template["particlesSettings"]["variant"] == "classic"
