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
) -> list[np.ndarray]:
    """Return list of polylines as ``(N, 2)`` float32 arrays in pixel space.

    Coordinate system matches particle/spectrum preview: +x right, +y down.
    """
    style_key = normalize_lightning_style(style)
    if flash <= 0.02:
        return []

    # Convert abstract up-space direction into y-down screen.
    dx, dy_up = _direction_vector(direction, seed=seed + time_sec * 0.17)
    dy = -dy_up
    length = float(max(20.0, length_px)) * float(0.55 + 0.45 * flash)
    branch = float(max(0.0, min(1.0, branchiness)))

    if style_key == "pulse":
        return _pulse_ring(cx, cy, length * 0.35 * flash, segments=28)
    if style_key == "sheet":
        return _sheet_flash(cx, cy, length, dx, dy, flash)
    if style_key == "horizon":
        return _horizon_band(cx, cy, length, flash)
    if style_key == "spider":
        return _spider(cx, cy, length, branch, time_sec, seed, flash)
    if style_key == "storm":
        bolts = []
        for i in range(2 + int(round(branch * 3))):
            ox = ( _hash01(seed, i, 1.1) - 0.5) * length * 0.45
            oy = ( _hash01(seed, i, 2.2) - 0.5) * length * 0.25
            bolts.extend(
                _fork_bolt(cx + ox, cy + oy, length * (0.7 + 0.3 * _hash01(seed, i)), dx, dy, branch, time_sec, seed + i)
            )
        return bolts
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
) -> list[np.ndarray]:
    main = _jagged_bolt(cx, cy, length, dx, dy, time_sec, seed, segments=14, jitter=0.12)
    out = [main]
    forks = int(round(branch * 4))
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
    px, py = float(dx), float(dy)
    norm = math.hypot(px, py) or 1.0
    px /= norm
    py /= norm
    qx, qy = -py, px
    half_w = length * (0.55 + 0.35 * flash)
    half_h = length * 0.08
    # Three parallel soft strokes
    out = []
    for k in (-1.0, 0.0, 1.0):
        pts = np.array(
            [
                [cx - qx * half_w + px * half_h * k, cy - qy * half_w + py * half_h * k],
                [cx + qx * half_w + px * half_h * k, cy + qy * half_w + py * half_h * k],
            ],
            dtype=np.float32,
        )
        out.append(pts)
    return out


def _horizon_band(cx: float, cy: float, length: float, flash: float) -> list[np.ndarray]:
    half = length * (0.8 + 0.4 * flash)
    y = cy + length * 0.15
    return [
        np.array([[cx - half, y], [cx + half, y]], dtype=np.float32),
        np.array([[cx - half * 0.7, y + 6.0], [cx + half * 0.7, y + 6.0]], dtype=np.float32),
    ]


def _spider(
    cx: float,
    cy: float,
    length: float,
    branch: float,
    time_sec: float,
    seed: float,
    flash: float,
) -> list[np.ndarray]:
    count = 4 + int(round(branch * 4))
    out: list[np.ndarray] = []
    for i in range(count):
        ang = (math.pi * 2.0) * (float(i) / float(count)) + time_sec * 0.4
        dx, dy = math.cos(ang), math.sin(ang)
        out.append(
            _jagged_bolt(
                cx,
                cy,
                length * (0.45 + 0.4 * flash),
                dx,
                dy,
                time_sec,
                seed + i,
                segments=8,
                jitter=0.1,
            )
        )
    return out


def lightning_flash_envelope(
    *,
    time_sec: float,
    flash_rate: float,
    speed: float,
    reactivity: float,
    audio_env: float,
    seed: float = 1.0,
) -> float:
    """0..1 flash amount for this frame."""
    rate = float(max(0.05, flash_rate)) * float(max(0.05, speed))
    phase = float(time_sec) * rate + seed * 7.13
    # Sharp pulses
    pulse = abs(math.sin(phase * math.pi))
    pulse = float(max(0.0, pulse - 0.72) / 0.28)
    audio = float(max(0.0, min(1.0, audio_env)))
    react = float(max(0.0, min(1.0, reactivity)))
    triggered = pulse * (0.35 + 0.65 * (1.0 - react)) + audio * react
    return float(max(0.0, min(1.0, triggered)))
