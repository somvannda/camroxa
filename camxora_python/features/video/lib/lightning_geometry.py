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


def hash01(*parts: float) -> float:
    """Deterministic 0..1 hash from float parts (stable per strike seed)."""
    x = 0.0
    for p in parts:
        x = math.sin(x * 12.9898 + float(p) * 78.233) * 43758.5453
    return float(x - math.floor(x))


# Back-compat alias used by older call sites / tests.
_hash01 = hash01


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
    length_reactivity: float = 0.0,
) -> list[np.ndarray]:
    """Return polylines for **one** lightning bolt (one layer = one bolt).

    Coordinate system matches particle/spectrum preview: +x right, +y down.
    Side forks from ``branchiness`` belong to that single bolt; they are not
    extra independent lightnings. Want more bolts → add more layers.
    ``rotation`` is an extra 0..360° clockwise spin on top of ``direction``.

    Length is stable by default. ``length_reactivity`` (0..1) optionally lets
    flash/volume stretch reach — off (0) keeps Bolt Length fixed.
    ``speed`` no longer stretches length (timing only in the flash envelope).
    """
    del speed  # reserved for callers / API compatibility; length is independent
    style_key = normalize_lightning_style(style)
    if flash <= 0.02:
        return []

    # Convert abstract up-space direction into y-down screen, then apply free rotation.
    dx, dy_up = _direction_vector(direction, seed=seed + time_sec * 0.17)
    dy = -dy_up
    dx, dy = _rotate2(dx, dy, rotation)
    length_react = float(max(0.0, min(1.0, length_reactivity)))
    length_mul = (1.0 - length_react) + length_react * float(0.55 + 0.45 * flash)
    length = float(max(20.0, length_px)) * float(length_mul)
    branch = float(max(0.0, min(1.0, branchiness)))

    if style_key == "pulse":
        return _pulse_ring(cx, cy, length * 0.35 * max(0.35, flash), segments=28)
    if style_key == "sheet":
        return _sheet_flash(cx, cy, length, dx, dy, flash)
    if style_key == "horizon":
        return _horizon_band(cx, cy, length, flash, dx=dx, dy=dy)
    if style_key == "spider":
        return _spider_single(cx, cy, length, branch, time_sec, seed, flash, dx, dy)
    if style_key == "storm":
        # Respect branchiness=0 (no forced min forks).
        return _fork_bolt(
            cx,
            cy,
            length,
            dx,
            dy,
            branch if branch > 0.0 else 0.0,
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
        neon_branch = branch * 0.6 if branch > 0.0 else 0.0
        return _fork_bolt(cx, cy, length, dx, dy, neon_branch, time_sec, seed)
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
        # Slightly stronger mid-path wander for a more natural bolt.
        mid = math.sin(t * math.pi)
        j = (_hash01(seed, time_sec * 3.1, i) - 0.5) * 2.0 * jitter * length * (0.55 + 0.45 * mid)
        # Locked shape uses shape_time; keep flicker soft (not frantic).
        j *= 0.78 + 0.22 * math.sin(time_sec * 9.0 + i * 1.7 + seed)
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
    return _jagged_bolt(cx, cy, length, dx, dy, time_sec, seed, segments=18, jitter=0.1)


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
    half_w = length * (0.7 + 0.2 * flash)
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
    half = length * (0.9 + 0.2 * flash)
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
    spider_branch = branch if branch > 0.0 else 0.0
    return _fork_bolt(
        cx,
        cy,
        length * (0.85 + 0.15 * flash),
        sdx,
        sdy,
        spider_branch,
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
    react_motion_speed: float = 1.0,
) -> int:
    """Stable strike counter — shape stays locked for the whole flash window."""
    rate = float(max(0.0, flash_rate)) * float(max(0.0, speed)) * float(max(0.05, react_motion_speed))
    if rate <= 1e-6:
        return 0
    return int(math.floor(float(time_sec) * rate + float(seed) * 7.13))


def _strike_pulse(
    *,
    time_sec: float,
    flash_rate: float,
    speed: float,
    seed: float,
    react_motion_speed: float = 1.0,
) -> float:
    """Brief on-window per strike — sharp attack, soft natural decay."""
    motion = float(max(0.05, min(4.0, react_motion_speed if react_motion_speed > 0 else 0.05)))
    rate = float(max(0.0, flash_rate)) * float(max(0.0, speed)) * motion
    if rate <= 1e-6:
        return 0.0
    phase = float(time_sec) * rate + float(seed) * 7.13
    period = phase - math.floor(phase)
    # Faster react motion → snappier (shorter) duty; slower → linger.
    duty = float(max(0.06, min(0.28, 0.16 / math.sqrt(motion))))
    if period >= duty:
        return 0.0
    t = period / duty
    # Fast rise (~first 12%), then soft power-curve fall — reads more like real lightning.
    if t < 0.12:
        attack = t / 0.12
        return float(attack * attack)
    fall = (1.0 - (t - 0.12) / 0.88) ** (0.7 + 0.35 / motion)
    return float(max(0.0, fall))


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
    react_motion_speed: float = 1.0,
) -> float:
    """0..1 flash amount — discrete strikes only (never a constant multi-bolt glow)."""
    from features.video.lib.lightning_style_registry import normalize_lightning_trigger

    pulse = _strike_pulse(
        time_sec=time_sec,
        flash_rate=flash_rate,
        speed=speed,
        seed=seed,
        react_motion_speed=react_motion_speed,
    )
    audio = float(max(0.0, min(1.0, audio_env)))
    bass_v = float(max(0.0, min(1.0, bass)))
    kick_v = float(max(0.0, min(1.0, kick)))
    beat_v = float(max(0.0, min(1.0, max(beat, onset))))
    react = float(max(0.0, min(1.0, reactivity)))
    thr = float(max(0.0, min(0.95, threshold)))
    mode = normalize_lightning_trigger(trigger)

    if mode == "timed":
        return float(max(0.0, min(1.0, pulse)))
    if mode == "audio":
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
    half_width_end: float | None = None,
) -> np.ndarray | None:
    """Expand a pixel-space polyline into an NDC triangle strip ``(2N, 2)``.

    When ``half_width_end`` is set, width lerps along the path (taper).
    """
    if pts is None or pts.ndim != 2 or pts.shape[0] < 2 or pts.shape[1] < 2:
        return None
    n = int(pts.shape[0])
    hw0 = float(max(0.05, half_width))
    hw1 = float(max(0.05, half_width if half_width_end is None else half_width_end))
    out = np.empty((n * 2, 2), dtype=np.float32)
    inv_w = 2.0 / float(max(1.0, frame_w))
    inv_h = 2.0 / float(max(1.0, frame_h))
    for i in range(n):
        t = float(i) / float(max(1, n - 1))
        hw = hw0 + (hw1 - hw0) * t
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
