"""Background domain option lists — port of Electron backgroundSettings.ts."""

from __future__ import annotations

BACKGROUND_FIT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("cover", "Cover"),
    ("contain", "Contain"),
    ("original", "Original"),
)

BACKGROUND_MOTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("none", "None"),
    ("zoom", "Zoom"),
    ("vibrate", "Vibrate"),
    ("both", "Zoom + Vibrate"),
)
