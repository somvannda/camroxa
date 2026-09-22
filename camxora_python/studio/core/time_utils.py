"""Small time/number helpers ported from the JS reference (fmtTime, snap, clamp)."""

from __future__ import annotations

SNAP_STEP_HZ = 20  # snap() rounds to nearest 1/20s = 0.05s, matching the reference


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def snap(t: float) -> float:
    """Round a timeline position to the nearest 0.05s, like the JS `snap()`."""
    return round(t * SNAP_STEP_HZ) / SNAP_STEP_HZ


def fmt_time_hms(seconds: float) -> str:
    """CapCut-style player timecode — HH:MM:SS (no frames)."""
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def fmt_time(seconds: float) -> str:
    """Format seconds as MM:SS.CC, matching the JS `fmtTime()`."""
    seconds = max(0.0, seconds)
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    centis = int((seconds % 1) * 100)
    return f"{minutes:02d}:{secs:02d}.{centis:02d}"


def fmt_time_ruler(seconds: float) -> str:
    """Compact ruler label — H:MM:SS for hour-scale, else MM:SS."""
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
