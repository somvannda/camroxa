"""Camera behavior evaluators — scene-level transform drivers."""

from __future__ import annotations

import math
from typing import Any

from visualizer.presets.camera import normalize_camera_behavior_id
from visualizer.scene import NONE


def evaluate_camera_behavior(
    behavior_id: str | None,
    *,
    time_sec: float = 0.0,
    audio_level: float = 0.0,
) -> dict[str, Any]:
    bid = normalize_camera_behavior_id(behavior_id)
    if not bid:
        return {
            "behaviorId": NONE,
            "enabled": False,
            "offsetX": 0.0,
            "offsetY": 0.0,
            "zoom": 1.0,
            "rotation": 0.0,
            "roll": 0.0,
            "shake": 0.0,
            "focus": 1.0,
        }

    t = float(time_sec)
    a = max(0.0, min(1.0, float(audio_level)))
    out: dict[str, Any] = {
        "behaviorId": bid,
        "enabled": True,
        "offsetX": 0.0,
        "offsetY": 0.0,
        "zoom": 1.0,
        "rotation": 0.0,
        "roll": 0.0,
        "shake": 0.0,
        "focus": 1.0,
    }

    if bid == "zoom":
        out["zoom"] = 1.0 + 0.08 * math.sin(t * 1.2) + 0.04 * a
    elif bid == "pan":
        out["offsetX"] = 0.04 * math.sin(t * 0.7)
    elif bid == "orbit":
        out["offsetX"] = 0.03 * math.cos(t * 0.9)
        out["offsetY"] = 0.03 * math.sin(t * 0.9)
        out["rotation"] = t * 8.0
    elif bid == "rotate":
        out["rotation"] = t * 12.0
    elif bid == "shake":
        out["shake"] = 0.02 + 0.06 * a
        out["offsetX"] = out["shake"] * math.sin(t * 40.0)
        out["offsetY"] = out["shake"] * math.cos(t * 37.0)
    elif bid == "tilt":
        out["rotation"] = 6.0 * math.sin(t * 0.5)
    elif bid == "dolly":
        out["zoom"] = 1.0 + 0.12 * math.sin(t * 0.4)
    elif bid == "roll":
        out["roll"] = 8.0 * math.sin(t * 0.6)
    elif bid == "focus_pull":
        out["focus"] = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(t * 0.8))
        out["zoom"] = 1.0 + 0.03 * (1.0 - out["focus"])
    elif bid == "parallax":
        out["offsetX"] = 0.02 * math.sin(t * 0.5)
        out["offsetY"] = 0.015 * math.cos(t * 0.4)
        out["zoom"] = 1.02
    elif bid == "handheld":
        out["offsetX"] = 0.01 * math.sin(t * 5.1) + 0.008 * math.sin(t * 11.0)
        out["offsetY"] = 0.01 * math.cos(t * 4.7) + 0.006 * math.cos(t * 9.3)
        out["rotation"] = 1.5 * math.sin(t * 3.2)
    elif bid == "crane":
        out["offsetY"] = -0.05 * math.sin(t * 0.35)
        out["zoom"] = 1.0 + 0.06 * math.sin(t * 0.35)
    elif bid == "whip_pan":
        # Continuous whip pulses (not sparse 15% windows that look like identity).
        pulse = abs(math.sin(t * 2.4))
        whip = pulse**6
        out["offsetX"] = 0.22 * whip * (1.0 if math.sin(t * 2.4) >= 0 else -1.0)
        out["shake"] = 0.01 * whip
    elif bid == "punch_in":
        out["zoom"] = 1.0 + 0.15 * a
    elif bid == "drift":
        out["offsetX"] = 0.025 * math.sin(t * 0.25)
        out["offsetY"] = 0.02 * math.sin(t * 0.18 + 1.2)
        out["zoom"] = 1.0 + 0.02 * math.sin(t * 0.2)

    return out
