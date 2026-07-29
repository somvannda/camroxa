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

from features.video.lib.video_template_draft import normalize_spectrum_preset_key
from visualizer.template_runtime import normalize_renderer_template

PACK_PRESET_PREFIX = "pack:"

# Camxora built-in single styles (marketplace-sellable ids).
SPECTRUM_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("orbit-spikes", "Orbit Spikes"),
    ("signal-needles", "Signal Needles"),
    ("pulse-beads", "Pulse Beads"),
    ("mirror-blades", "Mirror Blades"),
    ("aurora-ribbon", "Aurora Ribbon"),
    ("magma-ridge", "Magma Ridge"),
    ("plasma-bloom", "Plasma Bloom"),
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
# Gradients stay vivid (no white lead stops). Glow stays modest for premium color.
STYLE_PRESET_PATCHES: dict[str, dict[str, Any]] = {
    "orbit-spikes": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 5.0,
        "thickness": 36.0,
        "gravity": "normal",
        "glow": 22,
        "blur": 6,
        "blend_mode": "normal",
        "color": {
            "mode": "gradient",
            "gradientColors": ["#ff00ff", "#00ffff"],
            "gradientDirection": "left-to-right",
        },
    },
    "signal-needles": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 1.6,
        "thickness": 44.0,
        "gravity": "normal",
        "glow": 14,
        "blur": 3,
        "blend_mode": "normal",
        "color": {
            "mode": "gradient",
            "gradientColors": ["#a78bfa", "#38bdf8"],
            "gradientDirection": "left-to-right",
        },
    },
    "pulse-beads": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 4.5,
        "thickness": 40.0,
        "gravity": "normal",
        "glow": 24,
        "blur": 6,
        "blend_mode": "normal",
        "color": {
            "mode": "gradient",
            "gradientColors": ["#ff4fd8", "#22d3ee"],
            "gradientDirection": "left-to-right",
        },
    },
    "mirror-blades": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 5.5,
        "thickness": 42.0,
        "gravity": "normal",
        "glow": 18,
        "blur": 5,
        "blend_mode": "normal",
        "color": {
            "mode": "gradient",
            "gradientColors": ["#3b82f6", "#22d3ee"],
            "gradientDirection": "left-to-right",
        },
    },
    "aurora-ribbon": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 6.0,
        "thickness": 28.0,
        "gravity": "normal",
        "glow": 28,
        "blur": 8,
        "blend_mode": "normal",
        "color": {
            "mode": "gradient",
            "gradientColors": ["#22d3ee", "#ff4fd8", "#c084fc"],
            "gradientDirection": "left-to-right",
        },
    },
    "magma-ridge": {
        "curved": False,
        "mirrored": False,
        "fillCircle": True,
        "barWidth": 7.0,
        "thickness": 58.0,
        "gravity": "normal",
        "glow": 26,
        "blur": 7,
        "blend_mode": "normal",
        "color": {
            "mode": "gradient",
            "gradientColors": ["#ff4500", "#ff1493", "#7c3aed"],
            "gradientDirection": "left-to-right",
        },
    },
    "plasma-bloom": {
        "curved": False,
        "mirrored": False,
        "fillCircle": True,
        "barWidth": 10.0,
        "thickness": 46.0,
        "gravity": "normal",
        "glow": 30,
        "blur": 8,
        "blend_mode": "normal",
        "color": {
            "mode": "gradient",
            "gradientColors": ["#8b5cf6", "#ec4899", "#22d3ee"],
            "gradientDirection": "left-to-right",
        },
    },
    "grid-steps": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 6.0,
        "thickness": 38.0,
        "gravity": "normal",
        "glow": 16,
        "blur": 4,
        "blend_mode": "normal",
        "color": {
            "mode": "gradient",
            "gradientColors": ["#22c55e", "#14b8a6", "#06b6d4"],
            "gradientDirection": "left-to-right",
        },
    },
    "ignition-flare": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 7.5,
        "thickness": 48.0,
        "gravity": "normal",
        "glow": 32,
        "blur": 8,
        "blend_mode": "normal",
        "color": {
            "mode": "gradient",
            "gradientColors": ["#ff0000", "#ff8800", "#ff4fd8"],
            "gradientDirection": "left-to-right",
        },
    },
    "drift-capsules": {
        "curved": False,
        "mirrored": False,
        "fillCircle": False,
        "barWidth": 6.5,
        "thickness": 34.0,
        "gravity": "normal",
        "glow": 22,
        "blur": 6,
        "blend_mode": "normal",
        "color": {
            "mode": "gradient",
            "gradientColors": ["#6366f1", "#22d3ee"],
            "gradientDirection": "left-to-right",
        },
    },
}

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
                "glow": 20,
                "blur": 5,
                "color": {
                    "mode": "gradient",
                    "gradientColors": ["#ff8800", "#ff0000"],
                    "gradientDirection": "circular",
                },
            },
            {
                "name": "Pulse Orbit",
                "radiusOffset": 28,
                "barWidth": 8,
                "thickness": 44,
                "fillCircle": False,
                "opacity": 0.9,
                "blend_mode": "normal",
                "glow": 28,
                "blur": 7,
                "color": {
                    "mode": "gradient",
                    "gradientColors": ["#ff4d9d", "#22d3ee"],
                    "gradientDirection": "circular",
                },
            },
            {
                "name": "Outer Halo",
                "radiusOffset": 58,
                "barWidth": 7,
                "thickness": 32,
                "fillCircle": False,
                "opacity": 0.78,
                "blend_mode": "normal",
                "glow": 34,
                "blur": 8,
                "color": {
                    "mode": "gradient",
                    "gradientColors": ["#7c3aed", "#38bdf8"],
                    "gradientDirection": "circular",
                },
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
                "glow": 18,
                "blur": 5,
                "color": {
                    "mode": "gradient",
                    "gradientColors": ["#8b5cf6", "#ec4899"],
                    "gradientDirection": "circular",
                },
            },
            {
                "name": "Energy Ring",
                "radiusOffset": 24,
                "barWidth": 11,
                "thickness": 54,
                "fillCircle": False,
                "opacity": 0.88,
                "blend_mode": "normal",
                "glow": 28,
                "blur": 7,
                "color": {
                    "mode": "gradient",
                    "gradientColors": ["#ec4899", "#22d3ee"],
                    "gradientDirection": "circular",
                },
            },
            {
                "name": "Shock Aura",
                "radiusOffset": 54,
                "barWidth": 6,
                "thickness": 62,
                "fillCircle": False,
                "opacity": 0.72,
                "blend_mode": "normal",
                "glow": 32,
                "blur": 8,
                "color": {
                    "mode": "gradient",
                    "gradientColors": ["#60a5fa", "#a78bfa"],
                    "gradientDirection": "radial",
                },
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
                "opacity": 0.88,
                "blend_mode": "normal",
                "glow": 18,
                "blur": 6,
                "color": {
                    "mode": "gradient",
                    "gradientColors": ["#c084fc", "#22d3ee"],
                    "gradientDirection": "circular",
                },
            },
            {
                "name": "Bright Ribbon",
                "radiusOffset": 22,
                "barWidth": 5,
                "thickness": 30,
                "fillCircle": False,
                "opacity": 0.82,
                "blend_mode": "normal",
                "glow": 24,
                "blur": 7,
                "color": {
                    "mode": "gradient",
                    "gradientColors": ["#ff4fd8", "#67e8f9"],
                    "gradientDirection": "circular",
                },
            },
            {
                "name": "Outer Drift",
                "radiusOffset": 44,
                "barWidth": 9,
                "thickness": 20,
                "fillCircle": False,
                "opacity": 0.7,
                "blend_mode": "normal",
                "glow": 28,
                "blur": 8,
                "color": {
                    "mode": "gradient",
                    "gradientColors": ["#38bdf8", "#818cf8"],
                    "gradientDirection": "radial",
                },
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

    if replace_stack:
        layers = [patched_layer]
    else:
        layers[idx] = patched_layer

    return {
        **template,
        "style": normalize_spectrum_preset_key(style_key),
        "layers": layers,
    }


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
    return normalize_spectrum_preset_template(result)
