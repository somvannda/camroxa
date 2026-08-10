"""Apply composition cameraSettings to preview center/zoom (beyond shake)."""

from __future__ import annotations

from typing import Any


def camera_view_offset_px(
    camera: dict[str, Any] | None,
    *,
    width: int,
    height: int,
) -> tuple[float, float, float]:
    """Return (offset_x_px, offset_y_px, zoom_scale) from compiled cameraSettings."""
    if not isinstance(camera, dict) or not bool(camera.get("enabled")):
        return 0.0, 0.0, 1.0
    w = float(max(1, width))
    h = float(max(1, height))
    ox = float(camera.get("offsetX") or 0.0) * w * 0.5
    oy = float(camera.get("offsetY") or 0.0) * h * 0.5
    # Expert pan bias (normalized).
    ox += float(camera.get("panX") or 0.0) * w * 0.25
    oy += float(camera.get("panY") or 0.0) * h * 0.25
    # Approximate rotate/tilt/roll as a small orbital offset (no full matrix yet).
    try:
        import math

        rot = math.radians(float(camera.get("rotation") or 0.0))
        roll = math.radians(float(camera.get("roll") or 0.0))
        ox += math.sin(rot) * w * 0.02 + math.sin(roll) * w * 0.015
        oy += math.cos(rot * 0.85) * h * 0.015
    except Exception:
        pass
    zoom = float(camera.get("zoom") or 1.0) * float(camera.get("zoomBias") or 1.0)
    zoom = max(0.7, min(1.6, zoom))
    return ox, oy, zoom
