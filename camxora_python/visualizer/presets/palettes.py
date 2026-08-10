"""Color palette catalog (20) — vivid neon stops for clear spectrum bars."""

from __future__ import annotations

import colorsys
from copy import deepcopy
from typing import Any

# Saturated “true color” stops — avoid washed pastel / chalky midtones.
_PALETTE_ROWS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("cyberpunk", "Cyberpunk", ("#ff00ff", "#00ffff", "#7c3aed", "#ff2d95"), "#00e5ff"),
    ("synthwave", "Synthwave", ("#ff2bd6", "#ff6a3d", "#6d28d9", "#22d3ee"), "#ff8af0"),
    ("festival", "Festival", ("#ffcc00", "#ff2d6a", "#00e5ff", "#a3ff12"), "#ff8a00"),
    ("edm", "EDM", ("#00e5ff", "#8b5cff", "#ff2d95", "#00ff9a"), "#5ef0ff"),
    ("dubstep", "Dubstep", ("#b8ff00", "#7cff00", "#ff5a00", "#ff1a1a"), "#d4ff4a"),
    ("future_bass", "Future Bass", ("#c44dff", "#00e8ff", "#ff6ec7", "#6b5cff"), "#e9b0ff"),
    ("sunset", "Sunset", ("#ff3b6b", "#ff7a18", "#ffcc00", "#ff4f9a"), "#ff9a40"),
    ("aurora", "Aurora", ("#00ff9a", "#00e5ff", "#5b8cff", "#b44dff"), "#3dffa8"),
    ("galaxy", "Galaxy", ("#6b5cff", "#c44dff", "#ff2bd6", "#00c8ff"), "#a78bff"),
    ("fire", "Fire", ("#ff1a1a", "#ff5a00", "#ffcc00", "#ff3b6b"), "#ff8a8a"),
    ("ocean", "Ocean", ("#0090ff", "#00e5ff", "#00d4aa", "#3db8ff"), "#5ec8ff"),
    ("monochrome", "Monochrome", ("#ffffff", "#d4d4d8", "#a1a1aa", "#71717a"), "#f4f4f5"),
    ("midnight", "Midnight", ("#1d4ed8", "#312e81", "#6366f1", "#00e5ff"), "#60a5fa"),
    ("neon_pink", "Neon Pink", ("#ff00c8", "#ff4fd8", "#ff2d6a", "#b44dff"), "#ff7ab8"),
    ("tropical", "Tropical", ("#00d4aa", "#00ff9a", "#ffcc00", "#ff2d6a"), "#2dffc0"),
    (
        "rainbow",
        "Rainbow",
        ("#b000ff", "#ff0080", "#ff2200", "#ff9900", "#ffee00", "#00ff66", "#00c8ff", "#0040ff"),
        "#00e5ff",
    ),
    ("candy", "Candy", ("#ff2d6a", "#ff6ec7", "#7c6bff", "#00e5ff"), "#ff8ab8"),
    ("blood_moon", "Blood Moon", ("#8b0000", "#dc143c", "#ff5a00", "#ffcc00"), "#ff6b6b"),
    ("arctic", "Arctic", ("#e0f7ff", "#5ec8ff", "#0090ff", "#7c6bff"), "#9ad8ff"),
    ("gold_rush", "Gold Rush", ("#ffcc00", "#ffb000", "#ffd60a", "#ffe566"), "#ffc933"),
)

COLOR_PALETTE_CATALOG: tuple[dict[str, Any], ...] = tuple(
    {
        "id": row[0],
        "label": row[1],
        "stops": list(row[2]),
        "accent": row[3],
        "solid": row[2][0],
    }
    for row in _PALETTE_ROWS
)
COLOR_PALETTE_IDS: frozenset[str] = frozenset(item["id"] for item in COLOR_PALETTE_CATALOG)
COLOR_PALETTE_COUNT = len(COLOR_PALETTE_CATALOG)
assert COLOR_PALETTE_COUNT == 20, COLOR_PALETTE_COUNT

_BY_ID = {item["id"]: item for item in COLOR_PALETTE_CATALOG}
_ALIASES = {
    **{item["id"]: item["id"] for item in COLOR_PALETTE_CATALOG},
    **{item["label"].lower(): item["id"] for item in COLOR_PALETTE_CATALOG},
    "future bass": "future_bass",
    "neon pink": "neon_pink",
    "blood moon": "blood_moon",
    "gold rush": "gold_rush",
    "industrial": "monochrome",  # legacy id → nearest clear substitute
    "prism": "rainbow",
}


def list_color_palette_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in COLOR_PALETTE_CATALOG)


def normalize_color_palette_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in COLOR_PALETTE_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None


