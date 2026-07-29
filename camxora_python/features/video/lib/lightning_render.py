"""Shared GL draw for lightning layers (preview + export)."""

from __future__ import annotations

from typing import Any

import moderngl
import numpy as np

from features.video.lib.lightning_geometry import (
    build_lightning_polylines,
    lightning_flash_envelope,
    lightning_strike_index,
    polyline_to_ndc_strip,
)
from features.video.lib.lightning_style_registry import normalize_lightning_layers


def _hex_rgb(hex_col: str) -> tuple[float, float, float]:
    s = str(hex_col or "#e0f2fe")
    if not (s.startswith("#") and len(s) == 7):
        return (0.88, 0.95, 1.0)
    try:
        return (int(s[1:3], 16) / 255.0, int(s[3:5], 16) / 255.0, int(s[5:7], 16) / 255.0)
    except Exception:
        return (0.88, 0.95, 1.0)


def peak_lightning_flash(
    template: dict,
    *,
    time_sec: float,
    bass: float = 0.0,
    kick: float = 0.0,
    beat: float = 0.0,
    onset: float = 0.0,
    audio_env: float | None = None,
) -> float:
    """Max per-layer flash (0..1) for this frame — used to sync BG/vignette with strikes."""
    if not bool(template.get("lightningEnabled", False)):
        return 0.0
    raw_layers = template.get("lightningLayers")
    if not isinstance(raw_layers, list) or not raw_layers:
        return 0.0
    layers = normalize_lightning_layers(raw_layers)
    env = float(audio_env) if audio_env is not None else float(max(bass, kick, 0.0))
    peak = 0.0
    for layer_idx, layer in enumerate(layers):
        if not bool(layer.get("enabled", True)):
            continue
        seed_base = float(layer.get("seed", float(layer_idx + 1)) or float(layer_idx + 1))
        flash = lightning_flash_envelope(
            time_sec=float(time_sec),
            flash_rate=float(layer.get("flashRate", 0.85) or 0.85),
            speed=float(layer.get("speed", 1.0) or 1.0),
            reactivity=float(layer.get("reactivity", 0.55) or 0.55),
            audio_env=env,
            seed=seed_base,
            trigger=str(layer.get("trigger") or "always"),
            bass=float(bass),
            kick=float(kick),
            beat=float(beat),
            onset=float(onset),
            threshold=float(layer.get("triggerThreshold", 0.22) or 0.22),
        )
        intensity = float(layer.get("intensity", 0.72) or 0.72)
        flash = float(max(0.0, min(1.0, flash * (0.35 + 0.65 * intensity))))
        if flash > peak:
            peak = flash
    return float(peak)


def apply_vignette_reactivity(
    *,
    strength: float,
    opacity: float,
    reactivity: float,
    flash_env: float,
) -> tuple[float, float]:
    """Open vignette on audio/lightning hits — returns (strength, opacity)."""
    open_amt = float(max(0.0, min(1.0, float(flash_env) * float(max(0.0, reactivity)))))
    return (
        float(max(0.0, min(1.0, float(strength) * (1.0 - open_amt * 0.75)))),
        float(max(0.0, min(1.0, float(opacity) * (1.0 - open_amt)))),
    )


