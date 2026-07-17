"""Logo domain option lists — port of Electron logoSettings.ts."""

from __future__ import annotations

LOGO_SPIN_DIRECTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("cw", "Clockwise"),
    ("ccw", "Counter-clockwise"),
)

LOGO_SHAPE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("circle", "Circle Crop"),
    ("square", "Original Image"),
)

LOGO_MOTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("none", "None"),
    ("zoom", "Zoom"),
    ("vibrate", "Vibrate"),
    ("both", "Zoom + Vibrate"),
)