def get_palette(palette_id: str | None) -> dict[str, Any] | None:
    key = normalize_color_palette_id(palette_id)
    if not key:
        return None
    return deepcopy(_BY_ID[key])


def _parse_hex(hex_color: str) -> tuple[float, float, float]:
    text = str(hex_color or "#ffffff").strip().lstrip("#")
    if len(text) >= 6:
        try:
            return (
                int(text[0:2], 16) / 255.0,
                int(text[2:4], 16) / 255.0,
                int(text[4:6], 16) / 255.0,
            )
        except ValueError:
            pass
    return (1.0, 1.0, 1.0)


def _to_hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        int(max(0.0, min(1.0, r)) * 255.0 + 0.5),
        int(max(0.0, min(1.0, g)) * 255.0 + 0.5),
        int(max(0.0, min(1.0, b)) * 255.0 + 0.5),
    )


def tune_hex_color(hex_color: str, *, intensity: float = 1.0, saturation: float = 1.0) -> str:
    """Apply Expert palette intensity/saturation to a single hex stop."""
    r, g, b = _parse_hex(hex_color)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    sat = max(0.0, min(2.0, float(saturation)))
    inten = max(0.0, min(2.0, float(intensity)))
    s = max(0.0, min(1.0, s * sat))
    if inten >= 1.0:
        boost = inten - 1.0
        v = max(0.0, min(1.0, v * (1.0 + 0.35 * boost) + 0.12 * boost))
        s = max(0.0, min(1.0, s * (1.0 + 0.15 * boost)))
        # Already-max neon stops still need a visible boost path (hot highlight).
        if boost > 1e-6 and v >= 0.98 and s >= 0.98:
            s = max(0.0, min(1.0, s - 0.18 * boost))
            v = 1.0
    else:
        # Pull toward muted mid-gray while keeping hue.
        mix = 1.0 - inten
        v = max(0.0, min(1.0, v * (0.55 + 0.45 * inten) + 0.35 * mix * 0.5))
        s = max(0.0, min(1.0, s * inten))
    rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
    return _to_hex(rr, gg, bb)


def clarify_hex_color(hex_color: str, *, amount: float = 0.35) -> str:
    """Push a stop toward neon clarity (higher sat / cleaner value) for spectrum bars."""
    amt = max(0.0, min(1.0, float(amount)))
    if amt <= 1e-6:
        return str(hex_color or "#ffffff")
    r, g, b = _parse_hex(hex_color)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    # Lift muddy mid-sat toward vivid; keep near-grays from becoming neon noise.
    if s < 0.08:
        v = max(0.0, min(1.0, v + 0.08 * amt))
    else:
        s = max(0.0, min(1.0, s + (1.0 - s) * 0.55 * amt))
        v = max(0.0, min(1.0, v + (1.0 - v) * 0.22 * amt))
    rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
    return _to_hex(rr, gg, bb)


def clarify_palette(palette: dict[str, Any] | None, *, amount: float = 0.35) -> dict[str, Any] | None:
    """Return a clearer/vivid copy of a palette for spectrum preview."""
    if not isinstance(palette, dict):
        return None
    out = deepcopy(palette)
    amt = max(0.0, min(1.0, float(amount)))
    if amt <= 1e-6:
        return out
    stops = out.get("stops") if isinstance(out.get("stops"), list) else []
    out["stops"] = [clarify_hex_color(str(c), amount=amt) for c in stops]
    out["solid"] = clarify_hex_color(str(out.get("solid") or "#ffffff"), amount=amt)
    out["accent"] = clarify_hex_color(str(out.get("accent") or out["solid"]), amount=amt)
    return out


def apply_palette_expert(
    palette: dict[str, Any] | None,
    *,
    intensity: float = 1.0,
    saturation: float = 1.0,
) -> dict[str, Any] | None:
    """Return a palette copy with Expert intensity/saturation baked into stops."""
    if not isinstance(palette, dict):
        return None
    out = deepcopy(palette)
    inten = max(0.0, min(2.0, float(intensity)))
    sat = max(0.0, min(2.0, float(saturation)))
    if abs(inten - 1.0) < 1e-6 and abs(sat - 1.0) < 1e-6:
        return out
    stops = out.get("stops") if isinstance(out.get("stops"), list) else []
    out["stops"] = [tune_hex_color(str(c), intensity=inten, saturation=sat) for c in stops]
    out["solid"] = tune_hex_color(str(out.get("solid") or "#ffffff"), intensity=inten, saturation=sat)
    out["accent"] = tune_hex_color(str(out.get("accent") or out["solid"]), intensity=inten, saturation=sat)
    return out
