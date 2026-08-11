"""Shared GL draw for lightning layers (preview + export)."""

from __future__ import annotations

import math
from typing import Any

import moderngl
import numpy as np

from features.video.lib.lightning_geometry import (
    build_lightning_polylines,
    hash01,
    lightning_flash_envelope,
    lightning_strike_index,
    polyline_to_ndc_strip,
)
from features.video.lib.lightning_style_registry import normalize_lightning_layers, normalize_lightning_spawn


def _hex_rgb(hex_col: str) -> tuple[float, float, float]:
    s = str(hex_col or "#e0f2fe")
    if not (s.startswith("#") and len(s) == 7):
        return (0.88, 0.95, 1.0)
    try:
        return (int(s[1:3], 16) / 255.0, int(s[3:5], 16) / 255.0, int(s[5:7], 16) / 255.0)
    except Exception:
        return (0.88, 0.95, 1.0)


def _layer_float(layer: dict[str, Any], key: str, default: float) -> float:
    """Read layer float; 0.0 is a valid value (never ``x or default``)."""
    raw = layer.get(key, default)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _blend_rgb_normal_opaque_alpha(ctx: moderngl.Context) -> None:
    ctx.blend_func = (
        moderngl.SRC_ALPHA,
        moderngl.ONE_MINUS_SRC_ALPHA,
        moderngl.ZERO,
        moderngl.ONE,
    )


def _blend_rgb_additive_opaque_alpha(ctx: moderngl.Context) -> None:
    ctx.blend_func = (
        moderngl.SRC_ALPHA,
        moderngl.ONE,
        moderngl.ZERO,
        moderngl.ONE,
    )


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
    peaks = peak_lightning_flash_by_layer(
        template,
        time_sec=time_sec,
        bass=bass,
        kick=kick,
        beat=beat,
        onset=onset,
        audio_env=audio_env,
    )
    return float(max(peaks.values()) if peaks else 0.0)


def peak_lightning_flash_by_layer(
    template: dict,
    *,
    time_sec: float,
    bass: float = 0.0,
    kick: float = 0.0,
    beat: float = 0.0,
    onset: float = 0.0,
    audio_env: float | None = None,
) -> dict[int, float]:
    """Per-layer flash (0..1) at ``time_sec`` — keyed by layer index."""
    if not bool(template.get("lightningEnabled", False)):
        return {}
    raw_layers = template.get("lightningLayers")
    if not isinstance(raw_layers, list) or not raw_layers:
        return {}
    layers = normalize_lightning_layers(raw_layers)
    env = float(audio_env) if audio_env is not None else float(max(bass, kick, 0.0))
    out: dict[int, float] = {}
    for layer_idx, layer in enumerate(layers):
        if not bool(layer.get("enabled", True)):
            continue
        seed_base = _layer_float(layer, "seed", float(layer_idx + 1))
        opacity = float(max(0.0, min(1.0, _layer_float(layer, "opacity", 0.85))))
        if opacity <= 0.001:
            continue
        flash = lightning_flash_envelope(
            time_sec=float(time_sec),
            flash_rate=_layer_float(layer, "flashRate", 0.85),
            speed=_layer_float(layer, "speed", 1.0),
            reactivity=_layer_float(layer, "reactivity", 0.55),
            audio_env=env,
            seed=seed_base,
            trigger=str(layer.get("trigger") or "always"),
            bass=float(bass),
            kick=float(kick),
            beat=float(beat),
            onset=float(onset),
            threshold=_layer_float(layer, "triggerThreshold", 0.22),
            react_motion_speed=_layer_float(layer, "reactMotionSpeed", 1.0),
        )
        intensity = _layer_float(layer, "intensity", 0.72)
        flash = float(max(0.0, min(1.0, flash * (0.35 + 0.65 * intensity) * opacity)))
        if flash > 0.0:
            out[layer_idx] = flash
    return out


