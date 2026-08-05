"""P3 spectrum shapes — catalog + path geometry."""

from __future__ import annotations

import numpy as np
import pytest

from features.video.lib.composition_spectrum_shapes import (
    SPECTRUM_SHAPE_COUNT,
    SPECTRUM_SHAPE_IDS,
    apply_spectrum_shape_to_template,
    list_spectrum_shape_options,
    normalize_spectrum_shape_id,
    spectrum_shape_layer_recipe,
)
from visualizer._spectrum_fast import (
    generate_spectrum_layer_geometry,
    normalize_spectrum_path_mode,
    resolve_spectrum_path_mode,
)

CANONICAL_12 = (
    "circle",
    "double_circle",
    "wave",
    "bars",
    "hexagon",
    "diamond",
    "triangle",
    "infinity",
    "heart",
    "audio_ribbon",
    "spiral",
    "tunnel",
)
FILL_3 = ("ring", "starburst", "pillars")


def test_shape_catalog_count_is_15() -> None:
    assert SPECTRUM_SHAPE_COUNT == 15
    assert len(SPECTRUM_SHAPE_IDS) == 15
    assert len(list_spectrum_shape_options()) == 15
    for key in CANONICAL_12 + FILL_3:
        assert key in SPECTRUM_SHAPE_IDS


def test_normalize_shape_aliases() -> None:
    assert normalize_spectrum_shape_id("Double Circle") == "double_circle"
    assert normalize_spectrum_shape_id("orbit-spikes") == "bars"
    assert normalize_spectrum_shape_id("nope") is None


@pytest.mark.parametrize(
    "path_mode",
    ["triangle", "diamond", "hexagon", "heart", "infinity", "spiral", "tunnel", "circle"],
)
def test_extended_path_modes_generate_points(path_mode: str) -> None:
    assert normalize_spectrum_path_mode(path_mode) == path_mode
    assert (
        resolve_spectrum_path_mode(
            path_mode,
            curved=True,
            attached_to_logo=False,
            logo_shape="circle",
        )
        == path_mode
    )
    px, py, dx, dy, total = generate_spectrum_layer_geometry(
        48,
        curved=True,
        mirrored=True,
        gravity="outward",
        path_mode=path_mode,
        radius=120.0,
    )
    assert len(px) == 48
    assert len(py) == 48
    assert len(dx) == 48
    assert len(dy) == 48
    assert total > 1.0
    assert np.all(np.isfinite(px))
    assert np.all(np.isfinite(py))


def test_apply_shape_preserves_material_and_colors() -> None:
    template = {
        "style": "orbit-spikes",
        "layers": [
            {
                "curved": False,
                "color": {
                    "mode": "gradient",
                    "solidColor": "#ff00ff",
                    "gradientColors": ["#ff00ff", "#00ffff"],
                    "gradientDirection": "left-to-right",
                },
            }
        ],
        "composition": {
            "version": 1,
            "spectrum": {"shape": "bars", "material": "neon", "animation": "pulse"},
            "colorPalette": "synthwave",
        },
    }
    apply_spectrum_shape_to_template(template, "hexagon")
    assert template["composition"]["spectrum"]["shape"] == "hexagon"
    assert template["composition"]["spectrum"]["material"] == "neon"
    assert template["composition"]["spectrum"]["animation"] == "pulse"
    assert template["composition"]["colorPalette"] == "synthwave"
    assert template["layers"][0]["pathMode"] == "hexagon"
    assert template["layers"][0]["color"]["solidColor"] == "#ff00ff"


def test_double_circle_is_two_layers() -> None:
    layers = spectrum_shape_layer_recipe("double_circle")
    assert len(layers) == 2
    assert layers[0]["pathMode"] == "circle"
    assert layers[1]["radiusOffset"] == 28.0


@pytest.mark.parametrize("shape_id", CANONICAL_12 + FILL_3)
def test_every_shape_applies(shape_id: str) -> None:
    template = {"layers": [], "composition": {"spectrum": {"material": "glass", "animation": "none"}}}
    apply_spectrum_shape_to_template(template, shape_id)
    assert template["composition"]["spectrum"]["shape"] == shape_id
    assert template["composition"]["spectrum"]["material"] == "glass"
    assert isinstance(template["layers"], list) and template["layers"]
    # Geometry must resolve for preview/export path builder
    layer = template["layers"][0]
    px, py, *_rest = generate_spectrum_layer_geometry(
        32,
        curved=bool(layer.get("curved")),
        mirrored=bool(layer.get("mirrored")),
        gravity=str(layer.get("gravity") or "outward"),
        path_mode=str(layer.get("pathMode") or "auto"),
        radius=100.0,
    )
    assert len(px) == 32
    assert len(py) == 32


def test_unknown_shape_raises() -> None:
    with pytest.raises(ValueError):
        apply_spectrum_shape_to_template({}, "not-a-shape")
