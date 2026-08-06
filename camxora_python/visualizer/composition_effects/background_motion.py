"""Background motion evaluators — orthogonal to atmosphere."""

from __future__ import annotations

import math
from typing import Any

from visualizer.presets.background_motion import normalize_background_motion_id


def evaluate_background_motion(
    motion_id: str | None,
    *,
    time_sec: float = 0.0,
) -> dict[str, Any]:
    mid = normalize_background_motion_id(motion_id) or "static"
    t = float(time_sec)
    out: dict[str, Any] = {
        "motionId": mid,
        "scale": 1.0,
        "offsetX": 0.0,
        "offsetY": 0.0,
        "rotation": 0.0,
        "warp": 0.0,
        # Bridge hint for existing GPU backgroundSettings.motionMode
        "legacyMotionMode": "none",
    }

    if mid == "static":
        pass
    elif mid == "slow_zoom":
        out["scale"] = 1.0 + 0.04 * (0.5 + 0.5 * math.sin(t * 0.15))
        out["legacyMotionMode"] = "zoom"
    elif mid == "ken_burns":
        out["scale"] = 1.08
        out["offsetX"] = 0.03 * math.sin(t * 0.12)
        out["offsetY"] = 0.02 * math.cos(t * 0.1)
        out["legacyMotionMode"] = "zoom"
    elif mid == "orbit":
        out["offsetX"] = 0.025 * math.cos(t * 0.2)
        out["offsetY"] = 0.025 * math.sin(t * 0.2)
        out["legacyMotionMode"] = "pan"
    elif mid == "parallax":
        out["offsetX"] = 0.015 * math.sin(t * 0.25)
        out["scale"] = 1.03
        out["legacyMotionMode"] = "pan"
    elif mid == "ripple":
        out["warp"] = 0.02 * math.sin(t * 1.5)
        out["legacyMotionMode"] = "zoom"
    elif mid == "energy_wave":
        out["scale"] = 1.0 + 0.03 * abs(math.sin(t * 2.0))
        out["warp"] = 0.015 * math.sin(t * 2.0)
        out["legacyMotionMode"] = "zoom"
    elif mid == "floating":
        out["offsetY"] = 0.02 * math.sin(t * 0.35)
        out["legacyMotionMode"] = "pan"
    elif mid == "rotate":
        out["rotation"] = t * 3.0
        out["legacyMotionMode"] = "rotate"
    elif mid == "warp":
        out["warp"] = 0.04 + 0.02 * math.sin(t * 0.8)
        out["scale"] = 1.05
        out["legacyMotionMode"] = "zoom"

    return out
