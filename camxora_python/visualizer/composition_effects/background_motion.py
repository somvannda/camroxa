"""Background motion evaluators — orthogonal to atmosphere."""

from __future__ import annotations

import math
from typing import Any

from visualizer.presets.background_motion import normalize_background_motion_id


def evaluate_background_motion(
    motion_id: str | None,
    *,
    time_sec: float = 0.0,
    speed: float = 1.0,
    amplitude: float = 1.0,
    zoom_amount: float = 1.0,
    warp_amount: float = 1.0,
) -> dict[str, Any]:
    """Return a distinct transform signature per catalog motion id.

    GPU ``motionMode`` only accepts none/zoom/vibrate/both, so distinctness also
    comes from scale/offset/rotation/warp amplitudes (applied via userScale /
    userOffset / effect proxies in live_motion).

    Expert multipliers:
    - ``speed`` — how fast the motion cycles
    - ``amplitude`` — pan/orbit offset strength
    - ``zoom_amount`` — scale pulse / ken-burns zoom strength
    - ``warp_amount`` — ripple/warp distortion strength
    """
    mid = normalize_background_motion_id(motion_id) or "static"
    try:
        spd = max(0.15, min(3.0, float(speed)))
    except (TypeError, ValueError):
        spd = 1.0
    try:
        amp = max(0.15, min(3.0, float(amplitude)))
    except (TypeError, ValueError):
        amp = 1.0
    try:
        zoom = max(0.15, min(3.0, float(zoom_amount)))
    except (TypeError, ValueError):
        zoom = 1.0
    try:
        warp_s = max(0.0, min(3.0, float(warp_amount)))
    except (TypeError, ValueError):
        warp_s = 1.0
    t = float(time_sec) * spd
    out: dict[str, Any] = {
        "motionId": mid,
        "scale": 1.0,
        "offsetX": 0.0,
        "offsetY": 0.0,
        "rotation": 0.0,
        "warp": 0.0,
        # Bridge hint for existing GPU backgroundSettings.motionMode
        "legacyMotionMode": "none",
        "vibrateStrength": 1.0,
        "zoomStrength": 1.0,
        "speed": spd,
        "amplitude": amp,
        "zoomAmount": zoom,
        "warpAmount": warp_s,
    }

    if mid == "static":
        pass
    elif mid == "slow_zoom":
        out["scale"] = 1.0 + (0.06 * zoom) * (0.5 + 0.5 * math.sin(t * 0.18))
        out["legacyMotionMode"] = "zoom"
        out["zoomStrength"] = 1.4 * zoom
    elif mid == "ken_burns":
        out["scale"] = 1.0 + (0.12 * zoom) + (0.03 * zoom) * math.sin(t * 0.08)
        out["offsetX"] = 0.055 * amp * math.sin(t * 0.11)
        out["offsetY"] = 0.035 * amp * math.cos(t * 0.09)
        out["legacyMotionMode"] = "zoom"
        out["zoomStrength"] = 2.2 * zoom
    elif mid == "orbit":
        out["offsetX"] = 0.05 * amp * math.cos(t * 0.28)
        out["offsetY"] = 0.05 * amp * math.sin(t * 0.28)
        out["scale"] = 1.0 + 0.04 * zoom
        out["legacyMotionMode"] = "pan"
        out["vibrateStrength"] = 0.35 * amp
    elif mid == "parallax":
        out["offsetX"] = amp * (0.04 * math.sin(t * 0.22) + 0.015 * math.sin(t * 0.55))
        out["offsetY"] = 0.012 * amp * math.cos(t * 0.18)
        out["scale"] = 1.0 + 0.06 * zoom
        out["legacyMotionMode"] = "pan"
        out["vibrateStrength"] = 0.55 * amp
    elif mid == "ripple":
        out["warp"] = 0.035 * max(0.05, warp_s) * math.sin(t * 1.8)
        out["scale"] = 1.0 + (0.02 * zoom) * math.sin(t * 1.8)
        out["offsetX"] = 0.01 * amp * math.sin(t * 3.2)
        out["legacyMotionMode"] = "zoom"
        out["zoomStrength"] = 1.1 * zoom
    elif mid == "energy_wave":
        pulse = abs(math.sin(t * 2.4))
        out["scale"] = 1.0 + (0.07 * zoom) * pulse
        out["warp"] = 0.028 * max(0.05, warp_s) * math.sin(t * 2.4)
        out["offsetY"] = 0.018 * amp * math.sin(t * 1.2)
        out["legacyMotionMode"] = "both"
        out["zoomStrength"] = 2.8 * zoom
        out["vibrateStrength"] = 1.6 * amp
    elif mid == "floating":
        out["offsetY"] = 0.045 * amp * math.sin(t * 0.4)
        out["offsetX"] = 0.012 * amp * math.sin(t * 0.17)
        out["scale"] = 1.0 + 0.02 * zoom
        out["legacyMotionMode"] = "pan"
        out["vibrateStrength"] = 0.25 * amp
    elif mid == "rotate":
        out["rotation"] = t * 8.0
        out["offsetX"] = 0.03 * amp * math.cos(math.radians(out["rotation"]))
        out["offsetY"] = 0.03 * amp * math.sin(math.radians(out["rotation"]))
        out["scale"] = 1.0 + 0.08 * zoom
        out["legacyMotionMode"] = "rotate"
        out["zoomStrength"] = 1.5 * zoom
        out["vibrateStrength"] = 1.2 * amp
    elif mid == "warp":
        out["warp"] = (0.06 + 0.035 * math.sin(t * 0.9)) * max(0.05, warp_s)
        out["scale"] = 1.0 + (0.1 * zoom) + (0.04 * zoom) * math.sin(t * 0.55)
        out["offsetX"] = 0.02 * amp * math.sin(t * 1.1)
        out["offsetY"] = 0.02 * amp * math.cos(t * 0.85)
        out["legacyMotionMode"] = "both"
        out["zoomStrength"] = 3.0 * zoom
        out["vibrateStrength"] = 1.8 * amp

    return out
