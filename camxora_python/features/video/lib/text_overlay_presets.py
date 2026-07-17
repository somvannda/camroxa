"""Text overlay style presets — port of textOverlayPresets.ts + neon brush stack."""

from __future__ import annotations

import copy
from typing import Any

from features.video.lib.video_template_draft import build_default_text_overlay_draft


def build_text_preset_style(preset: str) -> dict[str, Any] | None:
    if preset == "neon_outline":
        return {
            "fontSize": 72,
            "color": "#ffffff",
            "strokeColor": "#ff4fd8",
            "strokeWidth": 3,
            "shadow": 0.45,
            "animation": "pop",
        }
    if preset == "soft_glow":
        return {
            "fontSize": 58,
            "color": "#dff6ff",
            "strokeColor": "#051229",
            "strokeWidth": 1.5,
            "shadow": 0.6,
            "animation": "fade",
        }
    if preset == "dark_stroke":
        return {
            "fontSize": 62,
            "color": "#ffffff",
            "strokeColor": "#000000",
            "strokeWidth": 4,
            "shadow": 0.35,
            "animation": "fade",
        }
    return None


def build_neon_brush_stack_overlays() -> list[dict[str, Any]]:
    return [
        {
            **build_default_text_overlay_draft(),
            "enabled": True,
            "text": "TEXT 1",
            "anchor": "top-center",
            "x": 0,
            "y": 70,
            "fontSize": 120,
            "color": "#ffffff",
            "strokeColor": "#38bdf8",
            "strokeWidth": 3,
            "shadow": 0.55,
            "animation": "pop",
        },
        {
            **build_default_text_overlay_draft(),
            "enabled": True,
            "text": "TEXT 2",
            "anchor": "top-center",
            "x": 0,
            "y": 200,
            "fontSize": 86,
            "color": "#ff4fd8",
            "strokeColor": "#0b1220",
            "strokeWidth": 2.5,
            "shadow": 0.45,
            "animation": "slide_right",
        },
        {
            **build_default_text_overlay_draft(),
            "enabled": True,
            "text": "2026",
            "anchor": "top-center",
            "x": 0,
            "y": 310,
            "fontSize": 74,
            "color": "#b6c3ff",
            "strokeColor": "#0b1220",
            "strokeWidth": 2.2,
            "shadow": 0.35,
            "animation": "fade",
        },
    ]


def clone_text_overlays(overlays: Any) -> list[dict[str, Any]]:
    if not isinstance(overlays, list):
        return []
    return [copy.deepcopy(item) for item in overlays if isinstance(item, dict)]
