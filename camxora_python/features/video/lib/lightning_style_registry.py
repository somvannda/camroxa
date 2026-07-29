"""Lightning style registry — multi-layer background bolts."""

from __future__ import annotations

from typing import Any

LIGHTNING_STYLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("fork", "Fork (classic branched)"),
    ("sheet", "Sheet (wide flash)"),
    ("pulse", "Pulse (bloom strobe)"),
    ("arc", "Arc (curved stroke)"),
    ("chain", "Chain (segmented)"),
    ("spider", "Spider (radial forks)"),
    ("ribbon", "Ribbon (thick glow)"),
    ("neon", "Neon (hot core)"),
    ("storm", "Storm (multi-bolt)"),
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

_VALID_STYLES = {key for key, _ in LIGHTNING_STYLE_OPTIONS}
_VALID_DIRECTIONS = {key for key, _ in LIGHTNING_DIRECTION_OPTIONS}
_VALID_BLENDS = {key for key, _ in LIGHTNING_BLEND_OPTIONS}


def normalize_lightning_style(value: Any) -> str:
    key = str(value or "fork").lower().strip()
    return key if key in _VALID_STYLES else "fork"


def normalize_lightning_direction(value: Any) -> str:
    key = str(value or "down").lower().strip()
    return key if key in _VALID_DIRECTIONS else "down"


def normalize_lightning_blend(value: Any) -> str:
    key = str(value or "add").lower().strip()
    return key if key in _VALID_BLENDS else "add"


def default_lightning_layer(*, index: int = 1) -> dict[str, Any]:
    return {
        "id": f"lightning-{index}",
        "name": f"Bolt {index}",
        "enabled": True,
        "style": "fork",
        "x": 0.0,
        "y": 0.0,
        "direction": "down",
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
        "branchiness": 0.55,
        "blend": "add",
        "length": 200.0,
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
        "branchiness": _f("branchiness", 0.0, 1.0, 0.55),
        "blend": normalize_lightning_blend(src.get("blend")),
        "length": _f("length", 40.0, 600.0, 200.0),
    }


def normalize_lightning_layers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        return [normalize_lightning_layer(default_lightning_layer(index=1), index=0)]
    out = [normalize_lightning_layer(item, index=i) for i, item in enumerate(raw) if isinstance(item, dict)]
    return out if out else [normalize_lightning_layer(default_lightning_layer(index=1), index=0)]
