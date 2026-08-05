"""Camxora-native spectrum preset registry.

Marketplace contract stays unchanged:
- template.style (string style id)
- template.layers[] (geometry + color + glow)
- effectPacks.spectrum { packId, version }

Built-in looks are Camxora originals. Legacy python_app / Electron style ids
alias into these so installed packs keep working.
"""

from __future__ import annotations

import copy
from typing import Any

from features.video.lib.spectrum_color_engine import (
    SPECTRUM_GRADIENT_PRESET_OPTIONS,
    spectrum_gradient_preset_colors,
)
from features.video.lib.video_template_draft import normalize_spectrum_preset_key
from visualizer.template_runtime import normalize_renderer_template

PACK_PRESET_PREFIX = "pack:"

# Bright palette catalog → style recipes (one palette per built-in look).
_P = {label: spectrum_gradient_preset_colors(value) for value, label in SPECTRUM_GRADIENT_PRESET_OPTIONS}


def _gradient(colors: list[str], *, direction: str = "left-to-right") -> dict[str, Any]:
    return {
        "mode": "gradient",
        "gradientColors": list(colors),
        "gradientDirection": direction,
    }

# Camxora built-in single styles (marketplace-sellable ids).
SPECTRUM_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("orbit-spikes", "Orbit Spikes"),
    ("signal-needles", "Signal Needles"),
    ("pulse-beads", "Pulse Beads"),
    ("mirror-blades", "Mirror Blades"),
    ("aurora-ribbon", "Aurora Ribbon"),
    ("magma-ridge", "Magma Ridge"),
    ("plasma-bloom", "Plasma Bloom"),
    ("contour-waves", "Contour Waves"),
    ("grid-steps", "Grid Steps"),
    ("ignition-flare", "Ignition Flare"),
    ("drift-capsules", "Drift Capsules"),
)

STACKED_SPECTRUM_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("triple-halo-orbit", "Triple Halo Orbit"),
    ("bass-core-bloom", "Bass Core Bloom"),
    ("mist-ribbon-stack", "Mist Ribbon Stack"),
)

ANCHOR_OPTIONS: tuple[tuple[str, str], ...] = (
    ("top-left", "Top Left"),
    ("top-center", "Top Center"),
    ("top-right", "Top Right"),
    ("center", "Center"),
    ("bottom-left", "Bottom Left"),
    ("bottom-center", "Bottom Center"),
    ("bottom-right", "Bottom Right"),
)

# Straight-bar Camxora recipes; Curve 180 / Mirror 360 turn them into a ring.
# Colors come from the bright SPECTRUM_GRADIENT_PRESET_OPTIONS catalog.
# Glow stays off by default so hue stays clear (glow washes to haze).
STYLE_PRESET_PATCHES: dict[str, dict[str, Any]] = {
    "orbit-spikes": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 5.0,
        "thickness": 36.0,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "color": _gradient(_P["Prism Beam"]),
    },
    "signal-needles": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 1.6,
        "thickness": 44.0,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "color": _gradient(_P["Electric Sky"]),
    },
    "pulse-beads": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 4.5,
        "thickness": 40.0,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "color": _gradient(_P["Hot Magenta"]),
    },
    "mirror-blades": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 5.5,
        "thickness": 42.0,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "color": _gradient(_P["Mint Freeze"]),
    },
    "aurora-ribbon": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 6.0,
        "thickness": 28.0,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "color": _gradient(_P["Neon Candy"]),
    },
    "magma-ridge": {
        "curved": False,
        "mirrored": False,
        "fillCircle": True,
        "barWidth": 7.0,
        "thickness": 58.0,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "color": _gradient(_P["Solar Pop"]),
    },
    "plasma-bloom": {
        "curved": False,
        "mirrored": False,
        "fillCircle": True,
        "barWidth": 10.0,
        "thickness": 46.0,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "color": _gradient(_P["Violet Ice"]),
    },
    "contour-waves": {
        "curved": True,
        "mirrored": True,
        "fillCircle": False,
        "solidBand": False,
        "barWidth": 2.0,
        "thickness": 48.0,
        "barCount": 96,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "reflectionEnabled": True,
        "reflectionOpacity": 0.28,
        "color": _gradient(_P["Aqua Flame"]),
    },
    "grid-steps": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 6.0,
        "thickness": 38.0,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "color": _gradient(_P["Lime Pulse"]),
    },
    "ignition-flare": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 7.5,
        "thickness": 48.0,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "color": _gradient(_P["Coral Wave"]),
    },
    "drift-capsules": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 6.5,
        "thickness": 34.0,
        "gravity": "top",
        "glow": 0,
        "blur": 0,
        "blend_mode": "normal",
        "color": _gradient(_P["Peach Neon"]),
    },
}

