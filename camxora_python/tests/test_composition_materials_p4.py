"""P4 spectrum materials — 20 look packs."""

from __future__ import annotations

import pytest

from features.video.lib.composition_materials import (
    SPECTRUM_MATERIAL_COUNT,
    SPECTRUM_MATERIAL_IDS,
    apply_spectrum_material_to_template,
    get_spectrum_material,
    list_spectrum_material_options,
    normalize_spectrum_material_id,
)
from features.video.lib.composition_spectrum_shapes import apply_spectrum_shape_to_template

CANONICAL_12 = (
    "neon",
    "glass",
    "crystal",
    "electric",
    "fire",
    "ice",
    "metal",
    "liquid",
    "plasma",
    "gold",
    "hologram",
    "carbon",
)
FILL_8 = (
    "chrome",
    "matte",
    "velvet",
    "obsidian",
    "iridescent",
    "latex",
    "frosted_glass",
    "wireframe",
)


def test_material_catalog_count_is_20() -> None:
    assert SPECTRUM_MATERIAL_COUNT == 20
    assert len(SPECTRUM_MATERIAL_IDS) == 20
    assert len(list_spectrum_material_options()) == 20
    for key in CANONICAL_12 + FILL_8:
        assert key in SPECTRUM_MATERIAL_IDS
        assert get_spectrum_material(key) is not None


def test_normalize_material_aliases() -> None:
    assert normalize_spectrum_material_id("Frosted Glass") == "frosted_glass"
    assert normalize_spectrum_material_id("unknown") is None


def test_neon_glass_fire_plasma_circle_same_shape_asset() -> None:
    """Requirement: Neon/Glass/Fire/Plasma Circle without four spectrum assets."""
    base = {"layers": [], "composition": {"spectrum": {"animation": "none"}}}
    apply_spectrum_shape_to_template(base, "circle")
    shape_path = base["layers"][0]["pathMode"]
    assert shape_path == "circle"

    looks: dict[str, dict] = {}
    for material_id in ("neon", "glass", "fire", "plasma"):
        tpl = {
            "layers": [dict(base["layers"][0])],
            "composition": {
                "spectrum": {
                    "shape": "circle",
                    "material": "none",
                    "animation": "none",
                }
            },
            "style": base.get("style"),
        }
        apply_spectrum_material_to_template(tpl, material_id)
        assert tpl["composition"]["spectrum"]["shape"] == "circle"
        assert tpl["composition"]["spectrum"]["material"] == material_id
        assert tpl["layers"][0]["pathMode"] == "circle"
        assert tpl["layers"][0]["curved"] is True
        looks[material_id] = {
            "glow": tpl["layers"][0]["glow"],
            "blur": tpl["layers"][0]["blur"],
            "blend_mode": tpl["layers"][0]["blend_mode"],
            "fillCircle": tpl["layers"][0]["fillCircle"],
        }

    # Materials differ in look, not geometry id
    assert looks["neon"]["glow"] != looks["glass"]["glow"]
    assert looks["neon"]["blend_mode"] == "add"
    assert looks["glass"]["fillCircle"] is True
    assert looks["plasma"]["glow"] >= looks["fire"]["glow"] or looks["plasma"]["fillCircle"] is True


def test_material_does_not_change_hexagon_path() -> None:
    template = {"layers": [], "composition": {"spectrum": {"material": "none", "animation": "pulse"}}}
    apply_spectrum_shape_to_template(template, "hexagon")
    apply_spectrum_material_to_template(template, "hologram")
    assert template["composition"]["spectrum"]["shape"] == "hexagon"
    assert template["composition"]["spectrum"]["material"] == "hologram"
    assert template["composition"]["spectrum"]["animation"] == "pulse"
    assert template["layers"][0]["pathMode"] == "hexagon"
    assert template["layers"][0]["blend_mode"] == "add"


@pytest.mark.parametrize("material_id", CANONICAL_12 + FILL_8)
def test_every_material_applies_on_circle(material_id: str) -> None:
    template = {"layers": [], "composition": {"spectrum": {"animation": "none"}}}
    apply_spectrum_shape_to_template(template, "circle")
    apply_spectrum_material_to_template(template, material_id)
    assert template["composition"]["spectrum"]["shape"] == "circle"
    assert template["composition"]["spectrum"]["material"] == material_id
    mat = get_spectrum_material(material_id)
    assert mat is not None
    assert template["layers"][0]["glow"] == mat["look"]["glow"]


def test_unknown_material_raises() -> None:
    with pytest.raises(ValueError):
        apply_spectrum_material_to_template({}, "not-a-material")
