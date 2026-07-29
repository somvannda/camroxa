"""Procedural lightning bolt geometry for preview/export."""

from __future__ import annotations

import math

import numpy as np

from features.video.lib.lightning_style_registry import normalize_lightning_direction, normalize_lightning_style


def _direction_vector(direction: str, *, seed: float = 0.0) -> tuple[float, float]:
    d = normalize_lightning_direction(direction)
    if d == "up":
        return (0.0, 1.0)
    if d == "left":
        return (-1.0, 0.0)
    if d == "right":
        return (1.0, 0.0)
    if d == "inward":
        return (0.0, -1.0)
    if d == "outward":
        return (0.0, 1.0)
    if d == "random":
        ang = float(seed) * 12.9898
        ang = (math.sin(ang) * 43758.5453) % (math.pi * 2.0)
        return (float(math.cos(ang)), float(math.sin(ang)))
    return (0.0, -1.0)  # down (y-up screen space for NDC later flips)


def _hash01(*parts: float) -> float:
    x = 0.0
    for p in parts:
        x = math.sin(x * 12.9898 + float(p) * 78.233) * 43758.5453
    return float(x - math.floor(x))


def _rotate2(dx: float, dy: float, degrees: float) -> tuple[float, float]:
    """Rotate a screen-space vector clockwise by degrees (0..360, y-down)."""
    rad = math.radians(float(degrees) % 360.0)
    c = math.cos(rad)
    s = math.sin(rad)
    # y-down: clockwise matches standard CCW matrix on these coords.
    return (float(dx * c - dy * s), float(dx * s + dy * c))


def build_lightning_polylines(
    *,
    style: str,
    cx: float,
    cy: float,
    length_px: float,
    direction: str,
    branchiness: float,
    time_sec: float,
    flash: float,
    seed: float = 1.0,
    speed: float = 1.0,
    rotation: float = 0.0,
) -> list[np.ndarray]:
    """Return polylines for **one** lightning bolt (one layer = one bolt).

    Coordinate system matches particle/spectrum preview: +x right, +y down.
    Side forks from ``branchiness`` belong to that single bolt; they are not
    extra independent lightnings. Want more bolts → add more layers.
    ``rotation`` is an extra 0..360° clockwise spin on top of ``direction``.
    """
    style_key = normalize_lightning_style(style)
    if flash <= 0.02:
        return []

    # Convert abstract up-space direction into y-down screen, then apply free rotation.
    dx, dy_up = _direction_vector(direction, seed=seed + time_sec * 0.17)
    dy = -dy_up
    dx, dy = _rotate2(dx, dy, rotation)
    # Speed stretches reach: at speed=1.0 length matches Bolt Length; higher = longer.
    speed_n = float(max(0.05, min(4.0, float(speed or 1.0))))
    length = float(max(20.0, length_px)) * float(0.55 + 0.45 * flash) * float(0.55 + 0.45 * speed_n)
    branch = float(max(0.0, min(1.0, branchiness)))

    if style_key == "pulse":
        return _pulse_ring(cx, cy, length * 0.35 * flash, segments=28)
    if style_key == "sheet":
        return _sheet_flash(cx, cy, length, dx, dy, flash)
    if style_key == "horizon":
        return _horizon_band(cx, cy, length, flash, dx=dx, dy=dy)
    if style_key == "spider":
        # One radial strike (not a fan of independent bolts).
        return _spider_single(cx, cy, length, branch, time_sec, seed, flash, dx, dy)
    if style_key == "storm":
        # One turbulent fork — stormy look without spawning extra bolts.
        return _fork_bolt(
            cx,
            cy,
            length,
            dx,
            dy,
            max(0.35, branch),
            time_sec,
            seed,
            segments=18,
            jitter=0.18,
        )
    if style_key == "arc":
        return [_arc_bolt(cx, cy, length, dx, dy, time_sec, seed)]
    if style_key == "chain":
        return [_chain_bolt(cx, cy, length, dx, dy, time_sec, seed)]
    if style_key == "ribbon":
        return [_jagged_bolt(cx, cy, length, dx, dy, time_sec, seed, segments=10, jitter=0.08)]
    if style_key == "neon":
        return _fork_bolt(cx, cy, length, dx, dy, max(0.2, branch * 0.6), time_sec, seed)
    # fork (default)
    return _fork_bolt(cx, cy, length, dx, dy, branch, time_sec, seed)


def _jagged_bolt(
    cx: float,
    cy: float,
    length: float,
    dx: float,
    dy: float,
    time_sec: float,
    seed: float,
    *,
    segments: int,
    jitter: float,
) -> np.ndarray:
    n = int(max(4, segments))
    pts = np.empty((n, 2), dtype=np.float32)
    px, py = float(dx), float(dy)
    norm = math.hypot(px, py) or 1.0
    px /= norm
    py /= norm
    qx, qy = -py, px
    for i in range(n):
        t = float(i) / float(n - 1)
        j = (_hash01(seed, time_sec * 3.1, i) - 0.5) * 2.0 * jitter * length
        # re-jitter along path over time for flicker
        j *= 0.65 + 0.35 * math.sin(time_sec * 17.0 + i * 1.7 + seed)
        pts[i, 0] = cx + px * length * t + qx * j
        pts[i, 1] = cy + py * length * t + qy * j
    return pts


