"""Lightning style registry — multi-layer background bolts."""

from __future__ import annotations

from typing import Any

LIGHTNING_STYLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("fork", "Fork (classic branched)"),
    ("sheet", "Sheet (wide flash)"),
    ("pulse", "Pulse (bloom strobe)"),
    ("arc", "Arc (curved stroke)"),
    ("chain", "Chain (segmented)"),
    ("spider", "Spider (forked strike)"),
    ("ribbon", "Ribbon (thick glow)"),
    ("neon", "Neon (hot core)"),
    ("storm", "Storm (turbulent fork)"),
    ("horizon", "Horizon (ground band)"),
)

LIGHTNING_DIRECTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("down", "Down"),
    ("up", "Up"),
    ("left", "Left"),
    ("right", "Right"),
    ("random", "Random"),
    ("inward", "Inward"),
    ("outward", "Outward"),
)

LIGHTNING_BLEND_OPTIONS: tuple[tuple[str, str], ...] = (
    ("add", "Additive"),
    ("screen", "Screen"),
    ("normal", "Normal"),
)

LIGHTNING_TRIGGER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("always", "Always (timed + audio)"),
    ("timed", "Timed pulse only"),
    ("audio", "Audio envelope"),
    ("bass", "Bass hits"),
    ("kick", "Kick hits"),
    ("beat", "Beat / onset"),
)

LIGHTNING_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("neon_sky", "Neon Sky"),
    ("ground_strike", "Ground Strike"),
    ("sheet_flash", "Sheet Flash"),
    ("pulse_bloom", "Pulse Bloom"),
    ("horizon_band", "Horizon Band"),
    ("storm_fork", "Storm Fork"),
)

_VALID_STYLES = {key for key, _ in LIGHTNING_STYLE_OPTIONS}
_VALID_DIRECTIONS = {key for key, _ in LIGHTNING_DIRECTION_OPTIONS}
_VALID_BLENDS = {key for key, _ in LIGHTNING_BLEND_OPTIONS}
_VALID_TRIGGERS = {key for key, _ in LIGHTNING_TRIGGER_OPTIONS}


def normalize_lightning_style(value: Any) -> str:
    key = str(value or "fork").lower().strip()
    return key if key in _VALID_STYLES else "fork"


def normalize_lightning_direction(value: Any) -> str:
    key = str(value or "down").lower().strip()
    return key if key in _VALID_DIRECTIONS else "down"


def normalize_lightning_blend(value: Any) -> str:
    key = str(value or "add").lower().strip()
    return key if key in _VALID_BLENDS else "add"


def normalize_lightning_trigger(value: Any) -> str:
    key = str(value or "always").lower().strip()
    return key if key in _VALID_TRIGGERS else "always"


def default_lightning_layer(*, index: int = 1) -> dict[str, Any]:
    return {
        "id": f"lightning-{index}",
        "name": f"Bolt {index}",
        "enabled": True,
        "style": "fork",
        "x": 0.0,
        "y": 0.0,
        "direction": "down",
        "rotation": 0.0,
        "color": {
            "mode": "gradient",
            "solidColor": "#e0f2fe",
            "gradientColors": ["#ffffff", "#7dd3fc", "#38bdf8"],
        },
        "opacity": 0.85,
        "intensity": 0.72,
        "reactivity": 0.55,
        "speed": 1.0,
        "flashRate": 0.85,
        "thickness": 2.8,
        "glow": 0.5,
        "branchiness": 0.35,
        "blend": "add",
        "length": 200.0,
        "trigger": "always",
        "triggerThreshold": 0.22,
        "seed": float(index),
        "seedLock": False,
    }


def normalize_lightning_layer(layer: Any, *, index: int = 0) -> dict[str, Any]:
    base = default_lightning_layer(index=index + 1)
    src = layer if isinstance(layer, dict) else {}
    color_in = src.get("color") if isinstance(src.get("color"), dict) else {}
    solid = str(color_in.get("solidColor", base["color"]["solidColor"]) or base["color"]["solidColor"])
    grads = color_in.get("gradientColors")
    if not isinstance(grads, list) or not grads:
        grads = list(base["color"]["gradientColors"])
    grads = [str(item) for item in grads if isinstance(item, str) and item.startswith("#")][:5]
    if len(grads) < 2:
        grads = list(base["color"]["gradientColors"])
    mode = "palette" if str(color_in.get("mode", "gradient")).lower() == "palette" else (
        "solid" if str(color_in.get("mode", "gradient")).lower() == "solid" else "gradient"
    )
    if mode == "palette":
        mode = "gradient"

    def _f(key: str, lo: float, hi: float, default: float) -> float:
        try:
            return float(max(lo, min(hi, float(src.get(key, default) or default))))
        except (TypeError, ValueError):
            return float(default)

    return {
        "id": str(src.get("id") or base["id"]),
        "name": str(src.get("name") or base["name"]),
        "enabled": bool(src.get("enabled", True)),
        "style": normalize_lightning_style(src.get("style")),
        "x": _f("x", -1000.0, 1000.0, 0.0),
        "y": _f("y", -1000.0, 1000.0, 0.0),
        "direction": normalize_lightning_direction(src.get("direction")),
        "rotation": _f("rotation", 0.0, 360.0, 0.0),
        "color": {
            "mode": mode,
            "solidColor": solid if solid.startswith("#") else "#e0f2fe",
            "gradientColors": grads,
        },
        "opacity": _f("opacity", 0.0, 1.0, 0.85),
        "intensity": _f("intensity", 0.0, 1.0, 0.72),
        "reactivity": _f("reactivity", 0.0, 1.0, 0.55),
        "speed": _f("speed", 0.05, 4.0, 1.0),
        "flashRate": _f("flashRate", 0.05, 4.0, 0.85),
        "thickness": _f("thickness", 0.5, 24.0, 2.8),
        "glow": _f("glow", 0.0, 1.0, 0.5),
        "branchiness": _f("branchiness", 0.0, 1.0, 0.35),
        "blend": normalize_lightning_blend(src.get("blend")),
        "length": _f("length", 40.0, 600.0, 200.0),
        "trigger": normalize_lightning_trigger(src.get("trigger")),
        "triggerThreshold": _f("triggerThreshold", 0.05, 0.95, 0.22),
        "seed": _f("seed", 0.0, 9999.0, float(index + 1)),
        "seedLock": bool(src.get("seedLock", False)),
    }


