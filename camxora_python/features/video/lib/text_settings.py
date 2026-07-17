"""Text domain option lists — port of Electron pythonVideoSettings / TextPanels."""

from __future__ import annotations

TEXT_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("neon_outline", "Neon Outline"),
    ("soft_glow", "Soft Glow"),
    ("dark_stroke", "Dark Stroke"),
    ("lower_third_title", "Lower Third Title"),
    ("kinetic_shout", "Kinetic Shout"),
    ("neon_brush_stack", "Neon Brush Stack"),
)

TEXT_ANIMATION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("fade", "Fade"),
    ("slide_up", "Slide Up"),
    ("slide_down", "Slide Down"),
    ("slide_left", "Slide Left"),
    ("slide_right", "Slide Right"),
    ("pop", "Pop"),
    ("typewriter", "Typewriter"),
    ("glow", "Glow Pulse"),
    ("shake", "Shake"),
    ("none", "None"),
)

TEXT_PANEL_MODES: tuple[tuple[str, str], ...] = (
    ("basic", "Basic"),
    ("style", "Style"),
    ("effects", "Effects"),
)
