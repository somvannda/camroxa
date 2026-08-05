"""P2 color palettes — 20 named catalogs."""

from __future__ import annotations

import pytest

from features.video.lib.composition_color_palettes import (
    COLOR_PALETTE_COUNT,
    COLOR_PALETTE_IDS,
    apply_color_palette_to_template,
    get_color_palette,
    list_color_palette_options,
    normalize_color_palette_id,
)


CANONICAL_12 = (
    "cyberpunk",
    "synthwave",
    "festival",
    "edm",
    "dubstep",
    "future_bass",
    "sunset",
    "aurora",
    "galaxy",
    "fire",
    "ocean",
    "monochrome",
)

FILL_8 = (
    "midnight",
    "neon_pink",
    "tropical",
    "industrial",
    "candy",
    "blood_moon",
    "arctic",
    "gold_rush",
)


def test_palette_catalog_count_is_20() -> None:
    assert COLOR_PALETTE_COUNT == 20
    assert len(COLOR_PALETTE_IDS) == 20
    assert len(list_color_palette_options()) == 20
    for key in CANONICAL_12 + FILL_8:
        assert key in COLOR_PALETTE_IDS
        assert get_color_palette(key) is not None


def test_normalize_palette_aliases() -> None:
    assert normalize_color_palette_id("Future Bass") == "future_bass"
    assert normalize_color_palette_id("neon-pink") == "neon_pink"
    assert normalize_color_palette_id("unknown-palette") is None


def test_apply_palette_paints_spectrum_particles_lighting_text() -> None:
    template = {
        "layers": [{"id": "l1", "color": {"mode": "solid", "solidColor": "#ffffff"}}],
        "particlesSettings": {"enabled": True, "color": "#ffffff", "reactColor": "#000000"},
        "lightningLayers": [
            {
                "id": "bolt-1",
                "color": {"mode": "solid", "solidColor": "#ffffff", "gradientColors": ["#fff", "#000"]},
            }
        ],
        "textOverlays": [{"enabled": True, "text": "Hi", "color": "#ffffff", "strokeColor": "#000000"}],
        "albumText": {"enabled": True, "style": {"fillMode": "solid"}},
        "overlaySettings": {"enabled": True, "items": [{"id": "frame-1", "color": "#111111"}]},
    }
    apply_color_palette_to_template(template, "synthwave")
    palette = get_color_palette("synthwave")
    assert palette is not None
    assert template["composition"]["colorPalette"] == "synthwave"
    assert template["layers"][0]["color"]["mode"] == "gradient"
    assert template["layers"][0]["color"]["gradientColors"] == palette["stops"]
    assert template["particlesSettings"]["color"] == palette["solid"]
    assert template["particlesSettings"]["reactColor"] == palette["accent"]
    assert template["particlesSettings"]["paletteColors"] == palette["stops"]
    assert template["lightningLayers"][0]["color"]["solidColor"] == palette["solid"]
    assert template["textOverlays"][0]["color"] == palette["solid"]
    assert template["albumText"]["style"]["fillMode"] == "gradient"
    assert template["overlaySettings"]["items"][0]["color"] == palette["solid"]


@pytest.mark.parametrize("palette_id", CANONICAL_12 + FILL_8)
def test_every_palette_applies(palette_id: str) -> None:
    template = {
        "layers": [{"color": {"mode": "solid", "solidColor": "#fff"}}],
        "particlesSettings": {},
        "lightningLayers": [{"color": {"mode": "gradient", "solidColor": "#fff", "gradientColors": ["#fff", "#000"]}}],
    }
    apply_color_palette_to_template(template, palette_id)
    assert template["composition"]["colorPalette"] == palette_id


def test_unknown_palette_raises() -> None:
    with pytest.raises(ValueError):
        apply_color_palette_to_template({}, "not-a-real-palette")