def _fork_bolt(
    cx: float,
    cy: float,
    length: float,
    dx: float,
    dy: float,
    branch: float,
    time_sec: float,
    seed: float,
    *,
    segments: int = 14,
    jitter: float = 0.12,
) -> list[np.ndarray]:
    main = _jagged_bolt(cx, cy, length, dx, dy, time_sec, seed, segments=segments, jitter=jitter)
    out = [main]
    # Cap side forks — branchiness adds twigs on ONE bolt, not extra lightnings.
    forks = int(min(2, max(0, round(branch * 2.0))))
    if forks <= 0 or main.shape[0] < 4:
        return out
    for i in range(forks):
        idx = 3 + int(_hash01(seed, i, 9.0) * (main.shape[0] - 4))
        idx = max(2, min(main.shape[0] - 2, idx))
        bx, by = float(main[idx, 0]), float(main[idx, 1])
        ang = (_hash01(seed, i, 4.4) - 0.5) * 1.2
        c, s = math.cos(ang), math.sin(ang)
        fdx = dx * c - dy * s
        fdy = dx * s + dy * c
        flen = length * (0.25 + 0.35 * _hash01(seed, i, 5.5))
        out.append(
            _jagged_bolt(bx, by, flen, fdx, fdy, time_sec, seed + 10 + i, segments=7, jitter=0.14)
        )
    return out


def _arc_bolt(cx: float, cy: float, length: float, dx: float, dy: float, time_sec: float, seed: float) -> np.ndarray:
    n = 16
    pts = np.empty((n, 2), dtype=np.float32)
    px, py = float(dx), float(dy)
    norm = math.hypot(px, py) or 1.0
    px /= norm
    py /= norm
    qx, qy = -py, px
    bend = (0.18 + 0.12 * _hash01(seed, 1.0)) * length
    bend *= math.sin(time_sec * 6.0 + seed)
    for i in range(n):
        t = float(i) / float(n - 1)
        curve = math.sin(t * math.pi) * bend
        pts[i, 0] = cx + px * length * t + qx * curve
        pts[i, 1] = cy + py * length * t + qy * curve
    return pts


def _chain_bolt(cx: float, cy: float, length: float, dx: float, dy: float, time_sec: float, seed: float) -> np.ndarray:
    base = _jagged_bolt(cx, cy, length, dx, dy, time_sec, seed, segments=18, jitter=0.1)
    # Drop every other segment visually by collapsing pairs slightly.
    return base


def _pulse_ring(cx: float, cy: float, radius: float, *, segments: int) -> list[np.ndarray]:
    n = int(max(8, segments))
    pts = np.empty((n + 1, 2), dtype=np.float32)
    for i in range(n + 1):
        a = (math.pi * 2.0) * (float(i) / float(n))
        pts[i, 0] = cx + math.cos(a) * radius
        pts[i, 1] = cy + math.sin(a) * radius
    return [pts]


def _sheet_flash(cx: float, cy: float, length: float, dx: float, dy: float, flash: float) -> list[np.ndarray]:
    """One wide sheet stroke per layer."""
    px, py = float(dx), float(dy)
    norm = math.hypot(px, py) or 1.0
    px /= norm
    py /= norm
    qx, qy = -py, px
    half_w = length * (0.55 + 0.35 * flash)
    return [
        np.array(
            [
                [cx - qx * half_w, cy - qy * half_w],
                [cx + qx * half_w, cy + qy * half_w],
            ],
            dtype=np.float32,
        )
    ]


def _horizon_band(
    cx: float,
    cy: float,
    length: float,
    flash: float,
    *,
    dx: float = 1.0,
    dy: float = 0.0,
) -> list[np.ndarray]:
    """One horizon flash band per layer (follows rotation via dx/dy)."""
    half = length * (0.8 + 0.4 * flash)
    px, py = float(dx), float(dy)
    norm = math.hypot(px, py) or 1.0
    # Band runs perpendicular to strike direction.
    qx, qy = -py / norm, px / norm
    return [
        np.array([[cx - qx * half, cy - qy * half], [cx + qx * half, cy + qy * half]], dtype=np.float32),
    ]


def _spider_single(
    cx: float,
    cy: float,
    length: float,
    branch: float,
    time_sec: float,
    seed: float,
    flash: float,
    dx: float,
    dy: float,
) -> list[np.ndarray]:
    """One spider-like strike: primary ray + short side forks (still one bolt)."""
    ang = math.atan2(dy, dx) + (_hash01(seed, time_sec, 0.3) - 0.5) * 0.35
    sdx, sdy = math.cos(ang), math.sin(ang)
    return _fork_bolt(
        cx,
        cy,
        length * (0.7 + 0.3 * flash),
        sdx,
        sdy,
        max(0.45, branch),
        time_sec,
        seed,
        segments=12,
        jitter=0.16,
    )