for _style_patch in STYLE_PRESET_PATCHES.values():
    _style_patch.setdefault("opacity", 1.0)

STACKED_LAYER_PRESETS: dict[str, dict[str, Any]] = {
    "triple-halo-orbit": {
        "style": "ignition-flare",
        "layers": [
            {
                "name": "Core Flare",
                "radiusOffset": 0,
                "barWidth": 10,
                "thickness": 28,
                "fillCircle": True,
                "opacity": 0.95,
                "blend_mode": "normal",
                "glow": 0,
                "blur": 0,
                "color": _gradient(_P["Solar Pop"], direction="circular"),
            },
            {
                "name": "Pulse Orbit",
                "radiusOffset": 28,
                "barWidth": 8,
                "thickness": 44,
                "fillCircle": False,
                "opacity": 0.9,
                "blend_mode": "normal",
                "glow": 0,
                "blur": 0,
                "color": _gradient(_P["Hot Magenta"], direction="circular"),
            },
            {
                "name": "Outer Halo",
                "radiusOffset": 58,
                "barWidth": 7,
                "thickness": 32,
                "fillCircle": False,
                "opacity": 0.88,
                "blend_mode": "normal",
                "glow": 0,
                "blur": 0,
                "color": _gradient(_P["Electric Sky"], direction="circular"),
            },
        ],
    },
    "bass-core-bloom": {
        "style": "plasma-bloom",
        "layers": [
            {
                "name": "Bloom Core",
                "radiusOffset": 0,
                "barWidth": 12,
                "thickness": 38,
                "fillCircle": True,
                "opacity": 0.94,
                "blend_mode": "normal",
                "glow": 0,
                "blur": 0,
                "color": _gradient(_P["Violet Ice"], direction="circular"),
            },
            {
                "name": "Energy Ring",
                "radiusOffset": 24,
                "barWidth": 11,
                "thickness": 54,
                "fillCircle": False,
                "opacity": 0.9,
                "blend_mode": "normal",
                "glow": 0,
                "blur": 0,
                "color": _gradient(_P["Neon Candy"], direction="circular"),
            },
            {
                "name": "Shock Aura",
                "radiusOffset": 54,
                "barWidth": 6,
                "thickness": 62,
                "fillCircle": False,
                "opacity": 0.85,
                "blend_mode": "normal",
                "glow": 0,
                "blur": 0,
                "color": _gradient(_P["Prism Bright"], direction="radial"),
            },
        ],
    },
    "mist-ribbon-stack": {
        "style": "aurora-ribbon",
        "layers": [
            {
                "name": "Base Mist",
                "radiusOffset": 0,
                "barWidth": 8,
                "thickness": 24,
                "fillCircle": False,
                "opacity": 0.92,
                "blend_mode": "normal",
                "glow": 0,
                "blur": 0,
                "color": _gradient(_P["Mint Freeze"], direction="circular"),
            },
            {
                "name": "Bright Ribbon",
                "radiusOffset": 22,
                "barWidth": 5,
                "thickness": 30,
                "fillCircle": False,
                "opacity": 0.9,
                "blend_mode": "normal",
                "glow": 0,
                "blur": 0,
                "color": _gradient(_P["Neon Candy"], direction="circular"),
            },
            {
                "name": "Outer Drift",
                "radiusOffset": 44,
                "barWidth": 9,
                "thickness": 20,
                "fillCircle": False,
                "opacity": 0.86,
                "blend_mode": "normal",
                "glow": 0,
                "blur": 0,
                "color": _gradient(_P["Peach Neon"], direction="radial"),
            },
        ],
    },
}

# Legacy / pack style ids → Camxora native ids (marketplace-safe).
_PRESET_ALIASES = {
    # Camxora native (identity)
    "orbit-spikes": "orbit-spikes",
    "signal-needles": "signal-needles",
    "pulse-beads": "pulse-beads",
    "mirror-blades": "mirror-blades",
    "aurora-ribbon": "aurora-ribbon",
    "magma-ridge": "magma-ridge",
    "plasma-bloom": "plasma-bloom",
    "contour-waves": "contour-waves",
    "grid-steps": "grid-steps",
    "ignition-flare": "ignition-flare",
    "drift-capsules": "drift-capsules",
    # Legacy python_app / Electron
    "classic-vertical": "orbit-spikes",
    "straight-bars": "orbit-spikes",
    "thin-lines": "signal-needles",
    "dot-matrix": "pulse-beads",
    "symmetrical-bars": "mirror-blades",
    "symmetrical": "mirror-blades",
    "orbital-bars": "mirror-blades",
    "soft-waveform": "aurora-ribbon",
    "continuous-waveform": "aurora-ribbon",
    "wave-ribbon": "aurora-ribbon",
    "mountain": "magma-ridge",
    "liquid": "plasma-bloom",
    "liquid-mass": "plasma-bloom",
    "radio-wave": "contour-waves",
    "contour": "contour-waves",
    "contour-wave": "contour-waves",
    "pixel-bars": "grid-steps",
    "neon-pulse": "ignition-flare",
    "flying-glow": "ignition-flare",
    "halo-stack": "ignition-flare",
    "floating-blocks": "drift-capsules",
    # Legacy stacked names
    "triple-neon-halo": "triple-halo-orbit",
    "bass-vortex-stack": "bass-core-bloom",
    "soft-aura-stack": "mist-ribbon-stack",
}

