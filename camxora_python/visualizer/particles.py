from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pygame


@dataclass(frozen=True)
class ParticleConfig:
    enabled: bool
    max_count: int
    spawn_rate: float
    lifetime_sec: float
    spawn_radius: float
    size: float
    opacity: float
    color: tuple[int, int, int]
    speed: float
    size_jitter: float = 0.0
    drift: float = 0.0
    swirl: float = 0.0
    spawn_area: str = "centerRing"
    travel_mode: str = "spawnFlow"
    color_mode: str = "solid"
    palette_colors: tuple[tuple[int, int, int], ...] = ()


class ParticleSystem:
    def __init__(self, cfg: ParticleConfig, width: int, height: int, rng_seed: int = 1) -> None:
        self._cfg = cfg
        self._w = int(width)
        self._h = int(height)
        self._rng = np.random.default_rng(rng_seed)
        self._pos = np.zeros((0, 2), dtype=np.float32)
        self._vel = np.zeros((0, 2), dtype=np.float32)
        self._age = np.zeros((0,), dtype=np.float32)
        self._size = np.zeros((0,), dtype=np.float32)
        self._rgb = np.zeros((0, 3), dtype=np.float32)
        self._speed_last = float(max(1e-6, float(cfg.speed)))
        self._spawn_carry = 0.0

    def update_cfg(self, cfg: ParticleConfig) -> None:
        prev = self._cfg
        self._cfg = cfg
        # Clear live particles when spawn/travel recipe changes so presets
        # like Embers do not inherit leftover particles from another look.
        if (
            str(getattr(prev, "spawn_area", "") or "") != str(getattr(cfg, "spawn_area", "") or "")
            or str(getattr(prev, "travel_mode", "") or "") != str(getattr(cfg, "travel_mode", "") or "")
            or str(getattr(prev, "color_mode", "") or "") != str(getattr(cfg, "color_mode", "") or "")
        ):
            self._pos = self._pos[:0]
            self._vel = self._vel[:0]
            self._age = self._age[:0]
            self._size = self._size[:0]
            self._rgb = self._rgb[:0]
            self._spawn_carry = 0.0
            self._speed_last = float(max(1e-6, float(cfg.speed)))

    @staticmethod
    def _blend_direction(
        ax: np.ndarray,
        ay: np.ndarray,
        bx: np.ndarray,
        by: np.ndarray,
        blend: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        t = float(max(0.0, min(1.0, blend)))
        x = ax * (1.0 - t) + bx * t
        y = ay * (1.0 - t) + by * t
        length = np.linalg.norm(np.stack([x, y], axis=1), axis=1).astype(np.float32)
        length = np.maximum(length, 1e-6)
        return (x / length).astype(np.float32), (y / length).astype(np.float32)

    def _apply_travel_mode(
        self,
        launch_dir: np.ndarray,
        pos: np.ndarray,
        *,
        cx: float,
        cy: float,
        n: int,
    ) -> np.ndarray:
        travel_mode = str(getattr(self._cfg, "travel_mode", "spawnFlow") or "spawnFlow")
        dx = launch_dir[:, 0].astype(np.float32)
        dy = launch_dir[:, 1].astype(np.float32)
        if travel_mode == "random":
            angles = self._rng.uniform(0.0, np.pi * 2.0, size=(n,)).astype(np.float32)
            return np.column_stack([np.cos(angles), np.sin(angles)]).astype(np.float32)
        # Preview/sim use top-left origin (y increases downward).
        # Rise = toward top (negative y). Fall = toward bottom (positive y).
        if travel_mode == "rise":
            bx = np.zeros((n,), dtype=np.float32)
            by = np.full((n,), -1.0, dtype=np.float32)
            dx, dy = self._blend_direction(dx, dy, bx, by, 0.88)
        elif travel_mode == "fall":
            bx = np.zeros((n,), dtype=np.float32)
            by = np.ones((n,), dtype=np.float32)
            dx, dy = self._blend_direction(dx, dy, bx, by, 0.88)
        elif travel_mode == "burst":
            outward_x = pos[:, 0].astype(np.float32) - float(cx)
            outward_y = pos[:, 1].astype(np.float32) - float(cy)
            length = np.linalg.norm(np.stack([outward_x, outward_y], axis=1), axis=1).astype(np.float32)
            length = np.maximum(length, 1e-6)
            bx = outward_x / length
            by = outward_y / length
            dx, dy = self._blend_direction(dx, dy, bx, by, 0.9)
        return np.column_stack([dx, dy]).astype(np.float32)

    def _spawn(self, n: int, boost: float) -> None:
        if n <= 0:
            return
        max_count = int(max(0, self._cfg.max_count))
        if max_count <= 0:
            return
        can_add = max(0, max_count - self._pos.shape[0])
        n = min(n, can_add)
        if n <= 0:
            return
        cx = float(self._w) * 0.5
        cy = float(self._h) * 0.5
        spawn_area = str(getattr(self._cfg, "spawn_area", "centerRing") or "centerRing")
        rr = float(self._cfg.spawn_radius) if float(self._cfg.spawn_radius) > 0.0 else (min(float(self._w), float(self._h)) * 0.035)
        if spawn_area == "bottom":
            spread = float(self._w) * 0.38
            x = (cx + self._rng.uniform(-1.0, 1.0, size=(n,)) * spread).astype(np.float32)
            # Spawn just inside the bottom edge so embers are immediately visible.
            y = self._rng.uniform(float(self._h) * 0.88, float(self._h) * 0.98, size=(n,)).astype(np.float32)
            pos = np.stack([x, y], axis=1)
            launch_dir = np.stack(
                [
                    self._rng.uniform(-0.35, 0.35, size=(n,)).astype(np.float32),
                    np.full((n,), -1.0, dtype=np.float32),
                ],
                axis=1,
            )
        elif spawn_area == "edges":
            edge = self._rng.integers(0, 4, size=(n,))
            x = np.zeros((n,), dtype=np.float32)
            y = np.zeros((n,), dtype=np.float32)
            x[edge == 0] = 0.0
            y[edge == 0] = self._rng.uniform(0.0, float(self._h), size=int(np.sum(edge == 0))).astype(np.float32)
            x[edge == 1] = float(self._w)
            y[edge == 1] = self._rng.uniform(0.0, float(self._h), size=int(np.sum(edge == 1))).astype(np.float32)
            x[edge == 2] = self._rng.uniform(0.0, float(self._w), size=int(np.sum(edge == 2))).astype(np.float32)
            y[edge == 2] = 0.0
            x[edge == 3] = self._rng.uniform(0.0, float(self._w), size=int(np.sum(edge == 3))).astype(np.float32)
            y[edge == 3] = float(self._h)
            pos = np.stack([x, y], axis=1)
            dir_vec = np.array([[cx, cy]], dtype=np.float32) - pos
            dir_len = np.linalg.norm(dir_vec, axis=1, keepdims=True).astype(np.float32)
            dir_len = np.maximum(dir_len, 1e-6)
            launch_dir = dir_vec / dir_len
            launch_dir += self._rng.uniform(-0.22, 0.22, size=launch_dir.shape).astype(np.float32)
        elif spawn_area == "full":
            x = self._rng.uniform(0.0, float(self._w), size=(n,)).astype(np.float32)
            y = self._rng.uniform(0.0, float(self._h), size=(n,)).astype(np.float32)
            pos = np.stack([x, y], axis=1)
            dir_vec = pos - np.array([[cx, cy]], dtype=np.float32)
            dir_len = np.linalg.norm(dir_vec, axis=1, keepdims=True).astype(np.float32)
            dir_len = np.maximum(dir_len, 1e-6)
            launch_dir = dir_vec / dir_len
            launch_dir += self._rng.uniform(-0.18, 0.18, size=launch_dir.shape).astype(np.float32)
        elif spawn_area in ("screenCenter", "screenRandom"):
            if spawn_area == "screenRandom":
                x = self._rng.uniform(0.0, float(self._w), size=(n,)).astype(np.float32)
                y = self._rng.uniform(0.0, float(self._h), size=(n,)).astype(np.float32)
            else:
                jitter = max(2.0, rr * 0.35)
                x = (cx + self._rng.uniform(-jitter, jitter, size=(n,))).astype(np.float32)
                y = (cy + self._rng.uniform(-jitter, jitter, size=(n,))).astype(np.float32)
            pos = np.stack([x, y], axis=1)
            dir_vec = pos - np.array([[cx, cy]], dtype=np.float32)
            dir_len = np.linalg.norm(dir_vec, axis=1, keepdims=True).astype(np.float32)
            dir_len = np.maximum(dir_len, 1e-6)
            launch_dir = dir_vec / dir_len
            launch_dir += self._rng.uniform(-0.15, 0.15, size=launch_dir.shape).astype(np.float32)
        else:
            a0 = self._rng.uniform(0.0, np.pi * 2.0, size=(n,)).astype(np.float32)
            ring_inner = rr * 0.82 if rr > 1.0 else 0.0
            r0 = self._rng.uniform(ring_inner, rr, size=(n,)).astype(np.float32)
            x = (cx + np.cos(a0) * r0).astype(np.float32)
            y = (cy + np.sin(a0) * r0).astype(np.float32)
            pos = np.stack([x, y], axis=1)
            dir_vec = pos - np.array([[cx, cy]], dtype=np.float32)
            dir_len = np.linalg.norm(dir_vec, axis=1, keepdims=True).astype(np.float32)
            dir_len = np.maximum(dir_len, 1e-6)
            dir_unit = dir_vec / dir_len
            tangential = np.column_stack([-dir_unit[:, 1], dir_unit[:, 0]]).astype(np.float32)
            tangential_jitter = self._rng.uniform(-0.18, 0.18, size=(n, 1)).astype(np.float32)
            launch_dir = dir_unit + (tangential * tangential_jitter)

        launch_dir = self._apply_travel_mode(launch_dir, pos, cx=cx, cy=cy, n=n)

        launch_len = np.linalg.norm(launch_dir, axis=1, keepdims=True).astype(np.float32)
        launch_len = np.maximum(launch_len, 1e-6)
        launch_dir = launch_dir / launch_len

        sp = self._rng.uniform(0.7, 1.15, size=(n, 1)).astype(np.float32) * float(self._cfg.speed) * float(boost)
        vel = (launch_dir * sp).astype(np.float32)
        sj = float(max(0.0, min(1.0, float(getattr(self._cfg, "size_jitter", 0.0) or 0.0))))
        if sj > 1e-6:
            size_factor = (1.0 + self._rng.uniform(-0.6, 0.6, size=(n,)).astype(np.float32) * sj).astype(np.float32)
            size_factor = np.maximum(size_factor, 0.2)
        else:
            size_factor = np.ones((n,), dtype=np.float32)

        if (
            str(getattr(self._cfg, "color_mode", "solid") or "solid") == "palette"
            and len(getattr(self._cfg, "palette_colors", ()) or ()) >= 2
        ):
            palette = list(getattr(self._cfg, "palette_colors", ()) or ())
            ts = self._rng.uniform(0.0, 1.0, size=(n,)).astype(np.float32)
            rgb = np.empty((n, 3), dtype=np.float32)
            stop_count = len(palette)
            for index, t in enumerate(ts):
                scaled = float(t) * float(stop_count - 1)
                left = int(np.floor(scaled))
                right = min(left + 1, stop_count - 1)
                blend = float(scaled - left)
                c0 = np.array(palette[left], dtype=np.float32)
                c1 = np.array(palette[right], dtype=np.float32)
                rgb[index] = c0 * (1.0 - blend) + c1 * blend
        else:
            rgb = np.tile(np.array(self._cfg.color, dtype=np.float32), (n, 1))

        self._pos = np.concatenate([self._pos, pos], axis=0)
        self._vel = np.concatenate([self._vel, vel], axis=0)
        self._age = np.concatenate([self._age, np.zeros((n,), dtype=np.float32)], axis=0)
        self._size = np.concatenate([self._size, size_factor], axis=0)
        self._rgb = np.concatenate([self._rgb, rgb], axis=0)

    def update(self, dt: float, audio: dict) -> None:
        if not self._cfg.enabled:
            self._pos = self._pos[:0]
            self._vel = self._vel[:0]
            self._age = self._age[:0]
            self._size = self._size[:0]
            self._rgb = self._rgb[:0]
            self._speed_last = float(max(1e-6, float(self._cfg.speed)))
            self._spawn_carry = 0.0
            return

        dt = float(dt)
        lifetime = max(0.05, float(self._cfg.lifetime_sec))

        speed_now = float(max(1e-6, float(self._cfg.speed)))
        ratio = speed_now / float(max(1e-6, float(self._speed_last)))
        ratio = float(max(0.25, min(4.0, ratio)))
        if self._vel.shape[0]:
            self._vel *= ratio
        self._speed_last = speed_now

        base_spawn = float(self._cfg.spawn_rate) * dt + float(self._spawn_carry)
        n = int(base_spawn)
        self._spawn_carry = float(base_spawn - float(n))
        self._spawn(n, 1.0)

        if self._pos.shape[0]:
            drift = float(max(0.0, min(1.0, float(getattr(self._cfg, "drift", 0.0) or 0.0))))
            swirl = float(max(0.0, min(1.0, float(getattr(self._cfg, "swirl", 0.0) or 0.0))))
            travel_mode = str(getattr(self._cfg, "travel_mode", "spawnFlow") or "spawnFlow")
            if drift > 1e-6:
                force = float(drift * 120.0) * dt
                if travel_mode == "rise":
                    self._vel[:, 1] -= force
                elif travel_mode == "fall":
                    self._vel[:, 1] += force
                elif travel_mode == "burst":
                    c = np.array([[float(self._w) * 0.5, float(self._h) * 0.5]], dtype=np.float32)
                    dv = self._pos - c
                    dlen = np.linalg.norm(dv, axis=1, keepdims=True).astype(np.float32)
                    dlen = np.maximum(dlen, 1e-6)
                    unit = dv / dlen
                    self._vel += unit * force
            if swirl > 1e-6:
                c = np.array([[float(self._w) * 0.5, float(self._h) * 0.5]], dtype=np.float32)
                dv = self._pos - c
                dlen = np.linalg.norm(dv, axis=1, keepdims=True).astype(np.float32)
                dlen = np.maximum(dlen, 1e-6)
                unit = dv / dlen
                tang = np.column_stack([-unit[:, 1], unit[:, 0]]).astype(np.float32)
                self._vel += tang * (float(swirl * 90.0) * dt)
            self._pos += self._vel * dt
            self._age += dt

            edge_pad = float(max(32.0, float(self._cfg.size) * 4.0))
            alive = (
                (self._age < lifetime)
                & (self._pos[:, 0] >= -edge_pad)
                & (self._pos[:, 0] <= float(self._w) + edge_pad)
                & (self._pos[:, 1] >= -edge_pad)
                & (self._pos[:, 1] <= float(self._h) + edge_pad)
            )
            self._pos = self._pos[alive]
            self._vel = self._vel[alive]
            self._age = self._age[alive]
            self._size = self._size[alive]
            self._rgb = self._rgb[alive]

    def render(self, surface: "pygame.Surface") -> None:
        import pygame

        if not self._cfg.enabled:
            return
        if self._pos.shape[0] == 0:
            return

        alpha = int(max(0.0, min(1.0, float(self._cfg.opacity))) * 255.0)
        col = (*self._cfg.color, alpha)
        base_size = float(self._cfg.size)
        s = pygame.Surface(surface.get_size(), flags=pygame.SRCALPHA)
        for (x, y), sf in zip(self._pos, self._size, strict=False):
            size = max(1, int(round(base_size * float(sf))))
            pygame.draw.circle(s, col, (int(x), int(y)), size)
        surface.blit(s, (0, 0))
