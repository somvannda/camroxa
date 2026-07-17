"""Particle color engine — solid base + multi-color palette (spectrum-style)."""

from __future__ import annotations

from typing import Any

import numpy as np

from features.video.lib.spectrum_color_engine import (
    GRADIENT_FALLBACK_COLOR,
    MAX_GRADIENT_COLOR_STOPS,
    SPECTRUM_GRADIENT_PRESET_OPTIONS,
    build_spectrum_gradient_preset_value,
    normalize_spectrum_gradient_colors,
)
from features.video.lib.template_value_utils import normalize_color, to_record, to_string_value

PARTICLE_COLOR_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("solid", "Solid Color"),
    ("palette", "Multi-Color Palette"),
)

PARTICLE_PALETTE_PRESET_OPTIONS: tuple[tuple[str, str], ...] = SPECTRUM_GRADIENT_PRESET_OPTIONS


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    normalized = normalize_color(hex_color, "#ffffff")
    return (int(normalized[1:3], 16), int(normalized[3:5], 16), int(normalized[5:7], 16))


def _rgb_to_unit(rgb: tuple[int, int, int] | np.ndarray) -> tuple[float, float, float]:
    if isinstance(rgb, np.ndarray):
        return (float(rgb[0]) / 255.0, float(rgb[1]) / 255.0, float(rgb[2]) / 255.0)
    return (float(rgb[0]) / 255.0, float(rgb[1]) / 255.0, float(rgb[2]) / 255.0)


def normalize_particle_palette_colors(
    raw_colors: list[Any],
    fallback: str,
    *,
    require_stops: bool = False,
) -> list[str]:
    """Normalize palette stops.

    When ``require_stops`` is False (solid mode / empty preset), keep an empty
    list empty so preset round-trips do not invent fake gradient stops.
    """
    if not require_stops and (not raw_colors or len(raw_colors) == 0):
        return []
    return normalize_spectrum_gradient_colors(raw_colors, fallback)


def extract_particle_color_model(settings: dict[str, Any] | None) -> dict[str, Any]:
    record = settings or {}
    nested = to_record(record.get("colorMeta"))
    if not nested and isinstance(record.get("color"), dict):
        nested = to_record(record.get("color"))
    solid_fallback = normalize_color(
        record.get("color") if not isinstance(record.get("color"), dict) else nested.get("solidColor"),
        "#ffffff",
    )
    mode_raw = to_string_value(
        record.get("colorMode") or nested.get("mode") or record.get("particlesColorMode"),
        "solid",
    ).lower()
    mode = "palette" if mode_raw == "palette" else "solid"
    palette_raw = record.get("paletteColors")
    if palette_raw is None:
        palette_raw = nested.get("paletteColors") or record.get("particlesPaletteColors")
    palette_colors = normalize_particle_palette_colors(
        list(palette_raw or []) if isinstance(palette_raw, list) else [],
        solid_fallback,
        require_stops=(mode == "palette"),
    )
    return {
        "mode": mode,
        "solidColor": solid_fallback,
        "paletteColors": palette_colors,
        "reactColor": normalize_color(record.get("reactColor"), "#ffffff"),
    }