WAVEFORM_STYLE_IDS = frozenset({"aurora-ribbon", "magma-ridge", "plasma-bloom"})
CONTOUR_STYLE_IDS = frozenset({"contour-waves"})
BAR_STYLE_IDS = frozenset(
    {
        "orbit-spikes",
        "signal-needles",
        "pulse-beads",
        "mirror-blades",
        "grid-steps",
        "ignition-flare",
        "drift-capsules",
    }
)
FLARE_STYLE_IDS = frozenset({"ignition-flare"})


def encode_pack_preset_key(pack_id: str, version: str) -> str:
    return f"{PACK_PRESET_PREFIX}{pack_id}::{version}"


def parse_pack_preset_key(preset_key: str) -> dict[str, str] | None:
    raw = str(preset_key or "")
    if not raw.startswith(PACK_PRESET_PREFIX):
        return None
    from features.video.lib.effect_pack_runtime import parse_effect_pack_catalog_value

    return parse_effect_pack_catalog_value(raw[len(PACK_PRESET_PREFIX) :])


def build_unified_spectrum_preset_options(
    catalog_items: list[dict[str, Any]] | None = None,
) -> tuple[tuple[str, str], ...]:
    options: list[tuple[str, str]] = list(SPECTRUM_PRESET_OPTIONS)
    for item in catalog_items or []:
        if item.get("domain") != "spectrum":
            continue
        if item.get("status") not in {"ready", "available"}:
            continue
        pack_id = str(item.get("packId") or "").strip()
        version = str(item.get("version") or "").strip()
        name = str(item.get("name") or pack_id).strip()
        if not pack_id or not version:
            continue
        options.append(
            (
                encode_pack_preset_key(pack_id, version),
                f"{name} ({version})",
            )
        )
    return tuple(options)


def normalize_spectrum_preset_key_for_apply(preset_key: str) -> str:
    normalized = str(preset_key or "").strip().lower()
    if not normalized:
        return "orbit-spikes"
    return _PRESET_ALIASES.get(normalized, normalized)


def is_waveform_spectrum_style(style_key: str) -> bool:
    return normalize_spectrum_preset_key_for_apply(style_key) in WAVEFORM_STYLE_IDS


def is_contour_spectrum_style(style_key: str) -> bool:
    return normalize_spectrum_preset_key_for_apply(style_key) in CONTOUR_STYLE_IDS


def is_flare_spectrum_style(style_key: str) -> bool:
    return normalize_spectrum_preset_key_for_apply(style_key) in FLARE_STYLE_IDS


# curved / mirrored / gravity are user-owned (Circle Form + Bar Growth).
# Style recipes still seed defaults when a preset is applied via
# ``build_spectrum_preset_template``; hydrate must not overwrite user gravity.
_STYLE_GEOMETRY_KEYS: tuple[str, ...] = ()


def style_geometry_patch(style_key: str) -> dict[str, Any]:
    """Legacy helper — no longer forces gravity (user-owned Bar Growth)."""
    del style_key
    return {}


def align_spectrum_layers_to_style_geometry(
    layers: list[dict[str, Any]] | None,
    style_key: str,
) -> list[dict[str, Any]]:
    """Pass-through clone. Gravity / circle form stay under user control.

    Kept for call-site compatibility after Bar Growth became user-owned.
    """
    del style_key
    return clone_layers(layers)