def lightning_strike_index(
    *,
    time_sec: float,
    flash_rate: float,
    speed: float,
    seed: float = 1.0,
) -> int:
    """Stable strike counter — shape stays locked for the whole flash window."""
    rate = float(max(0.05, flash_rate)) * float(max(0.05, speed))
    return int(math.floor(float(time_sec) * rate + float(seed) * 7.13))


def _strike_pulse(*, time_sec: float, flash_rate: float, speed: float, seed: float) -> float:
    """Brief on-window per strike period (sparse flashes, not a continuous strobe)."""
    rate = float(max(0.05, flash_rate)) * float(max(0.05, speed))
    phase = float(time_sec) * rate + float(seed) * 7.13
    period = phase - math.floor(phase)
    duty = 0.12
    if period >= duty:
        return 0.0
    return float((1.0 - period / duty) ** 0.55)


def lightning_flash_envelope(
    *,
    time_sec: float,
    flash_rate: float,
    speed: float,
    reactivity: float,
    audio_env: float,
    seed: float = 1.0,
    trigger: str = "always",
    bass: float = 0.0,
    kick: float = 0.0,
    beat: float = 0.0,
    onset: float = 0.0,
    threshold: float = 0.22,
) -> float:
    """0..1 flash amount — discrete strikes only (never a constant multi-bolt glow)."""
    from features.video.lib.lightning_style_registry import normalize_lightning_trigger

    pulse = _strike_pulse(time_sec=time_sec, flash_rate=flash_rate, speed=speed, seed=seed)
    audio = float(max(0.0, min(1.0, audio_env)))
    bass_v = float(max(0.0, min(1.0, bass)))
    kick_v = float(max(0.0, min(1.0, kick)))
    beat_v = float(max(0.0, min(1.0, max(beat, onset))))
    react = float(max(0.0, min(1.0, reactivity)))
    thr = float(max(0.05, min(0.95, threshold)))
    mode = normalize_lightning_trigger(trigger)

    if mode == "timed":
        return float(max(0.0, min(1.0, pulse)))
    if mode == "audio":
        # Audio scales strike brightness — does not keep lightning permanently on.
        if pulse <= 0.0 or audio < thr * 0.5:
            return 0.0
        return float(max(0.0, min(1.0, pulse * (0.4 + 0.6 * audio))))
    if mode == "bass":
        if bass_v < thr:
            return 0.0
        return float(max(0.0, min(1.0, (0.55 + 0.45 * bass_v) * max(pulse, 0.65))))
    if mode == "kick":
        if kick_v < thr:
            return 0.0
        return float(max(0.0, min(1.0, (0.55 + 0.45 * kick_v) * max(pulse, 0.65))))
    if mode == "beat":
        if beat_v < thr:
            return 0.0
        return float(max(0.0, min(1.0, (0.55 + 0.45 * beat_v) * max(pulse, 0.65))))
    # always: sparse timed strikes; audio only boosts those windows
    if pulse <= 0.0:
        return 0.0
    return float(max(0.0, min(1.0, pulse * (0.55 + 0.45 * audio * react))))


def polyline_to_ndc_strip(
    pts: np.ndarray,
    *,
    half_width: float,
    frame_w: float,
    frame_h: float,
) -> np.ndarray | None:
    """Expand a pixel-space polyline into an NDC triangle strip ``(2N, 2)``."""
    if pts is None or pts.ndim != 2 or pts.shape[0] < 2 or pts.shape[1] < 2:
        return None
    n = int(pts.shape[0])
    hw = float(max(0.35, half_width))
    out = np.empty((n * 2, 2), dtype=np.float32)
    inv_w = 2.0 / float(max(1.0, frame_w))
    inv_h = 2.0 / float(max(1.0, frame_h))
    for i in range(n):
        if i == 0:
            tx = float(pts[1, 0] - pts[0, 0])
            ty = float(pts[1, 1] - pts[0, 1])
        elif i == n - 1:
            tx = float(pts[i, 0] - pts[i - 1, 0])
            ty = float(pts[i, 1] - pts[i - 1, 1])
        else:
            tx = float(pts[i + 1, 0] - pts[i - 1, 0])
            ty = float(pts[i + 1, 1] - pts[i - 1, 1])
        length = math.hypot(tx, ty) or 1.0
        nx = (-ty / length) * hw
        ny = (tx / length) * hw
        x = float(pts[i, 0])
        y = float(pts[i, 1])
        # Pixel y-down → NDC y-up
        out[i * 2, 0] = (x - nx) * inv_w - 1.0
        out[i * 2, 1] = 1.0 - (y - ny) * inv_h
        out[i * 2 + 1, 0] = (x + nx) * inv_w - 1.0
        out[i * 2 + 1, 1] = 1.0 - (y + ny) * inv_h
    return out