def render_lightning_layers_gl(
    ctx: moderngl.Context,
    *,
    line_vbo: Any,
    vao_lines: Any,
    template: dict,
    w: int,
    h: int,
    sf: float,
    cx: float,
    cy: float,
    time_sec: float,
    bass: float = 0.0,
    kick: float = 0.0,
    beat: float = 0.0,
    onset: float = 0.0,
    audio_env: float | None = None,
) -> None:
    """Draw lightning over background / under spectrum+logo. No-op when disabled."""
    if not bool(template.get("lightningEnabled", False)):
        return
    raw_layers = template.get("lightningLayers")
    if not isinstance(raw_layers, list) or not raw_layers:
        return

    layers = normalize_lightning_layers(raw_layers)
    env = float(audio_env) if audio_env is not None else float(max(bass, kick, 0.0))

    for layer_idx, layer in enumerate(layers):
        if not bool(layer.get("enabled", True)):
            continue
        seed_base = float(layer.get("seed", float(layer_idx + 1)) or float(layer_idx + 1))
        seed_lock = bool(layer.get("seedLock", False))
        speed = float(layer.get("speed", 1.0) or 1.0)
        flash_rate = float(layer.get("flashRate", 0.85) or 0.85)
        flash = lightning_flash_envelope(
            time_sec=float(time_sec),
            flash_rate=flash_rate,
            speed=speed,
            reactivity=float(layer.get("reactivity", 0.55) or 0.55),
            audio_env=env,
            seed=seed_base,
            trigger=str(layer.get("trigger") or "always"),
            bass=float(bass),
            kick=float(kick),
            beat=float(beat),
            onset=float(onset),
            threshold=float(layer.get("triggerThreshold", 0.22) or 0.22),
        )
        intensity = float(layer.get("intensity", 0.72) or 0.72)
        flash = float(max(0.0, min(1.0, flash * (0.35 + 0.65 * intensity))))
        if flash <= 0.02:
            continue

        lx = float(cx) + float(layer.get("x", 0.0) or 0.0) * float(sf)
        ly = float(cy) + float(layer.get("y", 0.0) or 0.0) * float(sf)
        length_px = float(layer.get("length", 200.0) or 200.0) * float(sf)
        # One stable jagged shape per strike (not re-rolling every frame → “many bolts”).
        strike_id = lightning_strike_index(
            time_sec=float(time_sec),
            flash_rate=flash_rate,
            speed=speed,
            seed=seed_base,
        )
        shape_time = 0.0 if seed_lock else float(strike_id) * 0.17
        shape_seed = seed_base if seed_lock else seed_base + float(strike_id % 97)

        polys = build_lightning_polylines(
            style=str(layer.get("style") or "fork"),
            cx=lx,
            cy=ly,
            length_px=length_px,
            direction=str(layer.get("direction") or "down"),
            rotation=float(layer.get("rotation", 0.0) or 0.0),
            branchiness=float(layer.get("branchiness", 0.55) or 0.55),
            time_sec=shape_time,
            flash=flash,
            seed=shape_seed,
            speed=speed,
        )
        if not polys:
            continue

        color_cfg = layer.get("color") if isinstance(layer.get("color"), dict) else {}
        solid = str(color_cfg.get("solidColor") or "#e0f2fe")
        grads = color_cfg.get("gradientColors") if isinstance(color_cfg.get("gradientColors"), list) else []
        hex_col = str(grads[0]) if grads else solid
        r, g, b = _hex_rgb(hex_col)
        opacity = float(max(0.0, min(1.0, float(layer.get("opacity", 0.85) or 0.85))) * flash)
        thickness = float(layer.get("thickness", 2.8) or 2.8) * float(sf)
        glow = float(max(0.0, min(1.0, float(layer.get("glow", 0.5) or 0.5))))
        blend = str(layer.get("blend") or "add").lower().strip()
        if blend in {"add", "screen", "lighten"}:
            ctx.blend_func = moderngl.ADDITIVE_BLENDING
        else:
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        passes: list[tuple[float, float]] = []
        if glow > 0.02:
            passes.append((thickness * (2.4 + glow * 3.0), opacity * (0.18 + glow * 0.28)))
            passes.append((thickness * (1.5 + glow * 1.2), opacity * (0.28 + glow * 0.22)))
        passes.append((thickness, opacity))
        if str(layer.get("style") or "") == "neon":
            passes.append((max(0.6, thickness * 0.35), min(1.0, opacity * 1.35)))

        for half_mul, alpha in passes:
            half_w = float(max(0.4, half_mul * 0.5))
            for poly in polys:
                strip = polyline_to_ndc_strip(poly, half_width=half_w, frame_w=float(w), frame_h=float(h))
                if strip is None:
                    continue
                nn = int(strip.shape[0])
                cols = np.tile(np.array([r, g, b, float(alpha)], dtype=np.float32), (nn, 1))
                verts = np.column_stack([strip, cols]).astype(np.float32)
                if verts.nbytes > line_vbo.size:
                    line_vbo.orphan(size=verts.nbytes)
                line_vbo.write(np.ascontiguousarray(verts, dtype=np.float32))
                vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=nn)

    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