def normalize_lightning_layers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        return [normalize_lightning_layer(default_lightning_layer(index=1), index=0)]
    out = [normalize_lightning_layer(item, index=i) for i, item in enumerate(raw) if isinstance(item, dict)]
    return out if out else [normalize_lightning_layer(default_lightning_layer(index=1), index=0)]


LIGHTNING_PRESET_LAYER_PATCHES: dict[str, dict[str, Any]] = {
    "neon_sky": {
        "style": "neon",
        "direction": "down",
        "blend": "add",
        "trigger": "always",
        "length": 240.0,
        "thickness": 2.2,
        "glow": 0.85,
        "branchiness": 0.35,
        "opacity": 0.9,
        "intensity": 0.8,
        "reactivity": 0.45,
        "speed": 1.2,
        "flashRate": 1.0,
        "color": {
            "mode": "solid",
            "solidColor": "#7dd3fc",
            "gradientColors": ["#ffffff", "#7dd3fc", "#38bdf8"],
        },
        "seedLock": True,
    },
    "ground_strike": {
        "style": "fork",
        "direction": "down",
        "blend": "add",
        "trigger": "kick",
        "length": 320.0,
        "thickness": 3.4,
        "glow": 0.65,
        "branchiness": 0.7,
        "opacity": 0.95,
        "intensity": 0.85,
        "reactivity": 0.75,
        "speed": 1.6,
        "flashRate": 0.7,
        "color": {
            "mode": "solid",
            "solidColor": "#e0f2fe",
            "gradientColors": ["#ffffff", "#bae6fd"],
        },
        "seedLock": False,
    },
    "sheet_flash": {
        "style": "sheet",
        "direction": "down",
        "blend": "screen",
        "trigger": "beat",
        "length": 280.0,
        "thickness": 5.0,
        "glow": 0.7,
        "branchiness": 0.1,
        "opacity": 0.7,
        "intensity": 0.75,
        "reactivity": 0.6,
        "speed": 1.0,
        "flashRate": 0.9,
        "color": {
            "mode": "solid",
            "solidColor": "#a5b4fc",
            "gradientColors": ["#ffffff", "#a5b4fc"],
        },
        "seedLock": True,
    },
    "pulse_bloom": {
        "style": "pulse",
        "direction": "outward",
        "blend": "add",
        "trigger": "audio",
        "length": 180.0,
        "thickness": 3.0,
        "glow": 0.9,
        "branchiness": 0.0,
        "opacity": 0.8,
        "intensity": 0.7,
        "reactivity": 0.85,
        "speed": 1.4,
        "flashRate": 1.1,
        "color": {
            "mode": "solid",
            "solidColor": "#f0abfc",
            "gradientColors": ["#ffffff", "#f0abfc"],
        },
        "seedLock": True,
    },
    "horizon_band": {
        "style": "horizon",
        "direction": "right",
        "blend": "add",
        "trigger": "timed",
        "length": 360.0,
        "thickness": 4.0,
        "glow": 0.55,
        "branchiness": 0.0,
        "opacity": 0.75,
        "intensity": 0.65,
        "reactivity": 0.2,
        "speed": 0.8,
        "flashRate": 0.6,
        "color": {
            "mode": "solid",
            "solidColor": "#67e8f9",
            "gradientColors": ["#ffffff", "#67e8f9"],
        },
        "seedLock": True,
    },
    "storm_fork": {
        "style": "storm",
        "direction": "down",
        "blend": "add",
        "trigger": "always",
        "length": 260.0,
        "thickness": 2.6,
        "glow": 0.6,
        "branchiness": 0.85,
        "opacity": 0.88,
        "intensity": 0.78,
        "reactivity": 0.55,
        "speed": 1.8,
        "flashRate": 1.2,
        "color": {
            "mode": "solid",
            "solidColor": "#c4b5fd",
            "gradientColors": ["#ffffff", "#c4b5fd"],
        },
        "seedLock": False,
    },
}


def build_lightning_preset_layer_patch(preset_id: str) -> dict[str, Any] | None:
    key = str(preset_id or "").strip()
    patch = LIGHTNING_PRESET_LAYER_PATCHES.get(key)
    return dict(patch) if isinstance(patch, dict) else None


def is_lightning_preset_key(preset_id: str | None) -> bool:
    key = str(preset_id or "").strip()
    return any(key == pid for pid, _label in LIGHTNING_PRESET_OPTIONS)
