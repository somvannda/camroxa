"""Lightning style registry — multi-layer background bolts."""

from __future__ import annotations

from typing import Any

# Hard cap for preview + export (one layer = one bolt). Matches product budget.
MAX_LIGHTNING_LAYERS = 10

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

LIGHTNING_SPAWN_OPTIONS: tuple[tuple[str, str], ...] = (
    ("fixed", "Anchored (drag on preview)"),
    ("random", "Random on screen"),
)

LIGHTNING_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("neon_sky", "Neon Sky"),
    ("ground_strike", "Ground Strike"),
    ("sheet_flash", "Sheet Flash"),
    ("pulse_bloom", "Pulse Bloom"),
    ("horizon_band", "Horizon Band"),
    ("storm_fork", "Storm Fork"),
    ("wandering_bolt", "Wandering Bolt"),
)

_VALID_STYLES = {key for key, _ in LIGHTNING_STYLE_OPTIONS}
_VALID_DIRECTIONS = {key for key, _ in LIGHTNING_DIRECTION_OPTIONS}
_VALID_BLENDS = {key for key, _ in LIGHTNING_BLEND_OPTIONS}
_VALID_TRIGGERS = {key for key, _ in LIGHTNING_TRIGGER_OPTIONS}
_VALID_SPAWNS = {key for key, _ in LIGHTNING_SPAWN_OPTIONS}


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


def normalize_lightning_spawn(value: Any) -> str:
    key = str(value or "fixed").lower().strip()
    return key if key in _VALID_SPAWNS else "fixed"


def _read_float(src: dict[str, Any], key: str, default: float, lo: float, hi: float) -> float:
    """Read a float that may be 0 — never treat 0 as missing (``or default`` bug)."""
    raw = src.get(key, default)
    if raw is None:
        raw = default
    try:
        return float(max(lo, min(hi, float(raw))))
    except (TypeError, ValueError):
        return float(default)


