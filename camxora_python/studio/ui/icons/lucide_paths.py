"""Lucide icon geometry shared by Qt widgets and PIL playlist rendering.

Paths match lucide-static (viewBox 0 0 24 24). Playlist cards use filled
variants; toolbar buttons use stroked SVG via ``lucide_icons.py``.
"""

from __future__ import annotations

LUCIDE_VIEWBOX = 24.0

# Filled play triangle — same points as Lucide "play" (stroke icon in the UI).
LUCIDE_PLAY_POLYGON: tuple[tuple[float, float], ...] = (
    (6.0, 3.0),
    (20.0, 12.0),
    (6.0, 21.0),
)

_LUCIDE_FILLED: dict[str, tuple[tuple[float, float], ...]] = {
    "play": LUCIDE_PLAY_POLYGON,
}

# Minimal White reference — triangle height ≈ 22% of circle diameter.
PLAY_ICON_DIAMETER_RATIO = 0.22
LUCIDE_PLAY_SRC_HEIGHT = 18.0
PLAY_PREVIEW_DIAMETER = 20


def play_circle_radius_for_row(row_h: int) -> int:
    """Play hit-area radius sized to the row (bigger circle, small inner icon)."""
    ideal = int(row_h * 0.24)
    max_r = max(4, (row_h - 4) // 2)
    return max(4, min(12, ideal, max_r))


def play_diameter_for_row(row_h: int) -> int:
    return play_circle_radius_for_row(row_h) * 2


def play_icon_height_for_circle(circle_radius: int) -> int:
    diameter = circle_radius * 2
    return max(4, int(round(diameter * PLAY_ICON_DIAMETER_RATIO)))


def play_icon_scale_for_diameter(diameter_px: float) -> float:
    icon_h = diameter_px * PLAY_ICON_DIAMETER_RATIO
    return icon_h / LUCIDE_PLAY_SRC_HEIGHT


def _polygon_center(points: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def lucide_filled_polygon_points(
    name: str,
    cx: float,
    cy: float,
    *,
    height_px: float,
    optical_nudge_x: float = 0.85,
) -> list[tuple[float, float]]:
    """Scale a filled Lucide polygon to ``height_px`` and center on ``cx,cy``."""
    points = _LUCIDE_FILLED.get(name)
    if not points:
        return []

    ys = [p[1] for p in points]
    src_h = max(ys) - min(ys)
    if src_h <= 0:
        return []

    scale = height_px / src_h
    origin_x, origin_y = _polygon_center(points)
    nudge = optical_nudge_x * scale

    out: list[tuple[float, float]] = []
    for x, y in points:
        out.append((cx + (x - origin_x) * scale + nudge, cy + (y - origin_y) * scale))
    return out