def clone_layers(layers: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [copy.deepcopy(item) for item in (layers or []) if isinstance(item, dict)]


def heal_spectrum_layer_visibility(layers: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """If every ring is fully transparent, restore opacity so styles are visible again.

    Accidental Opacity=0 (or leftover from edits) makes every style preset look
    \"broken\" because ``build_spectrum_preset_template`` used to keep the old
    opacity when the recipe did not set one.
    """
    out = clone_layers(layers)
    if not out:
        return out
    opacities: list[float] = []
    for layer in out:
        try:
            opacities.append(float(layer.get("opacity", 1.0)))
        except (TypeError, ValueError):
            opacities.append(1.0)
    if opacities and all(value <= 0.001 for value in opacities):
        for layer in out:
            layer["opacity"] = 1.0
    return out


def build_spectrum_preset_template(
    template: dict[str, Any],
    preset_key: str,
    *,
    layer_index: int = 0,
    replace_stack: bool = True,
) -> dict[str, Any]:
    """Apply a single Camxora style preset.

    By default replaces the whole layer stack with one patched layer so leftover
    layers cannot render two geometries. Packs still use the same style+layers shape.
    """
    normalized = normalize_spectrum_preset_key_for_apply(preset_key)
    patch = STYLE_PRESET_PATCHES.get(normalized, STYLE_PRESET_PATCHES["orbit-spikes"])
    style_key = normalized if normalized in STYLE_PRESET_PATCHES else "orbit-spikes"

    raw_layers = template.get("layers") if isinstance(template.get("layers"), list) else []
    fallback_layer = copy.deepcopy(raw_layers[0]) if raw_layers and isinstance(raw_layers[0], dict) else {
        "color": {"mode": "solid", "solidColor": "#ffffff"}
    }
    layers = [copy.deepcopy(item) for item in raw_layers if isinstance(item, dict)]
    while len(layers) <= int(max(0, layer_index)):
        layers.append(copy.deepcopy(fallback_layer))
    idx = int(max(0, min(len(layers) - 1, layer_index)))
    patched_layer = {**layers[idx], **patch}
    # Factory styles must paint: never keep a leftover opacity=0 from the old layer.
    try:
        patch_opacity = float(patch["opacity"]) if "opacity" in patch else 1.0
    except (TypeError, ValueError):
        patch_opacity = 1.0
    patched_layer["opacity"] = float(max(0.05, min(1.0, patch_opacity)))

    if replace_stack:
        layers = [patched_layer]
    else:
        layers[idx] = patched_layer

    result = {
        **template,
        "style": normalize_spectrum_preset_key(style_key),
        "layers": layers,
    }
    # P1: preset button is a convenience patch → composition.spectrum.shape only.
    from features.video.lib.composition_axes import attach_spectrum_preset_to_composition

    return attach_spectrum_preset_to_composition(result, style_key)


def normalize_spectrum_preset_template(template: dict[str, Any]) -> dict[str, Any]:
    """Normalize style + layers after stacked preset apply."""
    normalized = normalize_renderer_template(template)
    return {
        **template,
        "style": normalized.get("style", template.get("style")),
        "layers": copy.deepcopy(normalized.get("layers") or template.get("layers") or []),
    }


def build_stacked_spectrum_preset_template(
    template: dict[str, Any],
    preset_key: str,
) -> dict[str, Any] | None:
    normalized = normalize_spectrum_preset_key_for_apply(preset_key)
    # Stacked keys may alias from legacy names.
    stacked_key = normalized if normalized in STACKED_LAYER_PRESETS else str(preset_key or "").strip().lower()
    stacked_key = _PRESET_ALIASES.get(stacked_key, stacked_key)
    preset = STACKED_LAYER_PRESETS.get(stacked_key)
    if not preset:
        return None

    raw_layers = template.get("layers") if isinstance(template.get("layers"), list) else []
    fallback_layer = copy.deepcopy(raw_layers[0]) if raw_layers and isinstance(raw_layers[0], dict) else {
        "color": {"mode": "solid", "solidColor": "#ffffff"}
    }

    next_layers: list[dict[str, Any]] = []
    style_key = normalize_spectrum_preset_key(str(preset.get("style") or "orbit-spikes"))
    stack_geometry = {
        **style_geometry_patch(style_key),
        "curved": True,
        "mirrored": True,
    }
    for index, layer_patch in enumerate(preset.get("layers") or []):
        if not isinstance(layer_patch, dict):
            continue
        fallback_color = fallback_layer.get("color") if isinstance(fallback_layer.get("color"), dict) else {}
        patch_color = layer_patch.get("color") if isinstance(layer_patch.get("color"), dict) else {}
        merged = copy.deepcopy(fallback_layer)
        merged.update(stack_geometry)
        merged.update(layer_patch)
        merged.update(stack_geometry)
        merged["id"] = f"stack-{stacked_key}-{index + 1}"
        merged["color"] = {**fallback_color, **patch_color}
        next_layers.append(merged)

    if not next_layers:
        return None

    result = {
        **template,
        "style": style_key,
        "layers": next_layers,
    }
    normalized = normalize_spectrum_preset_template(result)
    from features.video.lib.composition_axes import attach_spectrum_preset_to_composition

    return attach_spectrum_preset_to_composition(normalized, style_key)
