"""CapCut-inspired Recommended VBR bitrate for export encodes.

Anchors are calibrated from an observed CapCut 2K@30fps Recommended export
(~12 Mbps average), then scaled by resolution class, FPS, and Speed. Not a
bit-identical CapCut clone.
"""

from __future__ import annotations

from shared.lib.export_codec import normalize_export_speed_mode

# Target Mbps at 30 fps for Speed=Quality (1.0×).
_BASE_MBPS_720P = 5.0
_BASE_MBPS_1080P = 8.0
_BASE_MBPS_1440P = 12.0
_BASE_MBPS_4K = 24.0

_SPEED_BITRATE_MULT: dict[str, float] = {
    "best_quality": 1.25,
    "quality": 1.0,
    "balanced": 0.85,
    "fast": 0.70,
    "very_fast": 0.55,
}

_MAXRATE_MULT = 1.5
_BUFSIZE_MULT = 2.0


def _base_mbps_for_pixels(width: int, height: int) -> float:
    pixels = max(1, int(width)) * max(1, int(height))
    if pixels <= 1280 * 720:
        return _BASE_MBPS_720P
    if pixels <= int(1920 * 1080 * 1.15):
        return _BASE_MBPS_1080P
    if pixels <= int(2560 * 1440 * 1.05):
        return _BASE_MBPS_1440P
    return _BASE_MBPS_4K


def recommended_export_bitrate_kbps(
    width: int,
    height: int,
    fps: int | float,
    speed_mode: object = "quality",
) -> int:
    """Recommended average video bitrate in kbps for H.264 VBR export."""
    base = _base_mbps_for_pixels(int(width), int(height))
    fps_n = max(1.0, float(fps or 30))
    mode = normalize_export_speed_mode(speed_mode, default="quality")
    mult = float(_SPEED_BITRATE_MULT.get(mode, 1.0))
    mbps = base * (fps_n / 30.0) * mult
    return max(500, int(round(mbps * 1000.0)))


def recommended_vbr_ladder_kbps(
    width: int,
    height: int,
    fps: int | float,
    speed_mode: object = "quality",
) -> tuple[int, int, int]:
    """Return ``(target_kbps, maxrate_kbps, bufsize_kbps)`` for FFmpeg VBR."""
    target = recommended_export_bitrate_kbps(width, height, fps, speed_mode)
    maxrate = max(target, int(round(target * _MAXRATE_MULT)))
    bufsize = max(maxrate, int(round(target * _BUFSIZE_MULT)))
    return target, maxrate, bufsize


def format_bitrate_mbps(kbps: int) -> str:
    value = max(0, int(kbps)) / 1000.0
    if value >= 10:
        return f"{value:.0f} Mbps"
    return f"{value:.1f} Mbps"


def ffmpeg_vbr_bitrate_args(target_kbps: int, maxrate_kbps: int, bufsize_kbps: int) -> list[str]:
    """Shared ``-b:v`` / ``-maxrate`` / ``-bufsize`` fragment (no codec/-rc)."""
    return [
        "-b:v",
        f"{int(target_kbps)}k",
        "-maxrate",
        f"{int(maxrate_kbps)}k",
        "-bufsize",
        f"{int(bufsize_kbps)}k",
    ]