def default_lightning_layer(*, index: int = 1) -> dict[str, Any]:
    return {
        "id": f"lightning-{index}",
        "name": f"Bolt {index}",
        "enabled": True,
        "style": "fork",
        "spawnMode": "fixed",
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
        "reactMotionSpeed": 1.0,
        "flashRate": 0.85,
        "thickness": 2.8,
        "taper": 0.65,
        "glow": 0.5,
        "branchiness": 0.35,
        "blend": "add",
        "length": 200.0,
        "lengthReactivity": 0.0,
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

    return {
        "id": str(src.get("id") or base["id"]),
        "name": str(src.get("name") or base["name"]),
        "enabled": bool(src.get("enabled", True)),
        "style": normalize_lightning_style(src.get("style")),
        "spawnMode": normalize_lightning_spawn(src.get("spawnMode")),
        "x": _read_float(src, "x", 0.0, -1000.0, 1000.0),
        "y": _read_float(src, "y", 0.0, -1000.0, 1000.0),
        "direction": normalize_lightning_direction(src.get("direction")),
        "rotation": _read_float(src, "rotation", 0.0, 0.0, 360.0),
        "color": {
            "mode": mode,
            "solidColor": solid if solid.startswith("#") else "#e0f2fe",
            "gradientColors": grads,
        },
        "opacity": _read_float(src, "opacity", 0.85, 0.0, 1.0),
        "intensity": _read_float(src, "intensity", 0.72, 0.0, 1.0),
        "reactivity": _read_float(src, "reactivity", 0.55, 0.0, 1.0),
        "speed": _read_float(src, "speed", 1.0, 0.0, 4.0),
        "reactMotionSpeed": _read_float(src, "reactMotionSpeed", 1.0, 0.0, 4.0),
        "flashRate": _read_float(src, "flashRate", 0.85, 0.0, 4.0),
        "thickness": _read_float(src, "thickness", 2.8, 0.0, 24.0),
        "taper": _read_float(src, "taper", 0.65, 0.0, 1.0),
        "glow": _read_float(src, "glow", 0.5, 0.0, 1.0),
        "branchiness": _read_float(src, "branchiness", 0.35, 0.0, 1.0),
        "blend": normalize_lightning_blend(src.get("blend")),
        "length": _read_float(src, "length", 200.0, 20.0, 600.0),
        "lengthReactivity": _read_float(src, "lengthReactivity", 0.0, 0.0, 1.0),
        "trigger": normalize_lightning_trigger(src.get("trigger")),
        "triggerThreshold": _read_float(src, "triggerThreshold", 0.22, 0.0, 0.95),
        "seed": _read_float(src, "seed", float(index + 1), 0.0, 9999.0),
        "seedLock": bool(src.get("seedLock", False)),
    }


def normalize_lightning_layers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        return [normalize_lightning_layer(default_lightning_layer(index=1), index=0)]
    out = [
        normalize_lightning_layer(item, index=i)
        for i, item in enumerate(raw)
        if isinstance(item, dict)
    ][:MAX_LIGHTNING_LAYERS]
    return out if out else [normalize_lightning_layer(default_lightning_layer(index=1), index=0)]


LIGHTNING_PRESET_LAYER_PATCHES: dict[str, dict[str, Any]] = {
    "neon_sky": {
        "style": "neon",
        "spawnMode": "fixed",
        "direction": "down",
        "blend": "add",
        "trigger": "always",
        "length": 240.0,
        "thickness": 2.2,
        "taper": 0.7,
        "glow": 0.85,
        "branchiness": 0.35,
        "opacity": 0.9,
        "intensity": 0.8,
        "reactivity": 0.45,
        "speed": 1.2,
        "reactMotionSpeed": 1.1,
        "flashRate": 1.0,
        "lengthReactivity": 0.0,
        "color": {
            "mode": "solid",
            "solidColor": "#7dd3fc",
            "gradientColors": ["#ffffff", "#7dd3fc", "#38bdf8"],
        },
        "seedLock": True,
    },
    "ground_strike": {
        "style": "fork",
        "spawnMode": "fixed",
        "direction": "down",
        "blend": "add",
        "trigger": "kick",
        "length": 320.0,
        "thickness": 3.4,
        "taper": 0.8,
        "glow": 0.65,
        "branchiness": 0.7,
        "opacity": 0.95,
        "intensity": 0.85,
        "reactivity": 0.75,
        "speed": 1.6,
        "reactMotionSpeed": 1.4,
        "flashRate": 0.7,
        "lengthReactivity": 0.15,
        "color": {
            "mode": "solid",
            "solidColor": "#e0f2fe",
            "gradientColors": ["#ffffff", "#bae6fd"],
        },
        "seedLock": False,
    },
    "sheet_flash": {
        "style": "sheet",
        "spawnMode": "fixed",
        "direction": "down",
        "blend": "screen",
        "trigger": "beat",
        "length": 280.0,
        "thickness": 5.0,
        "taper": 0.2,
        "glow": 0.7,
        "branchiness": 0.1,
        "opacity": 0.7,
        "intensity": 0.75,
        "reactivity": 0.6,
        "speed": 1.0,
        "reactMotionSpeed": 1.0,
        "flashRate": 0.9,
        "lengthReactivity": 0.0,
        "color": {
            "mode": "solid",
            "solidColor": "#a5b4fc",
            "gradientColors": ["#ffffff", "#a5b4fc"],
        },
        "seedLock": True,
    },
    "pulse_bloom": {
        "style": "pulse",
        "spawnMode": "fixed",
        "direction": "outward",
        "blend": "add",
        "trigger": "audio",
        "length": 180.0,
        "thickness": 3.0,
        "taper": 0.0,
        "glow": 0.9,
        "branchiness": 0.0,
        "opacity": 0.8,
        "intensity": 0.7,
        "reactivity": 0.85,
        "speed": 1.4,
        "reactMotionSpeed": 1.6,
        "flashRate": 1.1,
        "lengthReactivity": 0.0,
        "color": {
            "mode": "solid",
            "solidColor": "#f0abfc",
            "gradientColors": ["#ffffff", "#f0abfc"],
        },
        "seedLock": True,
    },
    "horizon_band": {
        "style": "horizon",
        "spawnMode": "fixed",
        "direction": "right",
        "blend": "add",
        "trigger": "timed",
        "length": 360.0,
        "thickness": 4.0,
        "taper": 0.0,
        "glow": 0.55,
        "branchiness": 0.0,
        "opacity": 0.75,
        "intensity": 0.65,
        "reactivity": 0.2,
        "speed": 0.8,
        "reactMotionSpeed": 0.7,
        "flashRate": 0.6,
        "lengthReactivity": 0.0,
        "color": {
            "mode": "solid",
            "solidColor": "#67e8f9",
            "gradientColors": ["#ffffff", "#67e8f9"],
        },
        "seedLock": True,
    },
    "storm_fork": {
        "style": "storm",
        "spawnMode": "fixed",
        "direction": "down",
        "blend": "add",
        "trigger": "always",
        "length": 260.0,
        "thickness": 2.6,
        "taper": 0.75,
        "glow": 0.6,
        "branchiness": 0.85,
        "opacity": 0.88,
        "intensity": 0.78,
        "reactivity": 0.55,
        "speed": 1.8,
        "reactMotionSpeed": 1.5,
        "flashRate": 1.2,
        "lengthReactivity": 0.0,
        "color": {
            "mode": "solid",
            "solidColor": "#c4b5fd",
            "gradientColors": ["#ffffff", "#c4b5fd"],
        },
        "seedLock": False,
    },
    "wandering_bolt": {
        "style": "fork",
        "spawnMode": "random",
        "direction": "random",
        "blend": "add",
        "trigger": "always",
        "length": 220.0,
        "thickness": 2.4,
        "taper": 0.7,
        "glow": 0.7,
        "branchiness": 0.45,
        "opacity": 0.88,
        "intensity": 0.8,
        "reactivity": 0.5,
        "speed": 1.1,
        "reactMotionSpeed": 1.2,
        "flashRate": 0.9,
        "lengthReactivity": 0.0,
        "color": {
            "mode": "solid",
            "solidColor": "#e0f2fe",
            "gradientColors": ["#ffffff", "#7dd3fc"],
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