def sample_lightning_layer_peaks_over_interval(
    template: dict,
    *,
    time_sec: float,
    encode_dt: float,
    bass: float = 0.0,
    kick: float = 0.0,
    beat: float = 0.0,
    onset: float = 0.0,
    audio_env: float | None = None,
    sample_hz: float = 60.0,
) -> tuple[float, dict[int, float]]:
    """Peak per-layer flash inside ``[time_sec, time_sec + encode_dt)`` at ~60 Hz.

    Returns ``(global_peak, {layer_index: peak})`` so export can lift only the
    layers that actually struck (preview-like), not every bolt.
    """
    dt = float(max(0.0, encode_dt))
    hz = float(max(1.0, sample_hz))
    step = 1.0 / hz
    samples = max(1, int(math.ceil(dt * hz)) if dt > 0.0 else 1)
    peaks: dict[int, float] = {}
    global_peak = 0.0
    for sample_i in range(samples):
        t = float(time_sec) + float(sample_i) * step
        if dt > 0.0 and t >= float(time_sec) + dt and sample_i > 0:
            break
        sample_peaks = peak_lightning_flash_by_layer(
            template,
            time_sec=t,
            bass=bass,
            kick=kick,
            beat=beat,
            onset=onset,
            audio_env=audio_env,
        )
        for layer_idx, flash in sample_peaks.items():
            prev = peaks.get(layer_idx, 0.0)
            if flash > prev:
                peaks[layer_idx] = flash
            if flash > global_peak:
                global_peak = flash
    return float(global_peak), peaks


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


