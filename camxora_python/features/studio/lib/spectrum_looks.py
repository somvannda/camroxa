"""Studio spectrum look recipes — multi-layer looks (Trap Nation-style glow, etc.)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Selectable looks for Spectrum inspector. ``none`` leaves the current stack alone.
SPECTRUM_LOOK_OPTIONS: tuple[tuple[str, str], ...] = (
    ("none", "Custom (keep layers)"),
    ("prism-core-glow", "Prism Core Glow"),
)

_RAINBOW_STOPS = (
    "#b000ff",
    "#0040ff",
    "#00c8ff",
    "#00ff66",
    "#ffee00",
    "#ff9900",
    "#ff2200",
    "#ff0080",
)


def list_spectrum_look_options() -> tuple[tuple[str, str], ...]:
    return SPECTRUM_LOOK_OPTIONS


def normalize_spectrum_look_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower().replace(" ", "-").replace("_", "-")
    if not raw or raw in ("none", "custom", "custom-(keep-layers)"):
        return None
    aliases = {
        "prism-core-glow": "prism-core-glow",
        "prism-core": "prism-core-glow",
        "prism": "prism-core-glow",
        "trap-nation": "prism-core-glow",
        "trap-nation-glow": "prism-core-glow",
        "nation-glow": "prism-core-glow",
        "rainbow-glow": "prism-core-glow",
    }
    return aliases.get(raw)


def _solid(hex_color: str) -> dict[str, Any]:
    return {"mode": "solid", "solidColor": str(hex_color), "gradientColors": [str(hex_color), "#ffffff"]}


def _circular_rainbow() -> dict[str, Any]:
    stops = list(_RAINBOW_STOPS)
    return {
        "mode": "gradient",
        "solidColor": stops[0],
        "gradientColors": stops,
        "gradientDirection": "circular",
    }


def prism_core_glow_layers() -> list[dict[str, Any]]:
    """Three stacked rings: soft aura → rainbow body → white core."""
    return [
        {
            "name": "Soft Aura",
            "enabled": True,
            "radiusOffset": 14.0,
            "opacity": 0.48,
            "audioGain": 1.05,
            "barHeight": 1.15,
            "barWidthScale": 1.55,
            "thicknessScale": 1.35,
            "barCount": 96,
            "tipTaper": 0.15,
            "mirrored": True,
            "gravity": "outward",
            "peakCapsEnabled": False,
            "solidBand": False,
            "glow": 0.92,
            "blur": 5.5,
            "fillCircle": True,
            "blend_mode": "add",
            "stylePreset": "plasma-bloom",
            "color": _circular_rainbow(),
        },
        {
            "name": "Rainbow Body",
            "enabled": True,
            "radiusOffset": 4.0,
            "opacity": 0.88,
            "audioGain": 1.0,
            "barHeight": 1.0,
            "barWidthScale": 1.35,
            "thicknessScale": 1.05,
            "barCount": 96,
            "tipTaper": 0.2,
            "mirrored": True,
            "gravity": "outward",
            "peakCapsEnabled": False,
            "solidBand": False,
            "glow": 0.62,
            "blur": 1.8,
            "fillCircle": True,
            "blend_mode": "add",
            "stylePreset": "plasma-bloom",
            "color": _circular_rainbow(),
        },
        {
            "name": "White Core",
            "enabled": True,
            "radiusOffset": 0.0,
            "opacity": 1.0,
            "audioGain": 0.95,
            "barHeight": 0.82,
            "barWidthScale": 1.15,
            "thicknessScale": 0.72,
            "barCount": 96,
            "tipTaper": 0.05,
            "mirrored": True,
            "gravity": "outward",
            "peakCapsEnabled": False,
            "solidBand": False,
            "glow": 0.12,
            "blur": 0.0,
            "fillCircle": True,
            "blend_mode": "normal",
            "stylePreset": "plasma-bloom",
            "color": _solid("#ffffff"),
        },
    ]


def spectrum_look_axis_patch(look_id: str | None) -> dict[str, Any]:
    """Axis patch that seeds Shape / Material / Palette / Layers for a look."""
    key = normalize_spectrum_look_id(look_id)
    if key is None:
        return {"compositionSpectrumLook": None}
    if key == "prism-core-glow":
        return {
            "compositionSpectrumLook": key,
            "compositionSpectrumShape": "circle",
            "compositionSpectrumMaterial": "plasma",
            "compositionSpectrumColorPalette": "rainbow",
            "compositionSpectrumGradientColors": list(_RAINBOW_STOPS),
            "compositionSpectrumLayers": deepcopy(prism_core_glow_layers()),
            "compositionSpectrumLayerIndex": 2,  # white core selected
            "spectrumAttachToLogo": True,
            "compositionLogoContainInShape": True,
            "compositionLogoFitToShape": True,
            "compositionLogoMaskShape": "circle",
            "compositionLogoOffsetX": 0.0,
            "compositionLogoOffsetY": 0.0,
        }
    return {"compositionSpectrumLook": None}


__all__ = (
    "SPECTRUM_LOOK_OPTIONS",
    "list_spectrum_look_options",
    "normalize_spectrum_look_id",
    "prism_core_glow_layers",
    "spectrum_look_axis_patch",
)