def apply_particle_color_settings_patch(
    settings: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    current = extract_particle_color_model(settings)
    next_mode = (
        current["mode"]
        if patch.get("mode") is None
        else ("palette" if to_string_value(patch.get("mode"), "solid").lower() == "palette" else "solid")
    )
    if patch.get("mode") is None and patch.get("paletteColors") is not None:
        colors = [c for c in list(patch.get("paletteColors") or []) if c]
        if len(colors) >= 2:
            next_mode = "palette"
    next_solid = (
        current["solidColor"]
        if patch.get("solidColor") is None
        else normalize_color(patch.get("solidColor"), current["solidColor"])
    )
    next_palette = (
        current["paletteColors"]
        if patch.get("paletteColors") is None
        else normalize_particle_palette_colors(
            list(patch.get("paletteColors") or []),
            next_solid,
            require_stops=(next_mode == "palette"),
        )
    )
    next_react = (
        current["reactColor"]
        if patch.get("reactColor") is None
        else normalize_color(patch.get("reactColor"), current["reactColor"])
    )
    nested = to_record(settings.get("colorMeta"))
    return {
        **settings,
        "color": next_solid,
        "colorMode": next_mode,
        "paletteColors": next_palette,
        "reactColor": next_react,
        "colorMeta": {
            **nested,
            "mode": next_mode,
            "solidColor": next_solid,
            "paletteColors": next_palette,
        },
    }


def apply_particle_color_draft_patch(draft: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    current = {
        "color": draft.get("particlesColor"),
        "colorMode": draft.get("particlesColorMode"),
        "paletteColors": draft.get("particlesPaletteColors"),
        "reactColor": draft.get("particlesReactColor"),
    }
    merged = apply_particle_color_settings_patch(current, patch)
    model = extract_particle_color_model(merged)
    return {
        **draft,
        "particlesColor": model["solidColor"],
        "particlesColorMode": model["mode"],
        "particlesPaletteColors": model["paletteColors"],
        "particlesReactColor": model["reactColor"],
    }


def palette_colors_to_rgb_tuple(colors: list[str]) -> tuple[tuple[int, int, int], ...]:
    return tuple(_hex_to_rgb(color) for color in colors)


def sample_palette_rgb(colors: list[str], t: float) -> tuple[int, int, int]:
    stops = normalize_particle_palette_colors(colors, GRADIENT_FALLBACK_COLOR, require_stops=True)
    if len(stops) < 2:
        return _hex_to_rgb(stops[0] if stops else "#ffffff")
    clamped = float(max(0.0, min(1.0, t)))
    scaled = clamped * float(len(stops) - 1)
    left = int(np.floor(scaled))
    right = min(left + 1, len(stops) - 1)
    blend = float(scaled - left)
    c0 = np.array(_hex_to_rgb(stops[left]), dtype=np.float32)
    c1 = np.array(_hex_to_rgb(stops[right]), dtype=np.float32)
    mixed = c0 * (1.0 - blend) + c1 * blend
    return (int(mixed[0]), int(mixed[1]), int(mixed[2]))


def build_spawn_palette_rgbs(
    count: int,
    palette_colors: list[str],
    *,
    rng: np.random.Generator,
) -> np.ndarray:
    if count <= 0:
        return np.zeros((0, 3), dtype=np.float32)
    ts = rng.uniform(0.0, 1.0, size=(count,)).astype(np.float32)
    rows = np.empty((count, 3), dtype=np.float32)
    for index, t in enumerate(ts):
        rgb = sample_palette_rgb(palette_colors, float(t))
        rows[index] = np.array(rgb, dtype=np.float32)
    return rows


def mix_react_rgb(
    base_rgb: tuple[int, int, int] | np.ndarray,
    react_color: str,
    mix: float,
) -> tuple[float, float, float]:
    react = _hex_to_rgb(react_color)
    blend = float(max(0.0, min(1.0, mix)))
    if isinstance(base_rgb, np.ndarray):
        cr = float(base_rgb[0]) * (1.0 - blend) + float(react[0]) * blend
        cg = float(base_rgb[1]) * (1.0 - blend) + float(react[1]) * blend
        cb = float(base_rgb[2]) * (1.0 - blend) + float(react[2]) * blend
    else:
        cr = float(base_rgb[0]) * (1.0 - blend) + float(react[0]) * blend
        cg = float(base_rgb[1]) * (1.0 - blend) + float(react[1]) * blend
        cb = float(base_rgb[2]) * (1.0 - blend) + float(react[2]) * blend
    return (cr / 255.0, cg / 255.0, cb / 255.0)


def compute_particle_react_mix(
    *,
    reactive_env: float,
    trigger_env: float,
    react_strength: float,
) -> float:
    """Electron-parity react flash amount (webgpuSpectrumRenderer particle shader).

    colorDrive = clamp(max(reactiveEnv * 1.3, triggerEnv * 1.85), 0, 1)
    colorMix   = clamp(pow(colorDrive, 0.72) * reactStrength, 0, 1)
    """
    reactive = float(max(0.0, min(1.0, float(reactive_env))))
    trigger = float(max(0.0, min(1.0, float(trigger_env))))
    strength = float(max(0.0, min(1.0, float(react_strength))))
    color_drive = float(max(0.0, min(1.0, max(reactive * 1.3, trigger * 1.85))))
    return float(max(0.0, min(1.0, (color_drive**0.72) * strength)))


def build_particle_rgba_rows(
    *,
    settings: dict[str, Any],
    particle_rgbs: np.ndarray | None,
    react_mix: float | None = None,
    reactive_env: float | None = None,
    trigger_env: float | None = None,
) -> np.ndarray:
    model = extract_particle_color_model(settings)
    alpha = float(max(0.0, min(1.0, float(settings.get("opacity", 0.35) or 0.35))))
    react_strength = float(max(0.0, min(1.0, float(settings.get("reactStrength", 0.65) or 0.65))))
    if reactive_env is not None or trigger_env is not None:
        mix = compute_particle_react_mix(
            reactive_env=float(reactive_env or 0.0),
            trigger_env=float(trigger_env or 0.0),
            react_strength=react_strength,
        )
    else:
        # Legacy path: caller already combined envelopes into a 0..1 drive.
        mix = compute_particle_react_mix(
            reactive_env=float(react_mix or 0.0),
            trigger_env=float(react_mix or 0.0),
            react_strength=react_strength,
        )
    react_color = str(model.get("reactColor") or settings.get("reactColor") or "#ffffff")

    if particle_rgbs is None or particle_rgbs.shape[0] == 0:
        base = _hex_to_rgb(str(model.get("solidColor") or "#ffffff"))
        rgb = mix_react_rgb(base, react_color, mix)
        return np.array([[rgb[0], rgb[1], rgb[2], alpha]], dtype=np.float32)

    rows = np.empty((particle_rgbs.shape[0], 4), dtype=np.float32)
    for index in range(particle_rgbs.shape[0]):
        base = (
            int(particle_rgbs[index, 0]),
            int(particle_rgbs[index, 1]),
            int(particle_rgbs[index, 2]),
        )
        rgb = mix_react_rgb(base, react_color, mix)
        rows[index] = np.array([rgb[0], rgb[1], rgb[2], alpha], dtype=np.float32)
    return rows


def build_particle_palette_preset_value(colors: list[str]) -> str:
    return build_spectrum_gradient_preset_value(colors)