def apply_lightning_flash_floor(
    flash: float,
    *,
    peak_floor: float,
    opacity_base: float,
) -> float:
    """Raise pre-opacity flash using a sampler peak that already includes opacity.

    Sampler peaks (``peak_lightning_flash_by_layer`` / interval global peak) bake
    ``envelope * intensity_factor * opacity``. Render keeps flash in pre-opacity
    space (``envelope * intensity_factor``) and applies opacity later. Convert the
    floor into that space — never multiply intensity/opacity a second time.
    """
    flash_v = float(max(0.0, min(1.0, float(flash))))
    floor_v = float(max(0.0, min(1.0, float(peak_floor))))
    opacity_v = float(max(0.0, min(1.0, float(opacity_base))))
    if floor_v <= 0.0 or opacity_v <= 1e-6:
        return flash_v
    floor_flash = float(min(1.0, floor_v / opacity_v))
    return float(max(flash_v, floor_flash))


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
    flash_override: float | None = None,
    flash_overrides_by_layer: dict[int, float] | None = None,
    opaque_framebuffer_alpha: bool = True,
) -> None:
    """Draw lightning over background / under spectrum+logo. No-op when disabled.

    ``flash_overrides_by_layer`` maps layer index → sampler peak (already includes
    intensity×opacity). Only those layers are raised — matching preview per-bolt
    timing. Legacy ``flash_override`` (global peak applied to every layer) is used
    only when the per-layer map is omitted; prefer the per-layer map for export.

    When ``opaque_framebuffer_alpha`` is True (preview default), RGB blends
    normally/additively while destination alpha stays 1 so Qt translucent
    windows do not show the desktop through soft glow coronae.
    """
    if not bool(template.get("lightningEnabled", False)):
        return
    raw_layers = template.get("lightningLayers")
    if not isinstance(raw_layers, list) or not raw_layers:
        return

    layers = normalize_lightning_layers(raw_layers)
    env = float(audio_env) if audio_env is not None else float(max(bass, kick, 0.0))
    per_layer_floor: dict[int, float] = {}
    if isinstance(flash_overrides_by_layer, dict):
        for key, value in flash_overrides_by_layer.items():
            try:
                idx = int(key)
                per_layer_floor[idx] = float(max(0.0, min(1.0, float(value))))
            except (TypeError, ValueError):
                continue
    elif flash_override is not None:
        # Legacy global floor — keep for older call sites, but prefer per-layer.
        try:
            legacy = float(max(0.0, min(1.0, float(flash_override))))
        except (TypeError, ValueError):
            legacy = 0.0
        if legacy > 0.0:
            for layer_idx in range(len(layers)):
                per_layer_floor[layer_idx] = legacy

    for layer_idx, layer in enumerate(layers):
        if not bool(layer.get("enabled", True)):
            continue
        seed_base = _layer_float(layer, "seed", float(layer_idx + 1))
        seed_lock = bool(layer.get("seedLock", False))
        speed = _layer_float(layer, "speed", 1.0)
        flash_rate = _layer_float(layer, "flashRate", 0.85)
        react_motion = _layer_float(layer, "reactMotionSpeed", 1.0)
        opacity_base = float(max(0.0, min(1.0, _layer_float(layer, "opacity", 0.85))))
        if opacity_base <= 0.001:
            continue
        flash = lightning_flash_envelope(
            time_sec=float(time_sec),
            flash_rate=flash_rate,
            speed=speed,
            reactivity=_layer_float(layer, "reactivity", 0.55),
            audio_env=env,
            seed=seed_base,
            trigger=str(layer.get("trigger") or "always"),
            bass=float(bass),
            kick=float(kick),
            beat=float(beat),
            onset=float(onset),
            threshold=_layer_float(layer, "triggerThreshold", 0.22),
            react_motion_speed=react_motion,
        )
        intensity = _layer_float(layer, "intensity", 0.72)
        flash = float(max(0.0, min(1.0, flash * (0.35 + 0.65 * intensity))))
        peak_floor = float(per_layer_floor.get(layer_idx, 0.0))
        # Keep strikes visible when export undersamples the 60 Hz envelope.
        flash = apply_lightning_flash_floor(
            flash,
            peak_floor=peak_floor,
            opacity_base=opacity_base,
        )
        if flash <= 0.02:
            continue

        # One stable jagged shape per strike (not re-rolling every frame → “many bolts”).
        strike_id = lightning_strike_index(
            time_sec=float(time_sec),
            flash_rate=flash_rate,
            speed=speed,
            seed=seed_base,
            react_motion_speed=react_motion,
        )
        shape_time = 0.0 if seed_lock else float(strike_id) * 0.17
        shape_seed = seed_base if seed_lock else seed_base + float(strike_id % 97)

        spawn = normalize_lightning_spawn(layer.get("spawnMode"))
        if spawn == "random":
            # Full-frame random spawn per strike (keeps x/y as mild bias toward center).
            margin = 0.12
            jx = margin + hash01(shape_seed, 1.1) * (1.0 - 2.0 * margin)
            jy = margin + hash01(shape_seed, 2.2) * (1.0 - 2.0 * margin)
            lx = float(w) * jx + _layer_float(layer, "x", 0.0) * float(sf) * 0.15
            ly = float(h) * jy + _layer_float(layer, "y", 0.0) * float(sf) * 0.15
        else:
            lx = float(cx) + _layer_float(layer, "x", 0.0) * float(sf)
            ly = float(cy) + _layer_float(layer, "y", 0.0) * float(sf)

        length_px = _layer_float(layer, "length", 200.0) * float(sf)

        polys = build_lightning_polylines(
            style=str(layer.get("style") or "fork"),
            cx=lx,
            cy=ly,
            length_px=length_px,
            direction=str(layer.get("direction") or "down"),
            rotation=_layer_float(layer, "rotation", 0.0),
            branchiness=_layer_float(layer, "branchiness", 0.35),
            time_sec=shape_time,
            flash=flash,
            seed=shape_seed,
            speed=speed,
            length_reactivity=_layer_float(layer, "lengthReactivity", 0.0),
        )
        if not polys:
            continue

        color_cfg = layer.get("color") if isinstance(layer.get("color"), dict) else {}
        solid = str(color_cfg.get("solidColor") or "#e0f2fe")
        grads = color_cfg.get("gradientColors") if isinstance(color_cfg.get("gradientColors"), list) else []
        hex_col = str(grads[0]) if grads else solid
        r, g, b = _hex_rgb(hex_col)
        # Opacity gates both core and glow; flash only modulates strike brightness.
        opacity = float(opacity_base * flash)
        thickness = max(0.0, _layer_float(layer, "thickness", 2.8)) * float(sf)
        if thickness <= 0.05:
            continue
        glow = float(max(0.0, min(1.0, _layer_float(layer, "glow", 0.5))))
        taper = float(max(0.0, min(1.0, _layer_float(layer, "taper", 0.65))))
        blend = str(layer.get("blend") or "add").lower().strip()
        if opaque_framebuffer_alpha:
            if blend in {"add", "screen", "lighten"}:
                _blend_rgb_additive_opaque_alpha(ctx)
            else:
                _blend_rgb_normal_opaque_alpha(ctx)
        elif blend in {"add", "screen", "lighten"}:
            ctx.blend_func = moderngl.ADDITIVE_BLENDING
        else:
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        # Taper: thin at start → thicker toward the tip (real bolts often look this way).
        start_mul = float(max(0.12, 1.0 - taper * 0.88))
        end_mul = float(1.0 + taper * 0.55)

        # Passes: (half_mul_start, half_mul_end, alpha, rgb)
        passes: list[tuple[float, float, float, tuple[float, float, float]]] = []
        if glow > 0.02 and opacity > 0.02:
            # Wide soft corona (bright air glow around the strike).
            corona_a = opacity * (0.12 + glow * 0.28)
            passes.append(
                (
                    thickness * (3.6 + glow * 5.0) * start_mul,
                    thickness * (3.6 + glow * 5.0) * end_mul,
                    corona_a,
                    (min(1.0, r * 0.55 + 0.45), min(1.0, g * 0.55 + 0.45), min(1.0, b * 0.55 + 0.45)),
                )
            )
            passes.append(
                (
                    thickness * (2.2 + glow * 2.8) * start_mul,
                    thickness * (2.2 + glow * 2.8) * end_mul,
                    opacity * (0.18 + glow * 0.28),
                    (r, g, b),
                )
            )
            passes.append(
                (
                    thickness * (1.35 + glow * 1.1) * start_mul,
                    thickness * (1.35 + glow * 1.1) * end_mul,
                    opacity * (0.28 + glow * 0.22),
                    (r, g, b),
                )
            )
        passes.append((thickness * start_mul, thickness * end_mul, opacity, (r, g, b)))
        if str(layer.get("style") or "") == "neon":
            passes.append(
                (
                    max(0.4, thickness * 0.35 * start_mul),
                    max(0.4, thickness * 0.35 * end_mul),
                    min(1.0, opacity * 1.25),
                    (min(1.0, r + 0.25), min(1.0, g + 0.25), min(1.0, b + 0.25)),
                )
            )

        for half_start, half_end, alpha, rgb in passes:
            if alpha <= 0.001:
                continue
            half_w0 = float(max(0.15, half_start * 0.5))
            half_w1 = float(max(0.15, half_end * 0.5))
            cr, cg, cb = rgb
            for poly in polys:
                strip = polyline_to_ndc_strip(
                    poly,
                    half_width=half_w0,
                    half_width_end=half_w1,
                    frame_w=float(w),
                    frame_h=float(h),
                )
                if strip is None:
                    continue
                nn = int(strip.shape[0])
                cols = np.tile(np.array([cr, cg, cb, float(alpha)], dtype=np.float32), (nn, 1))
                verts = np.column_stack([strip, cols]).astype(np.float32)
                if verts.nbytes > line_vbo.size:
                    line_vbo.orphan(size=verts.nbytes)
                line_vbo.write(np.ascontiguousarray(verts, dtype=np.float32))
                vao_lines.render(mode=moderngl.TRIANGLE_STRIP, vertices=nn)

    if opaque_framebuffer_alpha:
        _blend_rgb_normal_opaque_alpha(ctx)
    else:
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
