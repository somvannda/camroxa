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
    # roll/rotation reserved for future; zoom drives spectrum/logo scale feel via centers stay
    zoom = float(camera.get("zoom") or 1.0)
    zoom = max(0.7, min(1.6, zoom))
    return ox, oy, zoom
